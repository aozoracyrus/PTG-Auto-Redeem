import os, random, time
from datetime import datetime, timezone


def sleep(sec):
    time.sleep(sec)


def rand_ms(lo, hi):
    return random.randint(int(lo), int(hi)) / 1000.0


def log(*a):
    print(f"[{datetime.now(timezone.utc).isoformat()}]", *a, flush=True)


def log_yt(*a):    log("📺 [YT   ]", *a)
def log_api(*a):   log("🔌 [API  ]", *a)
def log_queue(*a): log("🫸 [QUEUE]", *a)
def log_state(*a): log("💾 [STATE]", *a)
def log_hook(*a):  log("📡 [HOOK ]", *a)
def log_loop(*a):  log("🔁 [LOOP ]", *a)
def log_brw(*a):   log("🌐 [BRW  ]", *a)
def log_warn(*a):  log("⚠️ [WARN ]", *a)
def log_err(*a):   log("❌ [LOI  ]", *a)


def shot(page, tag):
    try:
        d = os.path.join(os.getcwd(), "shots")
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, f"{tag}-{int(time.time())}.png")
        page.screenshot(path=f, full_page=True)
        log_brw("Da luu anh:", f)
    except Exception as e:
        log_err("Chup anh loi:", e)
