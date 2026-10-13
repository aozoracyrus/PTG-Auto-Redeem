import os
from camoufox.sync_api import Camoufox
from . import config as C
from .utils import log

class BrowserSession:
    """1 Camoufox + 1 context xuyên suốt; locale/timezone VN; viewport mobile.
       restart() = mở browser fingerprint MỚI khi captcha (= 'xoá trình duyệt vào lại')."""
    def __init__(self):
        self._cm = None; self.browser = None; self.context = None

    def open(self):
        self._cm = Camoufox(headless=True, humanize=True, geoip=True, i_know_what_im_doing=True)
        self.browser = self._cm.__enter__()
        kw = dict(locale=C.LOCALE, timezone_id=C.TIMEZONE,
                  viewport=dict(C.MOBILE_VIEWPORT), device_scale_factor=3,
                  user_agent=C.MOBILE_UA)
        if C.STORAGE_STATE and os.path.exists(C.STORAGE_STATE):
            kw["storage_state"] = C.STORAGE_STATE
        self.context = self.browser.new_context(**kw)
        log(f"browser opened (locale={C.LOCALE}, mobile-viewport=yes, "
            f"login={'yes' if C.STORAGE_STATE else 'no'})")

    def close(self):
        try:
            if self._cm: self._cm.__exit__(None, None, None)
        except Exception as e: log("close lỗi", e)
        finally: self._cm = self.browser = self.context = None

    def restart(self):
        log("RESTART browser (xoá trình duyệt vào lại)"); self.close(); self.open()

    def new_temp_page(self): return self.context.new_page()
