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
MAXRUN      = int(os.getenv("MAX_RUNTIME", "20700"))
MIN_UPTIME  = int(os.getenv("MIN_UPTIME", "120"))
DMIN, DMAX  = int(os.getenv("DELAY_MIN", "15000")), int(os.getenv("DELAY_MAX", "30000"))
YT_COOLDOWN = int(os.getenv("YT_COOLDOWN", "60"))
YT_MAX_PROBE= int(os.getenv("YT_MAX_PROBE", "5"))

# kind thất bại VĨNH VIỄN (chốt cả khi nguồn=yt). dom/exception/form_invalid KHÔNG ở đây
# -> chúng là retry, để selector hỏng không đốt code vào state.
PERMANENT_ALWAYS = {"usage_limit", "id_error", "validation"}

def is_code_fully_done(code, users, state):
    if not users: return False
    return all(f"{code}|{u['id']}" in state for u in users)

def process_code(session, code, users, state, source):
    pending = [u for u in users if f"{code}|{u['id']}" not in state]
    if not pending: return (0, 0)
    log(f">> code {code} [src={source}]: {len(pending)} user pending")
    ne_hits = 0
    for u in pending:
        r = redeem_for_user(session, u["region"], code, u["id"])
        st = r["status"]
        if st in ("captcha", "retry", "unknown"):
            log(f"   {st} {u['region']}/{u['id']} -> skip (retry; khong chot, khong webhook)")
            sleep(rand_ms(DMIN, DMAX)); continue
        if st == "success":
            send(msg_success(u["region"], code, u["id"])); state.add(f"{code}|{u['id']}")
        else:
            kind = r.get("kind", "other")
            if kind in PERMANENT_ALWAYS or source == "web":
                send(msg_failure(u["region"], code, u["id"], r.get("reason", "unknown")))
                state.add(f"{code}|{u['id']}")
            else:
                if kind == "not_exist": ne_hits += 1
                log(f"   yt-probe {u['region']}/{u['id']} -> '{kind}' (chua sync, giu retry)")
        sleep(rand_ms(DMIN, DMAX))
    remaining = sum(1 for u in users if f"{code}|{u['id']}" not in state)
    return (remaining, ne_hits)

def force_commit_yt_timeout(code, users, state):
    for u in users:
        key = f"{code}|{u['id']}"
        if key not in state:
            send(msg_failure(u["region"], code, u["id"],
                             f"YT code không sync sau {YT_MAX_PROBE} lần thử (bỏ qua)"))
            state.add(key)

def main():
    start = time.time()
    log(f"start | REFRESH={REFRESH}s MAXRUN={MAXRUN}s delay={DMIN}-{DMAX}ms "
        f"YT_COOLDOWN={YT_COOLDOWN}s prefixes={C.CODE_PREFIXES} lang=EN|TH|VN ratio=0/1|1/1")
    session = BrowserSession()
    try:
        session.open()
        while time.time() - start < MAXRUN:
            try:
                now = time.time()
                codes_web = fetch_available_codes(session)
                web_set = set(codes_web)
                users = load_users(); state = load_state(); queue = YQ.load_queue()
                for c in get_yt_candidates():
                    if c in queue: continue
                    if is_code_fully_done(c, users, state): continue
                    if YQ.add_if_new(queue, c, now):
                        log(f"YT ALERT: queue+ {c} (cho {YT_COOLDOWN}s sync)")
                        send(msg_yt_alert(c, YT_COOLDOWN))
                touched = False
                for c in codes_web:
                    rem, _ = process_code(session, c, users, state, source="web")
                    if c in queue: queue.pop(c, None)
                    touched = True
                for c in list(queue.keys()):
                    if c in web_set: continue
                    if not YQ.eligible(queue, c, now, YT_COOLDOWN): continue
                    rem, ne = process_code(session, c, users, state, source="yt")
                    touched = True
                    if rem == 0: queue.pop(c, None)
                    elif ne > 0:
                        p = YQ.bump_probe(queue, c)
                        if p >= YT_MAX_PROBE:
                            log(f"YT timeout: {c} sau {p} probes -> bo cuoc")
                            force_commit_yt_timeout(c, users, state); queue.pop(c, None)
                if touched:
                    commit_and_push_state(state); YQ.commit_queue(queue)
                else:
                    log("khong co code moi (web/YT deu cu hoac da nhap het) -> doi refresh ky sau")
            except Exception as e:
                log("loop error:", e)
            sleep(REFRESH)
    except Exception as e:
        log("FATAL:", e)
    finally:
        try: session.close()
        except Exception: pass
        elapsed = time.time() - start
        log(f"end | runtime {int(elapsed)}s")
        if elapsed >= MIN_UPTIME: trigger_next_run()
        else: log(f"chuoi DUNG (runtime {int(elapsed)}s < MIN_UPTIME {MIN_UPTIME}s) — Run workflow lai")

if __name__ == "__main__":
    main()
