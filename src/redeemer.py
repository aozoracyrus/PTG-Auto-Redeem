from . import config as C
from .utils import log, sleep, rand_ms, shot

def _fill_by_ph(page, placeholders, value):
    for ph in placeholders:
        loc = page.get_by_placeholder(ph).first
        try:
            loc.wait_for(state="visible", timeout=2500); loc.click(); loc.fill(value); return True
        except Exception: continue
    return False

def _body_has(page, needles):
    t = page.locator("body").inner_text().lower()
    return any(str(n).lower() in t for n in needles)

def _attempt(page, region, code, uid):
    """status ∈ success|failure|captcha|unknown ; reason = nguyên văn chuỗi VNG (để classify).
       code -> ô PH_CODE ; uid -> ô PH_ID. Đúng chiều, không lộn."""
    url = C.URL_VN if region == "VN" else C.URL_TH
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        sleep(rand_ms(1200, 2200))
        if not _fill_by_ph(page, C.PH_CODE[region], code) or \
           not _fill_by_ph(page, C.PH_ID[region], uid):
            shot(page, f"fillfail-{region}")
            return {"status": "failure", "reason": "Không tìm thấy ô nhập code/ID (DOM đổi?)"}
        if _body_has(page, C.CAPTCHA_HINTS):                 # captcha hiện SẴN trước khi bấm
            cap = page.get_by_placeholder(r"Nhập mã xác thực|Enter captcha").first
            try:
                if cap.is_visible():
                    shot(page, f"captcha-pre-{region}"); return {"status": "captcha"}
            except Exception: pass
        btn = page.get_by_role("button", name=C.BTN_REDEEM[region]).or_(page.get_by_text(C.BTN_REDEEM[region]))
        btn.first.click(timeout=8000)
        sleep(rand_ms(2500, 4000))                           # chờ toast/redirect
        if _body_has(page, C.CAPTCHA_HINTS):                 # captcha do rate-limit sau khi bấm
            shot(page, f"captcha-post-{region}"); return {"status": "captcha"}
        t = page.locator("body").inner_text()
        if C.OK[region] in t: return {"status": "success"}
        for f in C.FAIL[region]:
            if f in t: return {"status": "failure", "reason": f}
        shot(page, f"unknown-{region}")
        return {"status": "unknown", "reason": "Không nhận diện được phản hồi"}
    except Exception as e:
        shot(page, f"err-{region}")
        return {"status": "failure", "reason": "exception: " + str(e)}

def redeem_for_user(session, region, code, uid):
    """captcha -> restart browser, retry 1 lần; vẫn captcha -> 'captcha' (main SKIP, không ghi state)."""
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
