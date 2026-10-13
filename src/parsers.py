import re
from . import config as C

# ---- NEO 1: YouTube (positional + prefix PT) ----
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

# ---- NEO 2: Web modal, look-back theo DONG chua NGAY dd/mm/yyyy ----
# Card: chip / badge / HEADING-CODE(in-hoa) / <label bat ky> dd/mm/yyyy / nut.
# Heading code luon <=2 dong phia truoc dong ngay; label/badge (co dau/Title-case)
# khong phai [A-Z0-9] -> khong bi chon nham. => lay duoc code du label tieng Viet la gi.
def code_gan_ngay_web(text: str) -> list:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    seen, out = set(), []
    for i, ln in enumerate(lines):
        dm = C.DATE_RE.search(ln)
        if not dm: continue
        cand = None
        pre = C.TOK_RE.findall(ln[:dm.start()])
        if pre: cand = pre[-1]
        if not cand:
            for back in (1, 2):
                j = i - back
                if j < 0: break
                toks = C.TOK_RE.findall(lines[j])
                if toks: cand = toks[-1]; break
        if cand:
            cu = cand.upper()
            if cu not in seen: seen.add(cu); out.append(cu)
    return out
