import os, requests
from .utils import log

def send(content):
    url = os.getenv("DISCORD_WEBHOOK")
    if not url:
        log("webhook bỏ qua (chưa set DISCORD_WEBHOOK):", content); return
    try:
        r = requests.post(url, json={"content": content,
                                     "allowed_mentions": {"parse": []}}, timeout=15)
        if r.status_code >= 400: log("webhook HTTP", r.status_code, r.text[:200])
    except Exception as e:
        log("webhook lỗi", e)

# Đúng nguyên văn spec
def msg_success(region, code, uid):
    return (f'Code "{code}" đã nhập thành công cho "{uid}"' if region == "VN"
            else f'Code "{code}" enter success for "{uid}"')

def msg_failure(region, code, uid, reason):
    return (f'Code "{code}" đã thất bại với lí do "{reason}"' if region == "VN"
            else f'Code "{code}" enter failure with reason "{reason}"')

def msg_yt_alert(code, cooldown_s):
    return (f'🔔 YouTube phát hiện "CODE CHUNG" -> mã `{code}`. '
            f'Đợi server sync ~{cooldown_s}s trước khi thử nhập (không chốt failure sớm).')
