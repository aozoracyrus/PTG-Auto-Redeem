import re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= API REDEEM (F12: khong Cookie -> login optional) =================
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
NUM_SUCCESS    = {0, 200}
NUM_TRANSIENT  = {1000, 1001, 2103}
NUM_VALIDATION = {1002}
NUM_NEED_LOGIN = {2101}
NUM_NOT_EXIST  = {2102}
NUM_ID_ERROR   = {2105}

# ================= MATCHER UI (VN, browser fallback; VN KHONG co nut list code) =================
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

DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
TOK_RE  = re.compile(r"[A-Z0-9]{2,}")
ID_RE   = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]

# ================= YOUTUBE = NGUON CODE DUY NHAT cho VN (HTML-only) =================
# RSS /feeds/videos.xml da CHET VINH VIEN cho channel nay: 404 tu CA IP dan cu (anh mo
# bang dien thoai) lan IP runner -> khong phai chan theo IP, ma YouTube khong phuc vu
# feed cho kenh nay. -> BO RSS hoan toan (khong backoff, khong streak, vo ich).
# Chi dung HTML /channel/<ID>/videos: anh mo /@.../videos thay video => HTML song;
# va runner truoc day fetch HTML 200 de resolve id => HTML-tu-runner song. Tab Videos
# mac dinh sort Latest => video code moi nhat LUON o dau => HTML initial render chua no.
# ID da ANH xac nhan bang tay (bam @handle -> /channel/UC.../videos) nen HARDCODE.
YT_CHANNEL_ID  = "UCnLyxhAWS7yakzX8aWO6PKQ"   # << bang chung anh vua gui, dung 100%
YT_HANDLE      = "@PlayTogetherVNGofficial"   # chi de doc/tham chieu, khong dung de fetch
YT_TOP_ENTRIES = 3                            # so title max lay tu HTML (video moi nhat)

LOCALE = ("vi-VN", "Asia/Ho_Chi_Minh")
STORAGE_STATE = None
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
