import re, time
from . import config as C
from .utils import log, sleep, rand_ms, shot

def _fill_by_ph(page, placeholders, value):
    for ph in placeholders:
        loc = page.get_by_placeholder(ph).first
        try:
            loc.wait_for(state="visible", timeout=4000)
            loc.click(); loc.fill(value)
            return loc
        except Exception: continue
    return None

def _blur(page, loc=None):
    """Ô code dạng CHIP: blur mới đóng gói chữ thành chip = commit state
       (giống 'tap ra khoảng không' trên điện thoại)."""
    try:
        if loc is not None: loc.blur()
    except Exception: pass
    try: page.mouse.click(2, 2)
    except Exception: pass
    sleep(rand_ms(200, 500))

def _low(page):
    try: return page.locator("body").inner_text().lower()
    except Exception: return ""

def _any(b, needles):
    return any(str(n).lower() in b for n in needles)

def _find_server_opener(page):
    factories = []
    for term in C.SRV_PH:
        factories.append(lambda t=term: page.get_by_placeholder(t))
    factories += [
        lambda: page.get_by_role("combobox"),
        lambda: page.locator("select"),
        lambda: page.get_by_text(re.compile(r"Server\s*\d|Máy chủ\s*\d", re.I)),
        lambda: page.locator("[class*='erver' i], [class*='máy chủ' i]"),
    ]
    for f in factories:
        try:
            L = f()
            if L.count() > 0: return L.first
        except Exception: continue
    return None

def _ensure_server(page):
    try:
        opener = _find_server_opener(page)
        if opener is None:
            log("server: khong tim thay o server (best-effort bo qua)"); return False
        opener.click(timeout=3000); sleep(0.8)
        opt = None
        for f in [lambda: page.get_by_role("option", name=C.SRV_OPT_RE),
                  lambda: page.get_by_text(C.SRV_OPT_RE),
                  lambda: page.get_by_role("listbox").get_by_role("option"),
                  lambda: page.get_by_role("option")]:
            try:
                L = f()
                if L.count() > 0: opt = L.first; break
            except Exception: continue
        if opt is not None:
            opt.click(timeout=2500); log("server: da chon (best-effort)")
            _blur(page); return True
        try:
            page.keyboard.press("ArrowDown"); sleep(0.3); page.keyboard.press("Enter")
            _blur(page); return True
        except Exception:
            return False
    except Exception as e:
        log("server best-effort loi (bo qua):", e); return False

def _wait_enabled(loc, secs=6):
    end = time.time() + secs
    while time.time() < end:
        try:
            if not loc.is_disabled(): return True
        except Exception: return True
        sleep(0.5)
    return False

def _classify(body_low):
    """Gọi KHI ĐÃ BIẾT 0/1. Trả (kind, reason)."""
    if _any(body_low, C.NEED_LOGIN):     return "need_login",  "chưa liên kết tài khoản (cần login/storage_state)"
    if _any(body_low, C.TRANSIENT):      return "transient",   "lỗi hệ thống tạm thời"
    if _any(body_low, C.FAIL_USAGE):     return "usage_limit", "hết lượt nhập / usage limit"
    if _any(body_low, C.FAIL_NOTEXIST):  return "not_exist",   "không tồn tại / sai mã"
    if _any(body_low, C.FAIL_IDERROR):   return "id_error",    "ID không tìm thấy/offline — kiểm tra id_user.txt"
    if _any(body_low, C.FAIL_VALIDATION):return "validation",  "thông tin nhập không hợp lệ"
    if _any(body_low, C.FAIL_SECTION):   return "other",       "thất bại"
    return "other", "thất bại"

def _attempt(page, code, uid):
    """status ∈ success|failure|retry|captcha|unknown. Phán quyền = 1/1 vs 0/1."""
    try:
        page.goto(C.URL_VN, wait_until="domcontentloaded", timeout=45000)
        try: page.wait_for_load_state("networkidle", timeout=8000)
        except Exception: pass
        sleep(rand_ms(1200, 2200))

        code_loc = _fill_by_ph(page, C.PH_CODE, code)
        if code_loc is None:
            shot(page, "fillfail-code"); return {"status": "retry", "kind": "dom", "reason": "Không tìm thấy ô nhập code"}
        _blur(page, code_loc)

        id_loc = _fill_by_ph(page, C.PH_ID, uid)
        if id_loc is None:
            shot(page, "fillfail-id"); return {"status": "retry", "kind": "dom", "reason": "Không tìm thấy ô nhập ID"}
        _blur(page, id_loc)
        sleep(rand_ms(400, 900))

        if _any(_low(page), C.CAPTCHA_HINTS):
            shot(page, "captcha-pre"); return {"status": "captcha"}

        btn = page.get_by_role("button", name=C.BTN_REDEEM).or_(page.get_by_text(C.BTN_REDEEM))
        if btn.count() == 0:
            shot(page, "nobtn"); return {"status": "retry", "kind": "dom", "reason": "không thấy nút Nhập code"}
        first = btn.first
        try: first.wait_for(state="visible", timeout=10000)
        except Exception:
            shot(page, "nobtn-visible"); return {"status": "retry", "kind": "dom", "reason": "nút Nhập code không visible"}

        if not _wait_enabled(first, 4):
            log("nut van DISABLED sau blur -> co gang chon server")
            _ensure_server(page); _blur(page)
            if not _wait_enabled(first, 6):
                shot(page, "disabled")
                return {"status": "retry", "kind": "form_invalid", "reason": "nút Nhập code vẫn vô hiệu"}

        try: first.scroll_into_view_if_needed(timeout=3000)
        except Exception: pass
        try: first.click(timeout=6000)
        except Exception:
            try: first.click(timeout=4000, force=True)
            except Exception:
                shot(page, "clickfail"); return {"status": "retry", "kind": "dom", "reason": "click nút Nhập code thất bại"}

        deadline = time.time() + C.REDEEM_POLL_TIMEOUT
        body = ""
        while time.time() < deadline:
            sleep(C.REDEEM_POLL_STEP); body = _low(page)
            if _any(body, C.CAPTCHA_HINTS):
                shot(page, "captcha-post"); return {"status": "captcha"}
            if C.RATIO_OK in body:
                return {"status": "success"}
            if C.RATIO_FAIL in body:
                kind, reason = _classify(body)
                if kind in ("need_login", "transient"):
                    log(f"RETRY {kind}: {reason}")
                    return {"status": "retry", "kind": kind, "reason": reason}
                return {"status": "failure", "kind": kind, "reason": reason}
        if _any(body, C.NEED_LOGIN):
            return {"status": "retry", "kind": "need_login", "reason": "chưa liên kết tài khoản"}
        if _any(body, C.TRANSIENT):
            return {"status": "retry", "kind": "transient", "reason": "lỗi hệ thống tạm"}
        shot(page, "unknown")
        log(f"UNKNOWN body[:500]={body[:500]!r}")
        return {"status": "unknown", "reason": "khong nhan dien duoc phan hoi"}
    except Exception as e:
        shot(page, "err")
        log(f"RETRY exception: {e.__class__.__name__}")
        return {"status": "retry", "kind": "exception", "reason": "exception: " + str(e)}

def redeem_for_user(session, code, uid):
    for _ in (1, 2):
        page = session.new_temp_page()
        try: r = _attempt(page, code, uid)
        finally:
            try: page.close()
            except Exception: pass
        if r["status"] != "captcha": return r
        log(f"captcha ({uid}) -> restart browser"); session.restart()
        sleep(rand_ms(3000, 6000))
    return {"status": "captcha"}
