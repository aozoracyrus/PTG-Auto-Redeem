# TRICH MA GIFT TU TIEU DE / MO TA / TEXT OCR.
#
# BUG CAT MA DA SUA: ban cu co nhom "vun" tham lam giua neo va ma -> nuot 5 ky tu dau
#   (PT26BATPET->BATPET, SWEETHALLOWEEN->HALLOWEEN) -> nhap ma cut -> 2106 -> spam probe.
# LUA HIEN TAI (dung lenh ban: lay NGAY SAU neo, khong bo qua gi):
#   1) STRICT: token [A-Z0-9]{>=CODE_MIN_LEN} DINH ngay sau neo (chi cho phep dau cach /
#      dau cau). KHONG nhom vun => KHONG cat duoc ma.
#   2) JOIN (CHI khi STRICT truot = anh OCR gian cach chu): ghep manh >=2 ky tu lien tiep,
#      dung o manh 1 ky tu (chu Viet vo dau), uu tien mo dau prefix roi den chua so;
#      ung vien ghep phai chua SO hoac mo dau prefix (chong rac GAMEPLAYTOGETHER).
# NEO: KW = C[OÔ][\s.:|_-]*D[EÉ] phu CODE / CÔ DÉ / CÔ.DÉ / CO DE / CODE: ... ; tuy chon
#   "CHUNG" di sau. Muon bo CÔ DÉ: _KW = r"CO[\s.:|_-]*DE".
import re
from . import config as C

_MIN = int(getattr(C, "CODE_MIN_LEN", 6))
_PREFIXES = [p.upper() for p in getattr(C, "CODE_PREFIXES", []) if p]
_KW = r"C[OÔ][\s.:|_-]*D[EÉ]"

_KW_POS_RE = re.compile(r"(?<![A-Z0-9])" + _KW + r"[\s:|_-]*(?:CHUNG[\s:|_-]*)?")
_TOK_RE = re.compile(r"[A-Z0-9]{%d,}" % _MIN)
_PIECE_RE = re.compile(r"[A-Z0-9]+")

_JOIN_MAX_PIECES = 6
_JOIN_MAX_LEN = 24


def _guard(tok):
    if any(ch.isdigit() for ch in tok):
        return True
    return any(tok.startswith(p) for p in _PREFIXES)


def _join_candidates(rest):
    pieces = _PIECE_RE.findall(rest[:80])
    out = []
    for i, p in enumerate(pieces):
        if len(p) < 2:
            continue
        glued = ""
        n = 0
        for q in pieces[i:]:
            if len(q) < 2:
                break
            glued += q
            n += 1
            if n >= _JOIN_MAX_PIECES or len(glued) >= _JOIN_MAX_LEN:
                break
        if len(glued) >= _MIN and glued not in out:
            out.append(glued)
    return out


def _choose(joined):
    for tok in joined:
        if any(tok.startswith(p) for p in _PREFIXES):
            return tok
    for tok in joined:
        if any(ch.isdigit() for ch in tok):
            return tok
    return ""


def _all_candidates(t):
    out = []
    for m in _KW_POS_RE.finditer(t):
        rest = t[m.end():]
        mt = _TOK_RE.match(rest)
        if mt:
            tok = mt.group(0)
        else:
            tok = _choose(_join_candidates(rest))
            if tok and not _guard(tok):
                tok = ""
        if tok and tok not in out:
            out.append(tok)
    return out


def code_sau_keyword_yt(title):
    cands = _all_candidates((title or "").upper())
    return [cands[0]] if cands else []


def code_from_ocr_text(text):
    return _all_candidates((text or "").upper())
