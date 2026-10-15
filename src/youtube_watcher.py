# NGUON CODE DUY NHAT cho VN = API (BO HTML: F12 to mobile shell rong; BO RSS: 404 vinh vien).
# 2 tang: A Data API v3 playlistItems(UU..) path co dinh (can YT_API_KEY THAT, qua env);
# B InnerTube browse key PUBLIC (fallback trong config -> khong bao gio mu vi quen secret),
# parse DE QUY gom MOI string chua 'CODE CHUNG' (immune renderer model).
# Quy uoc tra loi: None = tang BI BO QUA (khong key) | [] = CHAY that ma 0 | list = co title.
#
# "3 VIDEO MOI NHAT" (YT_VIDEO_SCAN=3): KHONG cat titles[:3] tho, vi moi video tao ~2 string
# variant ("...CODE CHUNG X..." + "...CODE CHUNG X... 56 giay") -> cat 3 string = ~1.5 video,
# ROT code video 2-3. CACH DUNG: gom het title (limit generous), NHOM theo code (variant cung
# code ve 1 video), lay 3 code distinct DAU = 3 video moi nhat (order Latest giu nguyen).
# Comment # dau file (khong docstring) -> tranh SyntaxError backslash-u luc import.
import os, re, json, requests
from collections import OrderedDict
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
            "maxResults": C.YT_VIDEO_SCAN * 4, "key": C.YT_API_KEY}, timeout=20)
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
    return out

def _via_innertube():
    if not C.INNERTUBE_KEY:
        log("YT InnerTube: khong co key (env + public deu trong) -> BO QUA tang B.")
        return None
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
    _collect_code_titles(j, out, seen, 200)   # generous: de group du variant cua 3 video dau
    log(f"   string chua 'CODE CHUNG' = {len(out)}")
    return out

def _group_by_code(titles):
    """Group cac title variant theo code, giu thu tu video moi nhat.
       Tra (codes, reps): codes = list code distinct theo thu tu; reps = title dai dien
       (title DAU tien gap cho moi code = gan keyword nhat). Title khong trich duoc code -> bo + log."""
    g = OrderedDict()
    for t in titles:
        cs = code_sau_keyword_yt(t)
        if not cs:
            log(f'YT: co "CODE CHUNG" nhung khong trich duoc code (token dau sau keyword < CODE_MIN_LEN?): "{t[:90]}"')
            continue
        c = cs[0]
        if c not in g: g[c] = t
    codes = list(g.keys())[: C.YT_VIDEO_SCAN]
    reps = [g[c] for c in codes]
    for c in codes: log(f'YT hit: "{g[c][:90]}" -> [{c}]')
    return codes, reps

def get_yt_candidates():
    global _dumped_once
    verbose = os.getenv("YT_VERBOSE", "0") == "1"
    a = _via_data_api()
    b = _via_innertube()
    raw_titles = None
    if a: raw_titles = a
    elif b: raw_titles = b
    if not raw_titles:
        sa = "khong key (BO QUA)" if a is None else "chay -> 0 title"
        sb = "khong key (BO QUA)" if b is None else "chay -> 0 title"
        log(f"YT: 0 title. DataAPI: {sa}; InnerTube: {sb}. "
            f"(InnerTube mac dinh chay bang key public fallback; neu 'BO QUA' kiem tra dong "
            f"INNERTUBE_KEY trong config.py.)")
        return []
    codes, reps = _group_by_code(raw_titles)
    if not codes:
        log(f"YT: co {len(raw_titles)} string 'CODE CHUNG' nhung 0 code trich duoc -> "
            f"kiem tra CODE_MIN_LEN / kieu code moi cua NPH.")
        return []
    if verbose or not _dumped_once:
        _dumped_once = True
        log(f"YT: {len(codes)} VIDEO MOI NHAT (toi da {C.YT_VIDEO_SCAN}), tieu de dai dien:")
        for i, t in enumerate(reps, 1): log(f"   [{i:2}] {t[:110]}")
    else:
        log(f"YT: OK ({len(codes)} code tu {C.YT_VIDEO_SCAN} video moi nhat)")
    return codes
