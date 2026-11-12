# OCR THUMBNAIL + VÒNG TỰ SỬA CÓ TRÍ NHỚ.
# 2117/2121 = USAGE-LIMIT TOÀN CỤC: embed ĐỎ + BLACKLIST code qua "|__DEAD__" -> _try_code
#   DỪNG ngay ID đầu gặp usage_limit, không thử ID khác. already-self vẫn XANH + đóng cặp.
# KIẾN TRÚC OCR = SEMANTIC + REGEX (hedged, bằng chứng 4 ảnh F12):
#   Cùng 1 LẦN GỌI Gemini: prompt trả JSON {"all_text":..., "redeem_code":...}.
#   all_text -> gate keyword + lưới regex. redeem_code -> SEMANTIC weight 10 (thắng regex).
#   Vẫn chạy _valid_code (form PT+>=6); mã PT-bịa do server 2106 + OCR_MAX_TRIES + ping đỡ.
#   Fail-soft: không parse được JSON -> coi cả response là all_text, regex vẫn chạy.
#   Im-lặng-teaser: model chủ định trả null VÀ cả hai lưới rỗng -> done="no_code", KHÔNG ping.
# DEADLINE: mọi vòng (video / candidate / ID) kiểm tra C.out_of_time() -> không tràn timeout job.
import os, io, re, time, json, base64, requests
from collections import Counter
from . import config as C
from .parsers import code_from_ocr_text
from .utils import log_yt, log_warn, log_hook, sleep, rand_ms
from .state import commit_paths
from .webhook import send, msg_success, msg_failure, msg_yt_alert, msg_ocr_fail, msg_already, msg_usage_limit
from .api_redeemer import redeem_via_api

DMIN = int(os.getenv("DELAY_MIN", "15000"))
DMAX = int(os.getenv("DELAY_MAX", "30000"))

MEM = lambda: os.path.join(os.getcwd(), "ocr_memory.json")
_BYTES = {}
_GATE_RECIPES = 2
DEAD_SUFFIX = "|__DEAD__"

# --- state Gemini per-PROCESS (= per-run) ---
_READER = None
_READER_FAILED = False
_GEMINI_LIST = None
_GEMINI_LIST_OK = False
_GEMINI_CHAIN = []
_GEMINI_CHAIN_BUILT = False
_GEMINI_DROPPED = []
_GEMINI_5XX = set()
_GEMINI_DEAD_MODEL = set()
_GEMINI_DEAD_KEY = False
_GEMINI_DEGRADED_UNTIL = 0.0
# --- ngân sách per-LOOP ---
_GEMINI_LOOP_BUDGET = 0
_GEMINI_LOOP_EXHAUSTED = False

RECIPES = [
    (2, "gray"), (2, "inv"), (3, "gray"), (3, "inv"),
    (2, "bin"), (3, "bin"), (4, "gray"), (4, "inv"),
    (2, "sharp"), (3, "sharp"), (4, "bin"), (5, "gray"),
]

_GEMINI_PROMPT = (
    "Bạn là bộ phận trích MÃ REDEEM từ ảnh thumbnail game Play Together (VNG). "
    "Ảnh có thể là: (A) MỘT thông báo sự kiện/teaser KHÔNG chứa mã (chỉ có chữ như 'CODE', "
    "'LIVESTREAM', 'BẬT MÍ CODE', 'CÔ DÉ CHUNG', tên sự kiện, ngày tháng...), hoặc "
    "(B) CÓ chứa MÃ REDEEM thật (chuỗi viết hoa, không dấu, thường bắt đầu 'PT', nằm sau cụm "
    "'CODE'/'MÃ CODE' hoặc trong khung nổi bật). "
    "TRẢ VỀ DUY NHẤT MỘT object JSON hợp lệ, không markdown, không văn bản ngoài JSON: "
    '{"all_text": "<mọi chữ NHÌN THẤY trong ảnh, giữ nguyên dấu tiếng Việt, nối cách bằng space>", '
    '"redeem_code": "<MÃ REDEEM thật nếu thấy rõ, viết hoa không dấu>"} hoặc '
    '{"all_text": "...", "redeem_code": null}. '
    "Quy tắc bắt buộc cho redeem_code: "
    "(1) Chỉ lấy chuỗi mà THỰC SỰ nhìn thấy trong ảnh; TUYỆT ĐỐI không bịa, không suy đoán, "
    "không 'đoán' mã từ tên sự kiện. "
    "(2) Nếu ảnh chỉ là teaser/thông báo sự kiện MÀ KHÔNG có chuỗi mã nào -> redeem_code = null. "
    "(3) KHÔNG lấy các từ như LIVESTREAM, HALLOWEEN, CODE, CHUNG, RIÊNG, MỚI, TẶNG, THÁNG, "
    "tên nhân vật, hashtag (#...) làm mã. "
    "(4) Mã thật thường: viết hoa, không dấu, >= 6 ký tự, đa phần bắt đầu 'PT'. "
    "VÍ DỤ (học theo): ảnh 'ĐÊM HỘI HALLOWEEN / BẬT MÍ / CODE / LIVESTREAM' -> "
    'redeem_code = null. ảnh "CÔ DÉ CHUNG / THÁNG 11 / PTHELLOAUTUMN" -> '
    'redeem_code = "PTHELLOAUTUMN".'
)


# ================= HẬU KIỂM MÃ (lưới form, vẫn dùng sau semantic) =================
def _valid_code(c):
    """Chỉ chấp nhận token dạng MÃ THẬT về FORM: prefix PT + >= CODE_MIN_LEN + ASCII chữ/số.
       Chặn 'LIVESTREAM','CHUNG'... KHÔNG chống được mã PT-bịa (server 2106 đỡ tầng dưới)."""
    c = (c or "").strip().upper()
    if len(c) < C.CODE_MIN_LEN:
        return False
    if not c.startswith(tuple(C.CODE_PREFIXES)):
        return False
    return bool(re.fullmatch(r"[A-Z0-9]+", c))


# ================= LƯỚI REGEX (dự phòng cho đường LOCAL khi Gemini chết) =================
_KW_SUFFIX_WORDS = r"(?:\s+(?:CHUNG|RIÊNG|RIENG|MỚI|MOI|TẶNG|TANG|LIVE|NEW))*"
_OCR_CODE_FALLBACK_RE = re.compile(
    r"C[OÔ][\s.:|_-]*D[EÉ]" + _KW_SUFFIX_WORDS + r"\s+([A-Z0-9]{6,})", re.I)


def _codes_fallback(txt):
    """Lưới regex: cho phép 0-3 từ nối chen giữa keyword và mã. Chỉ trả token qua _valid_code."""
    out = []
    for m in _OCR_CODE_FALLBACK_RE.finditer(txt or ""):
        tok = m.group(1).upper()
        if _valid_code(tok):
            out.append(tok)
    return out


def reset_gemini_budget():
    global _GEMINI_LOOP_BUDGET, _GEMINI_LOOP_EXHAUSTED
    _GEMINI_LOOP_BUDGET = C.GEMINI_MAX_CALLS
    _GEMINI_LOOP_EXHAUSTED = False


def _gemini_load_models():
    global _GEMINI_LIST, _GEMINI_LIST_OK
    if _GEMINI_LIST is not None:
        return _GEMINI_LIST
    _GEMINI_LIST = []
    if not C.GEMINI_API_KEY:
        _GEMINI_LIST_OK = False
        return _GEMINI_LIST
    try:
        r = requests.get(C.GEMINI_ENDPOINT,
                         params={"key": C.GEMINI_API_KEY, "pageSize": 200}, timeout=20)
    except Exception as e:
        log_warn("Gemini list lỗi mạng:", e.__class__.__name__)
        _GEMINI_LIST_OK = False
        return _GEMINI_LIST
    if r.status_code != 200:
        log_warn("Gemini list http", r.status_code, "->", (r.text or "")[:200])
        _GEMINI_LIST_OK = False
        return _GEMINI_LIST
    try:
        j = r.json()
    except Exception:
        log_warn("Gemini list không phải JSON")
        _GEMINI_LIST_OK = False
        return _GEMINI_LIST
    ids = []
    for m in (j.get("models") or []):
        nm = m.get("name") or ""
        bare = nm.split("/")[-1].strip()
        methods = m.get("supportedGenerationMethods") or []
        if bare and "generateContent" in methods:
            ids.append(bare)
    _GEMINI_LIST = ids
    _GEMINI_LIST_OK = True
    return ids


def _gemini_build_chain():
    global _GEMINI_CHAIN, _GEMINI_CHAIN_BUILT, _GEMINI_DROPPED
    if _GEMINI_CHAIN_BUILT:
        return
    _GEMINI_CHAIN_BUILT = True
    _GEMINI_CHAIN = []
    _GEMINI_DROPPED = []
    if not C.GEMINI_API_KEY:
        return
    prefs = []
    if C.GEMINI_MODEL:
        prefs.append(C.GEMINI_MODEL.split("/")[-1].strip())
    for s in C.GEMINI_MODEL_CHAIN:
        b = s.split("/")[-1].strip()
        if b and b not in prefs:
            prefs.append(b)
    ids = _gemini_load_models()
    if not _GEMINI_LIST_OK:
        log_warn("OCR gemini: không lấy được list model -> bỏ qua chuỗi (KHÔNG đoán slug). -> local auth.")
        return
    idset = set(ids)
    for p in prefs:
        if p in idset:
            _GEMINI_CHAIN.append(p)
        else:
            _GEMINI_DROPPED.append(p)
    if _GEMINI_CHAIN:
        log_yt("OCR gemini chuỗi (đã validate qua list key): " + " > ".join(_GEMINI_CHAIN)
               + (f" | bỏ (không có với key): {', '.join(_GEMINI_DROPPED)}" if _GEMINI_DROPPED else ""))
    else:
        log_warn("OCR gemini: KHÔNG tên nào trong chuỗi tồn tại với key này. "
                 f"List hợp lệ: {', '.join(ids[:15])} -> local auth. "
                 "(Đặt GEMINI_MODEL_CHAIN = id thật trong list để bật gemini.)")


def _gemini_busy_window_active():
    return time.monotonic() < _GEMINI_DEGRADED_UNTIL


def _current_gemini_model():
    global _GEMINI_DEGRADED_UNTIL
    if not C.GEMINI_API_KEY:
        return None, "no_key"
    _gemini_build_chain()
    if _GEMINI_DEAD_KEY:
        return None, "dead_key"
    if not _GEMINI_CHAIN:
        return None, "no_model"
    if _GEMINI_LOOP_BUDGET <= 0:
        _GEMINI_LOOP_EXHAUSTED = True
        return None, "budget"
    excluded = _GEMINI_5XX | _GEMINI_DEAD_MODEL
    for m in _GEMINI_CHAIN:
        if m not in excluded:
            return m, "ok"
    if _GEMINI_5XX:
        if _GEMINI_DEGRADED_UNTIL <= time.monotonic():
            _GEMINI_DEGRADED_UNTIL = time.monotonic() + C.GEMINI_BUSY_BACKOFF_SEC
            log_warn(f"OCR gemini: CẢ chuỗi 5xx (đông) -> chờ {int(C.GEMINI_BUSY_BACKOFF_SEC)}s; "
                     f"trong lúc đó dùng EasyOCR THEO CHẾ ĐỘ THĂM DÒ (chỉ dương tính, âm tính giữ pending).")
        return None, "busy_all"
    return None, "dead_key"


def _gemini_call(png_bytes, rec):
    global _GEMINI_LOOP_BUDGET, _GEMINI_DEAD_KEY
    while True:
        model, status = _current_gemini_model()
        if status != "ok":
            return None, status
        _GEMINI_LOOP_BUDGET -= 1
        b64 = base64.b64encode(png_bytes).decode("ascii")
        body = {"contents": [{"parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": _GEMINI_PROMPT},
        ]}]}
        url = f"{C.GEMINI_ENDPOINT}/{model}:generateContent"
        try:
            r = requests.post(url, json=body, params={"key": C.GEMINI_API_KEY},
                              timeout=C.GEMINI_TIMEOUT)
        except Exception as e:
            log_warn("Gemini lỗi mạng (cục bộ):", e.__class__.__name__)
            return None, "net"
        sc = r.status_code
        if sc == 200:
            try:
                j = r.json()
            except Exception:
                log_warn("Gemini không phải JSON (cục bộ)")
                return None, "net"
            cands = j.get("candidates") or []
            if not cands:
                log_warn("Gemini không trả candidate (safety/rỗng) -> coi như cục bộ")
                return None, "net"
            parts = (cands[0].get("content") or {}).get("parts") or []
            txt = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            rec["gemini_model"] = model
            sleep(C.GEMINI_THROTTLE_SEC)
            return ([txt] if txt else []), "ok"
        if sc in (500, 502, 503, 504):
            _GEMINI_5XX.add(model)
            log_warn(f"Gemini {model} {sc} (đông) -> bay khỏi chuỗi tạm thời, thử model kế tiếp.")
            sleep(1.5)
            continue
        if sc == 404:
            _GEMINI_DEAD_MODEL.add(model)
            log_warn(f"Gemini {model} 404 (slug không gọi được) -> bỏ, thử model kế tiếp.")
            continue
        if sc in (402, 403):
            _GEMINI_DEAD_KEY = True
            log_warn(f"Gemini {sc}: CÓ THỂ do phí/quyền/region -> KIỂM TRA AI Studio. "
                     f"Dừng gemini cả run -> local auth.")
            return None, "dead_key"
        if sc == 429:
            _GEMINI_DEAD_KEY = True
            log_warn("Gemini 429: chạm quota/rate (free-tier hết lượt?) -> dừng gemini cả run -> local auth.")
            return None, "dead_key"
        log_warn("Gemini http", sc, "->", (r.text or "")[:200])
        _GEMINI_DEAD_MODEL.add(model)
        continue


# ================= PARSE JSON SEMANTIC (fail-soft) =================
def _gemini_parse_answer(txt):
    """Bóc JSON {all_text, redeem_code}. Chịu cả markdown fence.
       Trả (all_text, redeem_code|None, parsed_ok). parsed_ok=False -> fail-soft về regex."""
    s = (txt or "").strip()
    if not s:
        return "", None, False
    if s.startswith("```"):
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        s = s.strip()
    st, en = s.find("{"), s.rfind("}")
    if st == -1 or en == -1 or en <= st:
        return (txt or ""), None, False
    try:
        obj = json.loads(s[st:en + 1])
    except Exception:
        return (txt or ""), None, False
    if not isinstance(obj, dict):
        return (txt or ""), None, False
    all_text = str(obj.get("all_text", "") or "")
    rc = obj.get("redeem_code", None)
    code = None if rc is None else (str(rc).strip().upper() or None)
    if not all_text and code:
        all_text = code
    return all_text, code, True


def _absorb_gemini(rec, all_text, sem_code):
    """Semantic weight 10 (thắng khi cả hai cùng ra); regex weight 1 (lưới)."""
    if all_text and all_text.strip():
        rec["raw"] = (rec["raw"] + " | " + all_text.strip().replace("\n", " "))[:900]
    hit = False
    if sem_code and _valid_code(sem_code):
        rec["reads"][sem_code] = rec["reads"].get(sem_code, 0) + 10
        hit = True
    for c in code_from_ocr_text(all_text or ""):
        if not _valid_code(c):
            continue
        rec["reads"][c] = rec["reads"].get(c, 0) + 1
    for c in _codes_fallback(all_text or ""):
        rec["reads"][c] = rec["reads"].get(c, 0) + 1
    if hit:
        rec["sem_hit"] = True
    return hit


def _gemini_pass(rec):
    if rec.get("gemini_done"):
        return
    if _GEMINI_DEAD_KEY or not C.GEMINI_API_KEY:
        return
    b = _fetch_bytes(rec["thumb"])
    if not b:
        return
    try:
        from PIL import Image
        pil = Image.open(io.BytesIO(b)).convert("RGB")
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        png = buf.getvalue()
    except Exception as e:
        log_warn("Gemini: không đọc được ảnh gốc:", e.__class__.__name__)
        return
    texts, status = _gemini_call(png, rec)
    if status != "ok" or texts is None:
        return
    rec["gemini_done"] = True
    for txt in texts:
        all_text, sem_code, parsed_ok = _gemini_parse_answer(txt)
        _absorb_gemini(rec, all_text, sem_code)
        if parsed_ok and sem_code is None:
            rec["sem_declared_none"] = True


def _easy_reader():
    global _READER, _READER_FAILED
    if _READER is not None:
        return _READER
    if _READER_FAILED or C.OCR_ENGINE == "tess":
        return None
    try:
        import easyocr
        _READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        log_yt("EasyOCR sẵn sàng (fallback local)")
    except Exception as e:
        _READER_FAILED = True
        log_warn("EasyOCR không khả dụng -> tesseract:", e.__class__.__name__)
        _READER = None
    return _READER


def _ocr_texts_local(img):
    r = _easy_reader()
    if r is not None:
        try:
            import numpy as np
            arr = np.array(img.convert("RGB"))
            parts = r.readtext(arr, detail=0, paragraph=False) or []
            return [" ".join(str(p) for p in parts)]
        except Exception as e:
            log_warn("EasyOCR lỗi ảnh này -> tesseract:", e.__class__.__name__)
    out = []
    for psm in (6, 11):
        try:
            import pytesseract
            t = pytesseract.image_to_string(img, config=f"--psm {psm} -l eng") or ""
        except Exception:
            t = ""
        if t.strip():
            out.append(t)
    return out


def load_mem():
    fp = MEM()
    if not os.path.exists(fp):
        return {}
    try:
        return json.load(open(fp, encoding="utf-8"))
    except Exception as e:
        log_warn("ocr_memory hỏng -> bắt đầu lại:", e)
        return {}


def save_mem(mem):
    json.dump(mem, open(MEM(), "w", encoding="utf-8"), indent=0, ensure_ascii=False)


def commit_mem(mem):
    save_mem(mem)
    commit_paths(["ocr_memory.json"], f"chore(ocr-memory): {len(mem)} video")


def _new_rec(v):
    return {"video_id": v["video_id"], "thumb": v["thumb_url"], "title": v.get("title", ""),
            "video_url": v.get("video_url", ""), "recipes_used": [], "reads": {},
            "raw": "", "tried": [], "tries": 0, "alerts": 0, "done": None, "pinged": False,
            "gemini_done": False, "pending_since": None, "gemini_model": "",
            "sem_hit": False, "sem_declared_none": False}


def _fetch_bytes(url):
    if url in _BYTES:
        return _BYTES[url]
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        b = r.content if r.status_code == 200 else b""
    except Exception:
        b = b""
    _BYTES[url] = b
    return b


def _apply_recipe(pil, up, kind):
    from PIL import Image, ImageOps, ImageEnhance
    w, h = pil.size
    img = pil.resize((max(1, w * up), max(1, h * up)), Image.LANCZOS)
    if kind == "gray":
        return ImageOps.autocontrast(img.convert("L"))
    if kind == "inv":
        return ImageOps.invert(ImageOps.autocontrast(img.convert("L")))
    if kind == "bin":
        return ImageOps.autocontrast(img.convert("L")).point(lambda p: 255 if p > 140 else 0)
    if kind == "sharp":
        g = ImageOps.autocontrast(img.convert("L"))
        return ImageEnhance.Contrast(g).enhance(2.0)
    return img


def _run_recipe_local(rec, idx):
    from PIL import Image
    b = _fetch_bytes(rec["thumb"])
    if not b:
        rec["recipes_used"].append(idx)
        return Counter()
    try:
        pil = Image.open(io.BytesIO(b)).convert("RGB")
    except Exception:
        rec["recipes_used"].append(idx)
        return Counter()
    up, kind = RECIPES[idx]
    img = _apply_recipe(pil, up, kind)
    cnt = Counter()
    for txt in _ocr_texts_local(img):
        if txt.strip():
            rec["raw"] = (rec["raw"] + " | " + txt.strip().replace("\n", " "))[:900]
        for c in code_from_ocr_text(txt):
            if not _valid_code(c):
                continue
            cnt[c] += 1
            rec["reads"][c] = rec["reads"].get(c, 0) + 1
        for c in _codes_fallback(txt):
            cnt[c] += 1
            rec["reads"][c] = rec["reads"].get(c, 0) + 1
    rec["recipes_used"].append(idx)
    return cnt


def _kw_present(rec):
    if rec.get("reads"):
        return True
    return bool(C.YT_KEYWORD_RE.search((rec.get("raw") or "").upper()))


def _local_decide(rec, authoritative):
    if not authoritative and C.LOCAL_WHEN != "probe":
        return "pending"
    for i in range(_GATE_RECIPES):
        if i not in rec["recipes_used"]:
            _run_recipe_local(rec, i)
    if _kw_present(rec):
        return "pass"
    return "fail" if authoritative else "pending"


def _gate(rec):
    _gemini_build_chain()
    model, status = _current_gemini_model()
    if status == "ok":
        _gemini_pass(rec)
        if rec.get("gemini_done"):
            return "pass" if _kw_present(rec) else "fail"
        _, st2 = _current_gemini_model()
        if st2 == "net":
            return "pending"
        return _local_decide(rec, authoritative=(st2 in ("dead_key", "no_model", "no_key")))
    if status == "net":
        return "pending"
    return _local_decide(rec, authoritative=(status in ("dead_key", "no_model", "no_key")))


def _pick(rec):
    pool = [(c, n) for c, n in rec["reads"].items() if c not in rec["tried"]]
    if not pool:
        return None
    return max(pool, key=lambda cn: (cn[1], len(cn[0])))[0]   # weight 10 semantic thắng 1 regex


def _ensure_candidate(rec, authoritative):
    if rec.get("gemini_done"):
        cand = _pick(rec)
        return cand, True
    while True:
        cand = _pick(rec)
        if cand is not None:
            return cand, authoritative
        if len(rec["recipes_used"]) >= len(RECIPES):
            return None, authoritative
        _run_recipe_local(rec, len(rec["recipes_used"]))


def _pretty_model(slug):
    if not slug:
        return ""
    return " ".join(p.capitalize() for p in slug.split("-") if p)


def _engine_label(rec=None):
    if rec is not None:
        m = (rec.get("gemini_model") or "").strip()
        if m:
            return m
    if _GEMINI_DEAD_KEY or not C.GEMINI_API_KEY:
        return "local(gemini off)"
    if _gemini_busy_window_active():
        return "local-probe(gemini busy)"
    if _GEMINI_LOOP_EXHAUSTED:
        return "gemini(budget-used->pending)"
    _gemini_build_chain()
    if _GEMINI_CHAIN:
        return "gemini:chain"
    return "local(no gemini slug)"


def _engine_display(rec=None):
    if rec is not None:
        m = (rec.get("gemini_model") or "").strip()
        if m:
            return _pretty_model(m) or "Gemini"
    lab = _engine_label()
    if "gemini" in lab and "off" not in lab and "no gemini" not in lab:
        return "Gemini"
    return "EasyOCR"


def _resolve_title(entry):
    t = (entry.get("title") or "").strip()
    if t and len(t) >= 12 and t.lower() not in C.BANNED_TITLE_OVERLAYS:
        return t
    if not getattr(C, "OCR_USE_OEMBED", True):
        return ""
    vid = (entry.get("video_id") or "").strip()
    if not vid:
        return ""
    try:
        r = requests.get("https://www.youtube.com/oembed",
                         params={"url": f"https://www.youtube.com/watch?v={vid}",
                                 "format": "json"}, timeout=8)
        if r.status_code == 200:
            real = (r.json().get("title") or "").strip()
            if real and len(real) >= 8:
                return real
    except Exception as e:
        log_warn("oEmbed lỗi (trả rỗng -> link thuần):", e.__class__.__name__)
    return ""


def _ping(rec, note):
    if rec.get("pinged"):
        return
    rec["pinged"] = True
    send(msg_ocr_fail(rec["video_url"], rec["title"], rec["thumb"], rec["tried"], note,
                      len(rec["recipes_used"]) or (1 if rec.get("gemini_done") else 0),
                      rec["tries"], rec.get("channel_avatar", "")))


def _try_code(code, users, state):
    # usage_limit toàn cục -> blacklist code + DỪNG thử ID còn lại.
    if f"{code}{DEAD_SUFFIX}" in state:
        return (0, 0, False, False)
    pending = [u for u in users if f"{code}|{u['id']}" not in state]
    if not pending:
        return (0, 0, False, False)
    ne = 0
    stuck = False
    ok = False
    committed = 0
    for u in pending:
        # DEADLINE: không nhận ID mới khi sắp hết giờ -> không tràn timeout job.
        if C.out_of_time(C.TASK_RESERVE_SEC):
            log_yt(f"OCR hết giờ an toàn -> dừng ở mã `{code}`, ID còn lại để run sau")
            stuck = True
            break
        r = redeem_via_api(code, u["id"])
        st = r.get("status")
        key = f"{code}|{u['id']}"
        if st == "success":
            ok = True
            send(msg_success(code, u["id"]))
            state.add(key)
            committed += 1
        elif st == "already":
            send(msg_already(code, u["id"], r.get("reason", "")))
            state.add(key)
            committed += 1
        elif st == "failure":
            k = r.get("kind", "other")
            if k == "usage_limit":
                send(msg_usage_limit(code, r.get("reason", "")))
                state.add(key)
                state.add(f"{code}{DEAD_SUFFIX}")
                committed += 1
                log_warn(f"OCR usage_limit `{code}` -> blacklist, ngừng thử ID khác")
                break
            if k == "not_exist":
                ne += 1
            else:
                send(msg_failure(code, u["id"], r.get("reason", "unknown")))
                state.add(key)
                committed += 1
        else:
            stuck = True
        left = C.time_left() - C.LOOP_RESERVE_SEC
        if left > 0:
            sleep(min(rand_ms(DMIN, DMAX), left))
    return (len(pending) - committed, ne, stuck, ok)


def _alert(rec, code, note, redeem_flag):
    if rec["alerts"] >= C.OCR_ALERT_CAP:
        log_hook(f"OCR alert vượt cap ({C.OCR_ALERT_CAP}) cho {rec['video_id']} -> chỉ log")
        return
    rec["alerts"] += 1
    if rec.get("sem_hit"):
        note = (note + " · Gemini xác nhận đây là mã redeem (không phải chữ trang trí).").strip(" ·")
    entry = {
        "code": code,
        "title": _resolve_title(rec),
        "video_url": rec["video_url"], "thumb_url": rec["thumb"],
        "channel_avatar": rec.get("channel_avatar", ""),
        "via": "OCR", "redeem": redeem_flag,
        "engine_display": _engine_display(rec),
        "ocr_text": rec["raw"], "ocr_note": note,
    }
    send(msg_yt_alert(entry, C.YT_COOLDOWN))


def _rec_untouched(rec):
    return (not rec.get("reads")) and (not rec.get("recipes_used")) and (not rec.get("tries"))


def _hold_pending(rec, now):
    if rec.get("pending_since") is None:
        rec["pending_since"] = now
    if now - rec["pending_since"] > C.OCR_ALERT_TTL:
        return True
    return False


def _gc_expired_pending(mem, now):
    removed = 0
    for vid in list(mem.keys()):
        rec = mem.get(vid)
        if not rec:
            continue
        ps = rec.get("pending_since")
        if ps is not None and (now - ps) > C.OCR_ALERT_TTL:
            mem.pop(vid, None)
            removed += 1
    if removed:
        log_yt(f"GC: xoá {removed} video pending quá {int(C.OCR_ALERT_TTL/3600)}h -> giải slot")
    return removed


def run_correction(users, state, bare_videos, now, known_codes=None):
    if C.OCR_MODE != "auto" or not bare_videos:
        return
    known = known_codes or set()
    mem = load_mem()
    gc_removed = _gc_expired_pending(mem, now)
    budget_end = time.monotonic() + C.OCR_LOOP_BUDGET
    changed = bool(gc_removed)
    deep_used = 0
    for v in bare_videos:
        rec = mem.setdefault(v["video_id"], _new_rec(v))
        rec.setdefault("channel_avatar", v.get("channel_avatar", ""))
        if rec.get("done"):
            continue
        # DEADLINE: hết budget OCR HOẶC hết giờ an toàn của job -> dừng, video còn lại run sau.
        if time.monotonic() >= budget_end or C.out_of_time(C.LOOP_RESERVE_SEC + 60):
            log_yt("OCR hết budget vòng này / hết giờ an toàn -> video còn lại cho run sau")
            break
        g = _gate(rec)
        if g == "pending":
            if _rec_untouched(rec):
                mem.pop(v["video_id"], None)
            else:
                _hold_pending(rec, now)
            log_yt(f"OCR[{_engine_label()}]: video {rec['video_id']} GIỮ PENDING "
                   f"(gemini busy/hết-trần-vòng/net) -> cho vòng sau, không no_keyword, không ping")
            changed = True
            continue
        if g == "fail":
            rec["done"] = "no_keyword"
            log_yt(f"OCR[{_engine_label()}]: ảnh không có chữ CODE/CÔ DÉ "
                   f"({rec['video_id']}) -> bỏ qua, không ping (không tính quota)")
            changed = True
            continue
        auth = not _gemini_busy_window_active() and not _GEMINI_LOOP_EXHAUSTED
        if deep_used >= C.OCR_MAX_IMAGES:
            break
        deep_used += 1
        while rec["tries"] < C.OCR_MAX_TRIES and time.monotonic() < budget_end:
            if C.out_of_time(C.TASK_RESERVE_SEC):
                log_yt(f"OCR hết giờ an toàn -> GIỮ video {rec['video_id']} cho run sau")
                changed = True
                break
            cand, finalize = _ensure_candidate(rec, auth)
            if cand is None:
                if rec.get("gemini_done") and rec.get("sem_declared_none") and not rec["reads"]:
                    rec["done"] = "no_code"
                    log_yt(f"OCR[{_engine_label(rec)}]: Gemini + regex đồng thuận ảnh chỉ là "
                           f"thông báo sự kiện, không chứa mã ({rec['video_id']}) -> bỏ qua IM LẶNG, "
                           f"không ping rác")
                elif finalize:
                    rec["done"] = "exhausted"
                    log_warn(f"OCR[{_engine_label(rec)}] có chữ CODE nhưng không đọc được mã "
                             f"({rec['video_id']}) -> PING nhập tay")
                    _ping(rec, f"Ảnh CÓ chữ CODE nhưng engine {_engine_label(rec)} không đọc được "
                               f"mã chắc chắn.")
                else:
                    if _hold_pending(rec, now):
                        rec["done"] = "exhausted"
                        log_warn(f"OCR[{_engine_label(rec)}] chờ gemini quá lâu ({rec['video_id']}) "
                                 f"-> PING nhập tay (không thể chờ mãi)")
                        _ping(rec, "Đã chờ Gemini quá lâu mà local vẫn không đọc được mã chắc chắn.")
                    else:
                        log_yt(f"OCR[{_engine_label(rec)}] local hết recipe mà vẫn busy/hết-trần -> "
                               f"GIỮ PENDING {rec['video_id']} cho vòng sau")
                changed = True
                break
            if cand in known:
                rec["done"] = "dup_with_text"
                log_yt(f"OCR skip dup: `{cand}` đã có từ tiêu đề/mô tả (tầng text lo) "
                       f"-> bỏ qua video {rec['video_id']}, không nhập không alert")
                changed = True
                break
            rec["tries"] += 1
            note = (f"Lần thử #{rec['tries']}/{C.OCR_MAX_TRIES} · engine={_engine_label(rec)} · "
                    f"đã loại: {rec['tried'] or 'chưa có'}")
            log_yt(f"OCR[{_engine_label(rec)}] thử #{rec['tries']}: `{cand}` "
                   f"(video {rec['video_id']}) [quota {deep_used}/{C.OCR_MAX_IMAGES}]")
            _alert(rec, cand, note, True)
            changed = True
            remaining, ne, stuck, ok = _try_code(cand, users, state)
            # DEADLINE: vừa nhập xong mà hết giờ -> KHÔNG chốt video, run sau nhập tiếp ID còn lại.
            if C.out_of_time(C.TASK_RESERVE_SEC):
                log_yt(f"OCR hết giờ an toàn sau mã `{cand}` -> KHÔNG chốt video, để run sau nhập tiếp")
                changed = True
                break
            pending = remaining + ne
            if ok or (remaining == 0 and ne == 0):
                rec["done"] = "committed"
                changed = True
                break
            if ne > 0 and ne == pending and remaining == pending:
                rec["tried"].append(cand)
                changed = True
                continue
            if stuck and ne == 0 and remaining == pending:
                log_warn(f"OCR stuck ở `{cand}` (captcha/kẹt) -> để vòng sau tiếp")
                break
            rec["done"] = "committed"
            changed = True
            break
        else:
            if rec["tries"] >= C.OCR_MAX_TRIES and not rec.get("done"):
                rec["done"] = "exhausted"
                log_warn(f"OCR[{_engine_label(rec)}] đạt giới hạn {C.OCR_MAX_TRIES} lượt cho "
                         f"{rec['video_id']} mà vẫn bị từ chối -> PING nhập tay")
                _ping(rec, f"Đã thử đủ {C.OCR_MAX_TRIES} lượt (engine {_engine_label(rec)}) mà "
                           f"mọi mã đọc được đều bị server từ chối.")
                changed = True
    if changed:
        commit_mem(mem)


def alert_only(bare_videos, known_codes=None):
    if C.OCR_MODE != "alert" or not bare_videos:
        return
    known = known_codes or set()
    mem = load_mem()
    gc_removed = _gc_expired_pending(mem, time.time())
    changed = bool(gc_removed)
    deep_used = 0
    for v in bare_videos:
        rec = mem.setdefault(v["video_id"], _new_rec(v))
        rec.setdefault("channel_avatar", v.get("channel_avatar", ""))
        if rec.get("done") or rec.get("alerts"):
            continue
        # DEADLINE: hết giờ an toàn -> dừng, video còn lại run sau.
        if C.out_of_time(C.LOOP_RESERVE_SEC + 60):
            log_yt("OCR(alert) hết giờ an toàn -> video còn lại cho run sau")
            break
        g = _gate(rec)
        if g == "pending":
            if _rec_untouched(rec):
                mem.pop(v["video_id"], None)
            log_yt(f"OCR(alert)[{_engine_label()}] GIỮ PENDING {rec['video_id']} cho vòng sau")
            changed = True
            continue
        if g == "fail":
            rec["done"] = "no_keyword"
            changed = True
            continue
        auth = not _gemini_busy_window_active() and not _GEMINI_LOOP_EXHAUSTED
        if deep_used >= C.OCR_MAX_IMAGES:
            break
        deep_used += 1
        cand, _fin = _ensure_candidate(rec, auth)
        if cand is None and rec.get("gemini_done") and rec.get("sem_declared_none") and not rec["reads"]:
            rec["done"] = "no_code"
            log_yt(f"OCR(alert): teaser không chứa mã ({rec['video_id']}) -> bỏ qua IM LẶNG")
            changed = True
            continue
        if cand and cand in known:
            rec["done"] = "dup_with_text"
            log_yt(f"OCR(alert) skip dup: `{cand}` đã có từ tầng text -> bỏ qua {rec['video_id']}")
            changed = True
            continue
        _alert(rec, cand or "(chưa đọc được mã)",
               f"Chế độ OCR = alert (engine {_engine_label(rec)}): bot CHỈ báo, không tự nhập.",
               False)
        rec["done"] = "alerted"
        changed = True
    if changed:
        commit_mem(mem)
