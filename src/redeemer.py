import re, time
from . import config as C
from .utils import log, sleep, rand_ms, shot

def _fill_by_ph(page, placeholders, value):
    for ph in placeholders:
        loc = page.get_by_placeholder(ph).first
        try:
            loc.wait_for(state="visible", timeout=4000)
            loc.click(); loc.fill(value)
            return loc
        except Exception: continue
    return None

def _blur(page, loc=None):
    try:
        if loc is not None: loc.blur()
    except Exception: pass
    try: page.mouse.click(2, 2)
    except Exception: pass
    sleep(rand_ms(200, 500))

def _low(page):
    try: return page.locator("body").inner_text().lower()
    except Exception: return ""

def _any(b, needles):
    return any(str(n).lower() in b for n in needles)

def _cookie_present(page):
    try:
        return page.get_by_text("chúng tôi sử dụng cookie", exact=False).count() > 0
    except Exception:
        return False

def _dismiss_cookie(page):
    if not _cookie_present(page):
        return False
    for name in (r"Đồng ý tất cả", r"Accept all", r"Agree"):
        try:
            b = page.get_by_role("button", name=re.compile(name, re.I))
            if b.count() > 0:
                b.first.click(timeout=3000); sleep(rand_ms(500, 900))
                if not _cookie_present(page):
                    log("cookie: đã bấm 'Đồng ý tất cả'"); return True
        except Exception:
            continue
    try:
        b = page.locator("cookie-consent button, [class*='cookie' i] button") \
                .filter(has_text=re.compile("đồng ý|accept", re.I))
        if b.count() > 0:
            b.first.click(timeout=3000); sleep(rand_ms(500, 900))
            if not _cookie_present(page):
                log("cookie: đã bấm nút trong component"); return True
    except Exception:
        pass
    try:
        page.evaluate("() => { document.querySelectorAll('cookie-consent').forEach(e => e.remove()); }")
        sleep(rand_ms(300, 600))
        log("cookie: đã xoá node <cookie-consent> khỏi DOM")
        return True
    except Exception:
        return False

_DIALOG_SEL = (
    "[role='dialog'], [role='alertdialog'], [role='alert'], [aria-modal='true'], "
    "dialog, [class*='modal' i], [class*='dialog' i], [class*='popup' i], "
    "[class*='confirm' i], [class*='toast' i], [class*='overlay' i], [class*='backdrop' i]"
)
_DIALOG_TEXT_NEEDLES = ["hoàn tất nhập mã", "đã hoàn tất", "thành công nhập",
                        "nhập thành công", "thất bại", "failed", "failure"]

def _read_dialog(page):
    try:
        locs = page.locator(_DIALOG_SEL)
        n = locs.count()
        if n == 0: return "", 0, ""
        empty_snippet = ""
        for i in range(min(n, 4)):
            try:
                txt = locs.nth(i).inner_text()
                low = txt.lower()
                if not txt.strip():
                    if not empty_snippet:
                        try:
                            html = locs.nth(i).evaluate("el => el.outerHTML")
                            empty_snippet = html[:500]
                        except Exception:
                            empty_snippet = "<eval-failed>"
                    continue
                if "cookie" in low and ("đồng ý" in low or "tùy chỉnh" in low):
                    continue
                return low, n, ""
            except Exception:
                continue
        return "", n, empty_snippet
    except Exception as e:
        return f"err:{e}", -1, ""

def _find_server_opener(page):
    """Tìm ô server bằng nhiều selector: placeholder, combobox, select, label text."""
    factories = []
    # Placeholder
    for term in C.SRV_PH:
        factories.append(lambda t=term: page.get_by_placeholder(t))
    # Role
    factories += [
        lambda: page.get_by_role("combobox"),
        lambda: page.locator("select"),
    ]
    # Text trong option
    factories.append(lambda: page.get_by_text(re.compile(r"Server\s*\d|Máy chủ\s*\d", re.I)))
    # Class name heuristic
    factories.append(lambda: page.locator("[class*='erver' i], [class*='máy chủ' i]"))
    # Label text "Máy chủ" / "Server" -> tìm input gần đó
    factories.append(lambda: page.locator("label:has-text('Máy chủ'), label:has-text('Server') + *"))
    factories.append(lambda: page.locator("text='Máy chủ' >> xpath=.. >> *"))
    
    for f in factories:
        try:
            L = f()
            if L.count() > 0: return L.first
        except Exception: continue
    return None

def _ensure_server(page):
    try:
        opener = _find_server_opener(page)
        if opener is None:
            log("server: KHÔNG TÌM THẤY ô server (form có thể không submit!)"); return False
        log(f"server: tìm thấy opener")
        opener.click(timeout=3000); sleep(0.8)
        opt = None
        for f in [lambda: page.get_by_role("option", name=C.SRV_OPT_RE),
                  lambda: page.get_by_text(C.SRV_OPT_RE),
                  lambda: page.get_by_role("listbox").get_by_role("option"),
                  lambda: page.get_by_role("option")]:
            try:
                L = f()
                if L.count() > 0: opt = L.first; break
            except Exception: continue
        if opt is not None:
            opt.click(timeout=2500); log("server: đã chọn option")
            _blur(page); return True
        # Fallback: phím mũi tên
        try:
            page.keyboard.press("ArrowDown"); sleep(0.3); page.keyboard.press("Enter")
            log("server: fallback phím"); _blur(page); return True
        except Exception:
            return False
    except Exception as e:
        log("server lỗi:", e); return False

def _dump_form_state(page):
    """Dump giá trị các ô input để debug form không submit."""
    try:
        inputs = page.locator("input, select, textarea").all()
        log(f"FORM STATE: {len(inputs)} input elements")
        for i, inp in enumerate(inputs[:10]):  # chỉ dump 10 cái đầu
            try:
                tag = inp.evaluate("el => el.tagName")
                ph = inp.evaluate("el => el.placeholder || ''")
                val = inp.evaluate("el => el.value || ''")
                name = inp.evaluate("el => el.name || el.id || ''")
                log(f"  input[{i}]: {tag} name={name!r} placeholder={ph!r} value={val[:50]!r}")
            except Exception:
                pass
    except Exception as e:
        log(f"FORM STATE dump lỗi: {e}")

def _wait_enabled(loc, secs=6):
    end = time.time() + secs
    while time.time() < end:
        try:
            if not loc.is_disabled(): return True
        except Exception: return True
        sleep(0.5)
    return False

def _classify(body_low):
    if _any(body_low, C.NEED_LOGIN):     return "need_login",  "chưa liên kết tài khoản"
    if _any(body_low, C.TRANSIENT):      return "transient",   "lỗi hệ thống tạm thời"
    if _any(body_low, C.FAIL_USAGE):     return "usage_limit", "hết lượt nhập / usage limit"
    if _any(body_low, C.FAIL_NOTEXIST):  return "not_exist",   "không tồn tại / sai mã"
    if _any(body_low, C.FAIL_IDERROR):   return "id_error",    "ID không tìm thấy/offline"
    if _any(body_low, C.FAIL_VALIDATION):return "validation",  "thông tin nhập không hợp lệ"
    if _any(body_low, C.FAIL_SECTION):   return "other",       "thất bại"
    return "other", "thất bại"

def _poll_modal(page, timeout, network_log):
    deadline = time.time() + timeout
    while time.time() < deadline:
        sleep(C.REDEEM_POLL_STEP)
        body_low = _low(page)
        d_text, _, _ = _read_dialog(page)
        combined = body_low + " " + d_text
        if _any(combined, C.CAPTCHA_HINTS):
            shot(page, "captcha-post"); return ("captcha", None, None)
        if C.RATIO_OK in combined:
            return ("success", None, None)
        if C.RATIO_FAIL in combined:
            kind, reason = _classify(d_text or body_low)
            if kind in ("need_login", "transient"):
                log(f"RETRY {kind}: {reason}"); return ("retry", kind, reason)
            return ("failure", kind, reason)
        if _any(d_text, _DIALOG_TEXT_NEEDLES):
            kind, reason = _classify(d_text)
            if kind in ("need_login", "transient"):
                log(f"RETRY(dialog) {kind}: {reason}"); return ("retry", kind, reason)
            if kind == "other" and _any(d_text, ["thành công", "hoàn tất"]):
                return ("success", None, None)
            return ("failure", kind, reason)
    d_text, d_count, empty_html = _read_dialog(page)
    body_full = ""
    try: body_full = page.locator("body").inner_text()
    except Exception: pass
    log(f"POLL_TIMEOUT: dialog_count={d_count} | dialog_text[:200]={d_text[:200]!r}")
    if empty_html and "__next-route-announcer__" not in empty_html:
        log(f"EMPTY_DIALOG_HTML[:500]={empty_html!r}")
    log(f"body[:1000]={body_full[:1000]!r}")
    log(f"NETWORK requests count: {len(network_log)}")
    if network_log:
        for line in network_log[-10:]:  # 10 request cuối
            log(f"  {line}")
    return None

def _submit_form_js(page):
    """Thử submit form bằng JavaScript nếu click nút không trigger request."""
    try:
        result = page.evaluate("""() => {
            // Tìm form element
            const forms = document.querySelectorAll('form');
            if (forms.length === 0) return {error: 'no-form'};
            const form = forms[0];
            
            // Tìm nút submit
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn) {
                submitBtn.click();
                return {method: 'submit-btn-click'};
            }
            
            // Tìm nút "Nhập code" bất kỳ
            const allBtns = form.querySelectorAll('button');
            for (const btn of allBtns) {
                if (btn.textContent.includes('Nhập code') || btn.textContent.includes('Redeem')) {
                    btn.click();
                    return {method: 'redeem-btn-click'};
                }
            }
            
            // Fallback: submit form trực tiếp
            form.submit();
            return {method: 'form-submit'};
        }""")
        log(f"JS submit: {result}")
        return True
    except Exception as e:
        log(f"JS submit lỗi: {e}")
        return False

def _attempt(page, code, uid):
    network_log = []
    console_errors = []

    def _on_response(response):
        try:
            url = response.url
            if any(kw in url.lower() for kw in ["redeem", "verify", "use", "giftcode", "api/"]):
                body = ""
                try: body = response.text()[:500]
                except Exception: body = "<no-body>"
                network_log.append(f"{response.status} {url[:120]} | {body}")
        except Exception:
            pass

    def _on_console(msg):
        try:
            if msg.type == "error":
                console_errors.append(msg.text[:200])
        except Exception:
            pass

    try:
        page.on("response", _on_response)
        page.on("console", _on_console)

        page.goto(C.URL_VN, wait_until="domcontentloaded", timeout=45000)
        try: page.wait_for_load_state("networkidle", timeout=8000)
        except Exception: pass
        sleep(rand_ms(1200, 2200))
        _dismiss_cookie(page)

        code_loc = _fill_by_ph(page, C.PH_CODE, code)
        if code_loc is None:
            shot(page, "fillfail-code"); return {"status": "retry", "kind": "dom", "reason": "Không tìm thấy ô nhập code"}
        _blur(page, code_loc)

        id_loc = _fill_by_ph(page, C.PH_ID, uid)
        if id_loc is None:
            shot(page, "fillfail-id"); return {"status": "retry", "kind": "dom", "reason": "Không tìm thấy ô nhập ID"}
        _blur(page, id_loc)
        sleep(rand_ms(400, 900))

        if _any(_low(page), C.CAPTCHA_HINTS):
            shot(page, "captcha-pre"); return {"status": "captcha"}

        _dismiss_cookie(page)

        # Chọn server
        _ensure_server(page)
        _blur(page)
        sleep(rand_ms(500, 1000))

        # Dump form state trước khi click
        _dump_form_state(page)

        btn = page.get_by_role("button", name=C.BTN_REDEEM).or_(page.get_by_text(C.BTN_REDEEM))
        if btn.count() == 0:
            shot(page, "nobtn"); return {"status": "retry", "kind": "dom", "reason": "không thấy nút Nhập code"}
        first = btn.first
        try: first.wait_for(state="visible", timeout=10000)
        except Exception:
            shot(page, "nobtn-visible"); return {"status": "retry", "kind": "dom", "reason": "nút Nhập code không visible"}

        if not _wait_enabled(first, 4):
            log("nút vẫn DISABLED sau khi chọn server")
            shot(page, "disabled")
            return {"status": "retry", "kind": "form_invalid", "reason": "nút Nhập code vẫn vô hiệu"}

        # Click nút
        try: first.scroll_into_view_if_needed(timeout=3000)
        except Exception: pass
        try:
            first.click(timeout=6000)
            log("click nút: ok=True, method=normal")
        except Exception:
            try:
                first.click(timeout=4000, force=True)
                log("click nút: ok=True, method=force")
            except Exception:
                shot(page, "clickfail")
                return {"status": "retry", "kind": "dom", "reason": "click nút thất bại"}

        # Chờ 3s xem có request API nào không
        sleep(3)
        if not network_log:
            log("KHÔNG có request API sau 3s -> thử submit form bằng JS")
            _submit_form_js(page)
            sleep(3)

        # Poll modal
        result = _poll_modal(page, 30, network_log)

        # Log console errors
        if console_errors:
            log(f"CONSOLE ERRORS: {len(console_errors)} lỗi")
            for err in console_errors[:5]:
                log(f"  {err}")

        if result is None:
            shot(page, "unknown")
            return {"status": "unknown", "reason": "form không submit hoặc modal không render"}
        status, kind, reason = result
        if status == "captcha":
            shot(page, "captcha-post"); return {"status": "captcha"}
        if status == "success":
            return {"status": "success"}
        if status == "retry":
            return {"status": "retry", "kind": kind, "reason": reason}
        return {"status": "failure", "kind": kind, "reason": reason}
    except Exception as e:
        shot(page, "err")
        log(f"RETRY exception: {e.__class__.__name__}")
        return {"status": "retry", "kind": "exception", "reason": "exception: " + str(e)}
    finally:
        try: page.remove_listener("response", _on_response)
        except Exception: pass
        try: page.remove_listener("console", _on_console)
        except Exception: pass

def redeem_for_user(session, code, uid):
    for _ in (1, 2):
        page = session.new_temp_page()
        try: r = _attempt(page, code, uid)
        finally:
            try: page.close()
            except Exception: pass
        if r["status"] != "captcha": return r
        log(f"captcha ({uid}) -> restart browser"); session.restart()
        sleep(rand_ms(3000, 6000))
    return {"status": "captcha"}
