# API-first. stuck -> 1 webhook/run (khong spam per-code). Code stuck/retry KHONG pop ->
# run sau van thay trong queue -> khong ALERT lai (diet spam lop 2). exit 0 noi chain, 2 dung.
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config as C
from src.utils import log, sleep, rand_ms
from src.browser_session import BrowserSession
from src.scraper import fetch_available_codes
from src.redeemer import redeem_for_user
from src.api_redeemer import redeem_via_api, preview_payload
from src.users import load_users
from src.state import load_state, commit_and_push_state
from src.webhook import send, msg_success, msg_failure, msg_yt_alert, msg_status
from src.youtube_watcher import get_yt_candidates
from src import yt_queue as YQ

REFRESH      = int(os.getenv("REFRESH_INTERVAL", "60"))
MAXRUN       = int(os.getenv("MAX_RUNTIME", "20700"))
MIN_UPTIME   = int(os.getenv("MIN_UPTIME", "120"))
DMIN, DMAX   = int(os.getenv("DELAY_MIN", "15000")), int(os.getenv("DELAY_MAX", "30000"))
YT_COOLDOWN  = int(os.getenv("YT_COOLDOWN", "60"))
YT_MAX_PROBE = int(os.getenv("YT_MAX_PROBE", "5"))
USE_API      = os.getenv("USE_API", "1") == "1"
DRY_RUN      = os.getenv("DRY_RUN", "0") == "1"
TEST_CODE    = os.getenv("TEST_CODE", "").strip().upper()

SERVER_FAIL_COMMIT = {"usage_limit", "id_error", "validation", "other"}

def is_code_fully_done(code, users, state):
    if not users: return False
    return all(f"{code}|{u['id']}" in state for u in users)

def process_code(session, code, users, state, source):
    pending = [u for u in users if f"{code}|{u['id']}" not in state]
    if not pending: return (0, 0, None)
    log(f">> code {code} [src={source}]: {len(pending)} user pending")
    ne_hits = 0; stuck = None
    for u in pending:
        if DRY_RUN:
            log(f"   DRY-RUN would redeem {code} for {u['id']} (via={'API' if USE_API else 'browser'})")
            log(f"   DRY-RUN payload -> POST {C.API_URL} : {preview_payload(code, u['id'])}")
            sleep(rand_ms(DMIN, DMAX)); continue
        r = redeem_via_api(code, u["id"]) if USE_API else redeem_for_user(session, code, u["id"])
        st = r["status"]
        if st == "stuck":
            stuck = r.get("reason", "ket tam thoi")
            log(f"   stuck {u['id']} -> {stuck} (khong chot, khong webhook per-code)")
            sleep(rand_ms(DMIN, DMAX)); continue
        if st in ("captcha", "retry", "unknown"):
            log(f"   {st} {u['id']} -> skip (retry; khong chot, khong webhook)")
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
                    ne_hits += 1; log(f"   yt-probe {u['id']} -> not_exist (chua sync, giu retry)")
            else:
                log(f"   bot-error {kind} {u['id']} -> skip (retry, khong chot)")
        sleep(rand_ms(DMIN, DMAX))
    remaining = sum(1 for u in users if f"{code}|{u['id']}" not in state)
    return (remaining, ne_hits, stuck)

def force_commit_yt_timeout(code, users, state):
    for u in users:
        key = f"{code}|{u['id']}"
        if key not in state:
            send(msg_failure(code, u["id"], f"YT code khong sync sau {YT_MAX_PROBE} lan thu (bo qua)"))
            state.add(key)

def main():
    start = time.time()
    log(f"start | REFRESH={REFRESH}s MAXRUN={MAXRUN}s delay={DMIN}-{DMAX}ms "
        f"YT_COOLDOWN={YT_COOLDOWN}s USE_API={USE_API} DRY_RUN={DRY_RUN} TEST_CODE={TEST_CODE or '(off)'} "
        f"prefixes={C.CODE_PREFIXES}")
    session = BrowserSession()
    if not USE_API: session.open()
    else: log("USE_API=1 -> bo qua mo Camoufox (redeem qua API; web-list VN = rong).")
    stuck_notified = False
    try:
        while time.time() - start < MAXRUN:
            try:
                now = time.time()
                codes_web = fetch_available_codes(session)
                web_set = set(codes_web)
                users = load_users(); state = load_state(); queue = YQ.load_queue()
                touched = False; queue_dirty = False; run_stuck = None

                for c in get_yt_candidates():
                    if c in queue: continue
                    if is_code_fully_done(c, users, state): continue
                    if YQ.add_if_new(queue, c, now):
                        queue_dirty = True
                        log(f"YT ALERT: queue+ {c} (cho {YT_COOLDOWN}s sync)")
                        send(msg_yt_alert(c, YT_COOLDOWN))

                for c in codes_web:
                    rem, _, stk = process_code(session, c, users, state, source="web")
                    if c in queue: queue.pop(c, None); queue_dirty = True
                    touched = True
                    if stk and not run_stuck: run_stuck = stk

                if TEST_CODE and not is_code_fully_done(TEST_CODE, users, state):
                    log(f"TEST_CODE: ep redeem {TEST_CODE} (source=web -> khong doi cooldown)")
                    _, _, stk = process_code(session, TEST_CODE, users, state, source="web")
                    touched = True
                    if stk and not run_stuck: run_stuck = stk

                for c in list(queue.keys()):
                    if c in web_set: continue
                    if not YQ.eligible(queue, c, now, YT_COOLDOWN): continue
                    rem, ne, stk = process_code(session, c, users, state, source="yt")
                    touched = True
                    if stk and not run_stuck: run_stuck = stk
                    if rem == 0:
                        queue.pop(c, None); queue_dirty = True
                    elif ne > 0:
                        p = YQ.bump_probe(queue, c); queue_dirty = True
                        if p >= YT_MAX_PROBE:
                            log(f"YT timeout: {c} sau {p} probes -> bo cuoc")
                            force_commit_yt_timeout(c, users, state); queue.pop(c, None)

                if touched: commit_and_push_state(state)
                if queue_dirty or touched: YQ.commit_queue(queue)
                if run_stuck and not stuck_notified:
                    stuck_notified = True; send(msg_status(run_stuck, len(queue)))
                if not touched and not queue_dirty:
                    log("khong co code moi (YT cu/het, web-list VN von rong) -> doi refresh ky sau")
                elif queue_dirty and not touched:
                    log(f"da queue {len(queue)} code, cho {YT_COOLDOWN}s sync roi redeem vong sau.")
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
        if elapsed < MIN_UPTIME:
            log(f"chuoi DUNG (runtime {int(elapsed)}s < MIN_UPTIME {MIN_UPTIME}s) - fix roi Run workflow tay.")
            sys.exit(2)

if __name__ == "__main__":
    main()
