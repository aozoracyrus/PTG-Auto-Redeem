"""Parse giftcode từ title YouTube: neo = cụm "CODE CHUNG"; mã = token in-hoa mở đầu
   prefix (PT...) đứng NGAY SAU neo. Không ràng buộc độ dài, không cần chữ số,
   không dựa ngoặc (title thật không có "" / ())."""
import re
from . import config as C

_PREFIXES = [p.upper() for p in C.CODE_PREFIXES if p]
if _PREFIXES:
    _ALT = "|".join(re.escape(p) for p in _PREFIXES)
    _YT_AFTER_KW = re.compile(C.KEYWORD_PATTERN + r"([^A-Z0-9]*)((?:" + _ALT + r")[A-Z0-9]*)")
else:
    _YT_AFTER_KW = re.compile(C.KEYWORD_PATTERN + r"([^A-Z0-9]*)([A-Z0-9]+)")

def code_sau_keyword_yt(title: str) -> list:
    t = (title or "").upper()
    m = _YT_AFTER_KW.search(t)
    return [m.group(2)] if (m and m.group(2)) else []
