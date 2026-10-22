# Discord webhook dang EMBED. msg_ocr_fail dung khuon: content='<@ID>' (ping that,
# allowed_mentions chi mo 1 user) + embed(description + footer) + url + image.
import os, requests
from datetime import datetime, timezone, timedelta
from . import config as C
from .utils import log_hook, log_err

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
    if fields:
        e["fields"] = fields
    return {"embeds": [e]}


def send(payload):
    url = os.getenv("DISCORD_WEBHOOK")
    if not url:
        log_hook("Bo qua webhook (chua set DISCORD_WEBHOOK):", payload)
        return
    body = payload if isinstance(payload, dict) else {"content": payload,
                                                      "allowed_mentions": {"parse": []}}
    try:
        r = requests.post(url, json=body, timeout=15)
        if r.status_code >= 400:
            log_err("Webhook HTTP", r.status_code, (r.text or "")[:200])
    except Exception as e:
        log_err("Loi khi gui webhook:", e)


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


def msg_ocr_fail(video_url, title, thumb_url, tried, note, n_recipe=0, tries=0, avatar=""):
    uid = (getattr(C, "OCR_PING_USER", "") or "1160199218313564210").strip()
    lines = [
        "🆘 **OCR bế tắc — cần nhập code bằng tay**",
        f"Video: [{title or video_url}]({video_url})",
        f"Các mã OCR đã thử và bị server từ chối: "
        f"`{', '.join(tried) if tried else '(chưa đọc được mã nào)'}`",
    ]
    if note:
        lines.append(note)
    lines.append(f"👉 Mở ảnh thumbnail bên dưới, đọc mã bằng mắt rồi nhập tay tại "
                 f"[trang quy đổi VNG]({C.URL_VN}).")
    emb = {
        "title": "🆘 OCR không đọc được mã chắc chắn",
        "description": "\n".join(lines),
        "color": C_FAILURE,
        "footer": {"text": f"Lúc {_vn_hhmm()} (giờ VN) · OCR đã chạy {n_recipe} biến thể / "
                           f"{tries} lượt thử"},
    }
    if video_url:
        emb["url"] = video_url
    author = {"name": getattr(C, "YT_CHANNEL_NAME", "Play Together VNG"),
              "url":   getattr(C, "YT_CHANNEL_URL",
                               "https://www.youtube.com/@PlayTogetherVNGofficial/videos")}
    av = (avatar or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    if av:
        author["icon_url"] = av
    emb["author"] = author
    if thumb_url:
        emb["image"] = {"url": thumb_url}
    payload = {"embeds": [emb]}
    if uid:
        payload["content"] = f"<@{uid}>"
        payload["allowed_mentions"] = {"users": [uid]}
    return payload


def msg_yt_alert(entry, cooldown_s):
    code  = entry.get("code", "")
    title = (entry.get("title") or f"Mã {code}").strip()
    via   = entry.get("via", "TITLE")
    src_label = {"TITLE": "tiêu đề", "DESC": "mô tả video",
                 "OCR": "ảnh thumbnail (OCR)"}.get(via, via)
    lines = ["🔔 Phát hiện code mới (YouTube)",
             f"Mã `{code}` — phát hiện qua **{src_label}** — đợi server sync ~{cooldown_s}s "
             f"trước khi nhập code tại [trang chủ quy đổi VNG]({C.URL_VN})"]
    if via == "OCR":
        if not entry.get("redeem", True):
            lines.append("⛔ Chế độ OCR = **alert**: bot CHỈ báo, không tự nhập. "
                         "Xem thumbnail bên dưới để xác nhận mã.")
        else:
            lines.append("🔁 Chế độ OCR = **auto**: bot sẽ tự thử và tự sửa nếu server "
                         "từ chối mã (mỗi mã sai được ghi nhớ và loại khỏi lần thử sau).")
        conf = entry.get("conf", "")
        lines.append("🔎 Độ tin OCR: " + ("CAO (consensus ≥2 lượt đọc)" if conf == "high"
                                          else "THẤP (1 lượt đọc)"))
        note = (entry.get("ocr_note") or "").strip()
        if note:
            lines.append(f"🧭 {note}")
        raw = (entry.get("ocr_text") or "").strip()
        if raw:
            lines.append(f"📝 Text OCR thô: `{raw[:240]}`")
    emb = {"title": title, "description": "\n".join(lines), "color": C_ALERT}
    vurl = entry.get("video_url", "")
    if vurl:
        emb["url"] = vurl
    author = {"name": getattr(C, "YT_CHANNEL_NAME", "Play Together VNG"),
              "url":   getattr(C, "YT_CHANNEL_URL",
                               "https://www.youtube.com/@PlayTogetherVNGofficial/videos")}
    av = (entry.get("channel_avatar") or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    if av:
        author["icon_url"] = av
    emb["author"] = author
    thumb = entry.get("thumb_url", "")
    if thumb:
        emb["image"] = {"url": thumb}
    emb["footer"] = {"text": f'Code "{code}" đã được phát hiện lúc {_vn_hhmm()}'}
    return {"embeds": [emb]}
