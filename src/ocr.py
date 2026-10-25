# OCR THUMBNAIL + VONG TU SUA CO TRI NHO.
# TRIET LY XU LY "GEMINI KHONG KHA DUNG" (5 lop chan, xem comment config.py):
#   Lop 1 _gemini_usable(): ten 'gemini-3.8-flash' phai NAM TRONG GET /v1beta/models cua
#          chinh key -> khong thi TAT gemini ca run, ve local. (chong 404 lap / key sai surface)
#   Lop 2 _gemini_call(): 402/403 -> "co the do PHI"; 429 -> "het free-tier"; 404 -> list;
#          ca ba TAT ca run -> local. (chong chay am tham khi billed/quota)
#   Lop 3 _GEMINI_CALLS >= GEMINI_MAX_CALLS -> TAT ca run -> local. (chong runaway $)
#   Lop 4 _gate/_ensure_candidate: Gemini tra None (chet) -> chay _run_recipe_local. (fallback)
#   Lop 5 phan biet "chet" vs "song-nhung-sot": Gemini OK ma [] -> TIN no, khong roi local
#          (Gemini nhan cach dieu gioi hon local, bat no quay local vi 1 anh trong la tu ban).
# 2106 -> blacklist tried[] + candidate ke tiep; 2117 = ma DUNG het luot -> dung sua.
# Gate (CODE/CO DE) van chan live/trailer im lang, KHONG tinh quota; chi video PASS gate
#   moi vao vong sau + co the ping be tac (1 lan/video).
import os, io, time, json, base64, requests
from collections import Counter
from . import config as C
from .parsers import code_from_ocr_text
from .utils import log_yt, log_warn, log_hook, sleep, rand_ms
from .state import commit_paths
from .webhook import send, msg_success, msg_failure, msg_yt_alert, msg_ocr_fail
from .api_redeemer import redeem_via_api

DMIN = int(os.getenv("DELAY_MIN", "15000"))
DMAX = int(os.getenv("DELAY_MAX", "30000"))

MEM = lambda: os.path.join(os.getcwd(), "ocr_memory.json")
_BYTES = {}
_GATE_RECIPES = 2

# --- state Gemini per-PROCESS (= per-run; ca loop 345' chay 1 process) ---
_READER = None
_READER_FAILED = False
_GEMINI_LIST = None          # None = chua fetch; [] = fetch that/bi loi
_GEMINI_LIST_OK = False
_GEMINI_DECISION = None      # None = chua quyet; True/False = da quyet (opt-in + validate)
_GEMINI_BARE = ""            # id da validate, dung de goi
_GEMINI_BLOCKED = False      # True sau 402/403/404/429/tran -> TAT ca run
_GEMINI_CALLS = 0            # dem generate da goi (chan bang GEMINI_MAX_CALLS)

RECIPES = [
    (2, "gray"), (2, "inv"), (3, "gray"), (3, "inv"),
    (2, "bin"), (3, "bin"), (4, "gray"), (4, "inv"),
    (2, "sharp"), (3, "sharp"), (4, "bin"), (5, "gray"),
]

# Prompt chong bai: cam suy doan, cam sua chinh ta, giu dau + hoa/thuong, moi chuoi 1 dong.
_GEMINI_PROMPT = (
    "Ban la cong cu trich xuat chu (OCR) tu anh thumbnail game. Nhiem vu: liet ke CHINH XAC "
    "moi chuoi chu (tieng Viet co dau va tieng Anh) THUC SU nhin thay trong anh, ke ca chu "
    "cach dieu, chu co do bong, chu trong khung/nut/pill. Quy tac bat buoc: "
    "(1) CHI ghi chu thuc su thay, TUYET DOI khong suy doan, khong bia, khong sua loi chinh ta, "
    "khong them chu khong co. "
    "(2) Moi chuoi nam tren MOT dong rieng. "
    "(3) Giu nguyen viet hoa/thuong va dau tieng Viet. "
    "(4) Neu thay cum 'CODE' hoac 'CO DE' dung canh mot chuoi ma, ghi nguyen ven chuoi ma do "
    "tren cung dong (khong tach roi). "
    "(5) Khong giai thich, khong mo dau, chi tra danh sach dong."
)


# ================= Lop 1: discover + opt-in + validate ten =================
def _gemini_load_models():
    """GET /v1beta/models -> list id ho tro generateContent cua CHINH KEY. Cache per-process.
       Loi/feu -> [] va _GEMINI_LIST_OK=False de _gemini_usable tu choi goi (thua nhan
       khong biet hon la goi nham model)."""
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
        log_warn("Gemini list loi mang:", e.__class__.__name__)
        _GEMINI_LIST_OK = False
        return _GEMINI_LIST
    if r.status_code != 200:
        log_warn("Gemini list http", r.status_code, "->", (r.text or "")[:200])
        _GEMINI_LIST_OK = False
        return _GEMINI_LIST
    try:
        j = r.json()
    except Exception:
        log_warn("Gemini list khong phai JSON")
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


def _gemini_usable():
    """Quyet MOT LAN per-run co goi Gemini khong. Chi True khi: key co + model non-empty +
       list fetch OK + model NAM TRONG list. Moi truong hop khac -> False + log LIET KE
       id hop le (de user dat secret) -> local. -> khong the goi nham ten, khong 404 lap."""
    global _GEMINI_DECISION, _GEMINI_BARE
    if _GEMINI_BLOCKED:
        return False
    if _GEMINI_DECISION is True:
        return True
    if _GEMINI_DECISION is False:
        return False
    if not C.GEMINI_API_KEY:
        _GEMINI_DECISION = False
        return False
    model = (C.GEMINI_MODEL or "").strip()
    if not model:
        _GEMINI_DECISION = False
        ids = _gemini_load_models()
        log_warn("OCR gemini TAT (opt-in): GEMINI_MODEL trong -> KHONG goi. Dat GEMINI_MODEL "
                 "= 1 id trong list: " + (", ".join(ids[:12]) if ids else "(list rong/loi)")
                 + " -> local.")
        return False
    bare = model.split("/")[-1].strip()
    ids = _gemini_load_models()
    if not _GEMINI_LIST_OK:
        _GEMINI_DECISION = False
        log_warn("OCR gemini TAT: khong lay duoc list model -> bo qua (KHONG doan id). -> local.")
        return False
    if bare not in ids:
        _GEMINI_DECISION = False
        log_warn(f"OCR gemini TAT: GEMINI_MODEL='{bare}' KHONG goi duoc voi key nay "
                 f"(key co the thuoc surface khac / region khac). List hop le: "
                 + ", ".join(ids[:15]) + " -> local.")
        return False
    _GEMINI_BARE = bare
    _GEMINI_DECISION = True
    log_yt(f"OCR gemini BAT: model='{bare}' (da validate qua list API cua key). "
           f"Tran goi/run={C.GEMINI_MAX_CALLS}.")
    return True


# ================= Lop 2+3: goi + phan loi tien/quota + chan tran =================
def _gemini_call(png_bytes):
    """1 lan generate tren anh PNG. Tra list[str] khi OK (ke ca [] = chay OK ma khong chu),
       None khi engine chet/bi chan (caller roi local). 402/403/429/404 -> TAT ca run."""
    global _GEMINI_CALLS, _GEMINI_BLOCKED
    if _GEMINI_CALLS >= C.GEMINI_MAX_CALLS:           # Lop 3: chan tran $
        if not _GEMINI_BLOCKED:
            _GEMINI_BLOCKED = True
            log_warn(f"OCR gemini: dat tran GEMINI_MAX_CALLS={C.GEMINI_MAX_CALLS} -> "
                     f"TAT gemini ca run -> local (chan phi runaway).")
        return None
    _GEMINI_CALLS += 1
    b64 = base64.b64encode(png_bytes).decode("ascii")
    body = {"contents": [{"parts": [
        {"inline_data": {"mime_type": "image/png", "data": b64}},
        {"text": _GEMINI_PROMPT},
    ]}]}
    url = f"{C.GEMINI_ENDPOINT}/{_GEMINI_BARE}:generateContent"
    try:
        r = requests.post(url, json=body, params={"key": C.GEMINI_API_KEY},
                          timeout=C.GEMINI_TIMEOUT)
    except Exception as e:                                   # Lop 4: loi mang -> None
        log_warn("Gemini loi mang:", e.__class__.__name__)
        return None
    sc = r.status_code
    if sc == 200:
        try:
            j = r.json()
        except Exception:
            log_warn("Gemini khong phai JSON")
            return None
        cands = j.get("candidates") or []
        if not cands:
            log_warn("Gemini khong tra candidate (safety/rong) -> fallback local video nay")
            return None
        parts = (cands[0].get("content") or {}).get("parts") or []
        txt = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        return [txt] if txt else []                          # [] = Lop 5: OK ma khong chu
    if sc == 404:                                            # Lop 2: ten khong ton tai
        log_warn("Gemini 404: model id khong goi duoc voi key nay (du da validate list — "
                 "co the list stale/region). List: " + ", ".join(_gemini_load_models()[:15])
                 + " -> TAT gemini ca run -> local.")
        _GEMINI_BLOCKED = True
        return None
    if sc in (402, 403):                                     # Lop 2: co the do PHI/quyen
        log_warn(f"Gemini {sc}: CO THE do PHI/quyen/region -> KIEM TRA AI Studio "
                 f"(billing/quota/key). TAT gemini ca run -> local (khong goi tiep).")
        _GEMINI_BLOCKED = True
        return None
    if sc == 429:                                            # Lop 2: het free-tier/quota
        log_warn("Gemini 429: cham quota/rate (free-tier het luot?) -> TAT gemini ca run "
                 "-> local. Chay lai sau hoac nang tier neu muon.")
        _GEMINI_BLOCKED = True
        return None
    log_warn("Gemini http", sc, "->", (r.text or "")[:200])
    return None


def _gemini_pass(rec):
    """Doc anh GOC bang Gemini 1 lan, nap candidate. Idempotent qua rec['gemini_done'].
       Chi chay khi _gemini_usable() True. None tu _gemini_call -> gemini_done van False
       de local thay the (Lop 4); [] -> gemini_done True (Lop 5: tin engine, anh khong chu)."""
    if rec.get("gemini_done"):
        return
    if not _gemini_usable():
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
        log_warn("Gemini: khong doc duoc anh goc:", e.__class__.__name__)
        return
    texts = _gemini_call(png)
    if texts is None:                 # chet -> de local chay sau
        return
    rec["gemini_done"] = True
    for txt in texts:
        if txt.strip():
            rec["raw"] = (rec["raw"] + " | " + txt.strip().replace("\n", " "))[:900]
        for c in code_from_ocr_text(txt):
            rec["reads"][c] = rec["reads"].get(c, 0) + 1


# ================= Engine local (EasyOCR > Tesseract) — duong ray khi Gemini chet =================
def _easy_reader():
    global _READER, _READER_FAILED
    if _READER is not None:
        return _READER
    if _READER_FAILED or C.OCR_ENGINE == "tess":
        return None
    try:
        import easyocr
        _READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        log_yt("EasyOCR san sang (fallback local)")
    except Exception as e:
        _READER_FAILED = True
        log_warn("EasyOCR khong kha dung -> tesseract:", e.__class__.__name__)
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
            log_warn("EasyOCR loi anh nay -> tesseract:", e.__class__.__name__)
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
        log_warn("ocr_memory hong -> bat dau lai:", e)
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
            "gemini_done": False}


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
            cnt[c] += 1
            rec["reads"][c] = rec["reads"].get(c, 0) + 1
    rec["recipes_used"].append(idx)
    return cnt


def _kw_present(rec):
    if rec.get("reads"):
        return True
    return bool(C.YT_KEYWORD_RE.search((rec.get("raw") or "").upper()))


# ================= Lop 4: gate — Gemini chet thi local lanh, khong bao gio dung =================
def _gate(rec):
    if _gemini_usable():
        _gemini_pass(rec)
        if rec.get("gemini_done"):          # Gemini song (OK hoac [] uy tin) -> quyet by no
            return _kw_present(rec)
        # Gemini chet (None) -> roi local ben duoi
    for i in range(_GATE_RECIPES):
        if i not in rec["recipes_used"]:
            _run_recipe_local(rec, i)
    return _kw_present(rec)


def _pick(rec):
    pool = [(c, n) for c, n in rec["reads"].items() if c not in rec["tried"]]
    if not pool:
        return None
    return max(pool, key=lambda cn: (cn[1], len(cn[0])))[0]


def _ensure_candidate(rec):
    if _gemini_usable():
        _gemini_pass(rec)
        if rec.get("gemini_done"):
            return _pick(rec)               # Gemini song: chi 1 lan anh goc, khong co recipe khac
    while True:                             # Gemini chet hoac ep local: quay RECIPES
        cand = _pick(rec)
        if cand is not None:
            return cand
        if len(rec["recipes_used"]) >= len(RECIPES):
            return None
        _run_recipe_local(rec, len(rec["recipes_used"]))


def _engine_label():
    if _gemini_usable():
        return "gemini"
    if C.GEMINI_API_KEY:
        return "local(gemini off)"          # co key nhung bi tat (sai ten/billed/tran) -> minh bach
    return "local"


def _ping(rec, note):
    if rec.get("pinged"):
        return
    rec["pinged"] = True
    send(msg_ocr_fail(rec["video_url"], rec["title"], rec["thumb"], rec["tried"], note,
                      len(rec["recipes_used"]) or (1 if rec.get("gemini_done") else 0),
                      rec["tries"], rec.get("channel_avatar", "")))


def _try_code(code, users, state):
    pending = [u for u in users if f"{code}|{u['id']}" not in state]
    if not pending:
        return (0, 0, False, False)
    ne = 0
    stuck = False
    ok = False
    committed = 0
    for u in pending:
        r = redeem_via_api(code, u["id"])
        st = r["status"]
        key = f"{code}|{u['id']}"
        if st == "success":
            ok = True
            send(msg_success(code, u["id"]))
            state.add(key)
            committed += 1
        elif st == "failure":
            k = r.get("kind", "other")
            if k == "not_exist":
                ne += 1
            else:
                send(msg_failure(code, u["id"], r.get("reason", "unknown")))
                state.add(key)
                committed += 1
        else:
            stuck = True
        sleep(rand_ms(DMIN, DMAX))
    return (len(pending) - committed, ne, stuck, ok)


def _alert(rec, code, note, redeem_flag):
    if rec["alerts"] >= C.OCR_ALERT_CAP:
        log_hook(f"OCR alert vuot cap ({C.OCR_ALERT_CAP}) cho {rec['video_id']} -> chi log")
        return
    rec["alerts"] += 1
    send(msg_yt_alert({
        "code": code, "title": rec["title"] or "Video mới (mã nằm trong ảnh thumbnail)",
        "video_url": rec["video_url"], "thumb_url": rec["thumb"],
        "channel_avatar": rec.get("channel_avatar", ""),
        "via": "OCR", "redeem": redeem_flag,
        "conf": "high" if rec["reads"].get(code, 0) >= 2 else "single",
        "ocr_text": rec["raw"], "ocr_note": note,
    }, C.YT_COOLDOWN))


def run_correction(users, state, bare_videos, now, known_codes=None):
    if C.OCR_MODE != "auto" or not bare_videos:
        return
    known = known_codes or set()
    mem = load_mem()
    budget_end = time.monotonic() + C.OCR_LOOP_BUDGET
    changed = False
    deep_used = 0
    for v in bare_videos:
        rec = mem.setdefault(v["video_id"], _new_rec(v))
        rec.setdefault("channel_avatar", v.get("channel_avatar", ""))
        if rec.get("done"):
            continue
        if time.monotonic() >= budget_end:
            log_yt("OCR het budget vong nay -> so video con lai cho vong sau")
            break
        if not _gate(rec):
            rec["done"] = "no_keyword"
            log_yt(f"OCR gate[{_engine_label()}]: anh khong co chu CODE/CO DE "
                   f"({rec['video_id']}) -> bo qua, khong ping (khong tinh quota)")
            changed = True
            continue
        if deep_used >= C.OCR_MAX_IMAGES:
            break
        deep_used += 1
        while rec["tries"] < C.OCR_MAX_TRIES and time.monotonic() < budget_end:
            cand = _ensure_candidate(rec)
            if cand is None:
                rec["done"] = "exhausted"
                log_warn(f"OCR[{_engine_label()}] co chu CODE nhung khong doc duoc ma "
                         f"({rec['video_id']}) -> PING nhap tay")
                _ping(rec, f"Ảnh CÓ chữ CODE nhưng engine {_engine_label()} không đọc được "
                           f"mã chắc chắn.")
                changed = True
                break
            if cand in known:
                rec["done"] = "dup_with_text"
                log_yt(f"OCR skip dup: `{cand}` da co tu tieu de/mo ta (tang text lo) "
                       f"-> bo qua video {rec['video_id']}, khong nhap khong alert")
                changed = True
                break
            rec["tries"] += 1
            note = (f"Lần thử #{rec['tries']}/{C.OCR_MAX_TRIES} · engine={_engine_label()} · "
                    f"đã loại: {rec['tried'] or 'chưa có'}")
            log_yt(f"OCR[{_engine_label()}] thu #{rec['tries']}: `{cand}` "
                   f"(video {rec['video_id']}) [quota {deep_used}/{C.OCR_MAX_IMAGES}]")
            _alert(rec, cand, note, True)
            changed = True
            remaining, ne, stuck, ok = _try_code(cand, users, state)
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
                log_warn(f"OCR stuck o `{cand}` (captcha/ket) -> de vong sau tiep")
                break
            rec["done"] = "committed"
            changed = True
            break
        else:
            if rec["tries"] >= C.OCR_MAX_TRIES and not rec.get("done"):
                rec["done"] = "exhausted"
                log_warn(f"OCR[{_engine_label()}] dat gioi han {C.OCR_MAX_TRIES} luot cho "
                         f"{rec['video_id']} ma van bi tu choi -> PING nhap tay")
                _ping(rec, f"Đã thử đủ {C.OCR_MAX_TRIES} lượt (engine {_engine_label()}) mà "
                           f"mọi mã đọc được đều bị server từ chối.")
                changed = True
    if changed:
        commit_mem(mem)


def alert_only(bare_videos, known_codes=None):
    if C.OCR_MODE != "alert" or not bare_videos:
        return
    known = known_codes or set()
    mem = load_mem()
    changed = False
    deep_used = 0
    for v in bare_videos:
        rec = mem.setdefault(v["video_id"], _new_rec(v))
        rec.setdefault("channel_avatar", v.get("channel_avatar", ""))
        if rec.get("done") or rec.get("alerts"):
            continue
        if not _gate(rec):
            rec["done"] = "no_keyword"
            changed = True
            continue
        if deep_used >= C.OCR_MAX_IMAGES:
            break
        deep_used += 1
        cand = _ensure_candidate(rec)
        if cand and cand in known:
            rec["done"] = "dup_with_text"
            log_yt(f"OCR(alert) skip dup: `{cand}` da co tu tang text -> bo qua {rec['video_id']}")
            changed = True
            continue
        _alert(rec, cand or "(chưa đọc được mã)",
               f"Chế độ OCR = alert (engine {_engine_label()}): bot CHỈ báo, không tự nhập.",
               False)
        rec["done"] = "alerted"
        changed = True
    if changed:
        commit_mem(mem)
