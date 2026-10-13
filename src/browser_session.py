import os
from camoufox.sync_api import Camoufox
from . import config as C
from .utils import log

class BrowserSession:
    """1 Camoufox + 1 context + 1 scan-page XUYÊN SUỐT loop.
       reload()=F5; restart()=fingerprint MỚI khi captcha.
       Viewport MOBILE để khớp layout bottom-sheet đã kiểm chứng bằng tay."""
    def __init__(self):
        self._cm = None; self.browser = None; self.context = None; self.scan_page = None

    def _locale_tz(self, region=None):
        if region and region in C.REGION_LOCALE: return C.REGION_LOCALE[region]
        return ("en-US", "UTC")

    def open(self, region=None):
        self._cm = Camoufox(headless=True, humanize=True, geoip=True, i_know_what_im_doing=True)
        self.browser = self._cm.__enter__()
        loc, tz = self._locale_tz(region)
        kw = dict(locale=loc, timezone_id=tz,
                  viewport=dict(C.MOBILE_VIEWPORT), device_scale_factor=3,
                  user_agent=C.MOBILE_UA)
        if C.STORAGE_STATE and os.path.exists(C.STORAGE_STATE):
            kw["storage_state"] = C.STORAGE_STATE
        self.context = self.browser.new_context(**kw)
        self.scan_page = self.context.new_page()
        log(f"browser opened (locale={loc}, tz={tz}, mobile-viewport=yes, "
            f"login={'yes' if C.STORAGE_STATE else 'no'})")

    def close(self):
        try:
            if self._cm: self._cm.__exit__(None, None, None)
        except Exception as e: log("close lỗi", e)
        finally: self._cm = self.browser = self.context = self.scan_page = None

    def reload(self):
        self.scan_page.reload(wait_until="domcontentloaded", timeout=45000)

    def restart(self, region=None):
        log("RESTART browser (xoá trình duyệt vào lại)"); self.close(); self.open(region=region)

    def new_temp_page(self): return self.context.new_page()
