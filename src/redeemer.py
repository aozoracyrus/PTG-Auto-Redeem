# BROWSER FALLBACK (chi khi USE_API=0). Mo /vn/redeem/ptg, dien code+ID, chon server
# best-effort, bam nut, poll TI SO 1/1 vs 0/1. Captcha -> restart, retry 1 lan, van captcha
# -> 'captcha' (main SKIP, khong chot). VN-only. Comment # dau file -> tranh SyntaxError \u.
import time
from . import config as C
from .utils import log, sleep, rand_ms, shot

def _fill_by_ph(page, placeholders, value, label=""):
    for ph in placeholders:
        loc = page.get_by_placeholder(ph).first
        try:
            loc.wait_for(state="visible", timeout=4000); loc.click(); loc.fill(value)
            log(f"OK filled {label} via placeholder '{ph}'"); return True
        except Exception as e:
            log(f"xx placeholder '{ph}' for {label}: {e.__class__.__name__}")
    log(f"xx KHONG tim thay placeholder nao cho {label} (da thu {len(placeholders)} cai)")
    return False

def _low(page):
    try: return page.locator("body").inner_text().lower()
    except Exception: return ""

def _any(b, needles): return any(str(n).lower() in b for n in needles)

def _find_server_opener(page):
    factories = [lambda t=term: page.get_by_placeholder(t) for term in C.SRV_PH + ["Server"]]
    factories += [lambda: page.get_by_role("combobox"), lambda: page.locator("select"),
                  lambda: page.locator("[class*='erver' i], [class*='may chu' i]")]
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
            opt.click(timeout=2500); log("OK server: da chon (best-effort)"); return True
        try:
            page.keyboard.press("ArrowDown"); sleep(0.3); page.keyboard.press("Enter")
            log("OK server: fallback phim da gui"); return True
        except Exception:
            log("xx server: khong chon duoc option"); return False
    except Exception as e:
        log(f"xx server best-effort loi (bo qua): {e}"); return False

def _classify(body_low):
    if _any(body_low, C.NEED_LOGIN):     return "need_login",  "chua lien ket tai khoan (can login/storage_state)"
    if _any(body_low, C.TRANSIENT):      return "transient",   "loi he thong tam thoi"
    if _any(body_low, C.FAIL_USAGE):     return "usage_limit", "het luot nhap / usage limit"
    if _any(body_low, C.FAIL_NOTEXIST):  return "not_exist",   "khong ton tai / sai ma"
    if _any(body_low, C.FAIL_IDERROR):   return "id_error",    "ID khong tim thay/offline - kiem tra id_user.txt"
    if _any(body_low, C.FAIL_VALIDATION):return "validation",  "thong tin nhap khong hop le"
    if _any(body_low, C.FAIL_SECTION):   return "other",       "that bai"
    return "other", "that bai"

def _find_redeem_btn(page):
    btn = page.get_by_role("button", name=C.BTN_REDEEM).or_(page.get_by_text(C.BTN_REDEEM))
    if btn.count() > 0:
        log("OK tim thay nut Redeem qua regex chinh"); return btn.first
    for alt in C.BTN_REDEEM_ALTS:
        btn = page.get_by_role("button", name=alt).or_(page.get_by_text(alt))
        if btn.count() > 0:
            log(f"OK tim thay nut qua alt regex: {alt.pattern}"); return btn.first
    for sel in ['button:has-text("code")','button:has-text("redeem")','button:has-text("nhap")']:
        try:
            loc = page.locator(sel)
            if loc.count() > 0: log(f"OK tim thay nut qua CSS: {sel}"); return loc.first
        except Exception: continue
    return None

def _attempt(page, code, uid):
    try:
        log(f"goto {C.URL_VN} (code={code}, id={uid})")
        page.goto(C.URL_VN, wait_until="domcontentloaded", timeout=45000)
        try: page.wait_for_load_state("networkidle", timeout=8000)
        except Exception: pass
        sleep(rand_ms(1200, 2200))
        ok_code = _fill_by_ph(page, C.PH_CODE, code, label="CODE")
        ok_id   = _fill_by_ph(page, C.PH_ID,   uid,   label="ID")
        if not ok_code or not ok_id:
            shot(page, "fillfail-VN")
            return {"status":"failure","kind":"dom","reason":f"Khong tim thay o nhap {'code' if not ok_code else 'ID'}"}
        if _any(_low(page), C.CAPTCHA_HINTS):
            shot(page, "captcha-pre-VN"); return {"status":"captcha"}
        srv_ok = _ensure_server(page)
        btn = _find_redeem_btn(page)
        if btn is None:
            shot(page, "no-button-VN")
            return {"status":"failure","kind":"dom","reason":"Khong tim thay nut Redeem"}
        try:
            btn.wait_for(state="visible", timeout=5000)
            cls = (btn.get_attribute("class") or "").lower()
            is_disabled = btn.get_attribute("disabled") is not None or "disabled" in cls
            if is_disabled:
                log(f"nut dang disabled (srv_ok={srv_ok}) -> force click"); btn.click(timeout=8000, force=True)
            else:
                log("nut visible & enabled, clicking..."); btn.click(timeout=8000)
        except Exception as e:
            log(f"click timeout -> force click (err={e.__class__.__name__})")
            try: btn.click(timeout=8000, force=True)
            except Exception as e2:
                shot(page, "click-timeout-VN")
                return {"status":"failure","kind":"dom","reason":f"Click timeout: {e2.__class__.__name__}"}
        deadline = time.time() + C.REDEEM_POLL_TIMEOUT; body = ""
        while time.time() < deadline:
            sleep(C.REDEEM_POLL_STEP); body = _low(page)
            if _any(body, C.CAPTCHA_HINTS): shot(page,"captcha-post-VN"); return {"status":"captcha"}
            if C.RATIO_OK in body: log("thy 1/1 -> success"); return {"status":"success"}
            if C.RATIO_FAIL in body:
                kind, reason = _classify(body)
                if kind in ("need_login","transient"):
                    log(f"thy 0/1 + {kind} -> retry"); return {"status":"retry","kind":kind,"reason":reason}
                log(f"thy 0/1 + {kind} -> failure"); return {"status":"failure","kind":kind,"reason":reason}
        if _any(body, C.NEED_LOGIN):
            log("khong thy ti so nhung co need_login -> retry"); return {"status":"retry","kind":"need_login","reason":"chua lien ket tai khoan"}
        if _any(body, C.TRANSIENT):
            log("khong thy ti so nhung co transient -> retry"); return {"status":"retry","kind":"transient","reason":"loi he thong tam"}
        shot(page, "unknown-VN")
        log(f"UNKNOWN: khong thy 0/1 hay 1/1 sau {C.REDEEM_POLL_TIMEOUT:.0f}s")
        log(f"   body[:500]={body[:500]!r}")
        return {"status":"unknown","reason":"khong nhan dien duoc phan hoi"}
    except Exception as e:
        shot(page, "err-VN")
        return {"status":"failure","kind":"exception","reason":f"exception: {e.__class__.__name__}: {e}"}

def redeem_for_user(session, code, uid):
    for _ in (1, 2):
        page = session.new_temp_page()
        try: r = _attempt(page, code, uid)
        finally:
            try: page.close()
            except Exception: pass
        if r["status"] != "captcha": return r
        log(f"captcha (VN/{uid}) -> restart browser"); session.restart(); sleep(rand_ms(3000, 6000))
    return {"status":"captcha"}
