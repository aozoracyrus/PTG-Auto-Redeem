r"""
NGUON CODE DUY NHAT cho VN = API (BO BO parse HTML /@handle/videos).

VI SAO BO HTML: F12 Quetta anh paste cho thay trang tra ve la MOBILE SHELL rong
(<body class="loading"> + spinner + ytm-* + favicon m.youtube.com), KHONG co
self.__next_f, KHONG co ytInitialData, KHONG co videoRenderer. Danh sach video duoc
fetch SAU bang XHR (InnerTube browse). -> Moi no luc parse initial HTML (nhay thuong
hay unescape RSC) VINH VIEN 0 renderer, vi trong HTML do khong co renderer de bat.
Day khong phai "schema doi" - la ban chat YouTube: data video o API, khong o HTML.

2 TANG API (khong dung HTML):
  A. Data API v3 playlistItems(UU..) -> items[].snippet.title. Path CO DINH, document,
     KHONG doan schema. Can YT_API_KEY (secret). Khong co key -> skip tang nay.
  B. InnerTube browse(browseId=UC.., params=tab Videos, key PUBLIC) -> parse DE QUY tim
     moi object co videoId+title -> chong vo khi YouTube A/B doi duong dan renderer.
     KHONG can secret -> chay ngay. params/clientVersion = hang chuan cong dong (neu fail,
     buoc tiep la anh chup F12 request 'browse' Payload+Response de toi hardcode exact,
     KHONG doan nua).

Keyword 'CODE CHUNG' + prefix 'PT' chay tren tung title da trich (parsers.code_sau_keyword_yt).
Docstring nay la RAW STRING de tranh loi unicode-escape luc import.
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
    """Lay text tu {title:{runs:[{text}]}} hoac {title:{simpleText}} hoac {title:'str'}."""
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
    """De quy qua JSON, moi dict co videoId + title -> lay title. Chong vo schema renderer
       (khong hardcode duong dan contents.twoColumn...videoRenderer)."""
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
    """Tang A: Data API v3 playlistItems theo uploads-playlist = dung tab Videos."""
    if not C.YT_API_KEY:
        return None                                   # None = khong co key -> bo qua tang nay
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
        sn = it.get("snippet") or {}
        t = str(sn.get("title", "")).strip()
        if t and t not in seen:
            seen.add(t); out.append(t)
        if len(out) >= C.YT_VIDEO_SCAN:
            break
    return out

def _via_innertube():
    """Tang B: InnerTube browse tab Videos, key public, parse de quy."""
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
    if r.status_code != 200:
        log("YT InnerTube http", r.status_code, "->", (r.text or "")[:200]); return []
    try:
        j = r.json()
    except Exception:
        log("YT InnerTube khong phai JSON"); return []
    out, seen = [], set()
    _walk_titles(j, out, seen, C.YT_VIDEO_SCAN)
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
    if a is not None:                                  # co key -> dung tang A (kể cả rỗng cũng tin A)
        titles, via = a, "DATA_API"
    if not titles:                                     # khong co key HOAC A tra rong -> thu B
        b = _via_innertube()
        if b:
            titles, via = b, "INNERTUBE"
        elif titles is None:
            titles, via = [], "NONE"

    if not titles:
        log("YT API: CA 2 tang deu 0 title (DataAPI " +
            ("co key" if C.YT_API_KEY else "khong key") +
            " / InnerTube da thu). -> chup F12 request 'browse' (Payload+Response) de hardcode exact, KHONG doan.")
        return []

    n_kw = sum(1 for t in titles if C.YT_KEYWORD_RE.search(t))
    if verbose or not _dumped_once:
        _dumped_once = True
        log(f"YT [{via}]: trich {len(titles)} TIEU DE VIDEO (moi nhat):")
        for i, t in enumerate(titles, 1):
            flag = "  <== CODE CHUNG" if C.YT_KEYWORD_RE.search(t) else ""
            log(f"   [{i:2}] {t[:110]}{flag}")
        log(f"YT [{via}]: so tieu de chua 'CODE CHUNG' = {n_kw}")
        if n_kw == 0:
            log(f"YT [{via}]: {len(titles)} video moi nhat chua co video code MOI (binh thuong)."
                + (" Bat YT_VERBOSE=1 de dump moi vong." if not verbose else ""))
    else:
        log(f"YT [{via}]: OK ({len(titles)} tieu de) - so chua 'CODE CHUNG' = {n_kw}")
    return _codes_from_titles(titles)
