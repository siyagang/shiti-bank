"""每日自动更新：导入新题 → 校验 → 派生文件同步 → 推送 GitHub → 清 CDN 缓存。

设计要点
--------
1. **默认不重跑生成器**。`build_zhongkao.py` 是「全量重建」，重跑会把 CSV 导入的题冲掉；
   只有在加了 `--rebuild` 时才重建（此时题库回到生成器的产出）。
2. 每天的日常流程是「增量」的：把 `inbox/` 里的 CSV 导入题库，校验通过后同步
   `q.json`、`q_app.json`、`data/stats.json`，再推送到 GitHub 并刷新 jsDelivr 缓存。
3. 校验不过（格式错误或答案核验 mismatch）就**中止并且不推送**，线上数据保持原样。
4. 本机 `git push` 因代理问题不可用，推送走 `push_via_api.py`（GitHub Data API）。

用法
----
    python scripts/daily_update.py                 # 日常：导入 inbox + 同步 + 推送
    python scripts/daily_update.py --dry-run       # 只看要做什么，不写文件、不推送
    python scripts/daily_update.py --rebuild       # 先全量重建再同步（会重置为生成器产出）
    python scripts/daily_update.py --no-push       # 只更新本地，不推 GitHub

`inbox/` 里的 CSV 导入成功后会被移到 `inbox/_done/日期/`，不会重复导入。
日志写在 `logs/daily.log`，最近一次的结构化结果在 `logs/last_run.json`。
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
INBOX = ROOT / "inbox"

PY = sys.executable


def run(cmd: list[str], *, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if not quiet:
        out = (r.stdout or "").strip()
        if out:
            print(out if len(out) < 4000 else out[:4000] + "\n…（输出过长，已截断）")
        if r.returncode != 0 and (r.stderr or "").strip():
            print((r.stderr or "").strip()[:2000])
    if check and r.returncode != 0:
        raise SystemExit(f"命令失败（退出码 {r.returncode}）：{' '.join(cmd)}")
    return r


# ------------------------------------------------------------------ 各步骤
def import_inbox(dry: bool) -> tuple[int, list[str]]:
    """把 inbox/ 下的 CSV 导入题库，成功后退档到 inbox/_done/日期/。"""
    if not INBOX.exists():
        return 0, []
    files = sorted(p for p in INBOX.glob("*.csv") if p.is_file())
    if not files:
        return 0, []

    total, moved = 0, []
    for path in files:
        print(f"[导入] {path.name}")
        r = run([PY, str(SCRIPTS / "import_csv.py"), str(path), "--dry-run"], check=False)
        if r.returncode != 0:
            print(f"  ! {path.name} 预检失败，跳过")
            continue
        if dry:
            print("  （--dry-run：不写入）")
            continue
        r2 = run([PY, str(SCRIPTS / "import_csv.py"), str(path)])
        m = re.search(r"可导入 (\d+) 条", r2.stdout or "")
        total += int(m.group(1)) if m else 0
        done = INBOX / "_done" / dt.date.today().isoformat()
        done.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(done / path.name))
        moved.append(path.name)
    return total, moved


def sync_derived(dry: bool) -> None:
    """q.json 是 data/questions.json 的副本，App 版由 make_app_json.py 生成。"""
    if dry:
        return
    (ROOT / "q.json").write_text(
        (DATA / "questions.json").read_text(encoding="utf-8"), encoding="utf-8")
    run([PY, str(SCRIPTS / "make_app_json.py")])


def check(dry: bool) -> bool:
    for name in ("validate.py", "verify_questions.py"):
        print(f"[校验] {name}")
        r = run([PY, str(SCRIPTS / name)], check=False, quiet=False)
        if r.returncode != 0:
            print(f"  ! {name} 未通过，本次不推送，线上数据保持不变")
            return False
    return True


def write_stats(dry: bool) -> dict:
    questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    topics = json.loads((DATA / "topics.json").read_text(encoding="utf-8"))
    tmap = {t["id"]: t for t in topics}
    covered = {q["topicId"] for q in questions}
    missing = [f"{t['id']}({t['name']})" for t in topics if t["id"] not in covered]

    stats = {
        "updatedAt": dt.datetime.now().isoformat(timespec="seconds"),
        "total": len(questions),
        "topics": len(topics),
        "topicsWithQuestions": len(covered),
        "regions": len({q.get("region") for q in questions if q.get("region")}),
        "bySubject": dict(collections.Counter(
            tmap[q["topicId"]]["subject"] for q in questions if q["topicId"] in tmap)),
        "byGrade": dict(sorted(collections.Counter(
            tmap[q["topicId"]]["grade"] for q in questions if q["topicId"] in tmap).items())),
        "bySemester": dict(collections.Counter(q.get("semester", "") for q in questions)),
        "byType": dict(collections.Counter(q.get("type", "") for q in questions)),
        "byDifficulty": dict(collections.Counter(q.get("difficulty", "") for q in questions)),
        "topicsWithoutQuestions": missing,
    }
    if not dry:
        (DATA / "stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def git_changed() -> list[str]:
    r = subprocess.run(["git", "-c", "core.quotepath=false", "status", "--porcelain"],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return [ln for ln in (r.stdout or "").splitlines() if ln.strip()]


def gh_token() -> str | None:
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok
    try:
        r = subprocess.run(["git", "credential", "fill"], cwd=ROOT, capture_output=True,
                           text=True, timeout=30,
                           input="protocol=https\nhost=github.com\n\n")
        for line in (r.stdout or "").splitlines():
            if line.startswith("password="):
                return line[len("password="):]
    except Exception:
        pass
    return None


def push(message: str) -> str | None:
    tok = gh_token()
    if not tok:
        print("[推送] 拿不到 GitHub 凭据，跳过推送")
        return None
    env = dict(os.environ, GH_TOKEN=tok)
    r = subprocess.run([PY, str(SCRIPTS / "push_via_api.py"), message], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", env=env)
    out = (r.stdout or "").strip()
    print(out)
    if r.returncode != 0:
        print((r.stderr or "").strip()[:1000])
        return None
    for line in out.splitlines():
        if "已提交" in line:
            return line.split("已提交", 1)[1].strip().split(" ")[0]
    return "noop"


def purge_cdn() -> None:
    urls = [
        "https://purge.jsdelivr.net/gh/siyagang/shiti-bank@main/q.json",
        "https://purge.jsdelivr.net/gh/siyagang/shiti-bank@main/data/questions.json",
        "https://purge.jsdelivr.net/gh/siyagang/shiti-bank@main/q_app.json",
    ]
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "shiti-bank-daily"})
            with urllib.request.urlopen(req, timeout=60) as f:
                body = json.loads(f.read() or b"{}")
            print(f"[清缓存] {u.split('/')[-1]} → {body.get('status', 'ok')}")
        except Exception as e:
            print(f"[清缓存] {u.split('/')[-1]} 失败：{type(e).__name__}")


# ------------------------------------------------------------------ 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="题库每日自动更新")
    ap.add_argument("--dry-run", action="store_true", help="只演练，不写文件、不推送")
    ap.add_argument("--rebuild", action="store_true", help="先全量重建题库（会重置 CSV 导入的题）")
    ap.add_argument("--no-push", action="store_true", help="不推送到 GitHub")
    ap.add_argument("--no-purge", action="store_true", help="不清 jsDelivr 缓存")
    args = ap.parse_args()

    started = dt.datetime.now()
    print(f"===== 题库每日更新 {started:%Y-%m-%d %H:%M:%S} =====")

    steps: list[tuple[str, str]] = []
    imported, moved = import_inbox(args.dry_run)
    if moved or imported:
        steps.append(("import", f"导入 {imported} 题，归档 {len(moved)} 个 CSV"))
        print(f"[导入] 共 {imported} 题" + (f"，归档 {', '.join(moved)}" if moved else ""))
    else:
        steps.append(("import", "inbox 无新文件"))

    if args.rebuild:
        print("[重建] build_zhongkao.py")
        if not args.dry_run:
            run([PY, str(SCRIPTS / "build_zhongkao.py")])
        steps.append(("rebuild", "已全量重建"))

    sync_derived(args.dry_run)
    ok = check(args.dry_run)
    stats = write_stats(args.dry_run)
    print(f"[统计] 共 {stats['total']} 题，覆盖 {stats['topicsWithQuestions']}/{stats['topics']} 个知识点")

    changed = git_changed()
    commit = None
    if not ok:
        steps.append(("verify", "校验未通过，已中止"))
    elif args.dry_run:
        steps.append(("push", f"演练：待提交 {len(changed)} 个文件"))
        for ln in changed[:20]:
            print("  " + ln)
    elif args.no_push:
        steps.append(("push", f"跳过推送，本地变更 {len(changed)} 个文件"))
    elif not changed:
        steps.append(("push", "内容无变化，无需提交"))
    else:
        msg = f"每日更新：{stats['total']} 题（导入 {imported} 题）"
        commit = push(msg)
        steps.append(("push", f"已提交 {commit}" if commit else "推送失败"))
        if commit and not args.no_purge:
            purge_cdn()
            steps.append(("purge", "已清 CDN 缓存"))

    elapsed = (dt.datetime.now() - started).total_seconds()
    record = {
        "time": started.isoformat(timespec="seconds"),
        "seconds": round(elapsed, 1),
        "ok": ok,
        "imported": imported,
        "total": stats["total"],
        "topicsWithQuestions": stats["topicsWithQuestions"],
        "commit": commit,
        "changedFiles": len(changed),
        "steps": [{"step": k, "detail": v} for k, v in steps],
    }
    if not args.dry_run:
        LOGS.mkdir(exist_ok=True)
        (LOGS / "last_run.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with (LOGS / "daily.log").open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"===== 完成，用时 {elapsed:.1f}s，{'成功' if ok else '校验未通过'} =====")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
