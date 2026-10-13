import os, re
from . import config as C
from .utils import log

_LEGACY = re.compile(r"^([A-Za-z]{2})\s*[-–]\s*(.+)$")

def load_users():
    """id_user.txt: mỗi dòng MỘT ID (4-4-4), KHÔNG cần prefix.
       Vẫn chấp nhận dòng kiểu cũ 'VN - XXXX-...' (tự cắt prefix) khỏi phải sửa file cũ.
       Trả về list ID (string), giữ thứ tự dòng = thứ tự nhập."""
    fp = os.path.join(os.getcwd(), "id_user.txt")
    if not os.path.exists(fp): return []
    ids = []
    for raw in open(fp, encoding="utf-8").read().splitlines():
        s = raw.strip()
        if not s or s.startswith("#"): continue
        s = s.split("#", 1)[0].strip()          # bỏ comment cuối dòng
        m = _LEGACY.match(s)
        uid = (m.group(2) if m else s).strip().upper()
        if not uid: continue
        if not C.ID_RE.fullmatch(uid):
            log(f"Cảnh báo: '{uid}' không đúng 4-4-4 — vẫn thử nhập.")
        if uid not in ids: ids.append(uid)
    return ids
