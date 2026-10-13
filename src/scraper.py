import re
from . import config as C
from .parsers import code_truoc_valid_until_web
from .utils import log, sleep, rand_ms

def _click_view_codes(page):
    btn = page.get_by_role("button", name=C.BTN_VIEW_CODES).or_(page.get_by_text(C.BTN_VIEW_CODES))
    try: btn.first.click(timeout=8000); return True
    except Exception:
        log("không thấy nút 'View available redemption codes' (có thể cần login)"); return False

def _close_modal(page):
    """Modal 'Available Redemption Codes' là bottom-sheet overlay; đóng nó (Escape,
       fallback bấm nút X/Close/Đóng) kẻo chặn thao tác tiếp trên CÙNG scan-page."""
    try:
        page.keyboard.press("Escape"); sleep(rand_ms(400, 800)); return
    except Exception: pass
    try:
        page.get_by_role("button", name=re.compile(r"^(X|Close|Đóng)$", re.I)).first.click(timeout=2000)
    except Exception: pass

def fetch_available_codes(session):
    """REFRESH TRÌNH DUYỆT: reload scan-page (trang TH), bấm View, parse giftcode
       (CÓ/KHÔNG có số đều được) bằng neo 'Valid until', rồi đóng bottom-sheet."""
    codes = set()
    try:
        if session.scan_page is None or session.scan_page.is_closed():
            session.scan_page = session.context.new_page()
        cur = session.scan_page.url
        if not cur or cur == "about:blank":
            session.scan_page.goto(C.URL_TH, wait_until="domcontentloaded", timeout=45000)
        else:
            session.reload()                       # <-- refresh 30s/1p
        sleep(rand_ms(1200, 2200))
        _click_view_codes(session.scan_page)
        sleep(rand_ms(1500, 2500))
        text = session.scan_page.locator("body").inner_text()
        for c in code_truoc_valid_until_web(text):
            codes.add(c)
        _close_modal(session.scan_page)            # đóng bottom-sheet sau khi đọc
        log("web fetch được", len(codes), "giftcode khả dụng:", ", ".join(sorted(codes)) or "(rỗng)")
    except Exception as e:
        log("scraper lỗi:", e)
    return sorted(codes)
