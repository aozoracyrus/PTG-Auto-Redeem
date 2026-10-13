import re

URL_TH = "https://giftcode.vnggames.com/th/redeem/ptg"
URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= MATCHER UI ĐA NGÔN NGỮ =================
# Route /th/ khóa TH, /vn/ khóa VN theo PATH (locale browser KHÔNG đổi được).
# Nên MỌI chuỗi dưới đây gom đủ [EN]|[TH]|[VN]. Candidate lấy từ screenshot thật
# (EN 16:32, TH 16:37+16:38, VN lượt đầu + knowledge-base). get_by_* mặc định
# substring + case-insensitive -> list/regex hợp nhất là ăn cả 3 ngôn ngữ.

# Nút cam mở modal danh sách code.  [EN] View available redemption codes
#                                   [TH] ดูโค้ดที่พร้อมใช้งาน   (hình 16:37)
#                                   [VN] Xem mã giftcode / Xem code
BTN_VIEW_CODES = re.compile(
    r"View available redemption codes"
    r"|ดูโค้ดที่พร้อมใช้งาน"
    r"|Xem\s*mã\s+giftcode|Xem\s+code", re.I)

# Placeholder ô NHẬP CODE.  [EN] Enter redemption code
#                           [TH] ใส่รหัสรับไอเทม        (hình 16:37)
#                           [VN] Nhập thông tin code / Nhập mã giftcode
PH_CODE = {
    "TH": ["Enter redemption code", "ใส่รหัสรับไอเทม"],
    "VN": ["Nhập thông tin code", "Nhập mã giftcode"],
}
# Placeholder ô NHẬP ID / nhân vật.  [EN] Select role / Fill in role ID  (hình 16:32)
#                                     [TH] เลือกตัวละคร / ใส่ role ID    (hình 16:37)
#                                     [VN] Chọn nhân vật / Nhập ID nhân vật
PH_ID = {
    "TH": ["Select role / Fill in role ID", "เลือกตัวละคร / ใส่ role ID",
           "Select character / Enter character ID", "Enter character ID"],
    "VN": ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"],
}
# Nút REDUCE/REDEEM.  [EN] Redeem   [TH] แลกครับ   [VN] Nhập code
BTN_REDEEM = re.compile(r"Redeem|แลกครับ|Nhập\s*code", re.I)

# ---- Toast/label PHẢN HỒI sau khi bấm redeem (so substring, lowercase 2 phía) ----
# [EN]+[VN] chắc chắn (đã thấy). [TH] = DỰ ĐOÁN (chưa có screenshot toast TH) ->
#   xem ghi chú cuối bài; mọi candidate TH đều chứa từ đặc trưng để KHÔNG trùng text tĩnh.
OK = {
    "TH": ["code entry completed", "แลกสำเร็จ", "รับไอเทมสำเร็จ", "กรอกสำเร็จ", "สำเร็จแล้ว"],
    "VN": ["đã hoàn tất nhập mã.", "hoàn tất nhập mã"],
}
FAIL_USAGE = {   # chạm giới hạn lượt dùng
    "TH": ["this code has reached its usage limit", "ถึงขีดจำกัด", "ใช้ครบแล้ว",
           "จำนวนเต็ม", "เต็มจำนวน", "หมดจำนวน"],
    "VN": ["mã này đã đạt đến giới hạn sử dụng.", "đã đạt đến giới hạn sử dụng"],
}
FAIL_NOTEXIST = {  # mã không tồn tại / sai
    "TH": ["this code does not exist", "ไม่พบรหัส", "รหัสไม่ถูกต้อง", "ไม่มีรหัสนี้",
           "ไม่ถูกต้อง", "รหัสผิด"],
    "VN": ["mã này không tồn tại", "không tồn tại. vui lòng kiểm tra lại"],
}
CAPTCHA_HINTS = ["captcha", "mã xác thực", "รหัสยืนยัน", "ยืนยันว่าคุณไม่ใช่หุ่นยนต์",
                 "ตรวจสอบ", "หุ่นยนต์"]

# ---- Text tĩnh trên trang/challenge (dùng để loại nhiễu, KHÔNG dùng để khớp nút) ----
# Ngày hết hạn dạng dd/mm/yyyy -> NEO parse modal, language-independent.
DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
# Token in-hoa ASCII (>=2) = ứng viên giftcode trong modal (heading code in hoa).
TOK_RE  = re.compile(r"[A-Z0-9]{2,}")

# ID người dùng: khuôn CỨNG 4-4-4, CHỈ validate dòng id_user.txt (không liên quan giftcode).
ID_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

# Neo keyword YouTube (title do NPH viết tay "CODE CHUNG", không auto-dịch -> giữ re.I).
KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
# YouTube: code PHẢI mở đầu prefix (mặc định "PT"); 10% đen -> thêm tiền tố, KHÔNG sửa độ dài.
CODE_PREFIXES = ["PT"]

REGION_LOCALE = {"VN": ("vi-VN", "Asia/Ho_Chi_Minh"), "TH": ("th-TH", "Asia/Bangkok")}
STORAGE_STATE = None   # login OPTIONAL (knowledge-base: "rút ngắn thời gian", không bắt buộc)

# Viewport MOBILE để khớp đúng layout bottom-sheet modal anh đã kiểm chứng bằng tay.
# (Firefox bỏ qua is_mobile/has_touch, nhưng media-query theo WIDTH vẫn kích layout mobile.)
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")

YT_HANDLE = "@PlayTogetherVNGofficial"
YT_TOP_ENTRIES = 3
YT_CHANNEL_ID_FILE = "yt_channel_id.txt"
