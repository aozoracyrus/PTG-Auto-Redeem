# TOAN BO CAU HINH. Comment = tieng Viet co dau; phan MAY DOC = ASCII nguyen van.
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
BTN_REDEEM = re.compile(r"Nhp\\s*code|Redeem", re.I)
BTN_REDEEM_ALTS = [re.compile(r"Nhp\\s*code|Nhp Code|nhp code|nhp m|Redeem", re.I),
                   re.compile(r"Gui|Submit", re.I)]
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"
SRV_PH = ["May chu", "Chon may chu", "Server"]
SRV_OPT_RE = re.compile(r"Server\\s*2|May chu\\s*2", re.I)

# ================= TABLE TEXT = CHUOI KHOP MESSAGE SERVER (KHONG DICH) =================
TRANSIENT       = ["da co loi xay ra", "thu lai sau it phut", "khong tim thay du lieu yeu cau",
                   "khong the tai thong tin game", "vui long thu lai sau"]
NEED_LOGIN      = ["chua lien ket tai khoan game", "lien ket tai khoan roi thu lai"]
FAIL_USAGE      = ["het luot nhap", "da dat den gioi han su dung", "gioi han su dung",
                   "vuot qua so lan nhap", "usage limit", "active code"]
FAIL_NOTEXIST   = ["nhan qua khong thanh cong", "kiem tra lai ma", "inbox fanpage",
                   "khong ton tai", "vui long kiem tra lai", "code not found"]
FAIL_IDERROR    = ["khong tim thay nhan vat", "nhan vat dang offline", "nhap lai id"]
FAIL_VALIDATION = ["thong tin nhap khong hop le", "data invalid"]
FAIL_SECTION    = ["that bai"]
CAPTCHA_HINTS   = ["captcha", "ma xac thuc"]

REDEEM_POLL_TIMEOUT = 20.0
REDEEM_POLL_STEP    = 1.5
ID_RE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}\b")

# ================= YOUTUBE =================
YT_CHANNEL_ID = "UCnLyxhAWS7yakzX8aWO6PKQ"
YT_UPLOADS_ID = "UU" + YT_CHANNEL_ID[2:]
YT_VIDEO_SCAN = 15          # TAM test OCR; ve 3 sau khi thay Gemini doc DUNG ma trong anh
# SUA LOI A: ocr.py _alert doc C.YT_COOLDOWN; truoc day chi ton tai trong main.py ->
#   AttributeError -> crash giua _alert -> candidate doc duong bi bo, khong nhap. Nay o day.
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

# Overlay badge pho bien trong UI card InnerTube -> KHONG phai title that cua video.
# _looks_title (youtube_watcher) tuoi chuoi nay; ocr._resolve_title coi no = khong co title
# -> goi oEmbed (schema co dinh, KHONG phai doan InnerTube nhu lan skipped_live=0).
BANNED_TITLE_OVERLAYS = {"đang phát", "phát trực tiếp", "live", "xem tiếp", "mới", "hot"}

# ================= NEO TRICH MA (mot regex dung chung title/desc/OCR) =================
KEYWORD_PATTERN = r"C[OÔ][\s.:|_-]*D[EÉ]"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]
CODE_MIN_LEN  = 6

# ================= OCR: CHUOI GEMINI (uu tien, quay khi 5xx) > EASYOCR > TESSERACT =================
# GEMINI_MODEL_CHAIN = uu tien, KHONG phai slug that. ocr.py GET /v1beta/models cua CHINH KEY
#   va chi giu ten NAM TRONG list -> ten khong co bi BO + log (khong doan mu, khong 404 lap).
#   GEMINI_MODEL (neu dat) duoc PREPEND de ghi de tam. Doi thu tu/them ten = sua env, khong code.
# TRAN GOI (sua loi B): GEMINI_MAX_CALLS = tran MỖI VÒNG LẶP (reset_gemini_budget() goi tu
#   main.py dau moi vong). Truoc day no tich luy per-process -> 26 video gate/vong dot het
#   tran trong 1.5 vong -> dead_key ca run -> EasyOCR lanh -> doc sai pill cach dieu. Nay het
#   tran = PENDING MEM (video chua xet giu cho vong sau), KHONG dead_key. dead_key chi do 402/403/429.
# NHIEP 5xx: CA chuoi 5xx -> "local tham do" (chi duong tinh, am tinh = pending) + cho
#   GEMINI_BUSY_BACKOFF_SEC roi Gemini quay lai. KHONG idel, KHONG mat ma, KHONG ping oan.
# LOCAL_WHEN (sua bug "local spam anh + lan chiem Gemini dang song"):
#   "fallback-only" (MAC DINH) = EasyOCR/Tesseract CHI chay khi Gemini THAT SU khong dung
#     duoc (busy_all/budget/dead_key/no-model/no-key). Mot lan Gemini loi mang/safety ("net")
#     KHONG kich hoat local -> video do pending cho vong sau retry Gemini.
#   "probe" = giu hanh vi cu: local tham do ca khi net (am tinh van pending, nhung van dot
#     recipe). Chi bat khi ban MUON local an nhanh video chu-thuong trong cua so busy, chap
#     nhan some-noise.
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
OCR_MAX_IMAGES  = int(os.getenv("OCR_MAX_IMAGES", "8"))               # TAM test; ve 3 sau khi OK
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
