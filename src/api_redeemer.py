# DUONG CHINH REDEEM = goi thang API (F12 21:52). Khong Cookie -> login OPTIONAL o tang
# redeem VNG (box "Dang nhap de rut ngan thoi gian..." chi la gay y; F12 to khong can
# cookie de redeem). Phan quan thang/thua = MA SO JSON (language-proof); ti so 0/1|1/1
# chi la backup khi response khong phai JSON. Cung contract voi redeemer._attempt de
# main.py KHONG can doi: status in success|failure|retry|captcha|unknown (+kind/reason).
# (Khong dung docstring module co chua backslash-u tran -> tranh SyntaxError luc import.)
import uuid, json, requests
from . import config as C
from .utils import log

def _headers():
    # Replica Request Headers F12 (bo Baggage/Sentry - server khong bat buoc). KHONG Cookie.
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

def _any(low, needles): return any(str(n).lower() in low for n in needles)

def _text_classify(low):
    if _any(low, C.FAIL_USAGE):     return "usage_limit", "hết lượt nhập / usage limit"
    if _any(low, C.FAIL_NOTEXIST):  return "not_exist",   "không tồn tại / sai mã"
    if _any(low, C.FAIL_IDERROR):   return "id_error",    "ID không tìm thấy/offline — kiểm tra id_user.txt"
    if _any(low, C.FAIL_VALIDATION):return "validation",  "thông tin nhập không hợp lệ"
    if _any(low, C.NEED_LOGIN):     return "need_login",  "chưa liên kết tài khoản"
    if _any(low, C.TRANSIENT):      return "transient",   "lỗi hệ thống tạm thời"
    return None, None

def _num_of(j):
    if not isinstance(j, dict): return None
    for k in ("code","errorCode","errcode","err_code","resultCode","status"):
        v = j.get(k)
        if isinstance(v, int): return v
    return None

def preview_payload(code, uid):
    """In raw payload JSON de doi chieu F12 tab Payload (main.py dung trong DRY_RUN).
       Day la ham MA main.py import -> thieu no la ImportErrors nhu anh gap."""
    return json.dumps(_payload(code, uid), ensure_ascii=False)

def redeem_via_api(code, uid):
    try:
        r = requests.post(C.API_URL, json=_payload(code, uid), headers=_headers(), timeout=20)
    except Exception as e:
        log(f"API network exc: {e.__class__.__name__} -> retry")
        return {"status": "retry", "kind": "transient", "reason": "network exception"}
    raw = r.text or ""; low = raw.lower()
    try: j = r.json()
    except Exception: j = None
    num = _num_of(j)
    msg = str((j or {}).get("message") or (j or {}).get("msg") or (j or {}).get("error") or "") if isinstance(j, dict) else ""
    mlow = (msg or raw).lower()
    log(f"API http={r.status_code} num={num} msg={msg[:120]!r}")

    if _any(low, C.CAPTCHA_HINTS) or r.status_code == 429:
        return {"status": "captcha"}
    if num in C.NUM_SUCCESS or (isinstance(j, dict) and j.get("success") is True):
        k, _ = _text_classify(mlow)                       # paranoia: message mau thuan?
        if k in ("usage_limit","not_exist","id_error"):
            return {"status":"failure","kind":k,"reason":f"num={num} nhưng message báo {k}"}
        return {"status": "success"}
    if num in C.NUM_VALIDATION:
        log("PAYLOAD SAI? (server tra 1002) -> mo F12 tab Payload, copy raw JSON "
            "vao API_PAYLOAD_TEMPLATE trong config.py. Bot retry, KHONG chot.")
        return {"status":"retry","kind":"payload_suspect","reason":"nghi payload sai ten field (1002)"}
    if num in C.NUM_TRANSIENT:  return {"status":"retry","kind":"transient","reason":f"loi he thong tam (num={num})"}
    if num in C.NUM_NEED_LOGIN: return {"status":"retry","kind":"need_login","reason":"chua lien ket tai khoan (2101)"}
    if num in C.NUM_NOT_EXIST:  return {"status":"failure","kind":"not_exist","reason":"khong ton tai / sai ma (2102)"}
    if num in C.NUM_ID_ERROR:   return {"status":"failure","kind":"id_error","reason":"ID khong tim thay/offline (2105)"}
    if num is not None:
        k, reason = _text_classify(mlow)
        if k: return {"status":"failure","kind":k,"reason":reason}
        return {"status":"failure","kind":"other","reason":f"ma loi chua map num={num}"}
    k, reason = _text_classify(mlow)
    if k in ("usage_limit","not_exist","id_error","validation"): return {"status":"failure","kind":k,"reason":reason}
    if k in ("transient","need_login"): return {"status":"retry","kind":k,"reason":reason}
    if r.ok:
        if C.RATIO_FAIL in low: return {"status":"failure","kind":"other","reason":"that bai (0/1)"}
        return {"status":"success"}
    if C.RATIO_FAIL in low: return {"status":"failure","kind":"other","reason":"that bai (0/1)"}
    log(f"API unknown http={r.status_code} body[:300]={raw[:300]!r}")
    return {"status":"unknown","reason":"api response chua map"}
