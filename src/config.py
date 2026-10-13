import re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ===== MATCHER UI TRANG VN =====
PH_CODE = ["Nhập thông tin code", "Nhập mã giftcode"]
PH_ID   = ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"]
BTN_REDEEM = re.compile(r"Nhập\s*code", re.I)

# ===== PHÁN QUYỀN THẮNG/THUA = TỈ SỐ (không dịch, không glyph) =====
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"

# ===== Chọn server best-effort =====
SRV_PH = ["Máy chủ", "Chọn máy chủ", "Server"]
SRV_OPT_RE = re.compile(r"Server\s*2|Máy chủ\s*2", re.I)

# ===== String phản hồi VN (thật từ blob i18n + ảnh modal) =====
TRANSIENT = ["đã có lỗi xảy ra", "thử lại sau ít phút", "không tìm thấy dữ liệu yêu cầu",
             "không thể tải thông tin game", "vui lòng thử lại sau"]
NEED_LOGIN = ["chưa liên kết tài khoản game", "liên kết tài khoản rồi thử lại"]
FAIL_USAGE = ["hết lượt nhập", "đã đạt đến giới hạn sử dụng", "giới hạn sử dụng"]
FAIL_NOTEXIST = ["nhận quà không thành công", "kiểm tra lại mã", "inbox fanpage",
                 "không tồn tại", "vui lòng kiểm tra lại"]
FAIL_IDERROR = ["không tìm thấy nhân vật", "nhân vật đang offline", "nhập lại id"]
FAIL_VALIDATION = ["thông tin nhập không hợp lệ", "vui lòng kiểm tra lại"]
FAIL_SECTION = ["thất bại"]

CAPTCHA_HINTS = ["captcha", "mã xác thực"]

REDEEM_POLL_TIMEOUT = 20.0
REDEEM_POLL_STEP    = 1.5

# ID khuôn 4-4-4 (chỉ cảnh báo, không chặn)
ID_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

# ===== YouTube =====
KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]        # 10% đen: thêm tiền tố mới vào đây

LOCALE, TIMEZONE = "vi-VN", "Asia/Ho_Chi_Minh"
STORAGE_STATE = None          # login OPTIONAL -> bớt captcha
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
YT_HANDLE = "@PlayTogetherVNGofficial"
YT_TOP_ENTRIES = 3
YT_CHANNEL_ID_FILE = "yt_channel_id.txt"
