"""
HAI HÀM PARSE GIFT CODE. CẢ HAI KHÔNG RÀNG BUỘC ĐỘ DÀI & KHÔNG CẦN SỐ.
  - YouTube : neo = "CODE CHUNG" + prefix PT (title NPH viết tay, language-independent).
  - Web     : neo = DÒNG CHỨA NGÀY dd/mm/yyyy (KHÔNG dùng chuỗi label "Valid until"
              vì label bị dịch EN/TH/VN -> mong manh; NGÀY thì không bao giờ dịch).
Title THẬT không có "" / () quanh code; bot KHÔNG dựa vào ngoặc.
"""
import re
from . import config as C

# ---- NEO 1: YouTube (positional + prefix), KHÔNG đổi so bản trước ----
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

# ---- NEO 2: Web modal, look-back theo DÒNG chứa NGÀY ----
# Cấu trúc card (quan sát từ hình EN lẫn TH):  chip-code / badge-hethan / HEADING-CODE /
#   <label-ngôn-ngữ> dd/mm/yyyy / nút-select.  Heading code (in-hoa ASCII) luôn nằm
#   <=2 dòng phía trên dòng chứa ngày; badge & label (Title-case / có dấu) KHÔNG phải
#   [A-Z0-9] nên không bao giờ bị chọn nhầm; chip-code nằm xa hơn window 2 dòng -> rớt.
# => lấy được code dù label là "Valid until" | "ใช้ได้ถึง" | "Có hiệu lực đến" | bất kỳ.
def code_gan_ngay_web(text: str) -> list:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    seen, out = set(), []
    for i, ln in enumerate(lines):
        dm = C.DATE_RE.search(ln)
        if not dm:
            continue
        cand = None
        # (a) cùng dòng, phần TRƯỚC ngày
        pre = C.TOK_RE.findall(ln[:dm.start()])
        if pre:
            cand = pre[-1]
        # (b) nhìn ngược tối đa 2 dòng, lấy token in-hoa gần ngày nhất
        if not cand:
            for back in (1, 2):
                j = i - back
                if j < 0:
                    break
                toks = C.TOK_RE.findall(lines[j])
                if toks:
                    cand = toks[-1]
                    break
        if cand:
            cu = cand.upper()
            if cu not in seen:
                seen.add(cu); out.append(cu)
    return out
