# Discord webhook = COMPONENTS V2 (container / section / text-display / thumbnail).
# LY DO: embed cu chi co 1 slot anh (image) + icon tac gia (author.icon_url) ma Discord
#   hay KHONG render (nhat la URL googleusercontent) -> mat avatar kenh. V2 cho moi
#   section kem 1 thumbnail accessory -> hien DU ca avatar kenh lan thumbnail video.
# Cau truc V2: flags = 1<<15 (IS_COMPONENTS_V2); components = [Container(17) chua
#   Section(9){components:[TextDisplay(10)], accessory: Thumbnail(11){media:{url}}}...].
#   TextDisplay ho tro markdown: link [..](..), mention <@id>, bold, newline.
# AN TOAN: moi msg_* tra {"v2": ..., "legacy": ...}; send() thu V2 truoc, neu Discord
#   tra 400 (chua ho tro V2) thi tu fallback sang embed cu -> KHONG mat thong bao.
#   call sites (main.py, ocr.py) KHONG doi: van goi send(msg_*(...)).
import os, requests
from datetime import datetime, timezone, timedelta
from . import config as C
from .utils import log_hook, log_err

C_SUCCESS = 0x2ECC71
C_FAILURE = 0xE74C3C
C_ALERT   = 0xF1C40F
C_STATUS  = 0xE67E22
_FLAG_V2  = 1 << 15                      # IS_COMPONENTS_V2

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    _TZ = timezone(timedelta(hours=7))


def _vn_hhmm():
    return datetime.now(_TZ).strftime("%H:%M")


# ================= Components V2 builders =================
def _td(content):
    """Text display (type 10)."""
    return {"type": 10, "content": content}


def _thumb(url):
    """Thumbnail (type 11) = accessory cua section."""
    return {"type": 11, "media": {"url": url}}


def _section(lines, accessory_url=None):
    """Section (type 9): nhieu text display + 1 thumbnail ben phai."""
    s = {"type": 9, "components": [_td(x) for x in lines]}
    if accessory_url:
        s["accessory"] = _thumb(accessory_url)
    return s


def _v2(children, color, mention_uid=None):
    p = {"flags": _FLAG_V2,
         "components": [{"type": 17, "accent_color": color, "components": children}]}
    if mention_uid:
        p["allowed_mentions"] = {"users": [mention_uid]}
    return p


def _both(v2_children, color, legacy_embeds, mention_uid=None, legacy_content=None):
    """Tra cap {v2, legacy} de send() thu V2 truoc, fallback embed khi bi 400."""
    legacy = {"embeds": legacy_embeds}
    if legacy_content:
        legacy["content"] = legacy_content
        legacy["allowed_mentions"] = {"users": [mention_uid]} if mention_uid else {"parse": []}
    return {"v2": _v2(v2_children, color, mention_uid), "legacy": legacy}


# ================= legacy embed builders (chi dung khi V2 bi 400) =================
def _embed(title, description, color, url=None, image=None, author=None, footer=None):
    e = {"title": title, "description": description, "color": color}
    if url:    e["url"] = url
    if image:  e["image"] = {"url": image}
    if author: e["author"] = author
    if footer: e["footer"] = {"text": footer}
    return e


def _author_obj(avatar=None):
    a = {"name": getattr(C, "YT_CHANNEL_NAME", "Play Together VNG"),
         "url":   getattr(C, "YT_CHANNEL_URL",
                          "https://www.youtube.com/@PlayTogetherVNGofficial/videos")}
    av = (avatar or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    if av:
        a["icon_url"] = av
    return a


# ================= send =================
def send(payload):
    url = os.getenv("DISCORD_WEBHOOK")
    if not url:
        log_hook("Bo qua webhook (chua set DISCORD_WEBHOOK)")
        return

    def post(body):
        return requests.post(url, json=body, timeout=15)

    r = None
    try:
        if isinstance(payload, dict) and "v2" in payload:
            r = post(payload["v2"])
            if r.status_code == 400 and payload.get("legacy"):
                log_hook("Discord tu choi Components V2 (400) -> fallback embed cu")
                r = post(payload["legacy"])
        elif isinstance(payload, dict):
            r = post(payload)
        else:
            r = post({"content": payload, "allowed_mentions": {"parse": []}})
    except Exception as e:
        log_err("Loi khi gui webhook:", e)
        return
    if r is not None and r.status_code >= 400:
        log_err("Webhook HTTP", r.status_code, (r.text or "")[:200])


# ================= cac loai tin nhan =================
def msg_success(code, uid):
    lines = ["**✅ Nhập thành công**", f'Code `{code}` đã nhập thành công cho ID `{uid}`']
    return _both([_section(lines)], C_SUCCESS,
                 [_embed("✅ Nhập thành công",
                         f'Code "{code}" đã nhập thành công cho ID "{uid}"', C_SUCCESS)])


def msg_failure(code, uid, reason):
    lines = ["**❌ Nhập thất bại**", f'Code `{code}` thất bại cho ID `{uid}` với lí do "{reason}"']
    return _both([_section(lines)], C_FAILURE,
                 [_embed("❌ Nhập thất bại",
                         f'Code "{code}" thất bại cho ID "{uid}" với lí do "{reason}"', C_FAILURE)])


def msg_status(reason, n_pending):
    lines = ["**⚠️ Bot đang kẹt**", reason,
             f'({n_pending} code đang chờ trong queue, không chốt failure oan, '
             f'sẽ tự thử lại khi mở khoá / khi payload được xác nhận.)']
    return _both([_section(lines)], C_STATUS,
                 [_embed("⚠️ Bot đang kẹt",
                         f'{reason}\n({n_pending} code đang chờ trong queue, không chốt '
                         f'failure oan, sẽ tự thử lại khi mở khoá.)', C_STATUS)])


def msg_yt_alert(entry, cooldown_s):
    code  = entry.get("code", "")
    title = (entry.get("title") or f"Mã {code}").strip()
    vurl  = entry.get("video_url", "")
    thumb = entry.get("thumb_url", "")
    avatar = (entry.get("channel_avatar") or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    via   = entry.get("via", "TITLE")
    src_label = {"TITLE": "tiêu đề", "DESC": "mô tả video",
                 "OCR": "ảnh thumbnail (OCR)"}.get(via, via)

    lines = ["**🔔 Phát hiện code mới (YouTube)**"]
    lines.append(f"[{title}]({vurl})" if vurl else title)
    lines.append(f"Mã `{code}` — phát hiện qua **{src_label}** — đợi server sync ~{cooldown_s}s "
                 f"trước khi nhập code tại [trang chủ quy đổi VNG]({C.URL_VN})")
    if via == "OCR":
        if not entry.get("redeem", True):
            lines.append("⛔ Chế độ OCR = **alert**: bot CHỈ báo, không tự nhập.")
        else:
            lines.append("🔁 Chế độ OCR = **auto**: bot tự thử và tự sửa nếu server từ chối mã.")
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

    children = [_section(lines, avatar or None)]
    if thumb:
        children.append(_section([foot], thumb))
    else:
        children.append(_section([foot]))

    legacy = _embed(title, "\n".join(lines[2:]), C_ALERT,
                    url=vurl or None, image=thumb or None,
                    author=_author_obj(avatar), footer=foot)
    return _both(children, C_ALERT, [legacy])


def msg_ocr_fail(video_url, title, thumb_url, tried, note, n_recipe=0, tries=0, avatar=""):
    """PING truc tiep khi OCR be tac. V2: dong mention <@id> nam trong text display dau
       (allowed_mentions chi mo dung 1 user) + section kem avatar + section kem thumbnail."""
    uid = (getattr(C, "OCR_PING_USER", "") or "1160199218313564210").strip()
    av = (avatar or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    lines = [f"<@{uid}>"] if uid else []
    lines += [
        "**🆘 OCR bế tắc — cần nhập code bằng tay**",
        f"Video: [{title or video_url}]({video_url})" if video_url else f"Video: {title}",
        f"Các mã OCR đã thử và bị server từ chối: "
        f"`{', '.join(tried) if tried else '(chưa đọc được mã nào)'}`",
    ]
    if note:
        lines.append(note)
    lines.append(f"👉 Mở ảnh thumbnail bên dưới, đọc mã bằng mắt rồi nhập tay tại "
                 f"[trang quy đổi VNG]({C.URL_VN}).")
    foot = f"Lúc {_vn_hhmm()} (giờ VN) · OCR đã chạy {n_recipe} biến thể / {tries} lượt thử"

    children = [_section(lines, av or None)]
    if thumb_url:
        children.append(_section([foot], thumb_url))
    else:
        children.append(_section([foot]))

    legacy_desc = "\n".join(lines[1:])
    legacy = _embed("🆘 OCR không đọc được mã chắc chắn", legacy_desc, C_FAILURE,
                    url=video_url or None, image=thumb_url or None,
                    author=_author_obj(av), footer=foot)
    return _both(children, C_FAILURE, [legacy],
                 mention_uid=uid or None, legacy_content=(f"<@{uid}>" if uid else None))
