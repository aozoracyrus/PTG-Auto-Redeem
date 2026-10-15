# Webhook Discord dang EMBED. msg_* tra payload dict {"embeds":[...]}; send() nhan ca dict
# (embed) lan str (text cu) -> main.py GOI send(msg_*) nhu cu, KHONG can sua. VN-only.
# Mau: success xanh 0x2ECC71, failure do 0xE74C3C, alert vang 0xF1C40F, stuck cam 0xE67E22.
import os, requests
from .utils import log

C_SUCCESS = 0x2ECC71
C_FAILURE = 0xE74C3C
C_ALERT   = 0xF1C40F
C_STATUS  = 0xE67E22

def _embed(title, description, color, fields=None):
    e = {"title": title, "description": description, "color": color}
    if fields: e["fields"] = fields
    return {"embeds": [e]}

def send(payload):
    url = os.getenv("DISCORD_WEBHOOK")
    if not url:
        log("webhook bo qua (chua set DISCORD_WEBHOOK):", payload); return
    body = payload if isinstance(payload, dict) else {"content": payload,
                                                      "allowed_mentions": {"parse": []}}
    try:
        r = requests.post(url, json=body, timeout=15)
        if r.status_code >= 400: log("webhook HTTP", r.status_code, r.text[:200])
    except Exception as e:
        log("webhook loi", e)

def msg_success(code, uid):
    return _embed("✅ Nhập thành công",
                  f'Code "{code}" đã nhập thành công cho ID "{uid}"', C_SUCCESS)

def msg_failure(code, uid, reason):
    return _embed("❌ Nhập thất bại",
                  f'Code "{code}" thất bại cho ID "{uid}" với lí do "{reason}"', C_FAILURE)

def msg_yt_alert(code, cooldown_s):
    return _embed("🔔 Phát hiện code mới (YouTube)",
                  f'Mã `{code}` — đợi server sync ~{cooldown_s}s trước khi thử nhập '
                  f'(không chốt failure sớm).', C_ALERT)

def msg_status(reason, n_pending):
    return _embed("⚠️ Bot đang kẹt",
                  f'{reason}\n({n_pending} code đang chờ trong queue, không chốt failure oan, '
                  f'sẽ tự thử lại khi mở khoá / khi payload được xác nhận.)', C_STATUS)
