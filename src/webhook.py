# Discord webhook = COMPONENTS V2 THUAN TUOI (KHONG embed V1).
# HAI DIEU KIEN BAT BUOC (docs.discord.com):
#   (1) flags = 32768 (IS_COMPONENTS_V2) -> tat content/embeds top-level;
#   (2) query ?with_components=true -> thieu thi components bi bo qua.
# CAU TRUC MOI (sua loi 400 {"components":["0"]}): bo Section+accessory (de vap
#   validation tren webhook execute), chuyen sang pattern ma quest-notifier cua ban dang
#   dung va chay: Container(17) chua [ TextDisplay(10) = noi dung, MediaGallery(12) =
#   items:[avatar, thumbnail] ]. MediaGallery la kho chuyen nhieu anh trong 1 muc ->
#   hien DU ca avatar kenh lan thumbnail video, khong can accessory.
# accent_color = spine trai (vieng vang/xanh/do/cam) — DA hoat dong (thay trong anh).
# AN TOAN: 400 -> log payload+body (co bang chung debug) va tu fallback sang
#   TextDisplay-only PHANG (van flags 32768 = V2, khong quay lai V1) de mat tin.
import os, json, requests
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


def _td(content):
    return {"type": 10, "content": content}


def _gallery(urls):
    """MediaGallery(12): moi url = 1 item. Loc rong/trung; toi da 10 item (gioi han V2)."""
    items, seen = [], set()
    for u in urls:
        u = (u or "").strip()
        if u and u.startswith("http") and u not in seen:
            seen.add(u)
            items.append({"media": {"url": u}})
        if len(items) >= 10:
            break
    return {"type": 12, "items": items} if items else None


def _container(text_lines, color, image_urls=None, mention_uid=None):
    """Container(17) = [TextDisplay(10) gop noi dung, MediaGallery(12) anh (tuy chon)]."""
    body = "\n".join(x for x in text_lines if x is not None)
    sq = _SQUARE.get(color, "")
    if sq:
        body = f"{sq} {body}"
    kids = [_td(body)]
    g = _gallery(image_urls or [])
    if g:
        kids.append(g)
    cont = {"type": 17, "accent_color": color, "components": kids}
    p = {"flags": _FLAG_V2, "components": [cont]}
    if mention_uid:
        p["allowed_mentions"] = {"users": [mention_uid]}
    return p, body


def _with_components(url):
    if "with_components=" in url:
        return url
    return url + ("&" if "?" in url else "?") + "with_components=true"


def send(payload):
    """payload = (full_payload, flat_text). Thu V2 co anh; 400 -> log + fallback V2 phang."""
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
            # Fallback VAN LA V2 (flags 32768), chi bo anh de cham hon validation.
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


def msg_failure(code, uid, reason):
    lines = ["**❌ Nhập thất bại**", f'Code `{code}` thất bại cho ID `{uid}` với lí do "{reason}"']
    return _container(lines, C_FAILURE)


def msg_status(reason, n_pending):
    lines = ["**⚠️ Bot đang kẹt**", reason,
             f"({n_pending} code đang chờ trong queue, không chốt failure oan, sẽ tự thử lại.)"]
    return _container(lines, C_STATUS)


def msg_yt_alert(entry, cooldown_s):
    code   = entry.get("code", "")
    title  = (entry.get("title") or f"Mã {code}").strip()
    vurl   = entry.get("video_url", "")
    thumb  = entry.get("thumb_url", "")
    avatar = (entry.get("channel_avatar") or getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip()
    via    = entry.get("via", "TITLE")
    src_label = {"TITLE": "tiêu đề", "DESC": "mô tả video",
                 "OCR": "ảnh thumbnail (OCR)"}.get(via, via)

    lines = ["**🔔 Phát hiện code mới (YouTube)**",
             f"[{title}]({vurl})" if vurl else title,
             f"Mã `{code}` — phát hiện qua **{src_label}** — đợi server sync ~{cooldown_s}s "
             f"trước khi nhập code tại [trang chủ quy đổi VNG]({C.URL_VN})"]
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
    lines.append(f'— Code `{code}` phát hiện lúc {_vn_hhmm()} (giờ VN)')
    return _container(lines, C_ALERT, image_urls=[avatar, thumb])


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
    lines.append(f"— Lúc {_vn_hhmm()} (giờ VN) · OCR đã chạy {n_recipe} biến thể / {tries} lượt thử")
    return _container(lines, C_FAILURE, image_urls=[av, thumb_url], mention_uid=uid or None)
