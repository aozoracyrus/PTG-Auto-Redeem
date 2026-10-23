# NGUON WEB-LIST CHO VN = KHONG TON TAI (khong nut xem danh sach code). Stub tra [],
# log 1 lan. Giu lam seam mo rong nguon web khac sau nay.
from .utils import log_loop

_logged = False


def fetch_available_codes(session=None):
    global _logged
    if not _logged:
        log_loop("Scraper: VN KHONG co nut 'Xem danh sach code' -> web-list = rong. "
                 "Nguon phat hien ma duy nhat = YouTube ('CODE CHUNG' / 'CODE' / 'CÔ DÉ'). "
                 "Redeem van qua API. (Muon them nguon web khac -> sua ham nay.)")
        _logged = True
    return []
