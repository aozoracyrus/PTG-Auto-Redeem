# NGUON CODE DUY NHAT cho VN = API (BO HTML: F12 to mobile shell rong; BO RSS: 404 vinh vien).
# 2 tang: A Data API v3 playlistItems (can YT_API_KEY THAT, qua env); B InnerTube browse key
# PUBLIC (fallback trong config -> khong bao gio mu vi quen secret).
#
# TRA VE list[dict] {code,title,video_id,video_url,thumb_url,channel_avatar}. Quy uoc tang:
#   None = BI BO QUA (khong key) | [] = chay that ma 0 | list = co entry.
#
# NGUYEN TAC PHAN BIET ANH (ap DEU ca 2 phuong, khong fallback gop):
#   thumbnail video = CHU host i.ytimg.com. avatar kan = CHU host googleusercontent + token
#   cat tron (=sNNN-c / -c-k-no) + hinh vuong, loai banner ngang. KHONG bao gio "lay dai
#   nhat trong so TAT CA anh" -> do la loi _pick_thumb ban cu (fallback 'or imgs' keo
#   googleusercontent vao pool thumb = hien avatar/banner thay anh video). Da sua: khong
#   co ytimg trong card -> thumb = '' (entry 'tran'), webhook tu bo image.
#
# _via_innertube LUON duoc goi moi vong (ke ca khi Data API la chinh) de co avatar (DataAPI
# playlist KHONG chua avatar kan) + redundancy; 1 POST/phut, rat nhe.
# Comment # dau file (khong docstring) -> tranh SyntaxError backslash-u luc import.
import os, re, json, requests
from collections import OrderedDict
from . import config as C
from .parsers import code_sau_keyword_yt
from .utils import log

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HDR = {"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6"}
_dumped_once = False
_VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_IMG_HOSTS = ("ytimg.com", "googleusercontent.com")
_AV_TOKEN = re.compile(r"=s\d+-c\b")          # token cat tron dac trung avatar (khong banner)

def _host(u):
    # khong dung urlparse (bo qua dependency); tach manual 'https://HOST/...'
    try:
        h = u.split("//", 1)[1].split("/", 1)[0]
    except Exception:
        return ""
    return h.lower()

def _is_img_host(u):
    h = _host(u)
    return any(h == d or h.endswith("." + d) for d in _IMG_HOSTS)

def _iter_images(node):
    """Yeu (w,h,url) moi dict la ANH (co url http + host thuoc CDN anh), di bo het subtree.
       Loc theo HOST (su that CDN) chu khong theo ten wrapper -> khong hardcode duong dan."""
    if isinstance(node, dict):
        u = node.get("url")
        if isinstance(u, str) and u.startswith("http") and _is_img_host(u):
            w = node.get("width") if isinstance(node.get("width"), int) else 0
            hh = node.get("height") if isinstance(node.get("height"), int) else 0
            yield (w, hh, u)
        for v in node.values():
            yield from _iter_images(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_images(v)

def _pick_thumb(node):
    """Thumb video = lon nhat trong nhom i.ytimg.com cua subtree card.
       DA SUA (bug ban cu): KHONG con fallback 'or imgs'. Ly do: imgs gom ca googleusercontent
       (owner avatar/banner trong card), neu fallback thi khi card khong co ytimg se lay
       googleusercontent lam thumb -> embed hien avatar tron thay anh video. Quy tac moi:
       chi ytimg; khong co ytimg -> '' (entry 'tran' ve thumb), webhook bo image. Nhat quan
       voi _pick_avatar (chi googleusercontent): moi thu chi lay dung CDN cua no, khong gop."""
    imgs = list(_iter_images(node))
    yt = [x for x in imgs if _host(x[2]).endswith("ytimg.com")]
    if not yt:
        return ""
    return max(yt, key=lambda x: (x[0] * x[1], x[0], x[1]))[2]

def _avatar_score(w, h, u):
    s = 0
    if _AV_TOKEN.search(u) or "-c-k-no" in u or "-c-k" in u:
        s += 1000                       # token cat tron -> avatar, khong banner
    if w and h and w == h:
        s += 100                        # vuong -> avatar
    if w and h and w > h * 2:
        s -= 1000                       # ngang ro ret -> banner, phat nang
    return s

def _pick_avatar(whole_json):
    """Avatar kan = diem cao nhat trong nhom googleusercontent cua TOAN bo response.
       Banner (ngang, khong token) bi -1000 loai; owner avatar tren card cung thuoc avatar
       (cung asset) nen khong hai; header avatar resolution cao nhat thang. Path-free."""
    gu = [x for x in _iter_images(whole_json) if _host(x[2]).endswith("googleusercontent.com")]
    if not gu:
        return ""
    return max(gu, key=lambda x: (_avatar_score(x[0], x[1], x[2]), x[0] * x[1], x[0], x[1]))[2]

def _video_id_of(d):
    v = d.get("videoId")
    if isinstance(v, str) and v:
        return v
    v = d.get("contentId")
    if isinstance(v, str) and _VID_RE.match(v):
        return v
    return ""

def _collect(node, anchor, out, seen):
    if isinstance(node, dict):
        vid = _video_id_of(node)
        child = node if vid else anchor
        for v in node.values():
            _collect(v, child, out, seen)
    elif isinstance(node, list):
        for v in node:
            _collect(v, anchor, out, seen)
    elif isinstance(node, str):
        if not C.YT_KEYWORD_RE.search(node):
            return
        cs = code_sau_keyword_yt(node)
        if not cs:
            log(f'YT: co "CODE CHUNG" nhung khong trich duoc code (token dau < CODE_MIN_LEN?): "{node[:90]}"')
            return
        code = cs[0]
        vid = _video_id_of(anchor) if anchor else ""
        key = vid if vid else ("S" + node)
        if key in seen:
            return
        seen.add(key)
        out.append({
            "code": code,
            "title": node.strip(),
            "video_id": vid,
            "video_url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
            "thumb_url": _pick_thumb(anchor) if anchor else "",
        })

def _dedup_by_code(entries, limit):
    g = OrderedDict()
    for e in entries:
        c = e["code"]
        cur = g.get(c)
        if cur is None:
            g[c] = e
        elif (not cur.get("video_id")) and e.get("video_id"):
            g[c] = e
    return list(g.values())[:limit]

def _via_data_api():
    # Tra (entries|None|[], avatar). DataAPI playlist KHONG chua avatar kan -> avatar ''.
    if not C.YT_API_KEY:
        return None, ""
    try:
        r = requests.get(C.DATA_API_PLAYLIST, params={
            "part": "snippet", "playlistId": C.YT_UPLOADS_ID,
            "maxResults": max(15, C.YT_VIDEO_SCAN * 5), "key": C.YT_API_KEY}, timeout=20)
    except Exception as e:
        log("YT DataAPI exc:", e.__class__.__name__, e); return [], ""
    if r.status_code != 200:
        log("YT DataAPI http", r.status_code, "->", (r.text or "")[:200]); return [], ""
    try:
        j = r.json()
    except Exception:
        log("YT DataAPI khong phai JSON"); return [], ""
    raw = []
    for it in (j.get("items") or []):
        sn = it.get("snippet") or {}
        t = str(sn.get("title", "")).strip()
        if not t or not C.YT_KEYWORD_RE.search(t):
            continue
        cs = code_sau_keyword_yt(t)
        if not cs:
            log(f'YT DataAPI: co "CODE CHUNG" nhung khong trich duoc code: "{t[:90]}"'); continue
        rid = sn.get("resourceId") or {}
        vid = str(rid.get("videoId") or sn.get("videoId") or "")
        thumbs = sn.get("thumbnails") or {}
        thumb = _pick_thumb(thumbs) if isinstance(thumbs, dict) else ""
        raw.append({"code": cs[0], "title": t, "video_id": vid,
                    "video_url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
                    "thumb_url": thumb})
    return _dedup_by_code(raw, C.YT_VIDEO_SCAN), ""

def _via_innertube():
    # Tra (entries|None|[], avatar). Avatar TU lay tu chinh response nay (path-free heuristic).
    if not C.INNERTUBE_KEY:
        log("YT InnerTube: khong co key (env + public deu trong) -> BO QUA tang B.")
        return None, ""
    body = {"context": {"client": {"clientName": "WEB", "clientVersion": C.INNERTUBE_VERSION,
                                    "hl": "vi", "gl": "VN", "platform": "DESKTOP"}},
            "browseId": C.YT_CHANNEL_ID, "params": C.INNERTUBE_PARAMS_VIDEOS}
    try:
        r = requests.post(C.INNERTUBE_BROWSE, params={"key": C.INNERTUBE_KEY, "prettyPrint": "false"},
                          json=body, headers={**_HDR, "Content-Type": "application/json"}, timeout=20)
    except Exception as e:
        log("YT InnerTube exc:", e.__class__.__name__, e); return [], ""
    txt = r.text or ""
    log(f"YT InnerTube DIAG: http={r.status_code} len={len(txt)} videoId={txt.count(chr(34)+'videoId'+chr(34))}")
    if r.status_code != 200:
        log("   body[:200]=", repr(txt[:200])); return [], ""
    try:
        j = r.json()
    except Exception:
        log("   khong phai JSON; body[:200]=", repr(txt[:200])); return [], ""
    avatar = _pick_avatar(j)
    out, seen = [], set()
    _collect(j, None, out, seen)
    log(f"   entry tho (truoc group) = {len(out)} | avatar auto = {'CO' if avatar else 'khong'}")
    entries = _dedup_by_code(out, C.YT_VIDEO_SCAN)
    for e in entries:
        e["channel_avatar"] = avatar
    return entries, avatar

def get_yt_candidates():
    global _dumped_once
    verbose = os.getenv("YT_VERBOSE", "0") == "1"
    a, ava = _via_data_api()
    b, avb = _via_innertube()          # LUON goi de co avatar + redundancy (1 POST/phut, nhe)
    entries = a if a else b
    via = "DATA_API" if a else ("INNERTUBE" if b else None)
    if not entries:
        sa = "khong key (BO QUA)" if a is None else "chay -> 0"
        sb = "khong key (BO QUA)" if b is None else "chay -> 0"
        log(f"YT: 0 code. DataAPI: {sa}; InnerTube: {sb}. "
            f"(InnerTube mac dinh chay bang key public; neu 'BO QUA' kiem tra INNERTUBE_KEY config.)")
        return []
    avatar = (C.YT_CHANNEL_AVATAR or "").strip() or avb or ava   # override > auto(Innertube) > auto(DataAPI='')
    for e in entries:
        e["channel_avatar"] = avatar    # dam bao du entry tu DataAPI cung co key nay
    if verbose or not _dumped_once:
        _dumped_once = True
        log(f"YT [{via}]: {len(entries)} VIDEO MOI NHAT CO 'CODE CHUNG' (toi da {C.YT_VIDEO_SCAN}):")
        for i, e in enumerate(entries, 1):
            tg = []
            if not e.get("video_url"): tg.append("tran:no-videoId")
            if not e.get("thumb_url"): tg.append("no-thumb")
            if not e.get("channel_avatar"): tg.append("no-avatar")
            tag = ("  [" + ",".join(tg) + "]") if tg else ""
            log(f"   [{i:2}] {e['title'][:100]} -> `{e['code']}`{tag}")
    else:
        log(f"YT [{via}]: OK ({len(entries)} code tu {C.YT_VIDEO_SCAN} video moi nhat)")
    return entries
