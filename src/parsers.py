# TRICH MA GIFT.
# NEO: C[OÔ][\s.:|_-]*D[EÉ] + "CHUNG" tuỳ chọn
#   => CODE / CODE CHUNG / CÔ DÉ / CÔ DÉ CHUNG / CO DE / CODE: ...
#
# STRICT: token [A-Z0-9]{>=6} dính ngay sau neo (cho title/desc).
# JOIN: chỉ cho OCR (khi chữ bị giãn cách), ghép mảnh >=2 ký tự,
#   dừng ở mảnh 1 ký tự (chữ Việt vỡ dấu), chốt: prefix known HOẶC (chứa số VÀ len>=10).
#
# MA TRAN:
#   Title:  strict only (không join) -> không sinh mã giả từ ngày tháng
#   Desc:   strict only
#   OCR:    strict + join (ảnh pill giãn chữ)
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
_JOIN_MIN_LEN_WITH_DIGIT = 10


def _guard_join(tok):
    if any(tok.startswith(p) for p in _PREFIXES):
        return True
    return len(tok) >= _JOIN_MIN_LEN_WITH_DIGIT and any(ch.isdigit() for ch in tok)


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


def _all_candidates(t, allow_join):
    out = []
    for m in _KW_POS_RE.finditer(t):
        rest = t[m.end():]
        mt = _TOK_RE.match(rest)
        if mt:
            tok = mt.group(0)
        elif allow_join:
            tok = _choose(_join_candidates(rest))
            if tok and not _guard_join(tok):
                tok = ""
        else:
            tok = ""
        if tok and tok not in out:
            out.append(tok)
    return out


def code_sau_keyword_yt(title):
    """Title: strict only."""
    cands = _all_candidates((title or "").upper(), False)
    return [cands[0]] if cands else []


def code_from_desc_text(desc):
    """Mô tả: strict only."""
    return _all_candidates((desc or "").upper(), False)


def code_from_ocr_text(text):
    """OCR: strict + join."""
    return _all_candidates((text or "").upper(), True)
