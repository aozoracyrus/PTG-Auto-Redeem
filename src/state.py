# Lich su "MA|ID" + commit/push nguoc. CHONG SPAM: pull --rebase --autostash TRUOC push
# + VERIFY exit code push (truoc day push fail im lang -> mat state giua run).
import os, subprocess
from .utils import log_state, log_warn, log_err

STATE = lambda: os.path.join(os.getcwd(), "code_da_nhap.txt")


def load_state():
    fp = STATE()
    if not os.path.exists(fp):
        return set()
    return {l.strip() for l in open(fp, encoding="utf-8") if l.strip()}


def _write_state(s):
    lines = sorted(s)
    open(STATE(), "w", encoding="utf-8").write("\n".join(lines) + ("\n" if lines else ""))


def commit_and_push_state(s):
    _write_state(s)
    commit_paths(["code_da_nhap.txt"], f"chore(state): da nhap {len(s)} muc")


def _sh(cmd, check=False, capture=False):
    r = subprocess.run(cmd, shell=True, cwd=os.getcwd(), capture_output=capture, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd} ma_loi={r.returncode} loi={(r.stderr or '')[:200]}")
    return r.returncode, (r.stdout or "")


def commit_paths(paths, message):
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        log_warn("KHONG push (thieu GITHUB_TOKEN hoac GITHUB_REPOSITORY)")
        return
    ref = os.getenv("GITHUB_REF_NAME", "main")
    try:
        _sh('git config user.name "ptg-bot"')
        _sh('git config user.email "ptg-bot@users.noreply.github.com"')
        _sh(f'git remote set-url origin https://x-access-token:{token}@github.com/{repo}.git')
        for p in paths:
            _sh(f'git add {p}')
        dirty = _sh('git status --porcelain ' + ' '.join(paths), capture=True)[1].strip()
        if not dirty:
            log_state("State khong doi, khong commit")
            return
        _sh(f'git commit -m "{message}"')
        _sh(f'git pull --rebase --autostash origin {ref}')
        rc, _ = _sh(f'git push origin HEAD:{ref}')
        if rc == 0:
            log_state("Da push:", ", ".join(paths))
        else:
            log_err(f"PUSH FAIL (ma_loi={rc}) -> state/queue CO THE MAT giua run. "
                    f"Kiem tra quyen ghi / scope PAT_TOKEN (contents).")
    except Exception as e:
        log_err("Loi khi push:", e)
