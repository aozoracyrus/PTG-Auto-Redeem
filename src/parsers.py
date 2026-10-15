# PARSE GIFT CODE tu title YouTube. INVARIENT tu ANH (da lieu nhieu video cu + 3 title F12):
#   'CODE CHUNG' LUON CO, code = TOKEN VIET LIEN DINH NGAY PHIA SAU no (khong tu dem chen
#   truoc, khong tach 2 tu). -> Rule khop tam tri anh = LAY TOKEN DAU SAU KEYWORD co do dai
#   >= CODE_MIN_LEN. Dung o token dau (khong quet het) -> tu tieng Anh dung SAU code
#   (HALLOWEEN/UPDATE) khong bao gio duoc xet -> khong nhieu. [A-Z0-9]+ tren .upper() tu vo
#   o ky tu co dau -> vụn tieng Viet chi 1-2 ky, bi min-len bo qua; neu no nam TRUOC code
#   thi vong lap nhien qua va LOG ra (de anh thay, dung doan mo). SWEETHALLOWEEN (glued
#   ASCII) -> token dau >=6 -> bat tu dong, KHONG can them vao CODE_PREFIXES.
# Comment # dau file (khong docstring) -> tranh SyntaxError \u luc import.
import re
from . import config as C
from .utils import log

_MIN = int(getattr(C, "CODE_MIN_LEN", 6))
_KW_RE = re.compile(C.KEYWORD_PATTERN)
_TOKEN_RE = re.compile(r"[A-Z0-9]+")

def code_sau_keyword_yt(title: str) -> list:
    t = (title or "").upper()
    m = _KW_RE.search(t)
    if not m:
        return []
    tail = t[m.end():]                      # TOAN BO doan sau keyword (invariant anh)
    tokens = _TOKEN_RE.findall(tail)
    skipped = []
    for tk in tokens:                       # quet theo thu tu, DUNG o token dau >= MIN
        if len(tk) >= _MIN:
            if skipped:
                log(f"   YT parse: nhay vụn dau {skipped} -> code = '{tk}'")
            return [tk]
        skipped.append(tk)
    return []
