# Discord webhook = COMPONENTS V2 THUAN TUOI (KHONG embed V1).
# Docs KB xac nhan:
#   (1) flags=32768 (IS_COMPONENTS_V2) -> tat content/embeds top-level;
#   (2) webhook BAT BUOC ?with_components=true;
#   (3) Container(17) allowed children = TextDisplay/Separator/Section/MediaGallery/ActionRow/File;
#       max 10 component/container (ta dung 3); TextDisplay content <=4000 ky tu; MediaGallery
#       items <=10. accent_color = spine trai (chi bao mau chinh thuc).
# KHONG con emoji vuong prefix (🟨//🟩/): accent_color da la chi bao mau.
#Them msg_already cho 2117/2121: khong phai that bai do, chi la ID da redeem code nay roi.
import os, json, requests
from datetime import datetime, timezone, timedelta
from . import config as C
from .utils import log_hook, log_err

C_SUCCESS  = 0x2ECC71
C_FAILURE  = 0xE74C3C
C_ALERT    = 0xF1C40F
C_STATUS   = 0xE67E22
C_ALREADY  = 0x3498DB  # xanh nuoc: da co truoc do / khong can nhap lai
_FLAG_V2   = 1 << 15

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    _TZ = timezone(timedelta(hours=7))


def _vn_hhmm():
    return datetime.now(_TZ).strftime("%H:%M")


def _td(content):
    return {"type": 10, "content": content}


def _accessory(url):
    return {"type": 11, "media": {"url": url}}


def _gallery_one(url):
    url = (url or "").strip()
    if not url or not url.startswith("http"):
        return None
    return {"type": 12, "items": [{"media": {"url": url}}]}


def _container(text_lines, color, avatar_url=None, thumb_url=None, footer=None, mention_uid=None):
    body = "\n".join(x for x in text_lines if x is not None)
    kids = []
    av = (avatar_url or "").strip()
    if av and av.startswith("http"):
        kids.append({"type": 9, "components": [_td(body)], "accessory": _accessory(av)})
    else:
        kids.append(_td(body))
    g = _gallery_one(thumb_url)
    if g:
        kids.append(g)
    ft = (footer or "").strip()
    if ft:
        kids.append(_td(ft))
    cont = {"type": 17, "accent_color": color, "components": kids}
    p = {"flags": _FLAG_V2, "components": [cont]}
    if mention_uid:
        p["allowed_mentions"] = {"users": [mention_uid]}
    flat = body + (("\n" + ft) if ft else "")
    return p, flat


def _with_components(url):
    if "with_components=" in url:
        return url
    return url + ("&" if "?" in url else "?") + "with_components=true"


def send(payload):
    url = os.getenv("DISCORD_WEBHOOK")
    if not url:
        log_hook("Bo qua webhook (chua set DISCORD_WEBHOOK)")
        return
    if isinstance(payload, tuple):
        full, flat = payload
    else:
        full, flat = payload, None
    target = _with_components(url)
    try:
        r = requests.post(target, json=full, timeout=15)
        if r.status_code < 400:
            return
        log_err("V2 bi tu choi http", r.status_code,
                "| Discord:", (r.text or "")[:300],
                "| payload:", json.dumps(full, ensure_ascii=False)[:500])
        if flat is not None:
            flat_payload = {"flags": _FLAG_V2, "components": [_td(flat)]}
            if full.get("allowed_mentions"):
                flat_payload["allowed_mentions"] = full["allowed_mentions"]
            r2 = requests.post(target, json=flat_payload, timeout=15)
            if r2.status_code >= 400:
                log_err("V2 phang cung bi tu choi http", r2.status_code,
                        "| Discord:", (r2.text or "")[:300])
            else:
                log_hook("Da gui ban V2 phang (chi chu, khong anh)")
    except Exception as e:
        log_err("Loi khi gui webhook:", e)


# ================= cac loai tin nhan =================
def msg_success(code, uid):
    lines = ["**✅ Nhập thành công**", f'Code `{code}` đã nhập thành công cho ID `{uid}`']
    return _container(lines, C_SUCCESS)


def msg_already(code, uid, reason=""):
    """2117/2121: ID nay da redeem code nay roi. Khong phai loi, khong spam do."""
    lines = [
        "**ℹ️ Code đã redeem trước đó**",
        f'Code `{code}` đã được nhận bởi ID `{uid}` — bot không nhập lại.',
    ]
    if reason:
        lines.append(f'Lí do: "{reason}"')
    return _container(lines, C_ALREADY)


def msg_failure(code, uid, reason):
    lines = ["**❌ Nhập thất bại**", f'Code `{code}` thất bại cho ID `{uid}` với lí do "{reason}"']
    return _container(lines, C_FAILURE)


def msg_status(reason, n_pending):
    lines = ["**⚠️ Bot đang kẹt**", reason,
             f"({n_pending} code đang chờ trong queue, không chốt failure oan, sẽ tự thử lại.)"]
    return _container(lines, C_STATUS)


def msg_yt_alert(entry, cooldown_s):
    code   = entry.get("code", "")
    title  = (entry.get("title") or "").strip()
    vurl   = entry.get("video_url", "")
    thumb  = entry.get("thumb_url", "")
    avatar = (entry.get("channel_avatar") or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    via    = entry.get("via", "TITLE")
    src_label = {"TITLE": "tiêu đề", "DESC": "mô tả video",
                 "OCR": "ảnh thumbnail (OCR)"}.get(via, via)

    if title:
        head_line = f"[{title}]({vurl})" if vurl else title
    else:
        head_line = f"[▶ Xem video]({vurl})" if vurl else "*(video không có tiêu đề)*"

    lines = ["**🔔 Phát hiện code mới (YouTube)**",
             head_line,
             f"Mã `{code}` — phát hiện qua **{src_label}** — đợi server sync ~{cooldown_s}s "
             f"trước khi nhập code tại [trang chủ quy đổi VNG]({C.URL_VN})"]
    if via == "OCR":
        if not entry.get("redeem", True):
            lines.append("⛔ OCR = **alert**: bot CHỈ báo, không tự nhập.")
        else:
            lines.append("🔁 OCR = **auto**: bot tự thử và tự sửa nếu server từ chối mã.")
        note = (entry.get("ocr_note") or "").strip()
        if note:
            lines.append(f"🧭 {note}")
        raw = (entry.get("ocr_text") or "").strip()
        if raw:
            disp = (entry.get("engine_display") or "Gemini").strip()
            lines.append(f"📝 Model {disp} đã đọc được: `{raw[:240]}`")
    footer = f'— Code `{code}` phát hiện lúc {_vn_hhmm()} (giờ VN)'
    return _container(lines, C_ALERT, avatar_url=avatar, thumb_url=thumb, footer=footer)


def msg_ocr_fail(video_url, title, thumb_url, tried, note, n_recipe=0, tries=0, avatar=""):
    uid = (getattr(C, "OCR_PING_USER", "") or "1160199218313564210").strip()
    av  = (avatar or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    lines = [f"<@{uid}>"] if uid else []
    lines += [
        "**🆘 OCR bế tắc — cần nhập code bằng tay**",
        f"Video: [{title or video_url}]({video_url})" if video_url else f"Video: {title}",
        f"Các mã OCR đã thử và bị server từ chối: "
        f"`{', '.join(tried) if tried else '(chưa đọc được mã nào)'}`",
    ]
    if note:
        lines.append(note)
    lines.append(f"👉 Mở ảnh thumbnail, đọc mã bằng mắt rồi nhập tay tại "
                 f"[trang quy đổi VNG]({C.URL_VN}).")
    footer = f"— Lúc {_vn_hhmm()} (giờ VN) · OCR đã chạy {n_recipe} biến thể / {tries} lượt thử"
    return _container(lines, C_FAILURE, avatar_url=av, thumb_url=thumb_url,
                      footer=footer, mention_uid=uid or None)
