import re
from . import config as C
from .parsers import code_gan_ngay_web          # <-- đổi từ code_truoc_valid_until_web
from .utils import log, sleep, rand_ms, shot

_ACCEPT_RE = re.compile(r"^(Accept|Agree|I agree|ตกลง|ยอมรับ|ยินยอม|Chấp nhận|同意)$", re.I)

def _dismiss_banner(page):
    """B3: nếu có cookie/consent banner che, bấm bỏ nó TRƯỚC khi chờ nút cam."""
    for _ in range(2):
        hit = False
        try:
            loc = page.get_by_role("button", name=_ACCEPT_RE).or_(page.get_by_text(_ACCEPT_RE))
            if loc.count() > 0:
                loc.first.click(timeout=2500); hit = True; sleep(rand_ms(400, 800))
        except Exception:
            pass
        if not hit:
            return

def _counts(page):
    parts = []
    for lbl, kind, val in [
        ("role:button", "role", C.BTN_VIEW_CODES),
        ("text:regex",  "text", C.BTN_VIEW_CODES),
        ("text_sub:codes", "sub", "redemption codes"),
        ("text_sub:โค้ด",   "sub", "โค้ดที่พร้อม"),
        ("text_sub:giftcode","sub","mã giftcode"),
    ]:
        try:
            if kind == "role": n = page.get_by_role("button", name=val).count()
            elif kind == "text": n = page.get_by_text(val).count()
            else: n = page.get_by_text(val, exact=False).count()
        except Exception as e:
            n = f"ERR:{e.__class__.__name__}"
        parts.append(f"{lbl}={n}")
    return " | ".join(parts)

def _open_modal(page):
    """Chờ nút cam HIỆN (B1 timing, timeout 20s), rồi bấm bằng nhiều chiến lược (B3)."""
    target = page.get_by_text(C.BTN_VIEW_CODES).or_(page.get_by_role("button", name=C.BTN_VIEW_CODES))
    try:
        target.first.wait_for(state="visible", timeout=20000)
    except Exception:
        log("diag counts (sau 20s chờ):", _counts(page))
        log("❌ nút cam KHÔNG hiện sau 20s -> hoặc selector vẫn sai, hoặc trang chưa render "
            "(tăng timeout / kiểm tra route có đúng /th/ hay /vn/).")
        shot(page, "no-button")
        return False
    sleep(rand_ms(600, 1200))
    for attempt in (False, True):               # lần 1 click thường, lần 2 force+dispatch
        try:
            el = target.first
            try: el.scroll_into_view_if_needed(timeout=3000)
            except Exception: pass
            el.click(timeout=6000, force=attempt); return True
        except Exception:
            if not attempt:
                try:
                    target.first.dispatch_event("click"); return True
                except Exception:
                    continue
    log("diag counts (khi bấm fail):", _counts(page))
    shot(page, "click-fail")
    return False

def _close_modal(page):
    try:
        page.keyboard.press("Escape"); sleep(rand_ms(400, 800)); return
    except Exception: pass
    try:
        page.get_by_role("button", name=re.compile(r"^(X|Close|Đóng|ปิด)$", re.I)).first.click(timeout=2000)
    except Exception: pass

def fetch_available_codes(session):
    """REFRESH TRÌNH DUYỆT: reload scan-page (/th), chờ+nút cam, parse neo NGÀY, đóng modal."""
    codes = set()
    page = None
    try:
        if session.scan_page is None or session.scan_page.is_closed():
            session.scan_page = session.context.new_page()
        page = session.scan_page
        cur = page.url
        if not cur or cur == "about:blank":
            page.goto(C.URL_TH, wait_until="domcontentloaded", timeout=45000)
        else:
            page.reload(wait_until="domcontentloaded", timeout=45000)
        try: page.wait_for_load_state("networkidle", timeout=8000)
        except Exception: pass
        sleep(rand_ms(1200, 2000))
        _dismiss_banner(page)
        if not _open_modal(page):
            return []
        sleep(rand_ms(1200, 2000))
        text = page.locator("body").inner_text()
        for c in code_gan_ngay_web(text):
            codes.add(c)
        _close_modal(page)
        log("web fetch được", len(codes), "giftcode:", ", ".join(sorted(codes)) or "(rỗng)")
    except Exception as e:
        log("scraper lỗi:", e.__class__.__name__, e)
        if page is not None:
            try: shot(page, "scraper-exc")
            except Exception: pass
    return sorted(codes)
