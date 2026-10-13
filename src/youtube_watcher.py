import os, re, html, requests
from . import config as C
from .parsers import code_sau_keyword_yt
from .utils import log

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_CID_CACHE = os.path.join(os.getcwd(), C.YT_CHANNEL_ID_FILE)

def _read_cached_cid():
    try:
        if os.path.exists(_CID_CACHE):
            v = open(_CID_CACHE, encoding="utf-8").read().strip()
            if v.startswith("UC"): return v
    except Exception: pass
    return None

def _write_cached_cid(cid):
    try: open(_CID_CACHE, "w", encoding="utf-8").write(cid + "\n")
    except Exception: pass

def resolve_channel_id():
    """Lấy UC... từ trang /@handle (desktop). Cache vào yt_channel_id.txt khỏi fetch lại."""
    cid = _read_cached_cid()
    if cid: return cid
    try:
        r = requests.get(f"https://www.youtube.com/{C.YT_HANDLE}", headers={"User-Agent": UA}, timeout=15)
        m = re.search(r'"channelId":"(UC[\w-]{20,})"', r.text) or \
            re.search(r'"externalId":"(UC[\w-]{20,})"', r.text)
        if m:
            _write_cached_cid(m.group(1)); log("resolved channel id:", m.group(1)); return m.group(1)
        log("YT: không resolve được channel id từ HTML (trang đổi cấu trúc?)")
    except Exception as e:
        log("YT resolve lỗi:", e)
    return None

def get_yt_candidates():
    """
    Trả về list giftcode từ title của N video MỚI NHẤT. Chiến lược positional:
      1) title phải chứa 'CODE CHUNG' (YT_KEYWORD_RE, re.I) -> lọc video không-code.
      2) lấy token in-hoa mở đầu PREFIX đứng ngay sau keyword (code_sau_keyword_yt).
    Vì NPH luôn đặt code NGAY SAU 'CODE CHUNG', bước 2 cho ra đúng 1 mã, bất kể
    code có số (PT26BATPET) hay không số (PTGIANTVEGGIE), bất kể độ dài.
    """
    cid = resolve_channel_id()
    if not cid:
        log("YT watcher: CHƯA có channel id -> bỏ qua vòng này (bot vẫn chạy web-only). "
            "Xem README mục 'Lấy Channel ID'.")
        return []
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    codes = []
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        if r.status_code != 200:
            log("YT RSS HTTP", r.status_code); return []
        entries = re.findall(r"<entry>(.*?)</entry>", r.text, re.DOTALL)[: C.YT_TOP_ENTRIES]
        for ent in entries:
            tm = re.search(r"<title>(.*?)</title>", ent, re.DOTALL)
            if not tm: continue
            title = html.unescape(tm.group(1)).strip()
            if not C.YT_KEYWORD_RE.search(title):
                continue                                  # không có 'CODE CHUNG' -> bỏ (lọc nhiễu)
            found = code_sau_keyword_yt(title)            # positional + prefix
            if found:
                log(f'YT hit: "{title[:90]}" -> {found}')
                codes.extend(found)
            else:
                log(f'YT: có "CODE CHUNG" nhưng không trích được code (token sau không mở đầu '
                    f'prefix {C.CODE_PREFIXES}?): "{title[:90]}"')
    except Exception as e:
        log("YT watcher lỗi:", e)
    seen, out = set(), []
    for c in codes:
        if c not in seen: seen.add(c); out.append(c)
    return out
