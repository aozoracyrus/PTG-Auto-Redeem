from .utils import log_loop

_logged = False


def fetch_available_codes(session=None):
    global _logged
    if not _logged:
        log_loop("Scraper: VN khong co nut 'Xem danh sach code' -> web-list = rong.")
        _logged = True
    return []
