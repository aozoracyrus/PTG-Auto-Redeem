"""
NGUỒN WEB-LIST CHO VN = KHÔNG TỒN TẠI (trang /vn/redeem/ptg không có nút
'View available redemption codes'; chỉ TH/EN mới có -> da xoa BTN_VIEW_CODES).

Do do ham nay tra [] co dinh, va log giai thich MOT LAN (khong spam moi vong 60s).
Nó duoc GIU LAI (khong xoa file) chi de:
  (a) main.py giu nguyen duong noi 'codes_web' -> sau nay neu anh them nguon web
      khac (VD fanpage/Telegram co list code) thi chi can sua ham nay tra list that,
      main.py KHONG phai doi.
  (b) chu ky source='web' trong main van con (chay 0 lan) -> khong ao, de mo rong.

Redeem van di qua API (api_redeemer) -> khong can ham nay. Browser fallback
(redeemer) van dien form + bam 'Nhap code' -> cung khong can ham nay.
"""
from .utils import log

_logged = False

def fetch_available_codes(session=None):
    """Stub: VN khong co web-list -> tra []. Nhan session de tuong thich chu ky
       main.py (khong dung den)."""
    global _logged
    if not _logged:
        log("scraper: VN KHONG co nut 'Xem danh sach code' -> web-list = rong. "
            "Nguon phat hien code duy nhat = YouTube ('CODE CHUNG' + prefix PT). "
            "Redeem van qua API. (Muon them nguon web khac -> sua ham nay.)")
        _logged = True
    return []
