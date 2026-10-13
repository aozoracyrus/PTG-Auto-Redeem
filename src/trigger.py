import os, requests
from .utils import log

API = "https://api.github.com"

def _token():
    # Ưu tiên PAT (tin cậy cho dispatches); fallback GITHUB_TOKEN (bị chặn đệ-quy ở nhiều repo)
    return os.getenv("PAT_TOKEN") or os.getenv("GITHUB_TOKEN")

def trigger_next_run():
    """Gọi workflow_dispatch API để spawn run kế tiếp -> chuỗi 24/7 không cần cron."""
    repo = os.getenv("GITHUB_REPOSITORY")
    wf   = os.getenv("WORKFLOW_FILE", "redeem.yml")
    ref  = os.getenv("GITHUB_REF_NAME") or "main"
    tok  = _token()
    if not repo or not tok:
        log("KHÔNG self-trigger: thiếu GITHUB_REPOSITORY / token"); return False
    url = f"{API}/repos/{repo}/actions/workflows/{wf}/dispatches"
    try:
        r = requests.post(url, headers={
                "Authorization": f"Bearer {tok}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"},
            json={"ref": ref, "inputs": {}}, timeout=20)
        if r.status_code in (200, 204):
            log(f"đã self-trigger run tiếp theo (ref={ref}, wf={wf})"); return True
        log("self-trigger HTTP", r.status_code, r.text[:300])
        if r.status_code == 403:
            log("403 -> GITHUB_TOKEN bị chặn đệ-quy? Tạo PAT scope 'workflow' + secret PAT_TOKEN")
        return False
    except Exception as e:
        log("self-trigger lỗi", e); return False
