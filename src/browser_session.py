import os
from camoufox.sync_api import Camoufox
from . import config as C
from .utils import log_brw, log_err


class BrowserSession:
    def __init__(self):
        self._cm = None
        self.browser = None
        self.context = None
        self.scan_page = None

    def open(self):
        self._cm = Camoufox(headless=True, humanize=True, geoip=True, i_know_what_im_doing=True)
        self.browser = self._cm.__enter__()
        loc, tz = C.LOCALE
        kw = dict(locale=loc, timezone_id=tz, viewport=dict(C.MOBILE_VIEWPORT),
                  device_scale_factor=3, user_agent=C.MOBILE_UA)
        if C.STORAGE_STATE and os.path.exists(C.STORAGE_STATE):
            kw["storage_state"] = C.STORAGE_STATE
        self.context = self.browser.new_context(**kw)
        self.scan_page = self.context.new_page()
        log_brw(f"Da mo browser (locale={loc}, tz={tz})")

    def close(self):
        try:
            if self._cm:
                self._cm.__exit__(None, None, None)
        except Exception as e:
            log_err("Loi dong browser:", e)
        finally:
            self._cm = self.browser = self.context = self.scan_page = None

    def reload(self):
        self.scan_page.reload(wait_until="domcontentloaded", timeout=45000)

    def restart(self):
        log_brw("RESTART browser")
        self.close()
        self.open()

    def new_temp_page(self):
        return self.context.new_page()
