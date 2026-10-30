# NGUON MA CHO VN = API (Data API v3 + InnerTube videos) + COMMUNITY POSTS (tab /posts).
# TRA VE (entries, bare): entries = video CO ma text (TITLE/DESC) + POST CO ma text;
#   bare = video upload KHONG co ma text nhung CO thumbnail + POST CHI CO ANH ma text
#   KHONG ra code = UNG VIEN OCR.
# COMMUNITY POSTS (schema THAT, bang chung F12 backstagePostRenderer): 3 duong hedged
#   (1) STRUCT _walk_posts doc dung postId/contentText/backstageImageRenderer -> entries
#       (link thang /post/<postId> + anh post) hoac bare (anh post, text khong code).
#   (2) FLAT regex 'MÃ CODE' tren HTML da giai \\uXXXX -> luoi entries text.
#   (3) BROWSE FALLBACK INNERTUBE_PARAMS_POSTS (params THAT) khi document GET consent wall.
# Dedupe video-truoc-post-sau: final = video_cut(3) + post_keep, post trung code video skip.
import os, re, json, requests
from . import config as C
from .parsers import code_sau_keyword_yt, code_from_desc_text
from .utils import log_yt, log_warn

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_HDR = {"User-Agent": UA, "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6"}
_dumped_once = False
_VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_IMG_HOSTS = ("ytimg.com", "googleusercontent.com", "ggpht.com")
_AV_TOKEN = re.compile(r"=s\d+-c\b")

# Neo post: "MÃ CODE" / "MA CODE" (5 dau A + a/A) -> token ASCII >=6.
# Cho pheo toi da 8 ky tu khong phai chu/sau (quote, backslash, space, dash...) de khop
# ca dang escaped trong HTML JS sau khi giai \\uXXXX. Hau kiem prefix PT/min-len.
_POST_CODE_RE = re.compile(
    r"M[ÀÁẢÃẠaàáảãạ]\s*CODE\s*[:\-–]?\s*[^A-Za-z0-9]{0,8}([A-Za-z0-9]{6,})", re.I)

_DUR_RE = re.compile(
    r"\s*(?:"
    r"\(?\d+(?:[:.]\d{1,2})?\s*(?:giây|giay|phút|phut|second|seconds|sec|minute|minutes|min)s?\)?"
    r"|\(\d{1,2}:\d{2}(?::\d{2})?\)"
    r")\s*$", re.I)

_YTID_MARK = re.compile(r"var\s+ytInitialData\s*=\s*")
_UESC = re.compile(r"\\u([0-9a-fA-F]{4})")


def _host(u):
    try:
        h = u.split("//", 1)[1].split("/", 1)[0]
    except Exception:
        return ""
    return h.lower()


def _abs_url(u):
    """//yt3... -> https://yt3... ; khong doi gi neu da http(s)."""
    u = (u or "").strip()
    if u.startswith("//"):
        return "https:" + u
    return u


def _is_img_host(u):
    h = _host(u)
    return any(h == d or h.endswith("." + d) for d in _IMG_HOSTS)


def _iter_images(node):
    if isinstance(node, dict):
        u = node.get("url")
        if isinstance(u, str):
            au = _abs_url(u)
            if au.startswith("http") and _is_img_host(au):
                w = node.get("width") if isinstance(node.get("width"), int) else 0
                hh = node.get("height") if isinstance(node.get("height"), int) else 0
                yield (w, hh, au)
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


def _find_nodes(node, key):
    """Lay moi dict con co key = <key> (duy de quy). Dung cho backstagePostRenderer."""
    if isinstance(node, dict):
        if key in node and isinstance(node[key], dict):
            yield node[key]
        for v in node.values():
            yield from _find_nodes(v, key)
    elif isinstance(node, list):
        for v in node:
            yield from _find_nodes(v, key)


def _pick_thumb(node):
    imgs = list(_iter_images(node))
    yt = [x for x in imgs if _host(x[2]).endswith(("ytimg.com", "ggpht.com"))]
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


def _strip_duration(s):
    return _DUR_RE.sub("", s or "").strip()


def _looks_title(s):
    if not s or len(s) < 8:
        return False
    if s.lower().startswith("http") or s.replace(".", "").isdigit():
        return False
    if s.strip().lower() in C.BANNED_TITLE_OVERLAYS:
        return False
    return " " in s


def _best_title(cands):
    if not cands:
        return ""
    cleaned = [_strip_duration(s) for s in cands]
    good = [s for s in cleaned if len(s) >= 12 and any(ch.isalnum() for ch in s)]
    if not good:
        return ""
    return max(good, key=len)


def _walk_cards(node, st):
    if isinstance(node, dict):
        vid = _video_id_of(node)
        if vid and vid not in st["seen"]:
            st["seen"].add(vid)
            idx = st["n"]
            st["n"] += 1
            thumb = _pick_thumb(node)
            tcode = None
            titles = []
            for s in _iter_strings(node):
                if _looks_title(s):
                    titles.append(s)
                cs = code_sau_keyword_yt(s)
                if cs and tcode is None:
                    tcode = cs[0]
            disp = _best_title(titles)
            card = {"idx": idx, "video_id": vid, "thumb_url": thumb,
                    "video_url": f"https://www.youtube.com/watch?v={vid}",
                    "title": disp, "title_code": tcode}
            if tcode:
                st["coded"].append(card)
            elif thumb:
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
    log_yt(f"   InnerTube: coded={len(entries)} | bare(ung vien OCR, CHUA xet gate)={len(st['bare'])} "
           f"| avatar={'CO' if avatar else 'khong'}")
    return entries, st["bare"], avatar


# ================= COMMUNITY POSTS (schema THAT: backstagePostRenderer) =================
def _post_text(post):
    """Noi dung contentText.runs[].text (code nam o day, bang chung F12)."""
    ct = post.get("contentText") or {}
    runs = ct.get("runs") or []
    return "".join(str(r.get("text", "")) for r in runs if isinstance(r, dict))


def _post_image(post):
    """Anh post tu backstageAttachment.backstageImageRenderer.image.thumbnails."""
    att = post.get("backstageAttachment") or {}
    bir = att.get("backstageImageRenderer") or {}
    img = bir.get("image") or {}
    thumbs = img.get("thumbnails") or []
    best, bw = "", 0
    for t in thumbs:
        if not isinstance(t, dict):
            continue
        u = _abs_url(t.get("url", ""))
        if not u.startswith("http"):
            continue
        w = t.get("width") if isinstance(t.get("width"), int) else 0
        h = t.get("height") if isinstance(t.get("height"), int) else 0
        if w * h > bw:
            bw = w * h
            best = u
    return best


def _post_code(text):
    for m in _POST_CODE_RE.finditer(text or ""):
        tok = m.group(1).upper()
        if len(tok) >= C.CODE_MIN_LEN and tok.startswith(tuple(C.CODE_PREFIXES)):
            return tok
    return None


def _post_title(text):
    """Title = dong dau contentText (vd '🧟【CODE CHUNG HALLOWEEN】...'), fallback nhan."""
    first = (text or "").split("\n", 1)[0].strip()
    if _looks_title(first):
        return first
    return "Bài đăng Community (Play Together VNG)"


def _walk_posts(j):
    """Duyet backstagePostRenderer THAT -> (entries text-code, bare anh-post-text-khong-code).
       entries: via=POST, video_url = link thang /post/<postId>, thumb_url = anh post.
       bare: chi khi post CO anh nhung text KHONG ra code -> ung vien OCR."""
    entries, bare = [], []
    seen_code = set()
    seen_pid = set()
    n = 0
    for post in _find_nodes(j, "backstagePostRenderer"):
        pid = str(post.get("postId", "") or "").strip()
        text = _post_text(post)
        code = _post_code(text)
        img = _post_image(post)
        link = (C.YT_POST_LINK + pid) if pid else C.YT_CHANNEL_POSTS

        if code:
            if code in seen_code:
                continue
            seen_code.add(code)
            entries.append({"code": code, "title": _post_title(text),
                            "video_id": ("POST-" + pid) if pid else ("POST-" + code),
                            "video_url": link, "thumb_url": img,
                            "via": "POST", "redeem": True, "idx": 100000 + n})
            n += 1
        elif img:
            if pid and pid in seen_pid:
                continue
            if pid:
                seen_pid.add(pid)
            vid = ("POSTIMG-" + pid) if pid else ("POSTIMG-" + str(n))
            bare.append({"idx": 200000 + n, "video_id": vid, "thumb_url": img,
                         "video_url": link, "title": _post_title(text)})
            n += 1
    return entries, bare


def _codes_from_text(s):
    """FLAT luoi: chay thang regex tren xấp text (da giai \\uXXXX)."""
    out, seen = [], set()
    for m in _POST_CODE_RE.finditer(s or ""):
        tok = m.group(1).upper()
        if len(tok) < C.CODE_MIN_LEN or not tok.startswith(tuple(C.CODE_PREFIXES)):
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _unescape_js(s):
    return _UESC.sub(lambda m: chr(int(m.group(1), 16)), s or "")


def _parse_posts_html(html):
    """(1) STRUCT: tach ytInitialData -> _walk_posts. (2) FLAT: regex toan bo HTML.
       Tra (entries, bare, diag)."""
    entries, bare = [], []
    struct_ok = False
    m = _YTID_MARK.search(html or "")
    if m:
        try:
            obj, _end = json.JSONDecoder().raw_decode(html, m.end())
            struct_ok = True
            entries, bare = _walk_posts(obj)
        except Exception:
            struct_ok = False

    seen = {e["code"] for e in entries}
    for c in _codes_from_text(_unescape_js(html or "")):
        if c not in seen:
            seen.add(c)
            entries.append({"code": c, "title": "Bài đăng Community (Play Together VNG)",
                            "video_id": "POST-" + c, "video_url": C.YT_CHANNEL_POSTS,
                            "thumb_url": "", "via": "POST", "redeem": True,
                            "idx": 150000 + len(entries)})

    diag = ""
    if not entries and not bare:
        diag = (f"struct={'CO' if struct_ok else 'KHONG'} ytInitialData; flat 0; "
                f"head={repr((html or '')[:200])}")
    return entries, bare, diag


def _via_posts_browse():
    """(3) FALLBACK: POST /browse voi INNERTUBE_PARAMS_POSTS (params THAT)."""
    if not C.INNERTUBE_KEY:
        return [], []
    for prm in C.INNERTUBE_PARAMS_POSTS:
        body = {"context": {"client": {"clientName": "WEB", "clientVersion": C.INNERTUBE_VERSION,
                                        "hl": "vi", "gl": "VN", "platform": "DESKTOP"}},
                "browseId": C.YT_CHANNEL_ID, "params": prm}
        try:
            r = requests.post(C.INNERTUBE_BROWSE,
                              params={"key": C.INNERTUBE_KEY, "prettyPrint": "false"},
                              json=body, headers={**_HDR, "Content-Type": "application/json"},
                              timeout=20)
        except Exception as e:
            log_yt("Posts browse loi mang (candidate", prm, "):", e.__class__.__name__)
            continue
        if r.status_code != 200:
            log_yt("Posts browse http", r.status_code, "(candidate", prm, ") -> thu ke")
            continue
        try:
            j = r.json()
        except Exception:
            log_yt("Posts browse khong phai JSON (candidate", prm, ") -> thu ke")
            continue
        ents, bars = _walk_posts(j)
        if ents or bars:
            log_yt(f"Posts browse: candidate {prm} -> {len(ents)} entries + {len(bars)} bare")
            return ents, bars
        log_yt("Posts browse candidate", prm, " -> 0 post -> thu ke")
    log_warn("Posts: document GET fail VA browse (INNERTUBE_PARAMS_POSTS that) cung 0. "
             "Mo F12 tab Posts -> copy 'params' day du vao env INNERTUBE_PARAMS_POSTS. "
             "Video/OCR van chay.")
    return [], []


def _via_posts():
    """Tra (entries, bare). Thu document GET (struct+flat) truoc; neu rong -> browse fallback."""
    if not C.YT_POSTS:
        return [], []
    hdr = dict(_HDR)
    hdr["Accept"] = "text/html,application/xhtml+xml"
    if C.YT_POSTS_COOKIE:
        hdr["Cookie"] = C.YT_POSTS_COOKIE
    try:
        r = requests.get(C.YT_CHANNEL_POSTS, headers=hdr, timeout=25)
        if r.status_code == 200:
            entries, bare, diag = _parse_posts_html(r.text or "")
            if entries or bare:
                log_yt(f"Posts: document -> {len(entries)} entries + {len(bare)} bare")
                return entries, bare
            log_yt(f"Posts: document {diag} -> 0, thu browse fallback")
        else:
            log_yt(f"Posts document http {r.status_code} -> thu browse fallback")
    except Exception as e:
        log_yt("Posts document loi mang:", e.__class__.__name__)
    return _via_posts_browse()


def get_yt_candidates():
    global _dumped_once
    verbose = os.getenv("YT_VERBOSE", "0") == "1"

    a_e, a_b, ava = _via_data_api()
    b_e, b_b, avb = _via_innertube()
    pools_e = [x for x in (a_e, b_e) if x]
    pools_b = [x for x in (a_b, b_b) if x]

    post_e, post_b = _via_posts()

    if not pools_e and not pools_b and not post_e and not post_b:
        sa = "khong key (BO QUA)" if a_e is None else "chay -> 0"
        sb = "khong key (BO QUA)" if b_e is None else "chay -> 0"
        log_yt(f"0 ma. DataAPI: {sa}; InnerTube: {sb}; Posts: 0. (OCR mode={C.OCR_MODE}.)")
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

    if post_e:
        kept = 0
        for p in post_e:
            if p["code"] in seen:
                log_yt(f"Posts skip dup: `{p['code']}` da co tu video (tang text lo) "
                       f"-> bo qua post, khong nhap 2 lan")
                continue
            if kept >= C.YT_POSTS_MAX:
                log_yt(f"Posts dat cap {C.YT_POSTS_MAX}/vong -> con {len(post_e)-kept} cho vong sau")
                break
            final.append(p)
            seen.add(p["code"])
            kept += 1

    all_pools_b = list(pools_b)
    if post_b:
        all_pools_b.append(post_b)

    bb = {}
    for lst in all_pools_b:
        for c in lst:
            cur = bb.get(c["video_id"])
            if cur is None or c["idx"] < cur["idx"]:
                bb[c["video_id"]] = c
    bare = sorted(bb.values(), key=lambda c: c["idx"])

    order = (getattr(C, "BARE_ORDER", "newest-first") or "").strip().lower()
    if order == "newest-first":
        bare = list(reversed(bare))
    elif order == "random":
        import random
        random.shuffle(bare)

    avatar = (getattr(C, "YT_CHANNEL_AVATAR", "") or "").strip() or avb or ava
    for e in final:
        e["channel_avatar"] = avatar
    for c in bare:
        c["channel_avatar"] = avatar

    n_post = sum(1 for e in final if e.get("via") == "POST")
    if verbose or not _dumped_once:
        _dumped_once = True
        log_yt(f"{len(final)} ENTRY CO MA TEXT (video<= {C.YT_VIDEO_SCAN} + post<= {C.YT_POSTS_MAX}; "
               f"post={n_post}):")
        for i, e in enumerate(final, 1):
            tg = [f"via={e.get('via')}"]
            if not e.get("thumb_url"):
                tg.append("no-thumb")
            log_yt(f"   [{i:2}] {e['title'][:90]} -> `{e['code']}`  [{', '.join(tg)}]")
        log_yt(f"{len(bare)} UNG VIEN OCR (BARE_ORDER={order}; gate chan neu khong chu CODE; "
               f"chi PASS gate moi tinh quota {C.OCR_MAX_IMAGES}):")
        for i, c in enumerate(bare[:12], 1):
            log_yt(f"   [{i:2}] {c['title'][:90]}  (video {c['video_id']})")
        if len(bare) > 12:
            log_yt(f"   ... con {len(bare)-12} nua (khong dump)")
    else:
        log_yt(f"OK ({len(final)} ma text [video+post={n_post}] + {len(bare)} ung vien OCR "
               f"choi gate, BARE_ORDER={order})")
    return final, bare
