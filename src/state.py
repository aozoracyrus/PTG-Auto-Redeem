import os, subprocess
from .utils import log

STATE = lambda: os.path.join(os.getcwd(), "code_da_nhap.txt")

def load_state():
    fp = STATE()
    if not os.path.exists(fp): return set()
    return {l.strip() for l in open(fp, encoding="utf-8") if l.strip()}

def _write_state(s):
    lines = sorted(s)
    open(STATE(), "w", encoding="utf-8").write("\n".join(lines) + ("\n" if lines else ""))

def commit_and_push_state(s):
    _write_state(s)
    commit_paths(["code_da_nhap.txt"], f"chore(state): redeemed {len(s)} entries")

def commit_paths(paths, message):
    """Commit + push danh sách file state bằng GITHUB_TOKEN (runner ephemeral -> phải push)."""
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        log("KHÔNG push (thiếu GITHUB_TOKEN/GITHUB_REPOSITORY)"); return
    ref = os.getenv("GITHUB_REF_NAME", "main")
    def run(cmd): subprocess.run(cmd, shell=True, cwd=os.getcwd(), check=False)
    try:
        run('git config user.name "ptg-bot"')
        run('git config user.email "ptg-bot@users.noreply.github.com"')
        run(f'git remote set-url origin https://x-access-token:{token}@github.com/{repo}.git')
        for p in paths: run(f'git add {p}')
        dirty = subprocess.run('git status --porcelain ' + ' '.join(paths),
                               shell=True, capture_output=True, text=True).stdout.strip()
        if not dirty:
            log("state không đổi, không commit"); return
        run(f'git commit -m "{message}"')
        run(f'git push origin HEAD:{ref}')
        log("đã push:", ", ".join(paths))
    except Exception as e:
        log("push lỗi:", e)
