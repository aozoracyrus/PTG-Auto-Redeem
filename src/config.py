import os, re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= API REDEEM (F12: khong Cookie -> login OPTIONAL o tang redeem VNG) =================
API_URL = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"
API_UA  = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36")
API_PAYLOAD_TEMPLATE = {
    "gameCode": "ptg",
    "code":     "{code}",
    "roleId":   "{id}",
    "serverId": 2,
    "region":   "{region}",
}
NUM_SUCCESS    = {0, 200}
NUM_TRANSIENT  = {1000, 1001, 2103}
NUM_VALIDATION = {1002}
NUM_NEED_LOGIN = {2101}
NUM_NOT_EXIST  = {2102}
NUM_ID_ERROR   = {2105}

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
FAIL_USAGE      = ["hết lượt nhập", "đã đạt đến giới hạn sử dụng", "giới hạn sử dụng"]
FAIL_NOTEXIST   = ["nhận quà không thành công", "kiểm tra lại mã", "inbox fanpage",
                   "không tồn tại", "vui lòng kiểm tra lại"]
FAIL_IDERROR    = ["không tìm thấy nhân vật", "nhân vật đang offline", "nhập lại id"]
FAIL_VALIDATION = ["thông tin nhập không hợp lệ"]
FAIL_SECTION    = ["thất bại"]
CAPTCHA_HINTS   = ["captcha", "mã xác thực"]

REDEEM_POLL_TIMEOUT = 20.0
REDEEM_POLL_STEP    = 1.5

ID_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

# ================= YOUTUBE = API (BO HTML: F12 Quetta to mobile shell rong, data load XHR sau) =================
# channelId ANH da xac nhan bang tay (bam @handle -> /channel/UC.../videos). Dung cho CA 2 tang API.
YT_CHANNEL_ID = "UCnLyxhAWS7yakzX8aWO6PKQ"
YT_UPLOADS_ID = "UU" + YT_CHANNEL_ID[2:]      # uploads-playlist = dung tab Videos, khong lan tag
YT_VIDEO_SCAN = 15

# Tang chinh: Data API v3 (path co dinh items[].snippet.title, KHONG doan schema). Can key secret.
# Dat qua env YT_API_KEY (secret trong redeem.yml) HOAC de trong chuoi duoi. Trong = tu dong skip tang nay.
YT_API_KEY = os.getenv("YT_API_KEY", "").strip()
DATA_API_PLAYLIST = "https://www.googleapis.com/youtube/v3/playlistItems"

# Tang fallback: InnerTube browse (key PUBLIC hardcoded, KHONG can secret -> chay ngay).
# parse DE QUY tim videoId+title -> chong vo schema renderer. params/clientVersion = hang chuan cong dong.
INNERTUBE_BROWSE = "https://www.youtube.com/youtubei/v1/browse"
INNERTUBE_KEY    = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"   # public web key, khong phai secret
INNERTUBE_PARAMS_VIDEOS = "EgZ2aWRlb3PyBgQKAjoA"               # protobuf token co dinh cho tab Videos
INNERTUBE_VERSION = "2.20261014.00.00"

KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]

LOCALE = ("vi-VN", "Asia/Ho_Chi_Minh")
STORAGE_STATE = None
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
