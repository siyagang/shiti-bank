"""批量导入：python scripts/import_csv.py 新题.csv

Excel 里先整理成表格，然后「另存为 → CSV UTF-8」，列名照下面写（顺序随意，多余的列忽略）：

  topicId | region | type | difficulty | prompt | answer | explanation | choices | verify | accept | unordered

  - topicId      必填，必须已存在于 data/topics.json，如 zk_math_g9_01
  - region       选填，省份名，如「江苏」；练习页的「地区」筛选靠它
  - type         numeric / choice / short / self
  - difficulty   basic / standard / advanced，留空默认 basic
  - choices      仅选择题，用 | 分隔：三角形|圆|长方形|平行四边形，也可写 A:三角形|B:圆|…
  - accept       仅短答题，等价答案用 | 分隔：三十六|36
  - unordered    仅多数值题，true / false
  - verify       可留空；会自动核验，不一致的会列出来

重复题（同 topicId + 同题干）默认跳过；加 --keep-dup 可以强行导入。
先用 --dry-run 试跑，只打印不写文件。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qbank import load_questions, load_topics, save_questions  # noqa: E402
from add_question import append_questions  # noqa: E402

COLUMNS = ("topicId", "region", "type", "difficulty", "prompt", "answer", "explanation",
           "choices", "verify", "accept", "unordered")


def read_csv(path: Path) -> list[dict]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with path.open(encoding=encoding, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"读不出 {path} 的编码，请在 Excel 里另存为「CSV UTF-8」")


def main() -> int:
    ap = argparse.ArgumentParser(description="从 CSV 批量导入题目")
    ap.add_argument("csv_file")
    ap.add_argument("--dry-run", action="store_true", help="只检查不写入")
    ap.add_argument("--keep-dup", action="store_true", help="保留与已有题重复的题")
    args = ap.parse_args()

    rows = read_csv(Path(args.csv_file))
    if not rows:
        raise SystemExit("CSV 里没有数据行")

    missing_cols = [c for c in ("topicId", "type", "prompt", "answer", "explanation")
                    if c not in (rows[0] or {})]
    if missing_cols:
        raise SystemExit(f"CSV 缺少必需的列：{', '.join(missing_cols)}")

    existing = load_questions()
    seen = {(q.get("topicId"), str(q.get("prompt", "")).strip()) for q in existing}
    topic_ids = {t["id"] for t in load_topics()}

    items, skipped = [], []
    for i, row in enumerate(rows, start=2):  # 第 1 行是表头
        item = {k: (v or "").strip() for k, v in row.items() if k in COLUMNS and (v or "").strip()}
        if not item:
            continue
        tid, prompt = item.get("topicId", ""), item.get("prompt", "")
        if tid not in topic_ids:
            skipped.append(f"第 {i} 行：topicId「{tid}」不在 topics.json 里")
            continue
        if (tid, prompt) in seen and not args.keep_dup:
            skipped.append(f"第 {i} 行：与已有题重复（{tid} {prompt[:20]}…），已跳过")
            continue
        seen.add((tid, prompt))
        items.append(item)

    print(f"读到 {len(rows)} 行，可导入 {len(items)} 条" + (f"，跳过 {len(skipped)} 条" if skipped else ""))
    for s in skipped[:30]:
        print("  · " + s)

    if args.dry_run:
        for it in items:
            print(f"  → {it.get('topicId')}  {it.get('type', 'numeric')}  {it.get('prompt', '')[:40]}")
        print("（--dry-run：没有写入）")
        return 0

    if not items:
        return 0

    code = append_questions(items)
    if not code:
        save_questions(load_questions())  # 统一一次格式化写盘
    return code


if __name__ == "__main__":
    raise SystemExit(main())
