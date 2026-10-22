# Tien ich: log theo tang (emoji + nhan ASCII thang cot, noi dung tieng Viet co dau),
# sleep, delay ngau nhien, screenshot khi browser fallback loi.
import os, random, time
from datetime import datetime, timezone


def sleep(sec):
    time.sleep(sec)


def rand_ms(lo, hi):
    """Tra so giay ngau nhien trong [lo, hi] miligiay (delay chong captcha)."""
    return random.randint(int(lo), int(hi)) / 1000.0


def log(*a):
    print(f"[{datetime.now(timezone.utc).isoformat()}]", *a, flush=True)


def log_yt(*a):    log("📺 [YT   ]", *a)   # tang YouTube: doc video, trich ma, OCR
def log_api(*a):   log("🔌 [API  ]", *a)   # tang redeem: goi API VNG, ket qua
def log_queue(*a): log("📦 [QUEUE]", *a)   # hang doi ma cho dong bo
def log_state(*a): log("💾 [STATE]", *a)   # luu/push state + queue + ocr_memory
def log_hook(*a):  log("📣 [HOOK ]", *a)   # Discord webhook
def log_loop(*a):  log("🔁 [LOOP ]", *a)   # vong lap chinh, start/end, self-chain
def log_brw(*a):   log("🌐 [BRW  ]", *a)   # browser fallback (chi khi USE_API=0)
def log_warn(*a):  log("⚠️ [WARN ]", *a)   # canh bao khong lam dung bot
def log_err(*a):   log("❌ [LOI  ]", *a)   # loi that, can xem


def shot(page, tag):
    """Chup anh trang khi browser fallback loi/captcha. Luu vao shots/."""
    try:
        d = os.path.join(os.getcwd(), "shots")
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, f"{tag}-{int(time.time())}.png")
        page.screenshot(path=f, full_page=True)
        log_brw("Da luu anh chang:", f)
    except Exception as e:
        log_err("Chup anh chang that bai:", e)
