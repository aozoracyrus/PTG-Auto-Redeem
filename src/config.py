import re

URL_TH = "https://giftcode.vnggames.com/th/redeem/ptg"
URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ===== MATCHER UI ĐA NGÔN NGỮ [EN]|[TH]|[VN] (route /th khóa TH, /vn khóa VN) =====
BTN_VIEW_CODES = re.compile(
    r"View available redemption codes"
    r"|ดูโค้ดที่พร้อมใช้งาน"
    r"|Xem\s*mã\s+giftcode|Xem\s+code", re.I)
PH_CODE = {
    "TH": ["Enter redemption code", "ใส่รหัสรับไอเทม"],
    "VN": ["Nhập thông tin code", "Nhập mã giftcode"],
}
PH_ID = {
    "TH": ["Select role / Fill in role ID", "เลือกตัวละคร / ใส่ role ID",
           "Select character / Enter character ID", "Enter character ID"],
    "VN": ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"],
}
# Nút redeem: TH thật là "แลกรับ" (hình 16:37), giữ thêm biến thể phòng đổi
BTN_REDEEM = re.compile(r"Redeem|แลกรับ|แลกครับ|Nhập\s*code", re.I)

# ===== PHÁN QUYỀN THẮNG/THUA = TỈ SỐ (lệnh anh: chỉ 0/1 vs 1/1) =====
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"

# ===== Chọn server best-effort (runner để trống ô server -> form chặn submit) =====
SRV_PH = {
    "TH": ["เซิร์ฟเวอร์", "เลือกเซิร์ฟเวอร์", "Server"],
    "VN": ["Máy chủ", "Chọn máy chủ", "Server"],
}
SRV_OPT_RE = re.compile(r"Server\s*2|เซิร์ฟเวอร์\s*2|Máy chủ\s*2", re.I)

# ===== String phản hồi: VN thật từ blob i18n + ảnh 16:52; TH = dự đoán (thiếu cũng không sao,
# ===== vì tỉ số mới quyết thắng/thua; text chỉ để lấy "lí do" cho webhook) =====
TRANSIENT = {   # lỗi hệ thống tạm -> RETRY, không chốt, không webhook
    "VN": ["đã có lỗi xảy ra", "thử lại sau ít phút", "không tìm thấy dữ liệu yêu cầu",
           "không thể tải thông tin game", "vui lòng thử lại sau"],
    "TH": ["เกิดข้อผิดพลาด", "ลองอีกครั้งภายหลัง", "ไม่พบข้อมูลที่ร้องขอ", "ไม่สามารถโหลดข้อมูลเกมได้"],
}
NEED_LOGIN = {  # blob 2101: chưa liên kết tài khoản -> RETRY + nhắc bật storage_state
    "VN": ["chưa liên kết tài khoản game", "liên kết tài khoản rồi thử lại"],
    "TH": ["ไม่ได้เชื่อมบัญชีเกม", "เชื่อมบัญชีแล้วลองใหม่อีกครั้ง"],
}
FAIL_USAGE = {  # đỏ: hết lượt (ảnh 16:52)
    "VN": ["hết lượt nhập", "đã đạt đến giới hạn sử dụng", "giới hạn sử dụng"],
    "TH": ["หมดจำนวน", "ครบจำนวน", "ถึงขีดจำกัด", "ใช้งานครบ", "แลกหมด"],
}
FAIL_NOTEXIST = {  # đỏ: không tồn tại (blob 2102)
    "VN": ["nhận quà không thành công", "kiểm tra lại mã", "inbox fanpage",
           "không tồn tại", "vui lòng kiểm tra lại"],
    "TH": ["โค้ดนี้ไม่มีอยู่", "ไม่มีอยู่", "ตรวจสอบอีกครั้ง", "แฟนเพจ"],
}
FAIL_IDERROR = {  # đỏ: lỗi theo ID (blob 2105) -> chốt, nhắc sửa id_user.txt
    "VN": ["không tìm thấy nhân vật", "nhân vật đang offline", "nhập lại id"],
    "TH": ["ไม่พบตัวละคร", "ตัวละครกำลังออฟไลน์", "กรอกไอดีใหม่อีกครั้ง"],
}
FAIL_VALIDATION = {  # blob 1002
    "VN": ["thông tin nhập không hợp lệ", "vui lòng kiểm tra lại"],
    "TH": ["ข้อมูลที่กรอกไม่ถูกต้อง", "ตรวจสอบอีกครั้ง"],
}
FAIL_SECTION = {"VN": ["thất bại"], "TH": ["ล้มเหลว", "ไม่สำเร็จ"]}

CAPTCHA_HINTS = ["captcha", "mã xác thực", "รหัสยืนยัน", "ยืนยันว่าคุณไม่ใช่หุ่นยนต์",
                 "ตรวจสอบ", "หุ่นยนต์"]

REDEEM_POLL_TIMEOUT = 20.0   # giây chờ modal tổng kết
REDEEM_POLL_STEP    = 1.5

# ===== Parse: ngày dd/mm/yyyy (neo web, không dịch) + token in-hoa + ID 4-4-4 =====
DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
TOK_RE  = re.compile(r"[A-Z0-9]{2,}")
ID_RE   = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

# ===== YouTube =====
KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]       # 10% đen: thêm tiền tố vào đây, KHÔNG sửa độ dài

REGION_LOCALE = {"VN": ("vi-VN", "Asia/Ho_Chi_Minh"), "TH": ("th-TH", "Asia/Bangkok")}
STORAGE_STATE = None         # login OPTIONAL; bật = bớt captcha (cookie đã auth)
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
YT_HANDLE = "@PlayTogetherVNGofficial"
YT_TOP_ENTRIES = 3
YT_CHANNEL_ID_FILE = "yt_channel_id.txt"
