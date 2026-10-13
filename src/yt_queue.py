import os, json
from .utils import log
from .state import commit_paths

QFILE = lambda: os.path.join(os.getcwd(), "yt_queue.json")

def load_queue():
    fp = QFILE()
    if not os.path.exists(fp): return {}
    try: return json.load(open(fp, encoding="utf-8"))
    except Exception as e: log("yt_queue đọc lỗi (coi như rỗng):", e); return {}

def save_queue(q):
    json.dump(q, open(QFILE(), "w", encoding="utf-8"), indent=0, ensure_ascii=False)

def commit_queue(q):
    save_queue(q); commit_paths(["yt_queue.json"], f"chore(yt-queue): {len(q)} pending")

def add_if_new(q, code, now):
    if code in q: return False
    q[code] = {"first_seen": now, "probes": 0}; return True

def eligible(q, code, now, cooldown):
    m = q.get(code); return bool(m) and (now - m["first_seen"] >= cooldown)

def bump_probe(q, code):
    m = q.get(code)
    if m: m["probes"] = m.get("probes", 0) + 1
    return m["probes"] if m else 0
