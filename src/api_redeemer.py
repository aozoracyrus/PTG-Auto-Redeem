import uuid, json, requests
from . import config as C
from .utils import log_api, log_warn

_VAL_LOCK_AFTER = 6
_val_streak = 0
_payload_locked = False


def _headers():
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6",
        "Content-Type": "application/json",
        "Origin": "https://giftcode.vnggames.com",
        "Referer": "https://giftcode.vnggames.com/",
        "User-Agent": C.API_UA,
        "X-Client-Region": "VN",
        "X-Request-Id": str(uuid.uuid4()),
        "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site",
    }


def _payload(code, uid):
    out = {}
    for k, v in C.API_PAYLOAD_TEMPLATE.items():
        out[k] = v.format(code=code, id=uid, region="vn") if isinstance(v, str) else v
    return out


def _any(low, needles):
    return any(str(n).lower() in low for n in needles)


def _text_classify(low):
    if _any(low, C.FAIL_USAGE):      return "usage_limit", "hết lượt nhập"
    if _any(low, C.FAIL_NOTEXIST):   return "not_exist",   "không tồn tại / sai mã"
    if _any(low, C.FAIL_IDERROR):    return "id_error",    "ID không tìm thấy/offline"
    if _any(low, C.FAIL_VALIDATION): return "validation",  "thông tin không hợp lệ"
    if _any(low, C.NEED_LOGIN):      return "need_login",  "chưa liên kết tài khoản"
    if _any(low, C.TRANSIENT):       return "transient",   "lỗi hệ thống tạm thời"
    return None, None


def _num_of(j):
    if not isinstance(j, dict):
        return None
    for k in ("errorCode", "code", "errcode", "err_code", "resultCode", "status"):
        v = j.get(k)
        if isinstance(v, int):
            return v
    return None


def preview_payload(code, uid):
    return json.dumps(_payload(code, uid), ensure_ascii=False)


def redeem_via_api(code, uid):
    global _val_streak, _payload_locked
    if _payload_locked:
        return {"status": "stuck", "kind": "payload_locked",
                "reason": "payload chưa xác nhận (1002 lặp)"}
    try:
        r = requests.post(C.API_URL, json=_payload(code, uid), headers=_headers(), timeout=20)
    except Exception as e:
        log_api(f"Loi mang ({e.__class__.__name__}) -> stuck")
        return {"status": "stuck", "kind": "network", "reason": f"mạng: {e.__class__.__name__}"}

    raw = r.text or ""
    low = raw.lower()
    try:
        j = r.json()
    except Exception:
        j = None
    num = _num_of(j)
    msg = str((j or {}).get("message") or (j or {}).get("description") or (j or {}).get("msg") or (j or {}).get("error") or "") if isinstance(j, dict) else ""
    mlow = (msg or raw).lower()
    log_api(f"http={r.status_code} errorCode={num} msg={msg[:120]!r}")

    if num != 1002:
        _val_streak = 0
        _payload_locked = False

    if _any(low, C.CAPTCHA_HINTS) or r.status_code == 429:
        return {"status": "captcha"}

    if num in C.NUM_SUCCESS:
        k, _ = _text_classify(mlow)
        if k in ("usage_limit", "not_exist", "id_error"):
            return {"status": "failure", "kind": k, "reason": f"errorCode={num} nhưng message báo {k}"}
        return {"status": "success"}
    if num in C.NUM_VALIDATION:
        _val_streak += 1
        pl = preview_payload(code, uid)
        log_api(f"PAYLOAD ({len(pl)} bytes): {pl}")
        if _val_streak >= _VAL_LOCK_AFTER:
            _payload_locked = True
            log_warn(f"1002 lap {_val_streak} lan -> KHOA payload")
            return {"status": "stuck", "kind": "payload_locked", "reason": "payload 1002 lặp"}
        return {"status": "retry", "kind": "payload_suspect", "reason": "nghi payload sai (1002)"}
    if num in C.NUM_USAGE:
        return {"status": "failure", "kind": "usage_limit", "reason": "hết lượt (2117)"}
    if num in C.NUM_CODE_BAD:
        return {"status": "failure", "kind": "not_exist", "reason": "không tồn tại / sai mã (2106/2102)"}
    if num in C.NUM_ID_ERROR:
        return {"status": "failure", "kind": "id_error", "reason": "ID không tìm thấy/offline (2105)"}
    if num in C.NUM_NEED_LOGIN:
        return {"status": "retry", "kind": "need_login", "reason": "chưa liên kết tài khoản (2101)"}
    if num in C.NUM_TRANSIENT:
        return {"status": "stuck", "kind": "transient", "reason": f"lỗi tạm (errorCode={num})"}

    if num is not None:
        k, reason = _text_classify(mlow)
        if k in ("usage_limit", "not_exist", "id_error", "validation"):
            return {"status": "failure", "kind": k, "reason": reason}
        if k == "transient":
            return {"status": "stuck", "kind": "transient", "reason": reason}
        if k == "need_login":
            return {"status": "retry", "kind": "need_login", "reason": reason}
        return {"status": "failure", "kind": "other", "reason": f"mã lỗi chưa map errorCode={num}"}

    k, reason = _text_classify(mlow)
    if k in ("usage_limit", "not_exist", "id_error", "validation"):
        return {"status": "failure", "kind": k, "reason": reason}
    if r.status_code in C.HTTP_STUCK:
        return {"status": "stuck", "kind": "http_stuck", "reason": f"HTTP {r.status_code}"}
    if r.ok:
        if C.RATIO_FAIL in low:
            return {"status": "failure", "kind": "other", "reason": "thất bại (0/1)"}
        return {"status": "success"}
    if C.RATIO_FAIL in low:
        return {"status": "failure", "kind": "other", "reason": "thất bại (0/1)"}
    log_api(f"Khong nhan dien duoc http={r.status_code} body[:300]={raw[:300]!r}")
    return {"status": "stuck", "kind": "unknown", "reason": f"response chưa map (http={r.status_code})"}
