# NGUON MA CHO VN = API (Data API v3 + InnerTube public fallback).
# TRA VE (entries, bare): entries = video CO ma text (TITLE/DESC); bare = video KHONG co
#   ma text nhung CO thumbnail = UNG VIEN OCR.
# SUA LAN NAY (nhan loi): BO _is_live_node. Ham do phong doan cau truc InnerTube
#   (liveStreamingDetails / style=="LIVE") -> skipped_live=0 = hong hoan toan, va nhan log
#   "live da loc" tung ho mot tinh nang khong chay. Live KHONG can loc bang field: OCR gate
#   (da chung minh chay dung) tu chan live im lang (anh live khong co chu CODE). Van de that
#   la quota bi ap TRUOC gate -> live dung dau an het slot. Nay: bare tra VE KHONG CAT, va
#   ocr.py ap quota SAU gate (chi video PASS gate moi tinh slot). -> khong con phong doan.
import os, re, json, requests
from . import config as C
from .parsers import code_sau_keyword_yt, code_from_desc_text
from .utils import log_yt, log_warn

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HDR = {"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6"}
_dumped_once = False
_VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_IMG_HOSTS = ("ytimg.com", "googleusercontent.com")
_AV_TOKEN = re.compile(r"=s\d+-c\b")


def _host(u):
    try:
        h = u.split("//", 1)[1].split("/", 1)[0]
    except Exception:
        return ""
    return h.lower()


def _is_img_host(u):
    h = _host(u)
    return any(h == d or h.endswith("." + d) for d in _IMG_HOSTS)


def _iter_images(node):
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


def _iter_strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _iter_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_strings(v)
    elif isinstance(node, str):
        yield node


def _pick_thumb(node):
    imgs = list(_iter_images(node))
    yt = [x for x in imgs if _host(x[2]).endswith("ytimg.com")]
    if not yt:
        return ""
    return max(yt, key=lambda x: (x[0] * x[1], x[0], x[1]))[2]


def _avatar_score(w, h, u):
    s = 0
    if _AV_TOKEN.search(u) or "-c-k-no" in u or "-c-k" in u:
        s += 1000
    if w and h and w == h:
        s += 100
    if w and h and w > h * 2:
        s -= 1000
    return s


def _pick_avatar(whole_json):
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


def _looks_title(s):
    return bool(s) and len(s) >= 8 and " " in s and not s.lower().startswith("http") \
        and not s.replace(".", "").isdigit()


def _walk_cards(node, st):
    if isinstance(node, dict):
        vid = _video_id_of(node)
        if vid and vid not in st["seen"]:
            st["seen"].add(vid)
            idx = st["n"]
            st["n"] += 1
            thumb = _pick_thumb(node)
            tcode = None
            disp = ""
            for s in _iter_strings(node):
                if not disp and _looks_title(s):
                    disp = s
                cs = code_sau_keyword_yt(s)
                if cs:
                    tcode = cs[0]
                    disp = s
                    break
            card = {"idx": idx, "video_id": vid, "thumb_url": thumb,
                    "video_url": f"https://www.youtube.com/watch?v={vid}",
                    "title": disp, "title_code": tcode}
            if tcode:
                st["coded"].append(card)
            elif thumb:                      # KHONG loc live o day; gate lo sau
                st["bare"].append(card)
        for v in node.values():
            _walk_cards(v, st)
    elif isinstance(node, list):
        for v in node:
            _walk_cards(v, st)


def _via_data_api():
    if not C.YT_API_KEY:
        return None, [], ""
    try:
        r = requests.get(C.DATA_API_PLAYLIST, params={
            "part": "snippet", "playlistId": C.YT_UPLOADS_ID,
            "maxResults": max(15, C.YT_VIDEO_SCAN * 5), "key": C.YT_API_KEY}, timeout=20)
    except Exception as e:
        log_yt("DataAPI loi mang:", e.__class__.__name__, e)
        return [], [], ""
    if r.status_code != 200:
        log_yt("DataAPI http", r.status_code, "->", (r.text or "")[:200])
        return [], [], ""
    try:
        j = r.json()
    except Exception:
        log_yt("DataAPI khong phai JSON")
        return [], [], ""
    entries, bare = [], []
    for i, it in enumerate(j.get("items") or []):
        sn = it.get("snippet") or {}
        title = str(sn.get("title", "")).strip()
        desc = str(sn.get("description", "")).strip()
        rid = sn.get("resourceId") or {}
        vid = str(rid.get("videoId") or sn.get("videoId") or "")
        thumbs = sn.get("thumbnails") or {}
        thumb = _pick_thumb(thumbs) if isinstance(thumbs, dict) else ""
        url = f"https://www.youtube.com/watch?v={vid}" if vid else ""
        tc = code_sau_keyword_yt(title)
        if tc:
            entries.append({"code": tc[0], "title": title or f"Mã {tc[0]}", "video_id": vid,
                            "video_url": url, "thumb_url": thumb, "via": "TITLE",
                            "redeem": True, "idx": i})
            continue
        dc = code_from_desc_text(desc)
        if dc:
            entries.append({"code": dc[0], "title": title or f"Mã {dc[0]}", "video_id": vid,
                            "video_url": url, "thumb_url": thumb, "via": "DESC",
                            "redeem": True, "idx": i})
        elif thumb:
            bare.append({"idx": i, "video_id": vid, "thumb_url": thumb,
                         "video_url": url, "title": title})
    return entries, bare, ""


def _via_innertube():
    if not C.INNERTUBE_KEY:
        log_warn("InnerTube: khong co key -> BO QUA tang B.")
        return None, [], ""
    body = {"context": {"client": {"clientName": "WEB", "clientVersion": C.INNERTUBE_VERSION,
                                    "hl": "vi", "gl": "VN", "platform": "DESKTOP"}},
            "browseId": C.YT_CHANNEL_ID, "params": C.INNERTUBE_PARAMS_VIDEOS}
    try:
        r = requests.post(C.INNERTUBE_BROWSE, params={"key": C.INNERTUBE_KEY, "prettyPrint": "false"},
                          json=body, headers={**_HDR, "Content-Type": "application/json"}, timeout=20)
    except Exception as e:
        log_yt("InnerTube loi mang:", e.__class__.__name__, e)
        return [], [], ""
    txt = r.text or ""
    log_yt(f"Chuan doan InnerTube: http={r.status_code}, dai={len(txt)}, "
           f"videoId={txt.count(chr(34) + 'videoId' + chr(34))}")
    if r.status_code != 200:
        log_yt("   body[:200]=", repr(txt[:200]))
        return [], [], ""
    try:
        j = r.json()
    except Exception:
        log_yt("   khong phai JSON; body[:200]=", repr(txt[:200]))
        return [], [], ""
    avatar = _pick_avatar(j)
    st = {"seen": set(), "n": 0, "coded": [], "bare": []}
    _walk_cards(j, st)
    entries = [{"code": c["title_code"], "title": c["title"] or f"Mã {c['title_code']}",
                "video_id": c["video_id"], "video_url": c["video_url"],
                "thumb_url": c["thumb_url"], "via": "TITLE", "redeem": True, "idx": c["idx"]}
               for c in st["coded"]]
    # Nhan log TRUNG THUC: khong con "da loc live" (khong loc nua).
    log_yt(f"   InnerTube: coded={len(entries)} | bare(ung vien OCR, CHUA xet gate)={len(st['bare'])} "
           f"| avatar={'CO' if avatar else 'khong'}")
    return entries, st["bare"], avatar


def get_yt_candidates():
    global _dumped_once
    verbose = os.getenv("YT_VERBOSE", "0") == "1"
    a_e, a_b, ava = _via_data_api()
    b_e, b_b, avb = _via_innertube()
    pools_e = [x for x in (a_e, b_e) if x]
    pools_b = [x for x in (a_b, b_b) if x]
    if not pools_e and not pools_b:
        sa = "khong key (BO QUA)" if a_e is None else "chay -> 0"
        sb = "khong key (BO QUA)" if b_e is None else "chay -> 0"
        log_yt(f"0 ma. DataAPI: {sa}; InnerTube: {sb}. (OCR mode={C.OCR_MODE}.)")
        return [], []
    by_vid = {}
    for lst in pools_e:
        for e in lst:
            vid = e.get("video_id") or ("S" + e["code"])
            cur = by_vid.get(vid)
            if cur is None or e["idx"] < cur["idx"]:
                by_vid[vid] = e
    merged = sorted(by_vid.values(), key=lambda e: e["idx"])
    seen, final = set(), []
    for e in merged:
        if e["code"] in seen:
            continue
        seen.add(e["code"])
        final.append(e)
    final = final[: C.YT_VIDEO_SCAN]
    bb = {}
    for lst in pools_b:
        for c in lst:
            cur = bb.get(c["video_id"])
            if cur is None or c["idx"] < cur["idx"]:
                bb[c["video_id"]] = c
    # KHONG cat bare o day: quota OCR_MAX_IMAGES se duoc ap SAU gate trong ocr.py,
    # de live/trailer (gate fail, im lang) khong an slot cua video ma-trong-anh.
    bare = sorted(bb.values(), key=lambda c: c["idx"])
    avatar = (getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip() or avb or ava
    for e in final:
        e["channel_avatar"] = avatar
    for c in bare:
        c["channel_avatar"] = avatar
    if verbose or not _dumped_once:
        _dumped_once = True
        log_yt(f"{len(final)} VIDEO MOI NHAT CO MA TEXT (toi da {C.YT_VIDEO_SCAN}):")
        for i, e in enumerate(final, 1):
            tg = [f"via={e.get('via')}"]
            if not e.get("thumb_url"):
                tg.append("no-thumb")
            log_yt(f"   [{i:2}] {e['title'][:90]} -> `{e['code']}`  [{', '.join(tg)}]")
        log_yt(f"{len(bare)} UNG VIEN OCR (se duoc gate chan neu khong co chu CODE; "
               f"chi video PASS gate moi tinh vao quota {C.OCR_MAX_IMAGES}):")
        for i, c in enumerate(bare[:12], 1):   # dump 12 dau du nhin, khong spam log
            log_yt(f"   [{i:2}] {c['title'][:90]}  (video {c['video_id']})")
        if len(bare) > 12:
            log_yt(f"   ... con {len(bare)-12} nua (khong dump)")
    else:
        log_yt(f"OK ({len(final)} ma text + {len(bare)} ung vien OCR choi gate)")
    return final, bare
