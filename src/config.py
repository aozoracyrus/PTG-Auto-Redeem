import re

URL_TH = "https://giftcode.vnggames.com/th/redeem/ptg"
URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ---------- Trang giftcode (selector / chuỗi phản hồi) ----------
BTN_VIEW_CODES = re.compile(r"View available redemption codes|Xem\s+mã\s+giftcode|Xem\s+code", re.I)
PH_CODE = {
    "TH": ["Enter redemption code", "Enter Redemption Code"],
    "VN": ["Nhập thông tin code", "Nhập mã giftcode"],
}
PH_ID = {
    "TH": ["Select character / Enter character ID", "Enter character ID",
           "Chọn nhân vật / Nhập ID nhân vật"],
    "VN": ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"],
}
BTN_REDEEM = {"TH": re.compile(r"^Redeem$", re.I), "VN": re.compile(r"^Nhập\s*code$", re.I)}
OK = {"TH": "Code entry completed", "VN": "Đã hoàn tất nhập mã."}
FAIL = {
    "TH": ["This code has reached its usage limit.",
           "This code does not exist. Please check again or contact the Fanpage for support."],
    "VN": ["Mã này đã đạt đến giới hạn sử dụng.",
           "Mã này không tồn tại. Vui lòng kiểm tra lại hoặc liên hệ Fanpage để được hỗ trợ."],
}
CAPTCHA_HINTS = ["Mã xác thực", "Captcha", "captcha"]

# Substring để PHÂN LOẠI failure (quyết định có chốt state hay không).
USAGE_LIMIT_SUB = {"TH": "reached its usage limit", "VN": "đã đạt đến giới hạn sử dụng"}
NOT_EXIST_SUB   = {"TH": "does not exist",          "VN": "không tồn tại"}

# ---------- ID người dùng: khuôn CỨNG 4-4-4 ----------
# CHỈ dùng validate/cảnh báo dòng trong id_user.txt. KHÔNG liên quan giftcode.
ID_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

# ---------- Parse giftcode: THEO ĐẶC TRƯNG, KHÔNG THEO ĐỘ DÀI, KHÔNG CẦN SỐ ----------
# Chuỗi keyword YouTube (title THẬT không có "" / (); re.I cho watcher khoan dung hoa-thường).
KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)

# YouTube: code PHẢI mở đầu 1 trong các prefix dưới đây (mặc định "PT" = Play Together, ~90%).
#   -> code ngắn mấy (PT26, PT...) vẫn lấy; từ sự kiện in-hoa (UPDATE/NGAY/VNG...) bị chặn.
#   -> 10% đen: thêm tiền tố mới vào list, KHÔNG bao giờ phải sửa độ dài.
#   -> để rỗng [] = tắt prefix, quay về "token in-hoa bất kỳ >=1" (sẽ lẫn nhiễu từ tiếng Việt
#      không-dấu; flow YT cooldown+probe+timeout sẽ gặm noise, chỉ dùng khi buộc phải).
CODE_PREFIXES = ["PT"]

# Web-modal: KHÔNG dùng prefix & KHÔNG dùng độ dài tối thiểu — neo "Valid until" đã đủ sạch
#   (chỉ token in-hoa LIỀN TRƯỚC "Valid until" được lấy; label Title-case tự rớt nhờ không re.I).

REGION_LOCALE = {"VN": ("vi-VN", "Asia/Ho_Chi_Minh"), "TH": ("th-TH", "Asia/Bangkok")}
STORAGE_STATE = None   # ví dụ "auth.json" (xem README mục đăng nhập)

# ---------- YouTube watcher ----------
YT_HANDLE = "@PlayTogetherVNGofficial"
YT_TOP_ENTRIES = 3                               # soi N video mới nhất của RSS
YT_CHANNEL_ID_FILE = "yt_channel_id.txt"         # cache UC... khỏi resolve mỗi vòng
