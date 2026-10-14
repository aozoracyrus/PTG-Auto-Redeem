r"""
NGUON CODE DUY NHAT cho VN = parse HTML /channel/<ID>/videos (KHONG con RSS, da 404 tu
ca IP dan cu lan IP runner -> YouTube khong phuc vu feed cho kenh nay).

SUA SCHEMA: title video nam trong JSON RSC o DANG "title":{"runs":[{"text":...}]} HOAC
"title":{"simpleText":...}. Regex cu chi bat "text" -> neu video code dung simpleText thi
VINH VIEN khong thay (giai thich "83 run, 0 CODE CHUNG"). Giay bat CA HAI dang.
Unescape bang json.loads BAT BUOC (RSC escape unicode \u1ea1... -> chay tren tho thi
'\u' bi upper thanh 'U' va khop nham [A-Z0-9]).

>>> DOCSTRING PHAI LA RAW STRING (chu 'r' truoc ''') vi no chua cac chu '\u' va '\u1ea1'
>>> de giai thich escape. Neu bo 'r' thi Python coi '\u' la unicode-escape va NO
>>> SyntaxError luc import (chinh cai loi "truncated \uXXXX escape" anh gap).

DUMP MAU: de ANH THAY bot da vao + doc duoc tieu de that (khong phai tin mu quang).
Mac dinh dump 1 lan o vong dau; bat YT_VERBOSE=1 de dump MOI VONG.
"""
import os, re, json, requests
from . import config as C
from .parsers import code_sau_keyword_yt
from .utils import log

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HDR = {"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6"}
_ID = C.YT_CHANNEL_ID
_dumped_once = False

# bat ca "text" (runs) va "simpleText"  -- raw string de regex giu nguyen backslash
_TEXT_RE = re.compile(r'"(?:text|simpleText)":"((?:[^"\\]|\\.)*)"')

def _unescape_all(html_text):
    out = []
    for raw in _TEXT_RE.findall(html_text):
        try: s = json.loads('"' + raw + '"').strip()
        except Exception: continue
        if s: out.append(s)
    return out

def _titles_from_html(html_text):
    runs = _unescape_all(html_text)
    seen, kw = set(), []
    for t in runs:
        if C.YT_KEYWORD_RE.search(t) and t not in seen:
            seen.add(t); kw.append(t)
    kw = kw[: C.YT_TOP_ENTRIES * 4]
    us, uniq = set(), []
    for t in runs:
        if t not in us: us.add(t); uniq.append(t)
    sample = sorted(uniq, key=len, reverse=True)[:8]   # chuoi DAI NHAT ~ video title
    return kw, sample, len(runs)

def _codes_from_titles(titles):
    codes = []
    for t in titles:
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
        r = requests.get(f"https://www.youtube.com/channel/{_ID}/videos", headers=_HDR, timeout=20)
    except Exception as e:
        log("YT HTML exc:", e.__class__.__name__, e); return []
    if r.status_code != 200:
        log("YT HTML /channel/<ID>/videos http", r.status_code,
            "-> (403/429 = consent/rate-limit tu IP; 404 = id sai; keo dai mai mai -> Plan B Data API)")
        return []
    kw, sample, total = _titles_from_html(r.text or "")

    if total == 0:
        log('YT HTML: 0 text-run khop regex "(?:text|simpleText)" -> SCHEMA YOUTUBE DOI, '
            "can soi Elements tab Videos va sua _TEXT_RE.")
        return []

    if verbose or not _dumped_once:
        _dumped_once = True
        log(f"YT HTML: VAO DUOC, {total} text-run. MAU {len(sample)} chuoi DAI NHAT (title/video):")
        for i, t in enumerate(sample, 1):
            log(f"   [{i}] {t[:120]}")
        log(f"YT HTML: so title chua 'CODE CHUNG' = {len(kw)}  {kw[:5]}")
        if not kw:
            log("YT HTML: chua co video code MOI (binh thuong). Bat YT_VERBOSE=1 de dump moi vong.")
    else:
        if not kw:
            log(f"YT HTML: OK ({total} text-run) nhung chua co title nao chua 'CODE CHUNG'.")
    return _codes_from_titles(kw)
