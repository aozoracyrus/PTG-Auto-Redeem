import os, re
from . import config as C
from .utils import log

# REGION - ID  (dấu ngăn "-" hoặc "–", có/không dấu cách; cho phép comment "#" cuối dòng)
_LINE = re.compile(r"^([A-Za-z]{2})\s*[-–]\s*(.+?)(?:\s+#.*)?$")

def load_users():
    """Đọc id_user.txt -> list user (số phần tử = số dòng hợp lệ, KHÔNG giới hạn).
       Mỗi ID một dòng 'REGION - ID'. Docstring/ví dụ CHỈ minh hoạ format, không phải limit."""
    fp = os.path.join(os.getcwd(), "id_user.txt")
    if not os.path.exists(fp): return []
    out = []
    for raw in open(fp, encoding="utf-8").read().splitlines():
        s = raw.strip()
        if not s or s.startswith("#"): continue          # dòng trống / comment -> skip
        m = _LINE.match(s)
        if not m:
            log("Bỏ qua dòng không hợp lệ:", repr(s)); continue
        region, uid = m.group(1).upper(), m.group(2).strip()
        if not C.ID_RE.fullmatch(uid):                   # chỉ CẢNH BÁO, không block
            log(f"Cảnh báo: ID '{uid}' (region {region}) không đúng format 4-4-4 — vẫn thử nhập.")
        out.append({"region": region, "id": uid})
    return out
