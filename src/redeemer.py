import re, time
from . import config as C
from .utils import log, sleep, rand_ms, shot

def _fill_by_ph(page, placeholders, value):
    for ph in placeholders:
        loc = page.get_by_placeholder(ph).first
        try:
            loc.wait_for(state="visible", timeout=4000)
            loc.click()
            loc.fill(value)
            return loc                     # trả locator đã fill để blur sau
        except Exception:
            continue
    return None

def _blur(page, loc=None):
    """Form VNG chỉ commit state khi ô nhập MẤT FOCUS (onBlur) — giống vụ người dùng
       điện thoại phải 'tap ra khoảng không' thì nút mới hết xám. Playwright fill()
       không tự blur -> phải blur tay: loc.blur() + click vùng trống của body."""
    try:
        if loc is not None: loc.blur()
    except Exception: pass
    try:
        page.mouse.click(2, 2)             # góc trái-trên = vùng padding body, không trúng UI
    except Exception: pass
    sleep(rand_ms(200, 500))

def _low(page):
    try: return page.locator("body").inner_text().lower()
    except Exception: return ""

def _any(b, needles):
    return any(str(n).lower() in b for n in needles)

def _find_server_opener(page, region):
    factories = []
    for term in C.SRV_PH.get(region, []) + ["Server"]:
        factories.append(lambda t=term: page.get_by_placeholder(t))
    factories += [
        lambda: page.get_by_role("combobox"),
        lambda: page.locator("select"),
        lambda: page.get_by_text(re.compile(r"Server\s*\d|เซิร์ฟเวอร์\s*\d|Máy chủ\s*\d", re.I)),
        lambda: page.locator("[class*='erver' i], [class*='เซิฟ' i], [class*='máy chủ' i]"),
    ]
    for f in factories:
        try:
            L = f()
            if L.count() > 0: return L.first
        except Exception: continue
    return None

def _ensure_server(page, region):
    try:
        opener = _find_server_opener(page, region)
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
        except Exception:
            return True
        sleep(0.5)
    return False

def _classify(body_low, region):
    """Chỉ gọi KHI ĐÃ BIẾT 0/1. Trả (kind, reason) cho webhook + cho main quyết chốt/retry."""
    if _any(body_low, C.NEED_LOGIN[region]):     return "need_login",  "chưa liên kết tài khoản (cần login/storage_state)"
    if _any(body_low, C.TRANSIENT[region]):      return "transient",   "lỗi hệ thống tạm thời"
    if _any(body_low, C.FAIL_USAGE[region]):     return "usage_limit", "hết lượt nhập / usage limit"
    if _any(body_low, C.FAIL_NOTEXIST[region]):  return "not_exist",   "không tồn tại / sai mã"
    if _any(body_low, C.FAIL_IDERROR[region]):   return "id_error",    "ID không tìm thấy/offline — kiểm tra id_user.txt"
    if _any(body_low, C.FAIL_VALIDATION[region]):return "validation",  "thông tin nhập không hợp lệ"
    if _any(body_low, C.FAIL_SECTION[region]):   return "other",       "thất bại"
    return "other", "thất bại"

def _attempt(page, region, code, uid):
    """status ∈ success|failure|retry|captcha|unknown.
       Phán quyền = TỈ SỐ: 1/1 -> success; 0/1 -> failure (kind/reason từ _classify).
       Lỗi DOM / lỗi tạm / captcha -> RETRY: KHÔNG chốt state, KHÔNG webhook."""
    url = C.URL_VN if region == "VN" else C.URL_TH
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try: page.wait_for_load_state("networkidle", timeout=8000)
        except Exception: pass
        sleep(rand_ms(1200, 2200))

        code_loc = _fill_by_ph(page, C.PH_CODE[region], code)
        if code_loc is None:
            shot(page, f"fillfail-code-{region}")
            return {"status": "retry", "kind": "dom", "reason": "Không tìm thấy ô nhập code"}
        _blur(page, code_loc)                       # commit code (onBlur)

        id_loc = _fill_by_ph(page, C.PH_ID[region], uid)
        if id_loc is None:
            shot(page, f"fillfail-id-{region}")
            return {"status": "retry", "kind": "dom", "reason": "Không tìm thấy ô nhập ID"}
        _blur(page, id_loc)                         # commit id (onBlur)
        sleep(rand_ms(400, 900))

        if _any(_low(page), C.CAPTCHA_HINTS):
            shot(page, f"captcha-pre-{region}"); return {"status": "captcha"}

        btn = page.get_by_role("button", name=C.BTN_REDEEM).or_(page.get_by_text(C.BTN_REDEEM))
        if btn.count() == 0:
            shot(page, f"nobtn-{region}")
            return {"status": "retry", "kind": "dom", "reason": "không thấy nút redeem"}
        first = btn.first
        try:
            first.wait_for(state="visible", timeout=10000)
        except Exception:
            shot(page, f"nobtn-visible-{region}")
            return {"status": "retry", "kind": "dom", "reason": "nút redeem không visible"}

        if not _wait_enabled(first, 4):             # blur rồi mà vẫn xám -> thử chọn server
            log(f"nut van DISABLED [{region}] sau blur -> co gang chon server")
            _ensure_server(page, region)
            _blur(page)
            if not _wait_enabled(first, 6):
                shot(page, f"disabled-{region}")
                return {"status": "retry", "kind": "form_invalid",
                        "reason": "nút redeem vẫn vô hiệu (form chưa hợp lệ)"}

        try:
            first.scroll_into_view_if_needed(timeout=3000)
        except Exception: pass
        try:
            first.click(timeout=6000)
        except Exception:
            try:
                first.click(timeout=4000, force=True)
            except Exception:
                shot(page, f"clickfail-{region}")
                return {"status": "retry", "kind": "dom", "reason": "click nút redeem thất bại"}

        deadline = time.time() + C.REDEEM_POLL_TIMEOUT
        body = ""
        while time.time() < deadline:
            sleep(C.REDEEM_POLL_STEP); body = _low(page)
            if _any(body, C.CAPTCHA_HINTS):
                shot(page, f"captcha-post-{region}"); return {"status": "captcha"}
            if C.RATIO_OK in body:
                return {"status": "success"}
            if C.RATIO_FAIL in body:
                kind, reason = _classify(body, region)
                if kind in ("need_login", "transient"):
                    log(f"RETRY [{region}] {kind}: {reason}")
                    return {"status": "retry", "kind": kind, "reason": reason}
                return {"status": "failure", "kind": kind, "reason": reason}
        if _any(body, C.NEED_LOGIN[region]):
            return {"status": "retry", "kind": "need_login", "reason": "chưa liên kết tài khoản"}
        if _any(body, C.TRANSIENT[region]):
            return {"status": "retry", "kind": "transient", "reason": "lỗi hệ thống tạm"}
        shot(page, f"unknown-{region}")
        log(f"UNKNOWN [{region}] body[:500]={body[:500]!r}")
        return {"status": "unknown", "reason": "khong nhan dien duoc phan hoi"}
    except Exception as e:
        shot(page, f"err-{region}")
        log(f"RETRY [{region}] exception: {e.__class__.__name__}")
        return {"status": "retry", "kind": "exception", "reason": "exception: " + str(e)}

def redeem_for_user(session, region, code, uid):
    for _ in (1, 2):
        page = session.new_temp_page()
        try: r = _attempt(page, region, code, uid)
        finally:
            try: page.close()
            except Exception: pass
        if r["status"] != "captcha": return r
        log(f"captcha ({region}/{uid}) -> restart browser"); session.restart(region=region)
        sleep(rand_ms(3000, 6000))
    return {"status": "captcha"}
