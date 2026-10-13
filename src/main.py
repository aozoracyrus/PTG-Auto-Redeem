import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config as C
from src.utils import log, sleep, rand_ms
from src.browser_session import BrowserSession
from src.redeemer import redeem_for_user
from src.users import load_users
from src.state import load_state, write_state, load_errors, write_errors, commit_paths
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

STATE_FILES = ["code_da_nhap.txt", "yt_queue.json", "id_code_loi.txt"]

def process_code(session, code, users, state, mem, errs):
    """Nhập code cho mọi ID chưa terminal.
       - success        -> webhook success; nếu cặp từng nằm trong sổ lỗi thì XOÁ dòng đó.
       - failure terminal -> webhook failure + GHI 'CODE|ID' vào id_code_loi.txt.
       - not_exist      -> retry (chưa sync), KHÔNG ghi sổ lỗi.
       - captcha/retry/unknown -> skip, không ghi gì.
       Khi TẤT CẢ ID terminal -> state.add(code) = 1 dòng trong code_da_nhap.txt."""
    term = mem.setdefault(code, set())
    pending = [uid for uid in users if uid not in term]
    if not pending: return 0, 0
    log(f">> code {code}: {len(pending)} ID pending")
    ne_hits = 0
    for uid in pending:
        r = redeem_for_user(session, code, uid)
        st = r["status"]
        if st in ("captcha", "retry", "unknown"):
            log(f"   {st} {uid} -> skip (retry; khong chot, khong webhook, khong so loi)")
            sleep(rand_ms(DMIN, DMAX)); continue
        pair = f"{code}|{uid}"
        if st == "success":
            send(msg_success(code, uid))
            term.add(uid)
            if pair in errs:
                errs.discard(pair)
                log(f"   {pair}: thanh cong -> xoa khoi so loi")
        else:
            kind = r.get("kind", "other")
            if kind == "not_exist":
                ne_hits += 1
                log(f"   yt-probe {uid} -> not_exist (chua sync, giu retry)")
            else:
                send(msg_failure(code, uid, r.get("reason", "unknown")))
                term.add(uid)
                errs.add(pair)                      # <-- GHI SỔ LỖI
                log(f"   {pair}: that bai -> ghi vao id_code_loi.txt")
        sleep(rand_ms(DMIN, DMAX))
    if users and all(uid in term for uid in users):
        state.add(code)
        log(f"   code {code}: TAT CA ID da terminal -> ghi state 1 dong")
    remaining = sum(1 for uid in users if uid not in term)
    return remaining, ne_hits

def main():
    start = time.time()
    log(f"start | MODE=YouTube->VN | REFRESH={REFRESH}s MAXRUN={MAXRUN}s "
        f"delay={DMIN}-{DMAX}ms YT_COOLDOWN={YT_COOLDOWN}s prefixes={C.CODE_PREFIXES}")
    session = BrowserSession()
    mem  = {}                    # code -> set(ID terminal) trong run
    errs = load_errors()         # sổ lỗi CODE|ID (giữ suốt run, push khi đổi)
    try:
        session.open()
        while time.time() - start < MAXRUN:
            try:
                now = time.time()
                users = load_users(); state = load_state(); queue = YQ.load_queue()

                for c in get_yt_candidates():
                    if c in state or c in queue: continue
                    if YQ.add_if_new(queue, c, now):
                        log(f"YT ALERT: queue+ {c} (cho {YT_COOLDOWN}s sync)")
                        send(msg_yt_alert(c, YT_COOLDOWN))

                touched = False
                for c in list(queue.keys()):
                    if c in state:
                        queue.pop(c, None); continue
                    if not YQ.eligible(queue, c, now, YT_COOLDOWN): continue
                    rem, ne = process_code(session, c, users, state, mem, errs)
                    touched = True
                    if c in state or (rem == 0 and ne == 0):
                        queue.pop(c, None)
                    elif ne > 0:
                        p = YQ.bump_probe(queue, c)
                        if p >= YT_MAX_PROBE:
                            log(f"YT timeout: {c} sau {p} probes -> bo cuoc")
                            for uid in users:
                                if uid not in mem.get(c, set()):
                                    send(msg_failure(c, uid,
                                        f"YT code không sync sau {YT_MAX_PROBE} lần thử (bỏ qua)"))
                                    errs.add(f"{c}|{uid}")          # <-- ghi sổ lỗi khi bỏ cuộc
                            state.add(c); queue.pop(c, None)
                if touched:
                    write_state(state); write_errors(errs); YQ.save_queue(queue)
                    commit_paths(STATE_FILES,
                                 f"chore(state): {len(state)} done / {len(errs)} loi")
                else:
                    log("chua co code moi tu YouTube (hoac da xong het) -> doi refresh ky sau")
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
