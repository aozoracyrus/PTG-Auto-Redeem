# TRICH MA GIFT TU TIEU DE / MO TA / TEXT OCR.
# NEO (chuoi da .upper() truoc khi khop):
#   KW = C[OÔ][\s.:|_-]*D[EÉ] -> phu moi cach viet: CODE, CÔ DÉ, CÔ.DÉ, CO DE, CODE:,
#   CODE- ... Ly do: thumbnail 10/29 viet stylized "CÔ DÉ PTMERGEHOTEL1029" -> OCR doc ra
#   "CÔ DÉ" chu khong phai "CODE"; neo cu chi nhan CODE nen bot mat ma (het han).
#   Bien CHUNG: KW + "CHUNG" (invariant cu) + cho phep vụn <=5 ky tu xen giua -> token >= MIN.
#   Bien DON  : KW + token >= MIN dinh ngay sau (± sep, hoac dinh lien voi OCR).
# THEO LENH BAN ("dieU 1", lua edit CODE_PREFIXES): BO CHOT so/prefix o bien DON -> ca hai
#   bien chap nhan moi token >= CODE_MIN_LEN. Danh doi (chap nhan co y thuc): title hiem
#   kieu "CODE TOGETHER ..." se bi lay nham "TOGETHER" -> ma gia an 2106 -> 5 probes ->
#   1 webhook failure roi thoai, KHONG mat ma that, KHONG lap. Con tu vun tieng Viet bi
#   vo dau (MOI->M, CUA->C, VA->V, TRONG->5) van tu loai vi ngan hon CODE_MIN_LEN.
# Thu tu uu tien: CHUNG truoc, DON sau; tra theo thu tu xuat hien de OCR lay consensus.
import re
from . import config as C

_MIN = int(getattr(C, "CODE_MIN_LEN", 6))
_KW = r"C[OÔ][\s.:|_-]*D[EÉ]"

_CHUNG_RE = re.compile(
    r"(?<![A-Z0-9])" + _KW +
    r"[\s:|_-]*CHUNG(?:[\s:|_-]+[A-Z0-9]{1,5})*[\s:|_-]*([A-Z0-9]{%d,})" % _MIN)
_BARE_RE = re.compile(
    r"(?<![A-Z0-9])" + _KW + r"[\s:|_-]*([A-Z0-9]{%d,})" % _MIN)


def _all_candidates(t):
    """Moi ung vien ma trong chuoi t (da .upper()), theo thu tu xuat hien, khong trung."""
    hits = []
    for m in _CHUNG_RE.finditer(t):
        hits.append((m.start(), m.group(1)))
    for m in _BARE_RE.finditer(t):
        hits.append((m.start(), m.group(1)))
    hits.sort(key=lambda x: x[0])
    out = []
    for _, tok in hits:
        if tok not in out:
            out.append(tok)
    return out


def code_sau_keyword_yt(title):
    """Tra [ma] dau tien trich duoc tu title; [] neu khong co neo hop le."""
    cands = _all_candidates((title or "").upper())
    return [cands[0]] if cands else []


def code_from_ocr_text(text):
    """Tra TAT CA ung vien ma (thu tu xuat hien) tu mo ta video / text OCR."""
    return _all_candidates((text or "").upper())
