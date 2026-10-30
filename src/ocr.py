# OCR THUMBNAIL + VONG TU SUA CO TRI NHO.
# 2117/2121 trong _try_code duoc xu ly la ALREADY: dong cap code|id, khong blacklist code,
# khong spam that bai do. Candidate chi bi blacklist khi that su not_exist (2106/2102).
import os, io, time, json, base64, requests
from collections import Counter
from . import config as C
from .parsers import code_from_ocr_text
from .utils import log_yt, log_warn, log_hook, sleep, rand_ms
from .state import commit_paths
from .webhook import send, msg_success, msg_failure, msg_yt_alert, msg_ocr_fail, msg_already
from .api_redeemer import redeem_via_api

DMIN = int(os.getenv("DELAY_MIN", "15000"))
DMAX = int(os.getenv("DELAY_MAX", "30000"))

MEM = lambda: os.path.join(os.getcwd(), "ocr_memory.json")
_BYTES = {}
_GATE_RECIPES = 2

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
# --- ngan sach per-LOOP ---
_GEMINI_LOOP_BUDGET = 0
_GEMINI_LOOP_EXHAUSTED = False

RECIPES = [
    (2, "gray"), (2, "inv"), (3, "gray"), (3, "inv"),
    (2, "bin"), (3, "bin"), (4, "gray"), (4, "inv"),
    (2, "sharp"), (3, "sharp"), (4, "bin"), (5, "gray"),
]

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
        log_warn("OCR gemini: khong lay duoc list model -> bo qua chuoi (KHONG doan slug). -> local auth.")
        return
    idset = set(ids)
    for p in prefs:
        if p in idset:
            _GEMINI_CHAIN.append(p)
        else:
            _GEMINI_DROPPED.append(p)
    if _GEMINI_CHAIN:
        log_yt("OCR gemini chuoi (da validate qua list key): " + " > ".join(_GEMINI_CHAIN)
               + (f" | bo (khong co voi key): {', '.join(_GEMINI_DROPPED)}" if _GEMINI_DROPPED else ""))
    else:
        log_warn("OCR gemini: KHONG ten nao trong chuoi ton tai voi key nay. "
                 f"List hop le: {', '.join(ids[:15])} -> local auth. "
                 "(Dat GEMINI_MODEL_CHAIN = id that trong list de bat gemini.)")


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
            log_warn(f"OCR gemini: CA chuoi 5xx (dong) -> cho {int(C.GEMINI_BUSY_BACKOFF_SEC)}s; "
                     f"in luc do dung EasyOCR THEO CHE DO THAM DO (chi duong tinh, am tinh giu pending).")
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
            log_warn("Gemini loi mang (cuc bo):", e.__class__.__name__)
            return None, "net"
        sc = r.status_code
        if sc == 200:
            try:
                j = r.json()
            except Exception:
                log_warn("Gemini khong phai JSON (cuc bo)")
                return None, "net"
            cands = j.get("candidates") or []
            if not cands:
                log_warn("Gemini khong tra candidate (safety/rong) -> coi nhu cuc bo")
                return None, "net"
            parts = (cands[0].get("content") or {}).get("parts") or []
            txt = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            rec["gemini_model"] = model
            sleep(C.GEMINI_THROTTLE_SEC)
            return ([txt] if txt else []), "ok"
        if sc in (500, 502, 503, 504):
            _GEMINI_5XX.add(model)
            log_warn(f"Gemini {model} {sc} (dong) -> bay khoi chuoi tam thoi, thu model ke tiep.")
            sleep(1.5)
            continue
        if sc == 404:
            _GEMINI_DEAD_MODEL.add(model)
            log_warn(f"Gemini {model} 404 (slug khong goi duoc) -> bo, thu model ke tiep.")
            continue
        if sc in (402, 403):
            _GEMINI_DEAD_KEY = True
            log_warn(f"Gemini {sc}: CO THE do PHI/quyen/region -> KIEM TRA AI Studio. "
                     f"Dung gemini ca run -> local auth.")
            return None, "dead_key"
        if sc == 429:
            _GEMINI_DEAD_KEY = True
            log_warn("Gemini 429: cham quota/rate (free-tier het luot?) -> dung gemini ca run -> local auth.")
            return None, "dead_key"
        log_warn("Gemini http", sc, "->", (r.text or "")[:200])
        _GEMINI_DEAD_MODEL.add(model)
        continue


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
        log_warn("Gemini: khong doc duoc anh goc:", e.__class__.__name__)
        return
    texts, status = _gemini_call(png, rec)
    if status != "ok" or texts is None:
        return
    rec["gemini_done"] = True
    for txt in texts:
        if txt.strip():
            rec["raw"] = (rec["raw"] + " | " + txt.strip().replace("\n", " "))[:900]
        for c in code_from_ocr_text(txt):
            rec["reads"][c] = rec["reads"].get(c, 0) + 1


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
            "gemini_done": False, "pending_since": None, "gemini_model": ""}


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
    return max(pool, key=lambda cn: (cn[1], len(cn[0])))[0]


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
        log_warn("oEmbed loi (tra rong -> link thuan):", e.__class__.__name__)
    return ""


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
        log_yt(f"GC: xoa {removed} video pending qua {int(C.OCR_ALERT_TTL/3600)}h -> giai slot")
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
        if time.monotonic() >= budget_end:
            log_yt("OCR het budget vong nay -> so video con lai cho vong sau")
            break
        g = _gate(rec)
        if g == "pending":
            if _rec_untouched(rec):
                mem.pop(v["video_id"], None)
            else:
                _hold_pending(rec, now)
            log_yt(f"OCR[{_engine_label()}]: video {rec['video_id']} GIU PENDING "
                   f"(gemini busy/het-tran-vong/net) -> cho vong sau, khong no_keyword, khong ping")
            changed = True
            continue
        if g == "fail":
            rec["done"] = "no_keyword"
            log_yt(f"OCR[{_engine_label()}]: anh khong co chu CODE/CO DE "
                   f"({rec['video_id']}) -> bo qua, khong ping (khong tinh quota)")
            changed = True
            continue
        auth = not _gemini_busy_window_active() and not _GEMINI_LOOP_EXHAUSTED
        if deep_used >= C.OCR_MAX_IMAGES:
            break
        deep_used += 1
        while rec["tries"] < C.OCR_MAX_TRIES and time.monotonic() < budget_end:
            cand, finalize = _ensure_candidate(rec, auth)
            if cand is None:
                if finalize:
                    rec["done"] = "exhausted"
                    log_warn(f"OCR[{_engine_label(rec)}] co chu CODE nhung khong doc duoc ma "
                             f"({rec['video_id']}) -> PING nhap tay")
                    _ping(rec, f"Ảnh CÓ chữ CODE nhưng engine {_engine_label(rec)} không đọc được "
                               f"mã chắc chắn.")
                else:
                    if _hold_pending(rec, now):
                        rec["done"] = "exhausted"
                        log_warn(f"OCR[{_engine_label(rec)}] cho gemini qua lau ({rec['video_id']}) "
                                 f"-> PING nhap tay (khong the cho mai)")
                        _ping(rec, "Đã chờ Gemini qua lâu mà local vẫn không đọc được mã chắc chắn.")
                    else:
                        log_yt(f"OCR[{_engine_label(rec)}] local het recipe ma van busy/het-tran -> "
                               f"GIU PENDING {rec['video_id']} cho vong sau")
                changed = True
                break
            if cand in known:
                rec["done"] = "dup_with_text"
                log_yt(f"OCR skip dup: `{cand}` da co tu tieu de/mo ta (tang text lo) "
                       f"-> bo qua video {rec['video_id']}, khong nhap khong alert")
                changed = True
                break
            rec["tries"] += 1
            note = (f"Lần thử #{rec['tries']}/{C.OCR_MAX_TRIES} · engine={_engine_label(rec)} · "
                    f"đã loại: {rec['tried'] or 'chưa có'}")
            log_yt(f"OCR[{_engine_label(rec)}] thu #{rec['tries']}: `{cand}` "
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
                log_warn(f"OCR[{_engine_label(rec)}] dat gioi han {C.OCR_MAX_TRIES} luot cho "
                         f"{rec['video_id']} ma van bi tu choi -> PING nhap tay")
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
        g = _gate(rec)
        if g == "pending":
            if _rec_untouched(rec):
                mem.pop(v["video_id"], None)
            log_yt(f"OCR(alert)[{_engine_label()}] GIU PENDING {rec['video_id']} cho vong sau")
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
        if cand and cand in known:
            rec["done"] = "dup_with_text"
            log_yt(f"OCR(alert) skip dup: `{cand}` da co tu tang text -> bo qua {rec['video_id']}")
            changed = True
            continue
        _alert(rec, cand or "(chưa đọc được mã)",
               f"Chế độ OCR = alert (engine {_engine_label(rec)}): bot CHỈ báo, không tự nhập.",
               False)
        rec["done"] = "alerted"
        changed = True
    if changed:
        commit_mem(mem)
