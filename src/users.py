# Doc id_user.txt -> danh sach ID. Moi dong 1 ID; chap nhan 'VN - ID' hoac ID tran; '#' comment.
import os, re
from . import config as C
from .utils import log_warn

_REGION_PREFIX = re.compile(r"^[A-Za-z]{2}\s*[-–]\s*(.+)$")


def load_users():
    fp = os.path.join(os.getcwd(), "id_user.txt")
    if not os.path.exists(fp):
        return []
    out = []
    for raw in open(fp, encoding="utf-8").read().splitlines():
        s = raw.split("#", 1)[0].strip()
        if not s:
            continue
        m = _REGION_PREFIX.match(s)
        uid = (m.group(1) if m else s).strip()
        if not C.ID_RE.fullmatch(uid):
            log_warn("Bo qua dong ID khong hop le (can dang 4-4-4):", repr(s))
            continue
        out.append({"id": uid})
    return out
