import re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= API REDEEM (F12 21:52: khong Cookie -> login optional) =================
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
# Ma so loi (blob i18n) -> kind. So KHONG bao gio bi dich => language-proof.
NUM_SUCCESS    = {0, 200}
NUM_TRANSIENT  = {1000, 1001, 2103}   # loi he thong tam -> retry
NUM_VALIDATION = {1002}              # nghi payload sai ten field -> retry + log gao
NUM_NEED_LOGIN = {2101}              # chua lien ket tai khoan -> retry
NUM_NOT_EXIST  = {2102}              # ma khong ton tai / sai
NUM_ID_ERROR   = {2105}              # ID khong tim thay / offline

# ================= MATCHER UI (VN, cho browser fallback + scraper) =================
PH_CODE = ["Nhập thông tin code", "Nhập mã giftcode"]
PH_ID   = ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"]
BTN_REDEEM = re.compile(r"Nhập\s*code|Redeem", re.I)
BTN_REDEEM_ALTS = [re.compile(r"Nhập\s*code|Nhập Code|nhập code|nhập mã|Redeem", re.I),
                   re.compile(r"Gửi|Submit", re.I)]

# ===== PHAN QUAN thang/thua CHO BROWSER FALLBACK = TI SO (API dung ma so JSON) =====
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"

# ===== CHON SERVER (best-effort; runner de o trong -> form chan submit) =====
SRV_PH = ["Máy chủ", "Chọn máy chủ", "Server"]
SRV_OPT_RE = re.compile(r"Server\s*2|Máy chủ\s*2", re.I)

# ===== TEXT scan (VN thuan; backup message JSON + browser path) =====
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

DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")   # neo parse modal: NGAY (khong dich)
TOK_RE  = re.compile(r"[A-Z0-9]{2,}")            # token in-hoa ASCII = ung vien code
ID_RE   = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")  # validate ID 4-4-4

KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]

LOCALE = ("vi-VN", "Asia/Ho_Chi_Minh")           # VN-only, hardcode
STORAGE_STATE = None                             # login OPTIONAL (F12: API khong can Cookie)
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
YT_HANDLE = "@PlayTogetherVNGofficial"
YT_TOP_ENTRIES = 3
YT_CHANNEL_ID_FILE = "yt_channel_id.txt"
