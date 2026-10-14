r"""
NGUON CODE DUY NHAT cho VN = parse HTML /@handle/videos (KHONG RSS, KHONG channel id).

VI SAO KHONG sort-by-length nhu cu: ham cu gom moi "text"/"simpleText" roi sap xep theo
do dai -> cau huong dan phim tat cua YouTube ("micro", "tua di", "phu de"...) DAI HON
tieu de video -> chim top, dump ra toan rac. CACH DUNG: tieu de video nam TRONG object
"videoRenderer", text UI thi khong. Nen locate "videoRenderer", cat cua so YT_WINDOW ky
tu sau no, match "title" ben TRONG cua so -> loai sach text UI, dump ra dung TIEU DE VIDEO.

Format RSC (minified): "title":{"runs":[{"text":"..."}]} HOAC "title":{"simpleText":"..."}.
Unescape bang json.loads (RSC escape unicode; chay tren tho thi backslash-u bi upper thanh
'U' va khop nham [A-Z0-9]). Docstring nay la RAW STRING de tranh loi unicode-escape luc import.

Quet YT_VIDEO_SCAN (15) video dau = 15 video moi nhat (tab Videos sort Latest).
Dump: vong dau in du 15 tieu de (bang chung "da vao + doc"); cac vong sau chi 1 dong tom
tat, tru khi YT_VERBOSE=1 (dump moi vong). Keyword 'CODE CHUNG' + prefix 'PT' van chay
tren tung tieu de da trich (parsers.code_sau_keyword_yt).
"""
import os, re, json, requests
from . import config as C
from .parsers import code_sau_keyword_yt
from .utils import log

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HDR = {"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6"}

_VR_RE     = re.compile(r'"videoRenderer"')
_TITLE_RUN = re.compile(r'"title"\s*:\s*\{\s*"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"')
_TITLE_SIM = re.compile(r'"title"\s*:\s*\{\s*"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"')

_dumped_once = False

def _unescape(raw):
    try: return json.loads('"' + raw + '"').strip()
    except Exception: return ""

def _extract_video_titles(html_text, limit):
    """Tra list tieu de video (da unescape), toi da `limit`, theo thu tu xuat hien.
       Chi lay title nam trong cua so sau moi "videoRenderer" -> text UI bi loai."""
    titles, seen = [], set()
    for m in _VR_RE.finditer(html_text):
        win = html_text[m.end(): m.end() + C.YT_WINDOW]
        t = ""
        mr = _TITLE_RUN.search(win)
        if mr: t = _unescape(mr.group(1))
        if not t:
            ms = _TITLE_SIM.search(win)
            if ms: t = _unescape(ms.group(1))
        if t and t not in seen:
            seen.add(t); titles.append(t)
        if len(titles) >= limit:
            break
    return titles

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
    try:
        r = requests.get(f"https://www.youtube.com/{C.YT_HANDLE}/videos", headers=_HDR, timeout=20)
    except Exception as e:
        log("YT HTML exc:", e.__class__.__name__, e); return []
    if r.status_code != 200:
        log("YT HTML /@handle/videos http", r.status_code,
            "-> (403/429 = consent/rate-limit tu IP; keo dai mai mai -> Plan B Data API)")
        return []

    titles = _extract_video_titles(r.text or "", C.YT_VIDEO_SCAN)
    if not titles:
        log("YT HTML: 0 videoRenderer/title nao trich duoc -> SCHEMA DOI, "
            "soi Elements tab Videos, tim chu 'videoRenderer' va sua _VR_RE/_TITLE_RUN.")
        return []

    n_kw = sum(1 for t in titles if C.YT_KEYWORD_RE.search(t))
    if verbose or not _dumped_once:
        _dumped_once = True
        log(f"YT HTML: VAO DUOC {C.YT_HANDLE}, trich {len(titles)} TIEU DE VIDEO (moi nhat):")
        for i, t in enumerate(titles, 1):
            flag = "  <== CODE CHUNG" if C.YT_KEYWORD_RE.search(t) else ""
            log(f"   [{i:2}] {t[:110]}{flag}")
        log(f"YT HTML: so tieu de chua 'CODE CHUNG' = {n_kw}")
        if n_kw == 0:
            log(f"YT HTML: {len(titles)} video moi nhat chua co video code MOI (binh thuong)."
                + (" Bat YT_VERBOSE=1 de dump moi vong." if not verbose else ""))
    else:
        log(f"YT HTML: OK ({len(titles)} tieu de) - so chua 'CODE CHUNG' = {n_kw}")
    return _codes_from_titles(titles)
