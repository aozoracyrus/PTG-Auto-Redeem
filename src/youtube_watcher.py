r"""
NGUON CODE DUY NHAT cho VN = API (BO parse HTML: F12 to mobile shell rong).

2 tang:
  A. Data API v3 playlistItems(UU..) -> items[].snippet.title. Path CO DINH, Google
     document, KHONG doan schema, KHONG phu thuoc params/A-B. Can YT_API_KEY (secret).
     -> DAY LA DUONG BEN NHAT: dung API duoc bao tuong thich, thay vi reverse-engineer.
  B. InnerTube browse (key PUBLIC, khong can secret) -> parse DE QUY. Nhuung params
     tab Videos la hang cong dong -> CO RUI RO YouTube doi. Tang nay DANG FAIL o vong
     nay; khoi bang chan doan duoi de biet fail o dau, va/hoac anh chup F12 'browse'
     de toi hardcode exact (bien doan thanh evidence).

Chan doan InnerTube in MOI VONG (khong can YT_VERBOSE): http / len / so videoId /
snippet quanh videoId dau -> phan biet 3 ca fail ma khong doan nua.
Keyword 'CODE CHUNG' + prefix 'PT' chay tren title da trich (parsers).
Docstring RAW STRING de tranh loi unicode-escape luc import.
"""
import os, re, json, requests
from . import config as C
from .parsers import code_sau_keyword_yt
from .utils import log

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HDR = {"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6"}

_dumped_once = False

def _title_from_obj(d):
    t = d.get("title")
    if isinstance(t, str):
        return t.strip()
    if isinstance(t, dict):
        runs = t.get("runs")
        if isinstance(runs, list) and runs and isinstance(runs[0], dict):
            return str(runs[0].get("text", "")).strip()
        st = t.get("simpleText")
        if isinstance(st, str):
            return st.strip()
    return ""

def _walk_titles(obj, out, seen, limit):
    if len(out) >= limit:
        return
    if isinstance(obj, dict):
        if "videoId" in obj:
            t = _title_from_obj(obj)
            if t and t not in seen:
                seen.add(t); out.append(t)
        for v in obj.values():
            _walk_titles(v, out, seen, limit)
    elif isinstance(obj, list):
        for v in obj:
            _walk_titles(v, out, seen, limit)

def _via_data_api():
    if not C.YT_API_KEY:
        return None                                   # None = khong key -> bo qua tang A
    try:
        r = requests.get(C.DATA_API_PLAYLIST, params={
            "part": "snippet", "playlistId": C.YT_UPLOADS_ID,
            "maxResults": C.YT_VIDEO_SCAN, "key": C.YT_API_KEY}, timeout=20)
    except Exception as e:
        log("YT DataAPI exc:", e.__class__.__name__, e); return []
    if r.status_code != 200:
        log("YT DataAPI http", r.status_code, "->", (r.text or "")[:200]); return []
    try:
        j = r.json()
    except Exception:
        log("YT DataAPI khong phai JSON"); return []
    out, seen = [], set()
    for it in (j.get("items") or []):
        t = str((it.get("snippet") or {}).get("title", "")).strip()
        if t and t not in seen:
            seen.add(t); out.append(t)
        if len(out) >= C.YT_VIDEO_SCAN:
            break
    return out

def _via_innertube():
    body = {
        "context": {"client": {"clientName": "WEB", "clientVersion": C.INNERTUBE_VERSION,
                                "hl": "vi", "gl": "VN", "platform": "DESKTOP"}},
        "browseId": C.YT_CHANNEL_ID,
        "params":   C.INNERTUBE_PARAMS_VIDEOS,
    }
    try:
        r = requests.post(C.INNERTUBE_BROWSE, params={"key": C.INNERTUBE_KEY, "prettyPrint": "false"},
                          json=body, headers={**_HDR, "Content-Type": "application/json"}, timeout=20)
    except Exception as e:
        log("YT InnerTube exc:", e.__class__.__name__, e); return []
    raw = r.text or ""
    vid_count = raw.count('"videoId"')
    # --- CHAN DOAN IN MOI VONG (khong can YT_VERBOSE) ---
    log(f"YT InnerTube DIAG: http={r.status_code} len={len(raw)} videoId={vid_count}")
    if r.status_code != 200:
        log("   body[:200]=", repr(raw[:200])); return []
    try:
        j = r.json()
    except Exception:
        log("   khong phai JSON; body[:200]=", repr(raw[:200])); return []
    out, seen = [], set()
    _walk_titles(j, out, seen, C.YT_VIDEO_SCAN)
    if vid_count > 0 and not out:
        # video co nhung title khong nam o 'title' -> in snippet de lock _title_from_obj
        i = raw.find('"videoId"')
        log("   co videoId nhung 0 title -> snippet quanh videoId dau (de sua _title_from_obj):")
        log("   ", repr(raw[max(0, i-40): i+260]))
    elif vid_count == 0:
        # 200 nhung khong co video nao -> params tab Videos sai/cu -> in dau blob de nhan dien
        log("   200 nhung 0 videoId -> PARAMS tab Videos cu/sai. Snippet dau blob:")
        log("   ", repr(raw[:300]))
    return out

def _codes_from_titles(titles):
    codes = []
    for t in titles:
        if not C.YT_KEYWORD_RE.search(t):
            continue
        found = code_sau_keyword_yt(t)
        if found:
            log(f'YT hit: "{t[:90]}" -> {found}'); codes.extend(found)
        else:
            log(f'YT: co "CODE CHUNG" nhung khong trich duoc code '
                f'(token sau khong mo dau prefix {C.CODE_PREFIXES}?): "{t[:90]}"')
    seen, out = set(), []
    for c in codes:
        if c not in seen: seen.add(c); out.append(c)
    return out

def get_yt_candidates():
    global _dumped_once
    verbose = os.getenv("YT_VERBOSE", "0") == "1"

    titles, via = None, None
    a = _via_data_api()
    if a is not None:
        titles, via = a, "DATA_API"
    if not titles:
        b = _via_innertube()
        if b:
            titles, via = b, "INNERTUBE"
        elif titles is None:
            titles, via = [], "NONE"

    if not titles:
        log("YT: 0 title. DataAPI=" + ("co key" if C.YT_API_KEY else "khong key") +
            "; InnerTube da chay (xem DIAG o tren). Duong het doan = tao YT_API_KEY (Data API).")
        return []

    n_kw = sum(1 for t in titles if C.YT_KEYWORD_RE.search(t))
    if verbose or not _dumped_once:
        _dumped_once = True
        log(f"YT [{via}]: trich {len(titles)} TIEU DE VIDEO (moi nhat):")
        for i, t in enumerate(titles, 1):
            flag = "  <== CODE CHUNG" if C.YT_KEYWORD_RE.search(t) else ""
            log(f"   [{i:2}] {t[:110]}{flag}")
        log(f"YT [{via}]: so tieu de chua 'CODE CHUNG' = {n_kw}")
    else:
        log(f"YT [{via}]: OK ({len(titles)} tieu de) - so chua 'CODE CHUNG' = {n_kw}")
    return _codes_from_titles(titles)
