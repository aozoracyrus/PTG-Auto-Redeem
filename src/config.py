import os, re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= API REDEEM (F12: khong Cookie -> login OPTIONAL) =================
API_URL = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"
API_UA  = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36")
# PAYLOAD = FACT (F3): redeem xanh tra errorCode:1 + data echo dung 5 field nay.
API_PAYLOAD_TEMPLATE = {
    "serverId": "2",
    "gameCode": "661",
    "roleId":   "{id}",
    "roleName": "{id}",
    "code":     "{code}",
}
NUM_SUCCESS    = {1}
NUM_USAGE      = {2117}
NUM_CODE_BAD   = {2106, 2102}
NUM_ID_ERROR   = {2105}
NUM_NEED_LOGIN = {2101}
NUM_TRANSIENT  = {1000, 1001, 2103}
NUM_VALIDATION = {1002}
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

# ================= YOUTUBE = API (BO HTML + BO RSS) =================
YT_CHANNEL_ID = "UCnLyxhAWS7yakzX8aWO6PKQ"
YT_UPLOADS_ID = "UU" + YT_CHANNEL_ID[2:]
# "3" = 3 video MOI NHAT CO CHUA 'CODE CHUNG' (khong phai 3 video dau cua kenh). Loc truoc
# slice nen video moi KHONG co code bi bo, khong day duoc video code ra khoi cua so.
YT_VIDEO_SCAN = 3
# Hang so cho EMBED 'phat hien video moi'.
YT_CHANNEL_NAME = "Play Together VNG"
YT_CHANNEL_URL  = "https://www.youtube.com/@PlayTogetherVNGofficial/videos"
# YT_CHANNEL_AVATAR = OVERRIDE TUY CHON, KHONG con la cach duy nhat. De TRONG thi bot TU
# lay avatar kan tu chinh response InnerTube bang bo loc su-that-URL (CDN googleusercontent
# + token cat tron =s..-c + hinh vuong, loai banner ngang) -> KHONG hardcode duong dan JSON,
# cung Triet ly voi thumbnail (chon theo kich thuoc/CDN, khong theo wrapper). Chi ghi vao
# day (hoac secret cung ten) khi muon mot crop rieng, hoac neu mot ngay YouTube doi ca CDN
# lan token (rat kho) de override van cứu. Truong hop xau nhat cua heuristic = mat icon tron,
# KHONG crash, va override van cover -> khong bao gio te hon ban cu.
YT_CHANNEL_AVATAR = os.getenv("YT_CHANNEL_AVATAR", "").strip()

YT_API_KEY = os.getenv("YT_API_KEY", "").strip()        # Data API v3, key THAT -> chi qua env
DATA_API_PLAYLIST = "https://www.googleapis.com/youtube/v3/playlistItems"
INNERTUBE_BROWSE = "https://www.youtube.com/youtubei/v1/browse"
INNERTUBE_PUBLIC = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
INNERTUBE_KEY    = (os.getenv("INNERTUBE_KEY", "").strip() or INNERTUBE_PUBLIC)
INNERTUBE_PARAMS_VIDEOS = "EgZ2aWRlb3PyBgQKAjoA"
INNERTUBE_VERSION = "2.20261014.00.00"

KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]
CODE_MIN_LEN  = 6

LOCALE = ("vi-VN", "Asia/Ho_Chi_Minh")
STORAGE_STATE = None
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
