# OCR THUMBNAIL + VONG TU SUA CO TRI NHO.
# ENGINE: EasyOCR (chinh) + tesseract (fallback).
# QUY THUAT QUOTA (sua loi "live chiem slot"): duet TOAN bo bare (khong cat truoc), chay
#   gate (2 recipe) cho tung video CHUA done. Gate FAIL (anh khong co chu CODE: live,
#   trailer, ...) -> done="no_keyword" IM LANG, KHONG tinh vao quota. Gate PASS (anh CO
#   chu CODE) -> MOI tinh quota va vao vong tu sau; du OCR_MAX_IMAGES video pass-gate thi
#   dung (phan con lai vong sau, idempotent qua ocr_memory). -> live/trailer khong bao gio
#   day video ma-trong-anh ra ngoai, va KHONG can phan-loai live bang field (da bo _is_live_node).
# 2106 -> blacklist tried[] + recipe moi; 2117 = ma DUNG het luot -> dung sua, chot failure.
# Be tac (het recipe / du luot ma van sai) -> ping OCR_PING_USER (1 lan/video).
import os, time, json, requests
from collections import Counter
from . import config as C
from .parsers import code_from_ocr_text
from .utils import log_yt, log_warn, log_hook, sleep, rand_ms
from .state import commit_paths
from .webhook import send, msg_success, msg_failure, msg_yt_alert, msg_ocr_fail
from .api_redeemer import redeem_via_api

DMIN = int(os.getenv("DELAY_MIN", "15000"))
DMAX = int(os.getenv("DELAY_MAX", "30000"))
OCR_ENGINE = os.getenv("OCR_ENGINE", "auto").strip().lower()

MEM = lambda: os.path.join(os.getcwd(), "ocr_memory.json")
_BYTES = {}
_GATE_RECIPES = 2
_READER = None
_READER_FAILED = False

RECIPES = [
    (2, "gray"), (2, "inv"), (3, "gray"), (3, "inv"),
    (2, "bin"), (3, "bin"), (4, "gray"), (4, "inv"),
    (2, "sharp"), (3, "sharp"), (4, "bin"), (5, "gray"),
]


def _easy_reader():
    global _READER, _READER_FAILED
    if _READER is not None:
        return _READER
    if _READER_FAILED or OCR_ENGINE == "tess":
        return None
    try:
        import easyocr
        _READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        log_yt("EasyOCR san sang (engine chinh)")
    except Exception as e:
        _READER_FAILED = True
        log_warn("EasyOCR khong kha dung -> fallback tesseract:", e.__class__.__name__)
        _READER = None
    return _READER


def _ocr_texts(img):
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
            "raw": "", "tried": [], "tries": 0, "alerts": 0, "done": None, "pinged": False}


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


def _run_recipe(rec, idx):
    from PIL import Image
    import io as _io
    b = _fetch_bytes(rec["thumb"])
    if not b:
        rec["recipes_used"].append(idx)
        return Counter()
    try:
        pil = Image.open(_io.BytesIO(b)).convert("RGB")
    except Exception:
        rec["recipes_used"].append(idx)
        return Counter()
    up, kind = RECIPES[idx]
    img = _apply_recipe(pil, up, kind)
    cnt = Counter()
    for txt in _ocr_texts(img):
        if txt.strip():
            rec["raw"] = (rec["raw"] + " | " + txt.strip().replace("\n", " "))[:600]
        for c in code_from_ocr_text(txt):
            cnt[c] += 1
            rec["reads"][c] = rec["reads"].get(c, 0) + 1
    rec["recipes_used"].append(idx)
    return cnt


def _kw_present(rec):
    if rec.get("reads"):
        return True
    return bool(C.YT_KEYWORD_RE.search((rec.get("raw") or "").upper()))


def _gate(rec):
    for i in range(_GATE_RECIPES):
        if i not in rec["recipes_used"]:
            _run_recipe(rec, i)
    return _kw_present(rec)


def _pick(rec):
    pool = [(c, n) for c, n in rec["reads"].items() if c not in rec["tried"]]
    if not pool:
        return None
    return max(pool, key=lambda cn: (cn[1], len(cn[0])))[0]


def _ensure_candidate(rec):
    while True:
        cand = _pick(rec)
        if cand is not None:
            return cand
        if len(rec["recipes_used"]) >= len(RECIPES):
            return None
        _run_recipe(rec, len(rec["recipes_used"]))


def _ping(rec, note):
    if rec.get("pinged"):
        return
    rec["pinged"] = True
    send(msg_ocr_fail(rec["video_url"], rec["title"], rec["thumb"], rec["tried"], note,
                      len(rec["recipes_used"]), rec["tries"], rec.get("channel_avatar", "")))


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
    deep_used = 0                      # quota = so video PASS gate duoc OCR sau
    for v in bare_videos:              # duet TOAN bo, khong cat truoc
        rec = mem.setdefault(v["video_id"], _new_rec(v))
        rec.setdefault("channel_avatar", v.get("channel_avatar", ""))
        if rec.get("done"):
            continue
        if time.monotonic() >= budget_end:
            log_yt("OCR het budget vong nay -> so video con lai cho vong sau")
            break
        # ===== GATE truoc, QUOTA sau: live/trailer (khong chu CODE) bi chan IM LANG,
        # ===== khong tinh vao deep_used -> khong an slot video ma-trong-anh. =====
        if not _gate(rec):
            rec["done"] = "no_keyword"
            log_yt(f"OCR gate: anh khong co chu CODE/CO DE ({rec['video_id']}) -> bo qua, khong ping (khong tinh quota)")
            changed = True
            continue
        if deep_used >= C.OCR_MAX_IMAGES:
            break                      # du slot video CO CODE -> dung, phan sau vong sau
        deep_used += 1
        while rec["tries"] < C.OCR_MAX_TRIES and time.monotonic() < budget_end:
            cand = _ensure_candidate(rec)
            if cand is None:
                rec["done"] = "exhausted"
                log_warn(f"OCR co chu CODE nhung khong doc duoc ma ({rec['video_id']}) sau "
                         f"{len(rec['recipes_used'])} recipe -> PING nhap tay")
                _ping(rec, "Ảnh CÓ chữ CODE nhưng OCR không đọc được mã sau mọi biến thể.")
                changed = True
                break
            if cand in known:
                rec["done"] = "dup_with_text"
                log_yt(f"OCR skip dup: `{cand}` da co tu tieu de/mo ta (tang text lo) "
                       f"-> bo qua video {rec['video_id']}, khong nhap khong alert")
                changed = True
                break
            rec["tries"] += 1
            note = (f"Lần thử #{rec['tries']}/{C.OCR_MAX_TRIES} · recipe "
                    f"#{rec['recipes_used'][-1] if rec['recipes_used'] else 0} · "
                    f"engine={OCR_ENGINE} · đã loại: {rec['tried'] or 'chưa có'}")
            log_yt(f"OCR thu #{rec['tries']}: `{cand}` (video {rec['video_id']}) [quota {deep_used}/{C.OCR_MAX_IMAGES}]")
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
                log_warn(f"OCR dat gioi han {C.OCR_MAX_TRIES} luot cho {rec['video_id']} "
                         f"ma van bi tu choi -> PING nhap tay")
                _ping(rec, f"Đã thử đủ {C.OCR_MAX_TRIES} lượt mà mọi mã đọc được đều bị "
                           f"server từ chối.")
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
        cand = _pick(rec)
        if cand and cand in known:
            rec["done"] = "dup_with_text"
            log_yt(f"OCR(alert) skip dup: `{cand}` da co tu tang text -> bo qua {rec['video_id']}")
            changed = True
            continue
        _alert(rec, cand or "(chưa đọc được mã)",
               "Chế độ OCR = alert: bot CHỈ báo, không tự nhập. Xem thumbnail để xác nhận.",
               False)
        rec["done"] = "alerted"
        changed = True
    if changed:
        commit_mem(mem)
