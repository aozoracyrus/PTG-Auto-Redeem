# VÒNG LẶP CHÍNH. API-first. Luồng: web-list (rỗng) -> YouTube (entries + bare) ->
# queue+cooldown mã text -> redeem -> OCR (auto/alert) -> webhook V2 -> commit state/queue.
#
# SỬA BUG "CHẠY 6H RỒI TỰ NGẮT" (2 tầng):
#   Tầng 1 (gốc): deadline tuyệt đối = min(start+MAX_RUNTIME, JOB_START+timeout-reserve).
#     Kiểm tra TRƯỚC mỗi mã, mỗi ID, mỗi lần ngủ -> không tràn timeout-minutes của job.
#   Tầng 2: ghi output `chain` cho step trigger. Run khoẻ -> chain=1. Crash sớm
#     (< MIN_CHAIN_SEC) -> chain=0 + exit 2 (dừng chuỗi, chống spam run lỗi).
#     Workflow dùng `if: !cancelled() && steps.run.outputs.chain != '0'` nên LỖI TẠM THỜI
#     (kể cả job bị giết, không ghi được output) VẪN nối chuỗi; chỉ Cancel tay mới dừng hẳn.
#
# 2117/2121 = usage-limit toàn cục: embed ĐỎ + blacklist code qua "|__DEAD__".
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config as C
from src import ocr
from src.utils import log_loop, log_queue, log_api, log_err, sleep, rand_ms
from src.browser_session import BrowserSession
from src.scraper import fetch_available_codes
from src.redeemer import redeem_for_user
from src.api_redeemer import redeem_via_api, preview_payload
from src.users import load_users
from src.state import load_state, commit_and_push_state
from src.webhook import send, msg_success, msg_failure, msg_yt_alert, msg_status, msg_already, msg_usage_limit
from src.youtube_watcher import get_yt_candidates
from src import yt_queue as YQ

REFRESH      = int(os.getenv("REFRESH_INTERVAL", "60"))
MAXRUN       = int(os.getenv("MAX_RUNTIME", "20700"))
MIN_UPTIME   = int(os.getenv("MIN_UPTIME", "120"))
DMIN, DMAX   = int(os.getenv("DELAY_MIN", "15000")), int(os.getenv("DELAY_MAX", "30000"))
YT_COOLDOWN  = C.YT_COOLDOWN
YT_MAX_PROBE = int(os.getenv("YT_MAX_PROBE", "5"))
USE_API      = os.getenv("USE_API", "1") == "1"
DRY_RUN      = os.getenv("DRY_RUN", "0") == "1"
TEST_CODE    = os.getenv("TEST_CODE", "").strip().upper()

SERVER_FAIL_COMMIT = {"usage_limit", "id_error", "validation", "other", "need_login"}
DEAD_SUFFIX = "|__DEAD__"


def _set_chain(val):
    """Ghi output cho step trigger. '1' = nối chuỗi, '0' = dừng (crash sớm)."""
    p = os.getenv("GITHUB_OUTPUT")
    if not p:
        return
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"chain={val}\n")
    except Exception as e:
        log_err("Không ghi được GITHUB_OUTPUT:", e)


def _nap_ngu(sec):
    """Ngủ nhưng KHÔNG ngủ lố deadline (nguồn tràn timeout lớn nhất)."""
    left = C.time_left() - C.LOOP_RESERVE_SEC
    if left <= 0:
        return
    sleep(min(sec, left))


def is_dead(code, state):
    return f"{code}{DEAD_SUFFIX}" in state


def mark_dead(code, state):
    state.add(f"{code}{DEAD_SUFFIX}")


def is_code_fully_done(code, users, state):
    if not users:
        return False
    return all(f"{code}|{u['id']}" in state for u in users)


def process_code(session, code, users, state, source):
    if is_dead(code, state):
        log_api(f">> mã {code} [nguồn={source}]: ĐÃ BLACKLIST (hết lượt toàn cục) -> bỏ qua")
        return (0, 0, None)
    pending = [u for u in users if f"{code}|{u['id']}" not in state]
    if not pending:
        return (0, 0, None)
    log_api(f">> mã {code} [nguồn={source}]: {len(pending)} ID cần nhập")
    ne_hits = 0
    stuck = None
    for u in pending:
        # DEADLINE: dừng nhận ID mới khi sắp hết giờ -> không tràn timeout job.
        if C.out_of_time(C.TASK_RESERVE_SEC):
            log_api(f"   hết giờ an toàn -> dừng ở mã {code}, ID còn lại để run sau")
            break
        if DRY_RUN:
            log_api(f"   DRY-RUN sẽ nhập {code} cho {u['id']} (via={'API' if USE_API else 'browser'})")
            log_api(f"   DRY-RUN payload -> POST {C.API_URL} : {preview_payload(code, u['id'])}")
            _nap_ngu(rand_ms(DMIN, DMAX))
            continue
        r = redeem_via_api(code, u["id"]) if USE_API else redeem_for_user(session, code, u["id"])
        st = r.get("status")
        if st == "stuck":
            stuck = r.get("reason", "kẹt tạm thời")
            log_api(f"   stuck {u['id']} -> {stuck} (không chốt, không webhook per-code)")
            _nap_ngu(rand_ms(DMIN, DMAX))
            continue
        if st in ("captcha", "retry", "unknown"):
            log_api(f"   {st} {u['id']} -> skip (retry; không chốt, không webhook)")
            _nap_ngu(rand_ms(DMIN, DMAX))
            continue
        if st == "success":
            send(msg_success(code, u["id"]))
            state.add(f"{code}|{u['id']}")
        elif st == "already":
            send(msg_already(code, u["id"], r.get("reason", "")))
            state.add(f"{code}|{u['id']}")
        else:
            kind = r.get("kind", "other")
            if kind == "usage_limit":
                send(msg_usage_limit(code, r.get("reason", "")))
                state.add(f"{code}|{u['id']}")
                mark_dead(code, state)
                log_api(f"   usage_limit {u['id']} -> blacklist mã {code}, ngừng thử ID khác")
                break
            if kind in SERVER_FAIL_COMMIT:
                send(msg_failure(code, u["id"], r.get("reason", "unknown")))
                state.add(f"{code}|{u['id']}")
            elif kind == "not_exist":
                if source == "web":
                    send(msg_failure(code, u["id"], r.get("reason", "unknown")))
                    state.add(f"{code}|{u['id']}")
                else:
                    ne_hits += 1
                    log_api(f"   {source}-probe {u['id']} -> not_exist (chưa đồng bộ / mã sai, giữ retry)")
            else:
                log_api(f"   bot-error {kind} {u['id']} -> skip (retry, không chốt)")
        _nap_ngu(rand_ms(DMIN, DMAX))
    remaining = sum(1 for u in users if f"{code}|{u['id']}" not in state)
    return (remaining, ne_hits, stuck)


def force_commit_yt_timeout(code, users, state):
    for u in users:
        key = f"{code}|{u['id']}"
        if key not in state:
            send(msg_failure(code, u["id"], f"Mã YouTube không đồng bộ sau {YT_MAX_PROBE} lần thử (bỏ qua)"))
            state.add(key)


def _compute_deadline(start):
    """Deadline = min(start+MAXRUN, JOB_START + timeout - reserve).
       Mốc JOB_START tính cả phút cài torch/deps/camoufox -> không bao giờ đụng timeout job."""
    cands = [start + MAXRUN]
    if C.JOB_START_EPOCH > 0:
        cands.append(C.JOB_START_EPOCH + C.JOB_TIMEOUT_MINUTES * 60 - C.SHUTDOWN_RESERVE_SEC)
    return min(cands)


def main():
    start = time.time()
    C.DEADLINE_EPOCH = _compute_deadline(start)
    job_budget = (C.JOB_START_EPOCH + C.JOB_TIMEOUT_MINUTES * 60 - C.SHUTDOWN_RESERVE_SEC) if C.JOB_START_EPOCH > 0 else 0
    log_loop(f"Bắt đầu | REFRESH={REFRESH}s MAXRUN={MAXRUN}s delay={DMIN}-{DMAX}ms "
             f"YT_COOLDOWN={YT_COOLDOWN}s USE_API={USE_API} DRY_RUN={DRY_RUN} "
             f"TEST_CODE={TEST_CODE or '(tắt)'} OCR_MODE={C.OCR_MODE} SCAN={C.YT_VIDEO_SCAN} "
             f"prefixes={C.CODE_PREFIXES}")
    log_loop(f"DEADLINE: còn {int(C.time_left())}s | ngân sách MAXRUN={MAXRUN}s"
             + (f" | ngân sách job (đã trừ cài đặt + {int(C.SHUTDOWN_RESERVE_SEC)}s dự phòng)"
                f"={int(job_budget - start)}s -> "
                f"{'JOB thắng (an toàn timeout)' if job_budget and job_budget < start + MAXRUN else 'MAXRUN thắng'}"))
    session = BrowserSession()
    if not USE_API:
        session.open()
    else:
        log_loop("USE_API=1 -> bỏ qua mở Camoufox (redeem qua API; web-list VN = rỗng).")
    stuck_notified = False
    try:
        # DEADLINE kiểm tra ở MỌI tầng, không chỉ đầu vòng.
        while not C.out_of_time(C.LOOP_RESERVE_SEC):
            try:
                now = time.time()
                ocr.reset_gemini_budget()
                codes_web = fetch_available_codes(session)
                web_set = set(codes_web)
                users = load_users()
                state = load_state()
                queue = YQ.load_queue()
                touched = False
                queue_dirty = False
                run_stuck = None

                entries, bare = get_yt_candidates()
                for e in entries:
                    code = e["code"]
                    if is_dead(code, state):
                        log_queue(f"- {code} đã blacklist (hết lượt toàn cục) -> không queue")
                        continue
                    if code in queue:
                        continue
                    if is_code_fully_done(code, users, state):
                        continue
                    if YQ.add_if_new(queue, code, now, redeem=True):
                        queue_dirty = True
                        log_queue(f"+ {code} (chờ {YT_COOLDOWN}s đồng bộ) [via={e.get('via')}]")
                        send(msg_yt_alert(e, YT_COOLDOWN))

                for c in codes_web:
                    if C.out_of_time(C.TASK_RESERVE_SEC):
                        break
                    rem, _, stk = process_code(session, c, users, state, source="web")
                    if c in queue:
                        queue.pop(c, None)
                        queue_dirty = True
                    touched = True
                    if stk and not run_stuck:
                        run_stuck = stk

                if TEST_CODE and not is_code_fully_done(TEST_CODE, users, state) and not is_dead(TEST_CODE, state):
                    log_api(f"TEST_CODE: ép nhập {TEST_CODE} (nguồn=web -> không đợi cooldown)")
                    _, _, stk = process_code(session, TEST_CODE, users, state, source="web")
                    touched = True
                    if stk and not run_stuck:
                        run_stuck = stk

                for c in list(queue.keys()):
                    if C.out_of_time(C.TASK_RESERVE_SEC):
                        log_queue("Hết giờ an toàn -> mã còn lại trong queue để run sau")
                        break
                    if c in web_set:
                        continue
                    if is_dead(c, state):
                        queue.pop(c, None)
                        queue_dirty = True
                        continue
                    if not YQ.is_redeemable(queue, c):
                        continue
                    if not YQ.eligible(queue, c, now, YT_COOLDOWN):
                        continue
                    rem, ne, stk = process_code(session, c, users, state, source="yt")
                    touched = True
                    if stk and not run_stuck:
                        run_stuck = stk
                    if rem == 0 or is_dead(c, state):
                        queue.pop(c, None)
                        queue_dirty = True
                    elif ne > 0:
                        p = YQ.bump_probe(queue, c)
                        queue_dirty = True
                        if p >= YT_MAX_PROBE:
                            log_queue(f"YT timeout: {c} sau {p} probes -> bỏ cuộc")
                            force_commit_yt_timeout(c, users, state)
                            queue.pop(c, None)

                known_codes = set(queue.keys()) | {k.split("|", 1)[0] for k in state}
                if C.OCR_MODE == "auto":
                    ocr.run_correction(users, state, bare, now, known_codes)
                    touched = True
                elif C.OCR_MODE == "alert":
                    ocr.alert_only(bare, known_codes)

                if YQ.prune_non_redeemable(queue, now, C.OCR_ALERT_TTL):
                    queue_dirty = True

                if touched:
                    commit_and_push_state(state)
                if queue_dirty or touched:
                    YQ.commit_queue(queue)
                if run_stuck and not stuck_notified:
                    stuck_notified = True
                    send(msg_status(run_stuck, len(queue)))
                if not touched and not queue_dirty:
                    log_loop("Không có mã mới -> đợi vòng sau.")
                elif queue_dirty and not touched:
                    log_queue(f"Đã queue {len(queue)} mã, chờ {YT_COOLDOWN}s đồng bộ rồi nhập vòng sau.")
            except Exception as e:
                log_err("Lỗi trong vòng lặp:", e)
            _nap_ngu(REFRESH)
        log_loop(f"Hết ngân sách thời gian (còn {int(C.time_left())}s dự phòng) -> thoát êm, kịp commit + trigger.")
    except Exception as e:
        log_err("FATAL:", e)
    finally:
        try:
            session.close()
        except Exception:
            pass
        elapsed = time.time() - start
        log_loop(f"Kết thúc | thời gian chạy {int(elapsed)}s")
        # Run quá ngắn = bất thường (crash lặp) -> KHÔNG nối chuỗi, tránh spam run lỗi.
        if elapsed < max(MIN_UPTIME, C.MIN_CHAIN_SEC):
            _set_chain("0")
            log_loop(f"CHUỖI DỪNG CÓ CHỦ ĐÍCH (chạy {int(elapsed)}s < ngưỡng {max(MIN_UPTIME, C.MIN_CHAIN_SEC)}s) "
                     f"- đây là lỗi thật, fix rồi Run workflow tay.")
            sys.exit(2)
        _set_chain("1")
        log_loop("chain=1 -> step trigger sẽ spawn run kế (kể cả run này có lỗi tạm thời).")


if __name__ == "__main__":
    main()
