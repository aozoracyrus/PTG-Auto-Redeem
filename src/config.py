# TOÀN BỘ CẤU HÌNH. Comment = tiếng Việt có dấu.
import os, re

URL_VN = "https://giftcode.vnggames.com/vn/redeem/ptg"

# ================= API REDEEM (bằng chứng F12) =================
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

# ================= BẢNG MÃ SỐ JSON (không phụ thuộc ngôn ngữ) =================
NUM_SUCCESS    = {1}

# 2117/2121: BẰNG CHỨNG RUNTIME 05/11/2026 (bạn quay) trả "Active code: usage limit"
#   = code HẾT LƯỢT TOÀN CỤC (đăng 5h trước, người ta nhập như điên), KHÔNG phải
#   "ID này đã nhận". Nên MẶC ĐỊNH là usage-limit (đỏ + blacklist code), trừ khi
#   message nói rõ "đã nhận/đã redeem bởi ID này" (khi đó mới là already-self, xanh).
#   already-self giờ suy từ ALREADY_SELF_TEXT, không từ mã số -> NUM_ALREADY để trống.
NUM_ALREADY    = set()
NUM_USAGE_LIMIT = {2117, 2121}          # mặc định = hết lượt toàn cục (đỏ + blacklist)
NUM_CODE_BAD   = {2106, 2102}
NUM_ID_ERROR   = {2105}
NUM_NEED_LOGIN = {2101}
NUM_TRANSIENT  = {1000, 1001, 2103}
NUM_VALIDATION = {1002}
HTTP_STUCK = {403, 404, 408, 425, 429, 500, 501, 502, 503, 504}

# ================= MATCHER UI (chỉ khi USE_API=0) =================
PH_CODE = ["Nhập thông tin code", "Nhập mã giftcode"]
PH_ID   = ["Chọn nhân vật / Nhập ID nhân vật", "Nhập ID nhân vật"]
BTN_REDEEM = re.compile(r"Nhập\s*code|Redeem", re.I)
BTN_REDEEM_ALTS = [re.compile(r"Nhập\s*code|Nhập Code|nhập code|nhập mã|Redeem", re.I),
                   re.compile(r"Gửi|Submit", re.I)]
RATIO_FAIL = "0/1"
RATIO_OK   = "1/1"
SRV_PH = ["Máy chủ", "Chọn máy chủ", "Server"]
SRV_OPT_RE = re.compile(r"Server\s*2|Máy chủ\s*2", re.I)

# ================= BẢNG TEXT = CHUỖI KHỚP MESSAGE SERVER (KHÔNG DỊCH) =================
TRANSIENT       = ["đã có lỗi xảy ra", "thử lại sau ít phút", "không tìm thấy dữ liệu yêu cầu",
                   "không thể tải thông tin game", "vui lòng thử lại sau"]
NEED_LOGIN      = ["chưa liên kết tài khoản game", "liên kết tài khoản rồi thử lại"]

# USAGE-LIMIT TOÀN CỤC -> EMBED ĐỎ + BLACKLIST CODE (mọi ID kế bỏ qua).
#   Khớp "Active code: usage limit" (bằng chứng runtime) và các biến thể hết lượt.
USAGE_LIMIT_TEXT = ["usage limit", "hết lượt nhập", "đã đạt đến giới hạn sử dụng",
                    "giới hạn sử dụng", "vượt quá số lần nhập", "quantity exhausted",
                    "user code management quantity exhausted", "active code"]
# ALREADY-SELF (ID NÀY ĐÃ NHẬN, code còn hạn cho người khác) -> EMBED XANH + ĐÓNG CẶP.
#   KHÔNG blacklist code (code còn sống, chỉ riêng ID này hết).
ALREADY_SELF_TEXT = ["đã redeem", "đã nhận", "already redeemed", "already claimed"]

# Giữ 2 list cũ cho browser-fallback matcher (redeemer.py) nếu còn tham chiếu.
FAIL_ALREADY    = ALREADY_SELF_TEXT + USAGE_LIMIT_TEXT   # tương thích ngược
FAIL_USAGE      = USAGE_LIMIT_TEXT                        # tương thích ngược
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
YT_VIDEO_SCAN = 3
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
YT_CHANNEL_POSTS  = "https://www.youtube.com/@PlayTogetherVNGofficial/posts"
YT_CHANNEL_AVATAR = os.getenv("YT_CHANNEL_AVATAR", "").strip()

BANNED_TITLE_OVERLAYS = {"đang phát", "phát trực tiếp", "live", "xem tiếp", "mới", "hot"}
BARE_ORDER = os.getenv("BARE_ORDER", "newest-first").strip().lower()
OCR_USE_OEMBED = os.getenv("OCR_USE_OEMBED", "1").strip() != "0"

# ================= COMMUNITY POSTS (tab /posts) =================
# BẰNG CHỨNG SCHEMA THẬT (F12, tab renderer + backstagePostRenderer):
#   - tab "Bài đăng" browseEndpoint params = "EgVwb3N0c_IGBAoCSgA%3D" (=%3D -> '=').
#   - post = sectionListRenderer>itemSectionRenderer>backstagePostThreadRenderer>post>
#       backstagePostRenderer{ postId, contentText.runs[].text (chứa "MÃ CODE: <MÃ>"),
#       backstageAttachment.backstageImageRenderer.image.thumbnails[] (ảnh post 1600x1600),
#       command.browseEndpoint.canonicalBaseUrl = "/post/<postId>" }.
# -> 3 đường lấy code post (hedged, đường nào có bằng chứng trước):
#   (1) STRUCT: document GET /posts -> tách ytInitialData -> _walk_posts đọc đúng
#       backstagePostRenderer (lấy cả text-code + ảnh-post + link-thẳng postId).
#   (2) FLAT: giải mã \\uXXXX cả HTML, chạy thẳng regex "MÃ CODE" (lưới khi blob/backstage
#       đổi key; chỉ ra entries text, không ra ảnh/link).
#   (3) BROWSE FALLBACK: nếu document GET bị consent wall (http!=200 / không có
#       ytInitialData) -> POST /browse với INNERTUBE_PARAMS_POSTS (params THẬT ở trên).
# Dedupe: video entries đi TRƯỚC post -> post trùng code video skip. Post text-code ->
#   entries (không tốn OCR). Post CHỈ có ảnh mà text KHÔNG ra code -> BỎ QUA (không OCR
#   ảnh post, tránh lỗi "Mã LIVESTREAM" từ ảnh teaser). Hai chiều -> chỉ nhập 1 LẦN.
YT_POSTS      = os.getenv("YT_POSTS", "1").strip() != "0"
YT_POSTS_MAX  = int(os.getenv("YT_POSTS_MAX", "5"))
INNERTUBE_PARAMS_POSTS = [s.strip() for s in
                          (os.getenv("INNERTUBE_PARAMS_POSTS")
                           or "EgVwb3N0c_IGBAoCSgA=,EgVwb3N0c_IGBAoCSgA%3D").split(",")
                          if s.strip()]
# Cookie (tuỳ) cho document GET /posts. MẶC ĐỊNH RỖNG. Chỉ đặt khi log FLOUD báo consent wall:
#   F12 -> Application -> Cookies -> copy VISITOR_INFO1_LIVE + __Secure-ROLLOUT_TOKEN.
YT_POSTS_COOKIE = os.getenv("YT_POSTS_COOKIE", "").strip()
YT_POST_LINK = "https://www.youtube.com/post/"   # + postId (bằng chứng canonicalBaseUrl)

# ================= NEO TRÍCH MÃ (một regex dùng chung title/desc/OCR) =================
KEYWORD_PATTERN = r"C[OÔ][\s.:|_-]*D[EÉ]"
YT_KEYWORD_RE   = re.compile(KEYWORD_PATTERN, re.I)
CODE_PREFIXES = ["PT"]
CODE_MIN_LEN  = 6

# ================= OCR: CHUỖI GEMINI (ưu tiên, quay khi 5xx) > EASYOCR > TESSERACT =================
# GEMINI_MODEL_CHAIN = ưu tiên, KHÔNG phải slug thật. ocr.py GET /v1beta/models của CHÍNH KEY
#   và chỉ giữ tên NẰM TRONG list -> tên không có bị BỎ + log (không đoán mù, không 404 lặp).
#   GEMINI_MODEL (nếu đặt) được PREPEND để ghi đè tạm. Đổi thứ tự/thêm tên = sửa env, không code.
# TRẦN GỌI: GEMINI_MAX_CALLS = trần MỖI VÒNG LẶP (reset_gemini_budget() gọi từ main.py đầu
#   mỗi vòng). Hết trần = PENDING MEM, KHÔNG dead_key. dead_key chỉ do 402/403/429.
# NHIỆP 5xx: CẢ chuỗi 5xx -> "local thăm dò" (chỉ dương tính, âm tính = pending) + chờ
#   GEMINI_BUSY_BACKOFF_SEC rồi Gemini quay lại. 5xx KHÔNG tính tiền (pricing: chỉ 200 mới
#   tính) -> chỉ là chống spam, không phải chống phí.
# LOCAL_WHEN: "fallback-only" (MẶC ĐỊNH) = EasyOCR/Tesseract CHỈ chạy khi Gemini THẬT SỰ
#   không dùng được. Một lần Gemini lỗi mạng ("net") KHÔNG kích hoạt local.
# OCR_ENGINE: auto = chuỗi gemini (nếu key có + có ít nhất 1 tên trong list) > easy > tess.
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
GEMINI_MAX_CALLS = int(os.getenv("GEMINI_MAX_CALLS", "8"))
GEMINI_BUSY_BACKOFF_SEC = float(os.getenv("GEMINI_BUSY_BACKOFF_SEC", "300"))
GEMINI_THROTTLE_SEC = float(os.getenv("GEMINI_THROTTLE_SEC", "2.5"))
OCR_MAX_IMAGES  = int(os.getenv("OCR_MAX_IMAGES", "3"))
OCR_MAX_TRIES   = int(os.getenv("OCR_MAX_TRIES", "50"))
OCR_LOOP_BUDGET = int(os.getenv("OCR_LOOP_BUDGET", "180"))
OCR_ALERT_CAP   = int(os.getenv("OCR_ALERT_CAP", "6"))
OCR_ALERT_TTL   = 21600
OCR_PING_USER   = (os.getenv("OCR_PING_USER", "").strip() or "1160199218313564210")

# ================= BROWSER FALLBACK (chỉ khi USE_API=0) =================
LOCALE = ("vi-VN", "Asia/Ho_Chi_Minh")
STORAGE_STATE = None
MOBILE_VIEWPORT = {"width": 390, "height": 844}
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
