# Hang doi ma YouTube. Record "redeem": True = ma text (tu nhap); False = alert-only
# (khong nhap, prune theo TTL). File hong -> tu chua '{}'.
import os, json
from .utils import log_queue, log_warn
from .state import commit_paths

QFILE = lambda: os.path.join(os.getcwd(), "yt_queue.json")


def load_queue():
    fp = QFILE()
    if not os.path.exists(fp):
        return {}
    try:
        return json.load(open(fp, encoding="utf-8"))
    except Exception as e:
        log_warn("yt_queue file hong -> tu ghi lai '{}':", e)
        try:
            save_queue({})
        except Exception as e2:
            log_warn("yt_queue ghi lai that bai:", e2)
        return {}


def save_queue(q):
    json.dump(q, open(QFILE(), "w", encoding="utf-8"), indent=0, ensure_ascii=False)


def commit_queue(q):
    save_queue(q)
    commit_paths(["yt_queue.json"], f"chore(yt-queue): {len(q)} dang cho")


def add_if_new(q, code, now, redeem=True):
    if code in q:
        return False
    q[code] = {"first_seen": now, "probes": 0, "redeem": bool(redeem)}
    return True


def eligible(q, code, now, cooldown):
    m = q.get(code)
    return bool(m) and (now - m["first_seen"] >= cooldown)


def is_redeemable(q, code):
    m = q.get(code)
    return True if not m else bool(m.get("redeem", True))


def bump_probe(q, code):
    m = q.get(code)
    if m:
        m["probes"] = m.get("probes", 0) + 1
    return m["probes"] if m else 0


def prune_non_redeemable(q, now, ttl):
    removed = 0
    for code in list(q.keys()):
        m = q.get(code) or {}
        if (not m.get("redeem", True)) and (now - m.get("first_seen", now) >= ttl):
            del q[code]
            removed += 1
    return removed
