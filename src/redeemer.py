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

def _any(low_body, needles):
    return any(str(n).lower() in low_body for n in needles)

def _reason(body_low, region):
    """Đọc text ĐỎ để suy lí do cho webhook failure. KHÔNG ảnh hưởng thắng/thua."""
    if _any(body_low, C.FAIL_USAGE[region]):
        return "usage_limit", "hết lượt nhập / usage limit"
    if _any(body_low, C.FAIL_NOTEXIST[region]):
        return "not_exist", "không tồn tại / does not exist"
    return "other", "thất bại"

def _attempt(page, region, code, uid):
    """status ∈ success|failure|captcha|unknown.
       Thắng/thua CHỈ nhìn tỉ số 1/1 vs 0/1 (dễ hiểu, không glyph-risk, không dịch).
       Text đỏ chỉ quyết định 'kind'/'reason' cho webhook."""
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
        body0 = _low(page)
        if _any(body0, C.CAPTCHA_HINTS):
            shot(page, f"captcha-pre-{region}"); return {"status": "captcha"}
        btn = page.get_by_role("button", name=C.BTN_REDEEM).or_(page.get_by_text(C.BTN_REDEEM))
        btn.first.click(timeout=8000)
        sleep(rand_ms(2500, 4000))
        body = _low(page)
        if _any(body, C.CAPTCHA_HINTS):
            shot(page, f"captcha-post-{region}"); return {"status": "captcha"}
        # ===== 2 DÒNG VÀNG =====
        if C.RATIO_FAIL in body:                      # 0/1 -> THẤT BẠI
            kind, reason = _reason(body, region)
            return {"status": "failure", "kind": kind, "reason": reason}
        if C.RATIO_OK in body:                        # 1/1 -> THÀNH CÔNG
            return {"status": "success"}
        # ===== lưới cuối =====
        shot(page, f"unknown-{region}")
        log(f"UNKNOWN [{region}] (không thấy 0/1 hay 1/1) body[:400]={body[:400]!r}")
        return {"status": "unknown", "reason": "không nhận diện được phản hồi"}
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
