# Webhook Discord dang EMBED. msg_* tra payload dict {"embeds":[...]}; send() nhan ca dict
# (embed) lan str (text cu) -> main.py GOI send(msg_*) nhu cu. VN-only.
# Mau: success xanh, failure do, alert vang, stuck cam.
import os, requests
from datetime import datetime, timezone, timedelta
from . import config as C
from .utils import log

C_SUCCESS = 0x2ECC71
C_FAILURE = 0xE74C3C
C_ALERT   = 0xF1C40F
C_STATUS  = 0xE67E22

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    _TZ = timezone(timedelta(hours=7))

def _vn_hhmm():
    return datetime.now(_TZ).strftime("%H:%M")

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

def msg_status(reason, n_pending):
    return _embed("⚠️ Bot đang kẹt",
                  f'{reason}\n({n_pending} code đang chờ trong queue, không chốt failure oan, '
                  f'sẽ tự thử lại khi mở khoá / khi payload được xác nhận.)', C_STATUS)

# EMBED 'PHAT HIEN VIDEO MOI'. Avatar = entry.channel_avatar (watcher TU lay tu response)
# HOAC override C.YT_CHANNEL_AVATAR; rong -> bo icon, embed van du moi thanh phan khac.
# Thu tu hien thi la Discord ep (author->title->desc->image->footer): avatar nam CANH TEN
# KE o dong dau, thumbnail dạt PHAI description (desktop)/duoi (mobile). Noi dung du 6
# element anh yeu cau; vi tri pixel theo khuon Discord, khong phai bug.
def msg_yt_alert(entry, cooldown_s):
    code  = entry.get("code", "")
    title = (entry.get("title") or f"Mã {code}").strip()
    desc  = ("🔔 Phát hiện code mới (YouTube)\n"
             f"Mã `{code}` — đợi server sync ~{cooldown_s}s trước khi nhập code tại "
             f"[trang chủ quy đổi VNG]({C.URL_VN})")
    emb = {"title": title, "description": desc, "color": C_ALERT}
    vurl = entry.get("video_url", "")
    if vurl:
        emb["url"] = vurl
    author = {"name": C.YT_CHANNEL_NAME, "url": C.YT_CHANNEL_URL}
    av = (entry.get("channel_avatar") or C.YT_CHANNEL_AVATAR or "").strip()
    if av:
        author["icon_url"] = av
    emb["author"] = author
    thumb = entry.get("thumb_url", "")
    if thumb:
        emb["image"] = {"url": thumb}
    emb["footer"] = {"text": f'Code "{code}" đã được phát hiện lúc {_vn_hhmm()}'}
    return {"embeds": [emb]}
