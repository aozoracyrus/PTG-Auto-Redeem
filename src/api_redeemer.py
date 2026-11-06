# API REDEEMER. Phân quang thắng/thua = MÃ SỐ JSON + TEXT, không phụ thuộc ngôn ngữ.
# 2117/2121: BẰNG CHỨNG RUNTIME 05/11/2026 = "Active code: usage limit" -> HẾT LƯỢT TOÀN CỤC.
#   Nên PHÂN LOẠI THEO TEXT TRƯỚC, MÃ SỐ SAU:
#     - text khớp USAGE_LIMIT_TEXT -> status="failure", kind="usage_limit" (ĐỎ + blacklist code).
#     - text khớp ALREADY_SELF_TEXT -> status="already" (XANH + đóng cặp, KHÔNG blacklist).
#     - mã 2117/2121 mà text không rõ -> MẶC ĐỊNH usage_limit (đỏ + blacklist), theo bằng chứng.
#   blacklsit code do tầng gọi (main.py/ocr.py) xử lý qua key "|__DEAD__" trong state.
import json, uuid, requests
from . import config as C
from .utils import log_api, log_warn


def _fill(node, code, uid):
    if isinstance(node, dict):
        return {k: _fill(v, code, uid) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill(x, code, uid) for x in node]
    if isinstance(node, str):
        return node.replace("{id}", str(uid)).replace("{code}", str(code))
    return node


def preview_payload(code, uid):
    return _fill(C.API_PAYLOAD_TEMPLATE, code, uid)


def _headers():
    return {
        "User-Agent": C.API_UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.6",
        "Origin": "https://giftcode.vnggames.com",
        "Referer": C.URL_VN,
        "X-Client-Region": "VN",
        "X-Request-Id": uuid.uuid4().hex,
    }


def _extract_error_code(node):
    if isinstance(node, dict):
        for k in ("errorCode", "error_code", "errCode", "statusCode"):
            if k in node:
                v = node[k]
                try:
                    return int(v)
                except Exception:
                    pass
        for v in node.values():
            ec = _extract_error_code(v)
            if ec is not None:
                return ec
    elif isinstance(node, list):
        for v in node:
            ec = _extract_error_code(v)
            if ec is not None:
                return ec
    return None


def _extract_message(node):
    if isinstance(node, dict):
        for k in ("description", "message", "msg", "errorMessage", "error"):
            if k in node:
                v = node[k]
                if isinstance(v, str) and v.strip():
                    return v.strip()
                if isinstance(v, (dict, list)):
                    s = _extract_message(v)
                    if s:
                        return s
        for v in node.values():
            s = _extract_message(v)
            if s:
                return s
    elif isinstance(node, list):
        for v in node:
            s = _extract_message(v)
            if s:
                return s
    return ""


def _contains_any(low, needles):
    return any(str(n).lower() in low for n in needles)


def _classify(http_status, body):
    text = (_extract_message(body) or "").strip()
    low = text.lower()
    ec = _extract_error_code(body)

    if http_status in C.HTTP_STUCK:
        return {
            "status": "stuck",
            "reason": f"HTTP {http_status}: {text[:180] or 'transport stuck'}",
            "numeric": ec,
        }

    # ---- TEXT-FIRST: usage-limit toàn cục (ĐỎ + blacklist) trược already-self (XANH) ----
    if _contains_any(low, C.USAGE_LIMIT_TEXT):
        return {
            "status": "failure",
            "kind": "usage_limit",
            "reason": text or "Code đã đạt giới hạn sử dụng toàn cục (usage limit).",
            "numeric": ec,
        }
    if _contains_any(low, C.ALREADY_SELF_TEXT):
        return {
            "status": "already",
            "kind": "already_redeemed",
            "reason": text or "ID này đã redeem code này trước đó (already).",
            "numeric": ec,
        }

    if ec is not None:
        if ec in C.NUM_SUCCESS:
            return {"status": "success", "reason": text or "Thành công", "numeric": ec}

        # 2117/2121 text không rõ -> MẶC ĐỊNH usage-limit (bằng chứng runtime 05/11/2026).
        if ec in C.NUM_USAGE_LIMIT:
            return {
                "status": "failure",
                "kind": "usage_limit",
                "reason": text or "Code đã hết lượt nhập toàn cục (2117/2121 mặc định usage).",
                "numeric": ec,
            }

        if ec in C.NUM_CODE_BAD:
            return {
                "status": "failure",
                "kind": "not_exist",
                "reason": text or "Mã không tồn tại hoặc sai.",
                "numeric": ec,
            }

        if ec in C.NUM_ID_ERROR:
            return {
                "status": "failure",
                "kind": "id_error",
                "reason": text or "ID nhân vật lỗi/offline/không tìm thấy.",
                "numeric": ec,
            }

        if ec in C.NUM_NEED_LOGIN:
            return {
                "status": "failure",
                "kind": "need_login",
                "reason": text or "Cần liên kết tài khoản game.",
                "numeric": ec,
            }

        if ec in C.NUM_TRANSIENT:
            return {
                "status": "retry",
                "reason": text or f"Transient {ec}",
                "numeric": ec,
            }

        if ec in C.NUM_VALIDATION:
            return {
                "status": "failure",
                "kind": "validation",
                "reason": text or f"Validation {ec}",
                "numeric": ec,
            }

    if _contains_any(low, C.CAPTCHA_HINTS):
        return {"status": "captcha", "reason": text or "Captcha"}

    if _contains_any(low, C.FAIL_NOTEXIST):
        return {
            "status": "failure",
            "kind": "not_exist",
            "reason": text or "Mã không tồn tại hoặc sai.",
            "numeric": ec,
        }

    if _contains_any(low, C.FAIL_IDERROR):
        return {
            "status": "failure",
            "kind": "id_error",
            "reason": text or "ID lỗi.",
            "numeric": ec,
        }

    if _contains_any(low, C.NEED_LOGIN):
        return {
            "status": "failure",
            "kind": "need_login",
            "reason": text or "Cần liên kết tài khoản game.",
            "numeric": ec,
        }

    if _contains_any(low, C.FAIL_VALIDATION):
        return {
            "status": "failure",
            "kind": "validation",
            "reason": text or "Dữ liệu không hợp lệ.",
            "numeric": ec,
        }

    if _contains_any(low, C.TRANSIENT):
        return {"status": "retry", "reason": text or "Transient", "numeric": ec}

    return {
        "status": "unknown",
        "reason": text or f"HTTP {http_status} unknown numeric={ec}",
        "numeric": ec,
    }


def redeem_via_api(code, uid):
    payload = preview_payload(code, uid)
    try:
        r = requests.post(C.API_URL, json=payload, headers=_headers(), timeout=20)
    except Exception as e:
        log_warn("API redeem lỗi mạng:", e.__class__.__name__)
        return {"status": "retry", "reason": f"network {e.__class__.__name__}"}

    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    res = _classify(r.status_code, body)

    if res.get("status") in ("failure", "stuck", "captcha", "retry", "unknown"):
        log_api(
            "API redeem non-success http", r.status_code,
            "code", code, "id", uid,
            "status", res.get("status"), "kind", res.get("kind"),
            "numeric", res.get("numeric"), "body", (r.text or "")[:240],
        )
    return res
