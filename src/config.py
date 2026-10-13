import re

URL_TH = "https://giftcode.vnggames.com/th/redeem/ptg"
URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

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
BTN_REDEEM = re.compile(r"Redeem|แลกครับ|Nhập\s*code", re.I)

# ===== PHAN QUAN THANG/THUA = TI SO (lenh anh: chi 0/1 vs 1/1) =====
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"

# ===== STRING THAT TU BLOB i18n (VN) + 16:52 (usage). EN/TH = du doan, thieu cung KO SAO =====
# transient = loi he thong tam -> RETRY, khong chot, khong webhook (cuu code khoi mat oan)
TRANSIENT = {
    "VN": ["đã có lỗi xảy ra", "thử lại sau ít phút", "không tìm thấy dữ liệu yêu cầu",
           "không thể tải thông tin game", "vui lòng thử lại sau"],
    "TH": ["เกิดข้อผิดพลาด", "ลองอีกครั้งภายหลัง", "ไม่พบข้อมูุลที่ร้องขอ", "ไม่สามารถโหลดข้อมูุลเกมได้"],
}
# need_login = chua link tai khoan (blob 2101) -> RETRY + nhac bat storage_state
NEED_LOGIN = {
    "VN": ["chưa liên kết tài khoản game", "liên kết tài khoản rồi thử lại"],
    "TH": ["ไม่ได้เชื่่อมบัญชีเกม", "เชื่่อมบัญชีแล้วลองใหม่อีกครั้ง"],
}
# usage_limit (16:52 + spec EN)
FAIL_USAGE = {
    "VN": ["hết lượt nhập", "đã đạt đến giới hạn sử dụng", "giới hạn sử dụng"],
    "TH": ["หมดจำนวณ", "ครบจำนวณ", "ถึงขีดจำกัด", "ใช้งานครบ", "แลกหมด"],
}
# not_exist (blob 2102)
FAIL_NOTEXIST = {
    "VN": ["nhận quà không thành công", "kiểm tra lại mã", "inbox fanpage",
           "không tồn tại", "vui lòng kiểm tra lại"],
    "TH": ["โค้ดนี้ไม่มีอยู่", "ไม่มีอยู่", "ตรวจสอบอีกครั้ง", "แฟนเพจ"],
}
# id_error (blob 2105) -> loi theo ID, khong phai code
FAIL_IDERROR = {
    "VN": ["không tìm thấy nhân vật", "nhân vật đang offline", "nhập lại id"],
    "TH": ["ไม่พบตัวละคร", "ตัวละครกําลังออฟไลน์", "กรอกไอดีใหม่อีกครั้ง"],
}
# validation (blob 1002)
FAIL_VALIDATION = {
    "VN": ["thông tin nhập không hợp lệ", "vui lòng kiểm tra lại"],
    "TH": ["ข้อมูุลที่กรอกไม่ถูกต้อง", "ตรวจสอบอีกครั้ง"],
}
# section loi (backup, tu 16:52)
FAIL_SECTION = {"VN": ["thất bại"], "TH": ["ลม้ เหลวก", "ไม่สำเร็จ"]}

CAPTCHA_HINTS = ["captcha", "mã xác thực", "รหัสยืนยัน", "ยืนยันว่าคุณไม่ใช่หุ่นยนต์",
                 "ตรวจสอบ", "หุ่นยนต์"]

REDEEM_POLL_TIMEOUT = 20.0
REDEEM_POLL_STEP    = 1.5

DATE_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
TOK_RE  = re.compile(r"[A-Z0-9]{2,}")
ID_RE   = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

KEYWORD_PATTERN = r"CODE\s+CHUNG"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]

REGION_LOCALE = {"VN": ("vi-VN", "Asia/Ho_Chi_Minh"), "TH": ("th-TH", "Asia/Bangkok")}
STORAGE_STATE = None
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
YT_HANDLE = "@PlayTogetherVNGofficial"
YT_TOP_ENTRIES = 3
YT_CHANNEL_ID_FILE = "yt_channel_id.txt"
