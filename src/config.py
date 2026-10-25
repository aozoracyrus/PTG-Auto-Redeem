# TOAN BO CAU HINH. Comment = tieng Viet khong dau; chuoi hien thi cho nguoi = co dau.
import os, re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= API REDEEM (FACT F12) =================
API_URL = "https://vgrapi-sea.vnggames.com/coordinator/api/v1/code/redeem"
API_UA  = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36")
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

# ================= MATCHER UI (chi khi USE_API=0) =================
PH_CODE = ["Nhập thông tin code", "Nhập mã giftcode"]
PH_ID   = ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"]
BTN_REDEEM = re.compile(r"Nhập\s*code|Redeem", re.I)
BTN_REDEEM_ALTS = [re.compile(r"Nhập\s*code|Nhập Code|nhập code|nhập mã|Redeem", re.I),
                   re.compile(r"Gửi|Submit", re.I)]
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"
SRV_PH = ["Máy chủ", "Chọn máy chủ", "Server"]
SRV_OPT_RE = re.compile(r"Server\s*2|Máy chủ\s*2", re.I)

# ================= TABLE TEXT = CHUOI KHOP MESSAGE SERVER (KHONG DICH) =================
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

# ================= YOUTUBE =================
YT_CHANNEL_ID = "UCnLyxhAWS7yakzX8aWO6PKQ"
YT_UPLOADS_ID = "UU" + YT_CHANNEL_ID[2:]
# PRODUCTION: 3 video moi nhat co ma text (title/desc) duoc queue+redeem.
YT_VIDEO_SCAN = 3
# ocr.py _alert doc C.YT_COOLDOWN; truoc day chi ton tai trong main.py -> AttributeError
#   -> crash giua _alert -> candidate doc duong bi bo, khong nhap. Nay o day.
YT_COOLDOWN = int(os.getenv("YT_COOLDOWN", "60"))
YT_API_KEY = os.getenv("YT_API_KEY", "").strip()
DATA_API_PLAYLIST = "https://www.googleapis.com/youtube/v3/playlistItems"
INNERTUBE_BROWSE = "https://www.youtube.com/youtubei/v1/browse"
INNERTUBE_PUBLIC = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
INNERTUBE_KEY    = (os.getenv("INNERTUBE_KEY", "").strip() or INNERTUBE_PUBLIC)
INNERTUBE_PARAMS_VIDEOS = "EgZ2aWRlb3PyBgQKAjoA"
INNERTUBE_VERSION = "2.20261014.00.00"

YT_CHANNEL_NAME   = "Play Together VNG"
YT_CHANNEL_URL    = "https://www.youtube.com/@PlayTogetherVNGofficial/videos"
YT_CHANNEL_AVATAR = os.getenv("YT_CHANNEL_AVATAR", "").strip()

# Overlay badge trong UI card InnerTube -> KHONG phai title that. _looks_title bo sung
#   chuoi nay; _best_title gom candidates va cat duration suffix truoc khi so do dai.
BANNED_TITLE_OVERLAYS = {"đang phát", "phát trực tiếp", "live", "xem tiếp", "mới", "hot"}

# Thu tu xu ly ung vien OCR: newest-first = dao nguoc list bare de video giftcode-moi
#   lot vao slot OCR thay vi bi trailer/live-cu chim het (sua "giu pending hieu nhieu").
BARE_ORDER = os.getenv("BARE_ORDER", "newest-first").strip().lower()

# Khi title tu InnerTube/DataAPI rong/bi banned -> goi oEmbed (schema co dinh). De 0 =
#   tat hoan toan, chi dung title da parse; van rong -> webhook in "[Xem video](url)" thuan.
OCR_USE_OEMBED = os.getenv("OCR_USE_OEMBED", "1").strip() != "0"

# ================= NEO TRICH MA (mot regex dung chung title/desc/OCR) =================
KEYWORD_PATTERN = r"C[OÔ][\s.:|_-]*D[EÉ]"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]
CODE_MIN_LEN  = 6

# ================= OCR: CHUOI GEMINI (uu tien, quay khi 5xx) > EASYOCR > TESSERACT =================
# GEMINI_MODEL_CHAIN = uu tien, KHONG phai slug that. ocr.py GET /v1beta/models cua CHINH KEY
#   va chi giu ten NAM TRONG list -> ten khong co bi BO + log (khong doan mu, khong 404 lap).
#   GEMINI_MODEL (neu dat) duoc PREPEND de ghi de tam. Doi thu tu/them ten = sua env, khong code.
# TRAN GOI: GEMINI_MAX_CALLS = tran MỖI VÒNG LẶP (reset_gemini_budget() goi tu main.py dau
#   moi vong). Truoc day tich luy per-process -> dead_key ca run -> EasyOCR lanh -> doc sai
#   pill. Nay het tran = PENDING MEM (video chua xet giu cho vong sau), KHONG dead_key.
#   dead_key chi do 402/403/429. KHONG CON soft-cap (_GEMINI_OK_COUNT per-run tung lam Gemini
#   tu giet minh sau 10 video dau -> da xoa het; quy tac: bien dem rate-limit phai reset cung
#   chu ky voi ngan sach no bao ve).
# NHIEP 5xx: CA chuoi 5xx -> "local tham do" (chi duong tinh, am tinh = pending) + cho
#   GEMINI_BUSY_BACKOFF_SEC roi Gemini quay lai. 5xx KHONG tinh tien (pricing: chi 200 moi
#   tinh) -> chi la chong spam, khong phai chong phi.
# LOCAL_WHEN: "fallback-only" (MAC DINH) = EasyOCR/Tesseract CHI chay khi Gemini THAT SU
#   khong dung duoc (busy_all/budget/dead_key/no-model/no-key). Mot lan Gemini loi mang
#   ("net") KHONG kich hoat local -> video do pending cho vong sau retry Gemini. "probe" =
#   giu hanh vi cu (local tham do ca khi net).
# OCR_ENGINE: auto = chuoi gemini (neu key co + co it nhat 1 ten trong list) > easy > tess.
OCR_MODE        = os.getenv("OCR_MODE", "auto").strip().lower()
OCR_ENGINE      = os.getenv("OCR_ENGINE", "auto").strip().lower()
LOCAL_WHEN      = os.getenv("LOCAL_WHEN", "fallback-only").strip().lower()
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL    = (os.getenv("GEMINI_MODEL") or "").strip()
GEMINI_MODEL_CHAIN = [s.strip() for s in
                      (os.getenv("GEMINI_MODEL_CHAIN")
                       or "gemini-3.8-flash,gemini-3.6-flash,gemini-3.5-flash-lite").split(",")
                      if s.strip()]
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_TIMEOUT  = int(os.getenv("GEMINI_TIMEOUT", "45"))
GEMINI_MAX_CALLS = int(os.getenv("GEMINI_MAX_CALLS", "8"))            # tran/goi-per-LOOP
GEMINI_BUSY_BACKOFF_SEC = float(os.getenv("GEMINI_BUSY_BACKOFF_SEC", "300"))
GEMINI_THROTTLE_SEC = float(os.getenv("GEMINI_THROTTLE_SEC", "2.5"))
# PRODUCTION: toi da 3 video PASS-GATE (anh CO chu CODE) duoc OCR sau moi vong. Gate fail
#   (live/trailer/khong chu CODE) KHONG tinh vao day -> 3 slot dun cho video ma-trong-anh.
OCR_MAX_IMAGES  = int(os.getenv("OCR_MAX_IMAGES", "3"))
OCR_MAX_TRIES   = int(os.getenv("OCR_MAX_TRIES", "50"))
OCR_LOOP_BUDGET = int(os.getenv("OCR_LOOP_BUDGET", "180"))
OCR_ALERT_CAP   = int(os.getenv("OCR_ALERT_CAP", "6"))
OCR_ALERT_TTL   = 21600
OCR_PING_USER   = (os.getenv("OCR_PING_USER", "").strip() or "1160199218313564210")

# ================= BROWSER FALLBACK (chi khi USE_API=0) =================
LOCALE = ("vi-VN", "Asia/Ho_Chi_Minh")
STORAGE_STATE = None
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
