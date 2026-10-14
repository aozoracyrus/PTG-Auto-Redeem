"""
NGUON CODE DUY NHAT cho VN = parse HTML /channel/<ID>/videos (KHONG con RSS).
Ly do bo RSS: 404 tu ca IP dan cu lan IP runner -> YouTube khong phuc vu feed cho kenh
nay (khong phai loi IP/transient) -> goi lai mai mai 404, backoff cung vo ich.
HTML thi KHAC: la trang web thuong, YouTube phuc vu binh thuong (anh mo /@.../videos
thay video; runner truoc day fetch HTML 200 de resolve id). Tab Videos sort Latest
=> video code moi nhat o dau => HTML initial render (RSC) chua no, khong can pagination.

Title video nam trong JSON RSC o dang "title":{"runs":[{"text":"<FULL TITLE>"}]}.
Ta findall moi "text":"...", UNESCAPE bang json.loads (BAT BUOC: RSC escape unicode
\u1ea1... -> neu chay regex tren tho thi '\\u' bi upper thanh 'U' va khop nham [A-Z0-9]),
roi loc chu chua 'CODE CHUNG' => chi con title video co code (UI/comment khong chua
keyword -> tu bi loai, khong can blacklist). Sau do chay code_sau_keyword_yt (prefix PT).

Plan B (chi khi HTML break - YouTube doi schema): YouTube Data API v3 (can secret
YT_API_KEY, goi playlistItems theo channelId, quota 10k/ngay du, khong dung feed/HTML).
Bao toi neu toi nuoc do; hien tai HTML du va khong can them secret.
"""
import re, json, requests
from . import config as C
from .parsers import code_sau_keyword_yt
from .utils import log

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HDR = {"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6"}
_ID = C.YT_CHANNEL_ID

def _titles_from_html(html_text):
    """Tra (titles_with_keyword, total_text_runs) de log phan biet 2 case:
       - total=0  -> schema YouTube doi (regex "text" kh con khop) -> CAN SUA.
       - total>0 nhung 0 chua 'CODE CHUNG' -> binh thuong, chua co video code MOI."""
    total, kept = 0, []
    for raw in re.findall(r'"text":"((?:[^"\\]|\\.)*)"', html_text):
        total += 1
        try: s = json.loads('"' + raw + '"').strip()
        except Exception: continue
        if s and C.YT_KEYWORD_RE.search(s): kept.append(s)
    seen, res = set(), []
    for t in kept:
        if t not in seen: seen.add(t); res.append(t)
    return res[: C.YT_TOP_ENTRIES * 4], total

def _codes_from_titles(titles):
    codes = []
    for t in titles:
        found = code_sau_keyword_yt(t)            # positional + prefix PT
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
    try:
        r = requests.get(f"https://www.youtube.com/channel/{_ID}/videos",
                         headers=_HDR, timeout=20)
    except Exception as e:
        log("YT HTML exc:", e.__class__.__name__, e); return []
    if r.status_code != 200:
        log("YT HTML /channel/<ID>/videos http", r.status_code,
            "-> (403/429 = co the bi consent/rate-limit tu IP nay; 404 = id sai; "
            "neu keu mai mai thi chuyen Plan B Data API)")
        return []
    titles, total = _titles_from_html(r.text or "")
    if total == 0:
        log("YT HTML: 0 text-run nao khop regex \"text\" -> SCHEMA YOUTUBE DOI, "
            "can sua _titles_from_html (soi Elements tab Videos, tim chu 'CODE CHUNG').")
        return []
    if not titles:
        log(f"YT HTML: OK ({total} text-run) nhung chua co title nao chua 'CODE CHUNG' "
            f"-> binh thuong, kenh chua dang video code MOI.")
        return []
    return _codes_from_titles(titles)
