import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config as C
from src.utils import log, sleep, rand_ms
from src.browser_session import BrowserSession
from src.scraper import fetch_available_codes
from src.redeemer import redeem_for_user
from src.users import load_users
from src.state import load_state, commit_and_push_state
from src.webhook import send, msg_success, msg_failure, msg_yt_alert
from src.trigger import trigger_next_run
from src.youtube_watcher import get_yt_candidates
from src import yt_queue as YQ

REFRESH     = int(os.getenv("REFRESH_INTERVAL", "60"))
MAXRUN      = int(os.getenv("MAX_RUNTIME", "20700"))      # 345 phút
MIN_UPTIME  = int(os.getenv("MIN_UPTIME", "120"))
DMIN, DMAX  = int(os.getenv("DELAY_MIN", "15000")), int(os.getenv("DELAY_MAX", "30000"))
YT_COOLDOWN = int(os.getenv("YT_COOLDOWN", "60"))
YT_MAX_PROBE= int(os.getenv("YT_MAX_PROBE", "5"))

def classify(reason, region):
    """usage_limit | not_exist | other  (dựa substring VNG trả)."""
    rl = (reason or "").lower()
    if C.USAGE_LIMIT_SUB[region].lower() in rl: return "usage_limit"
    if C.NOT_EXIST_SUB[region].lower()   in rl: return "not_exist"
    return "other"

def is_code_fully_done(code, users, state):
    """Mọi cặp CODE|ID đã ở state -> code xong vĩnh viễn (khỏi re-queue video cũ)."""
    if not users: return False
    return all(f"{code}|{u['id']}" in state for u in users)

def process_code(session, code, users, state, source):
    """Nhập 1 code cho mọi user pending. Trả (remaining_pending, not_exist_hits).
       QUY TẮC CHỐT STATE:
         - source=='web' : MỌI outcome chốt (web = nguồn thật).
         - source=='yt'  : CHỈ chốt success / usage_limit. 'not_exist'/'other' -> KHÔNG chốt
                           (server chưa sync / transient), đếm hit để main tăng probes & retry.
                           captcha -> skip, không chốt, không hit."""
    pending = [u for u in users if f"{code}|{u['id']}" not in state]
    if not pending: return (0, 0)
    log(f">> code {code} [src={source}]: {len(pending)} user pending")
    ne_hits = 0
    for u in pending:
        r = redeem_for_user(session, u["region"], code, u["id"])
        if r["status"] == "captcha":
            log(f"   captcha {u['region']}/{u['id']} -> skip (retry vòng sau)")
            sleep(rand_ms(DMIN, DMAX)); continue
        if r["status"] == "success":
            send(msg_success(u["region"], code, u["id"])); state.add(f"{code}|{u['id']}")
        else:
            cls = classify(r.get("reason", ""), u["region"])
            if source == "web" or cls == "usage_limit":
                send(msg_failure(u["region"], code, u["id"], r.get("reason", "unknown")))
                state.add(f"{code}|{u['id']}")
            else:
                if cls == "not_exist": ne_hits += 1
                log(f"   yt-probe {u['region']}/{u['id']} -> '{cls}' (chưa sync, giữ retry)")
        sleep(rand_ms(DMIN, DMAX))                         # 15-30s chống captcha
    remaining = sum(1 for u in users if f"{code}|{u['id']}" not in state)
    return (remaining, ne_hits)

def force_commit_yt_timeout(code, users, state):
    """Hết YT_MAX_PROBE mà vẫn 'not_exist' -> bỏ cuộc, chốt failure để không probe mãi."""
    for u in users:
        key = f"{code}|{u['id']}"
        if key not in state:
            send(msg_failure(u["region"], code, u["id"],
                             f"YT code không sync sau {YT_MAX_PROBE} lần thử (bỏ qua)"))
            state.add(key)

def main():
    start = time.time()
    log(f"start | REFRESH={REFRESH}s MAXRUN={MAXRUN}s delay={DMIN}-{DMAX}ms "
        f"YT_COOLDOWN={YT_COOLDOWN}s YT_MAX_PROBE={YT_MAX_PROBE} prefixes={C.CODE_PREFIXES}")
    session = BrowserSession()
    try:
        session.open()
        while time.time() - start < MAXRUN:                # thoát TRƯỚC trần 360' để kịp trigger
            try:
                now = time.time()
                # 1) WEB = nguồn thật (reload trình duyệt + parse neo 'Valid until')
                codes_web = fetch_available_codes(session)
                web_set = set(codes_web)
                users = load_users(); state = load_state(); queue = YQ.load_queue()

                # 2) YT = early-warning -> add queue (cooldown tính từ đây)
                for c in get_yt_candidates():
                    if c in queue: continue
                    if is_code_fully_done(c, users, state): continue
                    if YQ.add_if_new(queue, c, now):
                        log(f"YT ALERT: queue+ {c} (chờ {YT_COOLDOWN}s sync)")
                        send(msg_yt_alert(c, YT_COOLDOWN))

                touched = False
                # 3) Ưu tiên redeem code WEB trước (chắc chắn active)
                for c in codes_web:
                    rem, _ = process_code(session, c, users, state, source="web")
                    if c in queue: queue.pop(c, None)       # web xử lý rồi -> khỏi probe
                    touched = True

                # 4) Probe code YT-ONLY đã qua cooldown (web chưa liệt kê)
                for c in list(queue.keys()):
                    if c in web_set: continue               # đã xử lý ở bước 3
                    if not YQ.eligible(queue, c, now, YT_COOLDOWN):
                        continue                            # chưa đủ 30-60s -> chờ
                    rem, ne = process_code(session, c, users, state, source="yt")
                    touched = True
                    if rem == 0:
                        queue.pop(c, None)                  # xong hết -> xoá queue
                    elif ne > 0:
                        p = YQ.bump_probe(queue, c)
                        if p >= YT_MAX_PROBE:
                            log(f"YT timeout: {c} sau {p} probes -> bỏ cuộc")
                            force_commit_yt_timeout(c, users, state)
                            queue.pop(c, None)
                    # else: captcha-only (ne==0, rem>0) -> giữ queue, probes không đổi, retry

                if touched:
                    commit_and_push_state(state)
                    YQ.commit_queue(queue)
                else:
                    log("không có code mới (web/YT đều cũ hoặc đã nhập hết) -> đợi refresh kỳ sau")
            except Exception as e:
                log("loop error:", e)
            sleep(REFRESH)                                  # chờ rồi RELOAD TRÌNH DUYỆT tiếp
    except Exception as e:
        log("FATAL:", e)
    finally:
        try: session.close()
        except Exception: pass
        elapsed = time.time() - start
        log(f"end | runtime {int(elapsed)}s")
        if elapsed >= MIN_UPTIME: trigger_next_run()        # NỐI CHUỖI 24/7
        else: log(f"chuỗi DỪNG (runtime {int(elapsed)}s < MIN_UPTIME {MIN_UPTIME}s) "
                  f"— xem log/artifact 'shots' rồi Run workflow lại")

if __name__ == "__main__":
    main()
