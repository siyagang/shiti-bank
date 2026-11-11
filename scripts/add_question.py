"""每天加一道题：python scripts/add_question.py

三种用法：

1) 交互式（推荐，边想边填，回车跳过可选项）：
       python scripts/add_question.py

2) 一条 JSON（适合从别处复制粘贴，或让 AI 生成）：
       python scripts/add_question.py --json '{"topicId":"zk_math_g9_01","type":"numeric","prompt":"5+1=?","answer":"6","explanation":"5 再添 1 是 6","verify":"5+1"}'

3) 一个 JSON 文件（数组或单个对象，可一次导入多题）：
       python scripts/add_question.py --file new_questions.json

脚本会自动生成 id（<topicId>_q<N>），写完立即做格式校验和 verify 核验。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qbank import (  # noqa: E402
    DIFFICULTIES, TYPES, load_questions, load_topics, next_id, save_questions,
)
from validate import check_question  # noqa: E402
from verify_questions import verify_one  # noqa: E402


def parse_choices(raw: str) -> list[dict]:
    """把 "A:三角形|B:圆|C:长方形" 或 "三角形|圆|长方形" 解析成选项数组。"""
    out = []
    for i, chunk in enumerate([c for c in raw.split("|") if c.strip()]):
        chunk = chunk.strip()
        if len(chunk) > 2 and chunk[1] in ":：":
            key, text = chunk[0].upper(), chunk[2:].strip()
        else:
            key, text = chr(ord("A") + i), chunk
        out.append({"key": key, "text": text})
    return out


def build_from_json(item: dict, questions: list[dict]) -> dict:
    q = dict(item)
    topic_id = str(q.get("topicId", "")).strip()
    if not topic_id:
        raise ValueError("缺少 topicId")
    q.setdefault("difficulty", "basic")
    q.setdefault("type", "numeric")
    if isinstance(q.get("choices"), str):
        q["choices"] = parse_choices(q["choices"])
    if isinstance(q.get("accept"), str):
        q["accept"] = [x.strip() for x in q["accept"].split("|") if x.strip()]
    if "unordered" in q and isinstance(q["unordered"], str):
        q["unordered"] = q["unordered"].lower() in ("1", "true", "yes", "是")
    for k in ("id", "topicId", "difficulty", "type", "prompt", "answer", "explanation"):
        if k in q and isinstance(q[k], (int, float)):
            q[k] = str(q[k])
    # 强制重新分配 id，避免手写冲突
    q.pop("id", None)
    q["id"] = next_id(topic_id, questions)
    return q


def append_questions(new_items: list[dict]) -> int:
    questions = load_questions()
    topics = load_topics()
    topic_ids = {t["id"] for t in topics}
    external = {t["id"] for t in topics if t.get("external")}
    topic_name = {t["id"]: t.get("name", "") for t in topics}

    added, problems = [], []
    for item in new_items:
        try:
            q = build_from_json(item, questions)
        except ValueError as exc:
            problems.append(f"{item!r}：{exc}")
            continue
        errs = check_question(q, len(questions), topic_ids, external)
        if errs:
            problems.extend(errs)
            continue
        questions.append(q)
        added.append(q)

    if added:
        save_questions(questions)

    for q in added:
        status, msg = verify_one(q)
        mark = {"verified": "✓ 已核验", "mismatch": "✗ 不一致", "unverifiable": "· 无 verify",
                "error": "✗ verify 出错"}[status]
        print(f"{mark} {q['id']}  {topic_name.get(q['topicId'], '?')}  {q['prompt'][:30]}")
        if msg:
            print(f"    {msg}")

    if problems:
        print(f"\n有 {len(problems)} 条没导入：")
        for p in problems:
            print("  ✗ " + p)
        return 1
    print(f"\n已写入 {len(added)} 题，当前共 {len(questions)} 题。建议再跑一次 python scripts/validate.py")
    return 0


def interactive() -> list[dict]:
    topics = load_topics()
    subject_to_topics: dict[str, list[dict]] = {}
    for t in topics:
        if t.get("external"):
            continue
        subject_to_topics.setdefault(t.get("subject", "?"), []).append(t)

    print("已有知识点（按学科，输入编号选择）：")
    flat = []
    for subject, items in subject_to_topics.items():
        print(f"\n[{subject}]")
        for t in items:
            flat.append(t)
            print(f"  {len(flat):2d}. {t['id']:<12} {t.get('grade')}年级{t.get('semester', '')}  {t['name']}")
    try:
        idx = int(input("\n知识点编号：").strip())
        topic = flat[idx - 1]
    except (ValueError, IndexError):
        raise SystemExit("编号无效，退出。")

    print(f"\n正在为 {topic['id']}（{topic['name']}）加题\n")

    def ask(label, default="", required=False):
        while True:
            raw = input(f"{label}{f'（默认 {default}）' if default else ''}：").strip()
            if raw:
                return raw
            if default:
                return default
            if not required:
                return ""
            print("  这一项必填。")

    qtype = ask(f"题型 {'/'.join(TYPES)}", "numeric", required=True)
    difficulty = ask(f"难度 {'/'.join(DIFFICULTIES)}", "basic", required=True)
    prompt = ask("题干", required=True)
    q: dict = {"topicId": topic["id"], "type": qtype, "difficulty": difficulty, "prompt": prompt}

    if qtype == "choice":
        raw = ask("选项（用 | 分隔，可写 A:xxx|B:xxx）", required=True)
        q["choices"] = parse_choices(raw)
        q["answer"] = ask("正确答案（选项字母）", required=True).upper()
    else:
        q["answer"] = ask("答案（数字题写数，分数写 a/b，多解用，分隔）", required=True)

    q["explanation"] = ask("解析（1–3 句）", required=True)
    verify = ask("verify 表达式（可跳过，如 3+4 / Fraction(1,4) / sqrt(3**2+4**2)）")
    if verify:
        q["verify"] = verify
    accept = ask("等价答案（可跳过，用 | 分隔）")
    if accept:
        q["accept"] = [x.strip() for x in accept.split("|") if x.strip()]
    return [q]


def main() -> int:
    ap = argparse.ArgumentParser(description="向题库追加题目")
    ap.add_argument("--json", help="单条题目 JSON 字符串")
    ap.add_argument("--file", help="JSON 文件（数组或单个对象）")
    args = ap.parse_args()

    if args.json:
        return append_questions([json.loads(args.json)])
    if args.file:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
        return append_questions(data if isinstance(data, list) else [data])
    try:
        return append_questions(interactive())
    except (KeyboardInterrupt, EOFError):
        print("\n已取消。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
