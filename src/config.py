import re

URL_TH = "https://giftcode.vnggames.com/th/redeem/ptg"
URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= MATCHER UI ĐA NGÔN NGỮ [EN]|[TH]|[VN] =================
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

# ===== PHÂN LOẠI THẮNG/THUA: CHỈ NHÌN TỈ SỐ (dễ hiểu nhất, language-proof) =====
RATIO_FAIL = "0/1"   # modal thua  -> failure
RATIO_OK   = "1/1"   # modal thắng -> success
# (Bot redeem đơn lẻ 1 code x 1 ID -> modal luôn "X/1". Nếu sau này đổi sang
#  chọn nhiều code 1 lần thì tỉ số thành X/N, sửa 2 hằng này là xong.)

# ===== TEXT ĐỎ: CHỈ DÙNG ĐỂ LẤY "LÍ DO" CHO WEBHOOK FAILURE (không quyết thắng/thua) =====
# Sai/thiếu bản dịch TH cũng KHÔNG sao: cùng lắm reason = "thất bại", chiều vẫn đúng nhờ ratio.
FAIL_USAGE = {
    "TH": ["หมดจำนวณ", "ครบจำนวณ", "ถึงขีดจำกัด", "ใช้งานครบ", "แลกหมด",
           "reached its usage limit", "usage limit"],
    "VN": ["hết lượt nhập", "đã đạt đến giới hạn sử dụng", "giới hạn sử dụng",
           "reached its usage limit", "usage limit"],
}
FAIL_NOTEXIST = {
    "TH": ["โค้ดนี้ไม่มีอยู่ กรุณาตรวจสอบอีกครั้งหรือทักไปที่แฟนเพจเพื่อขอความช่วยเหลือ",
           "ไม่มีอยู่", "does not exist", "contact the fanpage"],
    "VN": ["không tồn tại", "vui lòng kiểm tra lại", "inbox fanpage",
           "does not exist", "contact the fanpage"],
}

CAPTCHA_HINTS = ["captcha", "mã xác thực", "รหัสยืนยัน", "ยืนยันว่าคุณไม่ใช่หุ่นยนต์",
                 "ตรวจสอบ", "หุ่นยนต์"]

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
