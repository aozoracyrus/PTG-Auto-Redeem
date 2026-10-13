"""
HAI HÀM PARSE GIFT CODE, HAI NEO KHÁC NHAU, CẢ HAI KHÔNG RÀNG BUỘC ĐỘ DÀI & KHÔNG CẦN SỐ.
  - YouTube : neo = cụm "CODE CHUNG" + bộ lọc PREFIX thương hiệu (PT...). Code ngắn vẫn lấy.
  - Web     : neo = dòng "Valid until <ngày>". Cấu trúc modal chặt -> min 1 ký tự, không prefix.
Title THẬT không có "" / () quanh code; bot KHÔNG dựa vào ngoặc. Code CÓ THỂ không có số
(PTGIANTVEGGIE toàn chữ vẫn bắt được).
"""
import re
from . import config as C

# ---------------------------------------------------------------------------
# NEO 1 — YouTube: token in-hoa mở đầu PREFIX, nằm ngay sau "CODE CHUNG".
# Build động từ C.CODE_PREFIXES (đã .upper()). Regex (trên title ĐÃ .upper()):
#   CODE\s+CHUNG  ([^A-Z0-9]*)  (?:PT|...)[A-Z0-9]*
#     phần đầu   = chính KEYWORD_PATTERN (định vị vị trí).
#     nhóm 1     = "skip rác": mọi ký tự KHÔNG phải chữ/số-hOA giữa keyword và code
#                  (space | ( ) " : ...). "*" = khoan dung mọi biến thể ngăn cách.
#     nhóm 2     = CODE THẬT: phải mở đầu 1 prefix, rồi [A-Z0-9]* greedy ăn hết thân
#                  (dừng ở khoảng trắng / ký tự có-dấu / ký tự thường). KHÔNG giới hạn
#                  độ dài dưới -> "PT26"(4) hay "PT"(2) vẫn khớp; "UPDATE"/"NGAY"/"VNG"
#                  rớt vì không mở đầu PT.
# Nếu CODE_PREFIXES rỗng -> fallback ([A-Z0-9]+) min 1, chấp nhận nhiễu (xem ghi chú config).
# ---------------------------------------------------------------------------
_PREFIXES = [p.upper() for p in C.CODE_PREFIXES if p]
if _PREFIXES:
    _ALT = "|".join(re.escape(p) for p in _PREFIXES)            # "PT" hoặc "PT|XX"
    _YT_AFTER_KW = re.compile(C.KEYWORD_PATTERN + r"([^A-Z0-9]*)((?:" + _ALT + r")[A-Z0-9]*)")
else:
    _YT_AFTER_KW = re.compile(C.KEYWORD_PATTERN + r"([^A-Z0-9]*)([A-Z0-9]+)")

def code_sau_keyword_yt(title: str) -> list:
    """Giftcode từ title YT = token in-hoa mở đầu prefix, đứng ngay sau 'CODE CHUNG'.
       .upper() title trước search -> khoan dung code viết thường, mà prefix vẫn chặn từ
       tiếng Việt có dấu (dấu giữ nguyên sau .upper() -> break [A-Z0-9])."""
    t = (title or "").upper()
    m = _YT_AFTER_KW.search(t)
    return [m.group(2)] if (m and m.group(2)) else []

# ---------------------------------------------------------------------------
# NEO 2 — Web modal: token in-hoa LIỀN TRƯỚC mỗi 'Valid until'.
#   ([A-Z0-9]+)\s+Valid\s+until
#   KHÔNG re.I -> chỉ in-hoa: label Title-case/thường (Selected, Quick select, Clear
#     selection, Coming soon, Enter code, Check, Select) tự rớt. 'Valid until' viết
#     đúng-case -> chỉ khớp chuỗi UI này.
#   finditer -> bắt MỌI card. PROMOTIONS (in-hoa) đứng trước 'Coming soon' chứ KHÔNG
#     trước 'Valid until' -> không bị bắt. => KHÔNG cần blacklist, KHÔNG prefix, KHÔNG độ dài.
#   Code heading in-hoa đứng ngay trước 'Valid until' được lấy dù dài 1 ký tự.
#   LƯU Ý: scraper đọc trang TH (modal tiếng Anh 'Valid until'). Nếu đổi sang trang VN và
#     modal dịch khác wording, sửa đúng regex dưới đây.
# ---------------------------------------------------------------------------
_WEB_BEFORE_VU = re.compile(r"([A-Z0-9]+)\s+Valid\s+until")

def code_truoc_valid_until_web(text: str) -> list:
    """List giftcode (in-hoa, dedup theo thứ tự) từ text modal web, neo 'Valid until'."""
    seen, out = set(), []
    for m in _WEB_BEFORE_VU.finditer(text or ""):
        c = m.group(1).upper()
        if c not in seen:
            seen.add(c); out.append(c)
    return out
