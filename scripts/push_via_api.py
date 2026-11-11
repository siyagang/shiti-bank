"""在 git 无法直接 push 时，用 GitHub API 提交工作区改动。

适用场景：本机 `git push` 报
    schannel: failed to receive handshake / CONNECT tunnel failed, response 502
（https://github.com 的 443 被代理挡住），而 api.github.com 仍可访问。

用法：
    # token 从 Git 凭据管理器读出来，或直接给一个有 repo 权限的 PAT
    GH_TOKEN=$(printf "protocol=https\\nhost=github.com\\n\\n" | git credential fill | sed -n 's/^password=//p') \\
        python scripts/push_via_api.py "提交说明"

脚本会读 `git status --porcelain`，把已修改/新增的文件按 UTF-8 + LF 的方式
通过 Git Data API（blobs → tree → commit → 更新 ref）提交到 main。
提交后远端领先本地，网络恢复时执行 `git fetch origin && git reset --hard origin/main` 对齐。
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.request

REPO = "siyagang/shiti-bank"
API = f"https://api.github.com/repos/{REPO}"
BRANCH = "main"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def req(method: str, url: str, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "shiti-bank-push",
    })
    with urllib.request.urlopen(r, timeout=180) as f:
        raw = f.read()
    return json.loads(raw) if raw else {}


def changed_files() -> list[str]:
    out = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--porcelain"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        status, path = line[:2], line[3:].strip()
        if status.strip() in ("D", "RD"):
            print(f"  跳过已删除文件 {path}（此脚本只提交新增/修改）")
            continue
        if " -> " in path:  # 重命名
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def main() -> int:
    message = sys.argv[1] if len(sys.argv) > 1 else "更新题库"
    files = changed_files()
    if not files:
        print("工作区没有待提交的改动")
        return 0

    ref = req("GET", f"{API}/git/ref/heads/{BRANCH}")
    head = ref["object"]["sha"]
    base_tree = req("GET", f"{API}/git/commits/{head}")["tree"]["sha"]
    print(f"远端 {BRANCH} @ {head[:10]}")

    tree_items = []
    for path in files:
        content = open(os.path.join(ROOT, path), "rb").read()
        try:
            text = content.decode("utf-8")
            if "\r\n" in text:
                content = text.replace("\r\n", "\n").encode("utf-8")
        except UnicodeDecodeError:
            pass
        blob = req("POST", f"{API}/git/blobs", {
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        })
        tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"  {path} ({len(content)} bytes)")

    tree = req("POST", f"{API}/git/trees", {"base_tree": base_tree, "tree": tree_items})
    commit = req("POST", f"{API}/git/commits",
                 {"message": message, "tree": tree["sha"], "parents": [head]})
    req("PATCH", f"{API}/git/refs/heads/{BRANCH}", {"sha": commit["sha"], "force": False})
    print(f"已提交 {commit['sha'][:10]} → https://github.com/{REPO}/commit/{commit['sha']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
