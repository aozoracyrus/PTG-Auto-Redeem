import time
from . import config as C
from .utils import log, sleep, rand_ms, shot

def _fill_by_ph(page, placeholders, value):
    for ph in placeholders:
        loc = page.get_by_placeholder(ph).first
        try:
            loc.wait_for(state="visible", timeout=4000); loc.click(); loc.fill(value); return True
        except Exception: continue
    return False

def _low(page):
    try: return page.locator("body").inner_text().lower()
    except Exception: return ""

def _any(b, needles):
    return any(str(n).lower() in b for n in needles)

def _find_server_opener(page, region):
    factories = []
    for term in C.SRV_PH.get(region, []) + ["Server"]:
        factories.append(lambda t=term: page.get_by_placeholder(t))
    factories += [lambda: page.get_by_role("combobox"), lambda: page.locator("select"),
                  lambda: page.locator("[class*='erver' i], [class*='เซิฟ' i], [class*='máy chủ' i]")]
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
            log("server: khong tim thay o server (best-effort bo qua)"); return
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
            opt.click(timeout=2500); log("server: da chon (best-effort)"); return
        try:
            page.keyboard.press("ArrowDown"); sleep(0.3); page.keyboard.press("Enter")
        except Exception: pass
    except Exception as e:
        log("server best-effort loi (bo qua):", e)

def _classify(body_low, region):
    """Duoc GOI KHI DA BIET 0/1 (that bai). Tra (kind, reason) de webhook + de main quyet chot/retry.
       Thu tu uu tien: need_login > transient > usage > not_exist > id_error > validation > section > other.
       (need_login/transient o day = 0/1 kem loi he thong/chua login -> main se coi la RETRY.)"""
    if _any(body_low, C.NEED_LOGIN[region]):    return "need_login",  "chưa liên kết tài khoản (cần login/storage_state)"
    if _any(body_low, C.TRANSIENT[region]):     return "transient",   "lỗi hệ thống tạm thời"
    if _any(body_low, C.FAIL_USAGE[region]):    return "usage_limit", "hết lượt nhập / usage limit"
    if _any(body_low, C.FAIL_NOTEXIST[region]): return "not_exist",   "không tồn tại / sai mã"
    if _any(body_low, C.FAIL_IDERROR[region]):  return "id_error",    "ID không tìm thấy/offline — kiểm tra id_user.txt"
    if _any(body_low, C.FAIL_VALIDATION[region]):return "validation", "thông tin nhập không hợp lệ"
    if _any(body_low, C.FAIL_SECTION[region]):  return "other",       "thất bại"
    return "other", "thất bại"

def _attempt(page, region, code, uid):
    """status in success|failure|retry|captcha|unknown.
       PHAN QUAN = TI SO: 1/1 -> success; 0/1 -> failure (kind/reason tu _classify).
       retry = loi tam/need_login (khong co ti so hoac 0/1 kem loi he thong) -> khong chot, khong webhook."""
    url = C.URL_VN if region == "VN" else C.URL_TH
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try: page.wait_for_load_state("networkidle", timeout=8000)
        except Exception: pass
        sleep(rand_ms(1200, 2200))
        if not _fill_by_ph(page, C.PH_CODE[region], code) or \
           not _fill_by_ph(page, C.PH_ID[region], uid):
            shot(page, f"fillfail-{region}")
            return {"status": "failure", "kind": "dom", "reason": "Không tìm thấy ô nhập code/ID"}
        if _any(_low(page), C.CAPTCHA_HINTS):
            shot(page, f"captcha-pre-{region}"); return {"status": "captcha"}
        _ensure_server(page, region)
        btn = page.get_by_role("button", name=C.BTN_REDEEM).or_(page.get_by_text(C.BTN_REDEEM))
        btn.first.click(timeout=8000)
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
                if kind in ("need_login", "transient"):          # 0/1 nhung do loi he thong/chua login
                    log(f"RETRY [{region}] {kind}: {reason}"); return {"status": "retry", "kind": kind, "reason": reason}
                return {"status": "failure", "kind": kind, "reason": reason}
        # het poll, khong thay ti so -> co phai loi tam/need_login?
        if _any(body, C.NEED_LOGIN[region]):
            log(f"RETRY [{region}] need_login (khong co modal tong ket)"); return {"status": "retry", "kind": "need_login", "reason": "chưa liên kết tài khoản"}
        if _any(body, C.TRANSIENT[region]):
            log(f"RETRY [{region}] transient (khong co modal tong ket)"); return {"status": "retry", "kind": "transient", "reason": "lỗi hệ thống tạm"}
        shot(page, f"unknown-{region}")
        log(f"UNKNOWN [{region}] (khong thay 0/1 hay 1/1) body[:500]={body[:500]!r}")
        return {"status": "unknown", "reason": "khong nhan dien duoc phan hoi"}
    except Exception as e:
        shot(page, f"err-{region}")
        return {"status": "failure", "kind": "exception", "reason": "exception: " + str(e)}

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
