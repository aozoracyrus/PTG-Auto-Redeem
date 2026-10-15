# NGUON WEB-LIST CHO VN = KHONG TON TAI (trang /vn/redeem/ptg khong co nut 'Xem danh sach
# code'; chi TH/EN co -> da xoa BTN_VIEW_CODES). Ham tra [] co dinh, log 1 LAN. GIU LAI de
# main.py giu duong noi 'codes_web' -> sau nay them nguon web khac thi chi sua ham nay.
from .utils import log

_logged = False

def fetch_available_codes(session=None):
    global _logged
    if not _logged:
        log("scraper: VN KHONG co nut 'Xem danh sach code' -> web-list = rong. "
            "Nguon phat hien code duy nhat = YouTube ('CODE CHUNG' + prefix PT). "
            "Redeem van qua API. (Muon them nguon web khac -> sua ham nay.)")
        _logged = True
    return []
