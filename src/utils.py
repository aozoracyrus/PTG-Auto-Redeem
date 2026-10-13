import os, random, time
from datetime import datetime, timezone

def sleep(sec): time.sleep(sec)
def rand_ms(lo, hi): return random.randint(int(lo), int(hi)) / 1000.0

def log(*a):
    print(f"[{datetime.now(timezone.utc).isoformat()}]", *a, flush=True)

def shot(page, tag):
    try:
        d = os.path.join(os.getcwd(), "shots"); os.makedirs(d, exist_ok=True)
        f = os.path.join(d, f"{tag}-{int(time.time())}.png")
        page.screenshot(path=f, full_page=True); log("screenshot:", f)
    except Exception as e:
        log("screenshot lỗi", e)
