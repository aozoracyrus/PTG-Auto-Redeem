# Discord webhook = COMPONENTS V2 THUAN TUOI (KHONG con embed V1).
# HAI DIEU KIEN BAT BUOC cho webhook V2 (theo docs.discord.com):
#   (1) flags = 32768 (IS_COMPONENTS_V2) -> tat content/embeds/stickers/poll o top-level;
#   (2) query param ?with_components=true -> NEU THIEU thi components bi bo qua / bi 400.
#       Day chinh la nguyen nhan lan truoc bi "Discord tu choi V2 (400)": code cu co flags
#       nhung KHONG co query param -> Discord reject -> roi vao fallback V1. Giu ba het V1.
# CAU TRUC: Container(17){accent_color, components:[Section(9){components:[TextDisplay(10)],
#   accessory: Thumbnail(11){media.url}}]}. Thumbnail type 11 render RELIABLE -> hien DU
#   ca avatar kenh (accessory section 1) lan thumbnail video (accessory section 2), khac
#   author.icon_url cua embed V1 hay bi nuot.
# MAU: accent_color = spine doc (vang/xanh/do/cam); them o mau emoji dau dong de doc la
#   biet loai tin ma khong can nhin spine.
import os, requests
from datetime import datetime, timezone, timedelta
from . import config as C
from .utils import log_hook, log_err

C_SUCCESS = 0x2ECC71
C_FAILURE = 0xE74C3C
C_ALERT   = 0xF1C40F
C_STATUS  = 0xE67E22
_FLAG_V2  = 1 << 15
_SQUARE   = {C_SUCCESS: "🟩", C_FAILURE: "🟥", C_ALERT: "🟨", C_STATUS: "🟧"}

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    _TZ = timezone(timedelta(hours=7))


def _vn_hhmm():
    return datetime.now(_TZ).strftime("%H:%M")


# ---------------- Components V2 builders ----------------
def _td(content):
    return {"type": 10, "content": content}


def _thumb(url):
    return {"type": 11, "media": {"url": url}}


def _section(lines, accessory_url=None):
    s = {"type": 9, "components": [_td(x) for x in lines]}
    if accessory_url:
        s["accessory"] = _thumb(accessory_url)
    return s


def _tag(children, color):
    """Prepends o mau emoji vao TextDisplay dau cua Section dau (de phan loai bang mat)."""
    sq = _SQUARE.get(color, "")
    if sq and children:
        comps = children[0].get("components") or []
        if comps and comps[0].get("type") == 10:
            comps[0]["content"] = f"{sq} {comps[0]['content']}"
    return children


def _wrap(children, color, mention_uid=None):
    """Payload V2 hoan chinh: flags + container; them allowed_mentions chi khi co ping."""
    cont = {"type": 17, "accent_color": color, "components": _tag(children, color)}
    p = {"flags": _FLAG_V2, "components": [cont]}
    if mention_uid:
        p["allowed_mentions"] = {"users": [mention_uid]}
    return p


# ---------------- send (V2-only, tu them query param) ----------------
def _with_components(url):
    """Webhook V2 BAT BUOC ?with_components=true; neu thieu -> Discord reject/400."""
    if "with_components=" in url:
        return url
    return url + ("&" if "?" in url else "?") + "with_components=true"


def send(payload):
    url = os.getenv("DISCORD_WEBHOOK")
    if not url:
        log_hook("Bo qua webhook (chua set DISCORD_WEBHOOK)")
        return
    if isinstance(payload, dict) and payload.get("flags"):
        target = _with_components(url)
        body = payload
    elif isinstance(payload, dict):
        target, body = url, payload
    else:
        target, body = url, {"content": payload, "allowed_mentions": {"parse": []}}
    try:
        r = requests.post(target, json=body, timeout=15)
        if r.status_code >= 400:
            # Log body loi de lan sau co bang chung debug (khong im lang mat tin).
            log_err("Webhook HTTP", r.status_code, (r.text or "")[:300])
    except Exception as e:
        log_err("Loi khi gui webhook:", e)


# ---------------- cac loai tin nhan ----------------
def msg_success(code, uid):
    lines = ["**✅ Nhập thành công**", f'Code `{code}` đã nhập thành công cho ID `{uid}`']
    return _wrap([_section(lines)], C_SUCCESS)


def msg_failure(code, uid, reason):
    lines = ["**❌ Nhập thất bại**", f'Code `{code}` thất bại cho ID `{uid}` với lí do "{reason}"']
    return _wrap([_section(lines)], C_FAILURE)


def msg_status(reason, n_pending):
    lines = ["**⚠️ Bot đang kẹt**", reason,
             f"({n_pending} code đang chờ trong queue, không chốt failure oan, "
             f"sẽ tự thử lại khi mở khoá.)"]
    return _wrap([_section(lines)], C_STATUS)


def msg_yt_alert(entry, cooldown_s):
    code   = entry.get("code", "")
    title  = (entry.get("title") or f"Mã {code}").strip()
    vurl   = entry.get("video_url", "")
    thumb  = entry.get("thumb_url", "")
    avatar = (entry.get("channel_avatar") or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    via    = entry.get("via", "TITLE")
    src_label = {"TITLE": "tiêu đề", "DESC": "mô tả video",
                 "OCR": "ảnh thumbnail (OCR)"}.get(via, via)

    lines = ["**🔔 Phát hiện code mới (YouTube)**"]
    lines.append(f"[{title}]({vurl})" if vurl else title)
    lines.append(f"Mã `{code}` — phát hiện qua **{src_label}** — đợi server sync ~{cooldown_s}s "
                 f"trước khi nhập code tại [trang chủ quy đổi VNG]({C.URL_VN})")
    if via == "OCR":
        if not entry.get("redeem", True):
            lines.append("⛔ OCR = **alert**: bot CHỈ báo, không tự nhập.")
        else:
            lines.append("🔁 OCR = **auto**: bot tự thử và tự sửa nếu server từ chối mã.")
        conf = entry.get("conf", "")
        lines.append("🔎 Độ tin OCR: " + ("CAO (consensus ≥2 lượt đọc)" if conf == "high"
                                          else "THẤP (1 lượt đọc)"))
        note = (entry.get("ocr_note") or "").strip()
        if note:
            lines.append(f"🧭 {note}")
        raw = (entry.get("ocr_text") or "").strip()
        if raw:
            lines.append(f"📝 Text OCR thô: `{raw[:240]}`")
    foot = f'Code "{code}" đã được phát hiện lúc {_vn_hhmm()} (giờ VN)'

    # Section 1 accessory = avatar kenh; Section 2 accessory = thumbnail video.
    # Hai thumbnail type 11 -> ca hai anh deu render (day la ly do chuyen V2).
    children = [_section(lines, avatar or None)]
    children.append(_section([foot], thumb or None))
    return _wrap(children, C_ALERT)


def msg_ocr_fail(video_url, title, thumb_url, tried, note, n_recipe=0, tries=0, avatar=""):
    """PING khi OCR be tac. Mention <@id> nam trong TextDisplay dau + allowed_mentions
       mo dung 1 user -> ping that; section 1 accessory = avatar, section 2 = thumbnail."""
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
    foot = f"Lúc {_vn_hhmm()} (giờ VN) · OCR đã chạy {n_recipe} biến thể / {tries} lượt thử"

    children = [_section(lines, av or None)]
    children.append(_section([foot], thumb_url or None))
    return _wrap(children, C_FAILURE, mention_uid=uid or None)
