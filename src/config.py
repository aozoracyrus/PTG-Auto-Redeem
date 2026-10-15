# TOAN BO FACT da chot (F1/F2/F3 + invariant parser + YouTube InnerTube/DataAPI + web-list rong).
# Khong con gia dinh nao. VN-only, bo TH.
import os, re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= API REDEEM (F12: khong Cookie -> login OPTIONAL) =================
API_URL = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"
API_UA  = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36")
# PAYLOAD = FACT (F3): request redeem xanh tra errorCode:1 + data echo dung 5 field nay.
# ServerId hardcode "2" dung cho ID nay; chi ban per-ID neu ID khac ra loi "sai server/role".
API_PAYLOAD_TEMPLATE = {
    "serverId": "2",
    "gameCode": "661",
    "roleId":   "{id}",
    "roleName": "{id}",
    "code":     "{code}",
}
# errorCode: F12 la trong tai tuyet doi (blob i18n chi ban dich frontend, khong day du).
NUM_SUCCESS    = {1}                    # FACT F1: errorCode:1, message:"Success"
NUM_USAGE      = {2117}                 # FACT "Active code: usage limit" -> that bai (CHOT)
NUM_CODE_BAD   = {2106, 2102}           # FACT "Code not found"(2106) + blob 2102 -> not_exist
NUM_ID_ERROR   = {2105}                 # blob "khong tim thay nhan vat/offline" -> loi ID (CHOT)
NUM_NEED_LOGIN = {2101}                 # blob "chua lien ket tai khoan" -> retry
NUM_TRANSIENT  = {1000, 1001, 2103}     # blob loi he thong tam -> stuck (retry, khong chot)
NUM_VALIDATION = {1002}                 # "Data invalid" = PAYLOAD SAI -> retry/lock (da het sau F3)
# F2: success cung la HTTP 200 -> status KHONG con la trong tai. Chi dung HTTP nhan KET tam
# thoi khi KHONG co errorCode nghiep vu (403/404/429/5xx). 200/400 deu quyet boi errorCode.
HTTP_STUCK = {403, 404, 408, 425, 429, 500, 501, 502, 503, 504}

# ================= MATCHER UI (VN, CH dung khi USE_API=0 browser fallback) =================
PH_CODE = ["Nhập thông tin code", "Nhập mã giftcode"]
PH_ID   = ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"]
BTN_REDEEM = re.compile(r"Nhập\s*code|Redeem", re.I)
BTN_REDEEM_ALTS = [re.compile(r"Nhập\s*code|Nhập Code|nhập code|nhập mã|Redeem", re.I),
                   re.compile(r"Gửi|Submit", re.I)]
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"
SRV_PH = ["Máy chủ", "Chọn máy chủ", "Server"]
SRV_OPT_RE = re.compile(r"Server\s*2|Máy chủ\s*2", re.I)

# text scan BACKUP (chi khi num chua map). Chu TIENG ANH machine-readable tu F12.
TRANSIENT       = ["đã có lỗi xảy ra", "thử lại sau ít phút", "không tìm thấy dữ liệu yêu cầu",
                   "không thể tải thông tin game", "vui lòng thử lại sau"]
NEED_LOGIN      = ["chưa liên kết tài khoản game", "liên kết tài khoản rồi thử lại"]
FAIL_USAGE      = ["hết lượt nhập", "đã đạt đến giới hạn sử dụng", "giới hạn sử dụng",
                   "vượt quá số lần nhập", "usage limit", "active code"]
FAIL_NOTEXIST   = ["nhận quà không thành công", "kiểm tra lại mã", "inbox fanpage",
                   "không tồn tại", "vui lòng kiểm tra lại", "code not found"]
FAIL_IDERROR    = ["không tìm thấy nhân vật", "nhân vật đang offline", "nhập lại id"]
FAIL_VALIDATION = ["thông tin nhập không hợp lệ", "data invalid"]
FAIL_SECTION    = ["thất bại"]
CAPTCHA_HINTS   = ["captcha", "mã xác thực"]

REDEEM_POLL_TIMEOUT = 20.0
REDEEM_POLL_STEP    = 1.5

ID_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

# ================= YOUTUBE = API (BO HTML: F12 to mobile shell rong; BO RSS: 404 vinh vien) =================
YT_CHANNEL_ID = "UCnLyxhAWS7yakzX8aWO6PKQ"     # FACT anh xac nhan bang tay
YT_UPLOADS_ID = "UU" + YT_CHANNEL_ID[2:]
YT_VIDEO_SCAN = 15
YT_API_KEY = os.getenv("YT_API_KEY", "").strip()        # Data API v3 (duong ben nhat, co key moi chay)
DATA_API_PLAYLIST = "https://www.googleapis.com/youtube/v3/playlistItems"
INNERTUBE_BROWSE = "https://www.youtube.com/youtubei/v1/browse"
INNERTUBE_KEY    = os.getenv("INNERTUBE_KEY", "").strip()  # public key -> doc tu env, HEAD sach
INNERTUBE_PARAMS_VIDEOS = "EgZ2aWRlb3PyBgQKAjoA"
INNERTUBE_VERSION = "2.20261014.00.00"

KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
# CODE_PREFIXES: parser KHONG dung de chon nua (invariant = code dinh ngay sau keyword ->
# token dau). Giu lai chi de log message tham chieu, khoi phai sua file khac.
CODE_PREFIXES = ["PT"]
CODE_MIN_LEN  = 6   # token alnum-khong-dau >= cay nay sau 'CODE CHUNG' = code.

LOCALE = ("vi-VN", "Asia/Ho_Chi_Minh")
STORAGE_STATE = None
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
