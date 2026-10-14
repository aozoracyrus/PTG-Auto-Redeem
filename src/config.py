import re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= API REDEEM (F12: khong Cookie -> login OPTIONAL o tang redeem VNG) =================
# Box "Dang nhap de rut ngan thoi gian..." chi la gay y; API redeem khong can cookie.
# Login chi tro thanh van de NEU log redeem bao num=2101 (chua lien ket tai khoan).
API_URL = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"
API_UA  = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36")
# Payload MAC DINH (gia thuyet tu Content-Length 107). NEU log gao "PAYLOAD SAI"
# (server tra 1002 lap lai) -> mo F12 tab Payload, copy raw JSON, sua template duoi.
API_PAYLOAD_TEMPLATE = {
    "gameCode": "ptg",
    "code":     "{code}",
    "roleId":   "{id}",
    "serverId": 2,
    "region":   "{region}",
}
# Ma so loi (blob i18n) -> kind. So KHONG bao gio bi dich => language-proof tuyet doi.
NUM_SUCCESS    = {0, 200}
NUM_TRANSIENT  = {1000, 1001, 2103}   # loi he thong tam -> retry (khong chot, khong webhook)
NUM_VALIDATION = {1002}              # nghi payload sai ten field -> retry + log gao
NUM_NEED_LOGIN = {2101}              # chua lien ket tai khoan -> retry
NUM_NOT_EXIST  = {2102}              # ma khong ton tai / sai
NUM_ID_ERROR   = {2105}              # ID khong tim thay / offline (loi theo ID, khong phai code)

# ================= MATCHER UI (VN, CH dung khi USE_API=0 browser fallback) =================
# VN KHONG co nut 'Xem danh sach code' -> khong con BTN_VIEW_CODES; web-list = rong (scraper stub).
PH_CODE = ["Nhập thông tin code", "Nhập mã giftcode"]
PH_ID   = ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"]
BTN_REDEEM = re.compile(r"Nhập\s*code|Redeem", re.I)
BTN_REDEEM_ALTS = [re.compile(r"Nhập\s*code|Nhập Code|nhập code|nhập mã|Redeem", re.I),
                   re.compile(r"Gửi|Submit", re.I)]

# Phan quan thang/thua CHO BROWSER FALLBACK = TI SO (API dung ma so JSON o tren).
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"

# Chon server best-effort (runner de o trong -> form chan submit).
SRV_PH = ["Máy chủ", "Chọn máy chủ", "Server"]
SRV_OPT_RE = re.compile(r"Server\s*2|Máy chủ\s*2", re.I)

# ================= TEXT scan (VN thuan; backup message JSON + browser fallback) =================
# La list PHAT (VN-only), khong con dict theo region.
TRANSIENT       = ["đã có lỗi xảy ra", "thử lại sau ít phút", "không tìm thấy dữ liệu yêu cầu",
                   "không thể tải thông tin game", "vui lòng thử lại sau"]
NEED_LOGIN      = ["chưa liên kết tài khoản game", "liên kết tài khoản rồi thử lại"]
FAIL_USAGE      = ["hết lượt nhập", "đã đạt đến giới hạn sử dụng", "giới hạn sử dụng"]
FAIL_NOTEXIST   = ["nhận quà không thành công", "kiểm tra lại mã", "inbox fanpage",
                   "không tồn tại", "vui lòng kiểm tra lại"]
FAIL_IDERROR    = ["không tìm thấy nhân vật", "nhân vật đang offline", "nhập lại id"]
FAIL_VALIDATION = ["thông tin nhập không hợp lệ"]
FAIL_SECTION    = ["thất bại"]
CAPTCHA_HINTS   = ["captcha", "mã xác thực"]

REDEEM_POLL_TIMEOUT = 20.0
REDEEM_POLL_STEP    = 1.5

# ID nguoi dung: khuon CUNG 4-4-4, CH validate dong id_user.txt (KHONG lien quan giftcode).
ID_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

# ================= YOUTUBE = NGUON CODE DUY NHAT cho VN (HTML-only) =================
# RSS /feeds/videos.xml da CHET VINH VIEN cho kenh nay (404 tu CA IP dan cu lan IP runner)
# -> bo RSS hoan toan (khong backoff/streak: vo ich voi loi vinh vien).
# Fetch TRUC TIEP @handle/videos (dung khu vực anh kiem chung hang ngay), KHONG qua channel id.
# Trich tieu de theo "videoRenderer" (KHONG sort-by-length -> loai sach text UI cua YouTube).
# Quet 15 video moi nhat (tab Videos sort Latest).
YT_HANDLE     = "@PlayTogetherVNGofficial"
YT_VIDEO_SCAN = 15     # so video Renderer max lay tu HTML
YT_WINDOW     = 3500   # ky tu cua so sau moi "videoRenderer" de tim "title"

# Keyword + prefix: 'CODE CHUNG' (NPH viet tay trong title, khong auto-dich) + mo dau 'PT'.
# 10% den -> them tien to vao CODE_PREFIXES, KHONG bao gio sua do dai.
KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]

# ================= Browser fallback (chi khi USE_API=0) =================
LOCALE = ("vi-VN", "Asia/Ho_Chi_Minh")          # VN-only, hardcode
STORAGE_STATE = None                             # login OPTIONAL; chi bat khi muon it captcha hon
MOBILE_VIEWPORT = {"width": 390, "height": 844}  # khop layout bottom-sheet da kiem chung tay
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
