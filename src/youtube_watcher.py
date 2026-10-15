# NGUON CODE DUY NHAT cho VN = API (BO HTML: F12 to mobile shell rong; BO RSS: 404 vinh vien).
# 2 tang: A Data API v3 playlistItems(UU..) path co dinh (can YT_API_KEY); B InnerTube browse
# key PUBLIC, parse DE QUY gom MOI string chua 'CODE CHUNG' (immune renderer model - bug cu
# la yeu cau videoId+title cung dict, model moi tach ra 2 dict -> 0 title). Comment # dau file.
import os, re, json, requests
from . import config as C
from .parsers import code_sau_keyword_yt
from .utils import log

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HDR = {"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6"}
_dumped_once = False

def _collect_code_titles(obj, out, seen, limit):
    if len(out) >= limit: return
    if isinstance(obj, str):
        if C.YT_KEYWORD_RE.search(obj) and obj not in seen:
            seen.add(obj); out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values(): _collect_code_titles(v, out, seen, limit)
    elif isinstance(obj, list):
        for v in obj: _collect_code_titles(v, out, seen, limit)

def _via_data_api():
    if not C.YT_API_KEY: return None
    try:
        r = requests.get(C.DATA_API_PLAYLIST, params={
            "part": "snippet", "playlistId": C.YT_UPLOADS_ID,
            "maxResults": C.YT_VIDEO_SCAN, "key": C.YT_API_KEY}, timeout=20)
    except Exception as e:
        log("YT DataAPI exc:", e.__class__.__name__, e); return []
    if r.status_code != 200:
        log("YT DataAPI http", r.status_code, "->", (r.text or "")[:200]); return []
    try: j = r.json()
    except Exception: log("YT DataAPI khong phai JSON"); return []
    out, seen = [], set()
    for it in (j.get("items") or []):
        t = str((it.get("snippet") or {}).get("title", "")).strip()
        if t and t not in seen: seen.add(t); out.append(t)
        if len(out) >= C.YT_VIDEO_SCAN: break
    return out

def _via_innertube():
    if not C.INNERTUBE_KEY:
        log("YT InnerTube: INNERTUBE_KEY trong -> bo qua tang B (dat secret INNERTUBE_KEY hoac YT_API_KEY).")
        return []
    body = {"context": {"client": {"clientName": "WEB", "clientVersion": C.INNERTUBE_VERSION,
                                    "hl": "vi", "gl": "VN", "platform": "DESKTOP"}},
            "browseId": C.YT_CHANNEL_ID, "params": C.INNERTUBE_PARAMS_VIDEOS}
    try:
        r = requests.post(C.INNERTUBE_BROWSE, params={"key": C.INNERTUBE_KEY, "prettyPrint": "false"},
                          json=body, headers={**_HDR, "Content-Type": "application/json"}, timeout=20)
    except Exception as e:
        log("YT InnerTube exc:", e.__class__.__name__, e); return []
    raw = r.text or ""
    log(f"YT InnerTube DIAG: http={r.status_code} len={len(raw)} videoId={raw.count(chr(34)+'videoId'+chr(34))}")
    if r.status_code != 200:
        log("   body[:200]=", repr(raw[:200])); return []
    try: j = r.json()
    except Exception: log("   khong phai JSON; body[:200]=", repr(raw[:200])); return []
    out, seen = [], set()
    _collect_code_titles(j, out, seen, 200)
    log(f"   string chua 'CODE CHUNG' = {len(out)}")
    return out

def _codes_from_titles(titles):
    codes = []
    for t in titles:
        found = code_sau_keyword_yt(t)
        if found: log(f'YT hit: "{t[:90]}" -> {found}'); codes.extend(found)
        else: log(f'YT: co "CODE CHUNG" nhung khong trich duoc code (token dau sau keyword < CODE_MIN_LEN?): "{t[:90]}"')
    seen, out = set(), []
    for c in codes:
        if c not in seen: seen.add(c); out.append(c)
    return out

def get_yt_candidates():
    global _dumped_once
    verbose = os.getenv("YT_VERBOSE", "0") == "1"
    titles, via = None, None
    a = _via_data_api()
    if a is not None: titles, via = a, "DATA_API"
    if not titles:
        b = _via_innertube()
        if b: titles, via = b, "INNERTUBE"
        elif titles is None: titles, via = [], "NONE"
    if not titles:
        log("YT: 0 title. DataAPI=" + ("co key" if C.YT_API_KEY else "khong key") +
            "; InnerTube da chay (xem DIAG). Duong het doan = tao YT_API_KEY (Data API).")
        return []
    n_kw = len(titles)
    if verbose or not _dumped_once:
        _dumped_once = True
        log(f"YT [{via}]: trich {n_kw} TITLE CHUA 'CODE CHUNG':")
        for i, t in enumerate(titles[:C.YT_VIDEO_SCAN], 1): log(f"   [{i:2}] {t[:110]}")
    else:
        log(f"YT [{via}]: OK ({n_kw} title 'CODE CHUNG')")
    return _codes_from_titles(titles)
