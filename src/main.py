import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config as C
from src.utils import log, sleep, rand_ms
from src.browser_session import BrowserSession
from src.scraper import fetch_available_codes          # stub -> []
from src.redeemer import redeem_for_user               # chi dung khi USE_API=0
from src.api_redeemer import redeem_via_api            # duong chinh
from src.users import load_users
from src.state import load_state, commit_and_push_state
from src.webhook import send, msg_success, msg_failure, msg_yt_alert
from src.youtube_watcher import get_yt_candidates
from src import yt_queue as YQ

REFRESH      = int(os.getenv("REFRESH_INTERVAL", "60"))
MAXRUN       = int(os.getenv("MAX_RUNTIME", "20700"))
MIN_UPTIME   = int(os.getenv("MIN_UPTIME", "120"))
DMIN, DMAX   = int(os.getenv("DELAY_MIN", "15000")), int(os.getenv("DELAY_MAX", "30000"))
YT_COOLDOWN  = int(os.getenv("YT_COOLDOWN", "60"))
YT_MAX_PROBE = int(os.getenv("YT_MAX_PROBE", "5"))
USE_API      = os.getenv("USE_API", "1") == "1"

SERVER_FAIL_COMMIT = {"usage_limit", "id_error", "validation", "other"}
BOT_ERROR_RETRY    = {"dom", "exception"}

def is_code_fully_done(code, users, state):
    if not users: return False
    return all(f"{code}|{u['id']}" in state for u in users)

def process_code(session, code, users, state, source):
    pending = [u for u in users if f"{code}|{u['id']}" not in state]
    if not pending: return (0, 0)
    log(f">> code {code} [src={source}]: {len(pending)} user pending")
    ne_hits = 0
    for u in pending:
        # USE_API=1 -> API (khong can session). USE_API=0 -> browser fallback.
        r = redeem_via_api(code, u["id"]) if USE_API else redeem_for_user(session, code, u["id"])
        st = r["status"]
        if st in ("captcha", "retry", "unknown"):
            log(f"   {st} {u['id']} -> skip (retry; không chốt, không webhook)")
            sleep(rand_ms(DMIN, DMAX)); continue
        if st == "success":
            send(msg_success(code, u["id"])); state.add(f"{code}|{u['id']}")
        else:
            kind = r.get("kind", "other")
            if kind in SERVER_FAIL_COMMIT:
                send(msg_failure(code, u["id"], r.get("reason", "unknown"))); state.add(f"{code}|{u['id']}")
            elif kind == "not_exist":
                if source == "web":
                    send(msg_failure(code, u["id"], r.get("reason", "unknown"))); state.add(f"{code}|{u['id']}")
                else:
                    ne_hits += 1; log(f"   yt-probe {u['id']} -> not_exist (chưa sync, giữ retry)")
            else:
                log(f"   bot-error {kind} {u['id']} -> skip (retry, không chốt)")
        sleep(rand_ms(DMIN, DMAX))
    remaining = sum(1 for u in users if f"{code}|{u['id']}" not in state)
    return (remaining, ne_hits)

def force_commit_yt_timeout(code, users, state):
    for u in users:
        key = f"{code}|{u['id']}"
        if key not in state:
            send(msg_failure(code, u["id"], f"YT code không sync sau {YT_MAX_PROBE} lần thử (bỏ qua)"))
            state.add(key)

def main():
    start = time.time()
    log(f"start | REFRESH={REFRESH}s MAXRUN={MAXRUN}s delay={DMIN}-{DMAX}ms "
        f"YT_COOLDOWN={YT_COOLDOWN}s USE_API={USE_API} prefixes={C.CODE_PREFIXES}")
    session = BrowserSession()
    # MO BROWSER LAZY: chi khi can fallback (USE_API=0). USE_API=1 -> khong mo
    # Camoufox -> nhanh hon, khong fingerprint, khong tai binary.
    if not USE_API:
        session.open()
    else:
        log("USE_API=1 -> bo qua mo Camoufox (redeem qua API; web-list VN = rong).")
    try:
        while time.time() - start < MAXRUN:
            try:
                now = time.time()
                codes_web = fetch_available_codes(session)   # stub -> []
                web_set = set(codes_web)                     # rong
                users = load_users(); state = load_state(); queue = YQ.load_queue()

                # NGUON CODE DUY NHAT (VN) = YouTube -> queue (cooldown bat dau tinh tu day)
                for c in get_yt_candidates():
                    if c in queue: continue
                    if is_code_fully_done(c, users, state): continue
                    if YQ.add_if_new(queue, c, now):
                        log(f"YT ALERT: queue+ {c} (chờ {YT_COOLDOWN}s sync)")
                        send(msg_yt_alert(c, YT_COOLDOWN))

                touched = False
                # duong 'web' chay 0 lan (codes_web rong) -> giu de mo rong sau nay
                for c in codes_web:
                    rem, _ = process_code(session, c, users, state, source="web")
                    if c in queue: queue.pop(c, None)
                    touched = True
                # probe code YT da qua cooldown (redeeem qua API)
                for c in list(queue.keys()):
                    if c in web_set: continue
                    if not YQ.eligible(queue, c, now, YT_COOLDOWN): continue
                    rem, ne = process_code(session, c, users, state, source="yt")
                    touched = True
                    if rem == 0: queue.pop(c, None)
                    elif ne > 0:
                        p = YQ.bump_probe(queue, c)
                        if p >= YT_MAX_PROBE:
                            log(f"YT timeout: {c} sau {p} probes -> bỏ cuộc")
                            force_commit_yt_timeout(c, users, state); queue.pop(c, None)

                if touched:
                    commit_and_push_state(state); YQ.commit_queue(queue)
                else:
                    log("không có code mới (YT cũ/hết, web-list VN vốn rong) -> đợi refresh kỳ sau")
            except Exception as e:
                log("loop error:", e)
            sleep(REFRESH)
    except Exception as e:
        log("FATAL:", e)
    finally:
        try: session.close()          # an toàn du chua open (_cm=None -> skip)
        except Exception: pass
        elapsed = time.time() - start
        log(f"end | runtime {int(elapsed)}s")
        if elapsed < MIN_UPTIME:
            log(f"chuỗi DỪNG (runtime {int(elapsed)}s < MIN_UPTIME {MIN_UPTIME}s) — fix rồi Run workflow tay.")
            sys.exit(2)               # exit 2 -> step 'Trigger next run' trong yml BO QUA
        # exit 0 -> step trigger trong redeem.yml self-chain

if __name__ == "__main__":
    main()
