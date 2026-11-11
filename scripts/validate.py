"""题库格式校验：python scripts/validate.py

只查「格式」，不判断答案对错（答案是否可信靠 verify_questions.py 和人工复核）。
有任何 error 时退出码为 1，方便在 git pre-commit 或 CI 里直接用。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qbank import (  # noqa: E402
    ALLOWED_FIELDS, DIFFICULTIES, ID_RE, REQUIRED_FIELDS, TYPES,
    load_questions, load_topics, parse_number, split_answers,
)

SVG_RE = re.compile(r"<svg\b", re.I)


def check_question(q: dict, idx: int, topic_ids: set[str], external: set[str]) -> list[str]:
    errs: list[str] = []
    where = f"[{idx}] {q.get('id') or '(无 id)'}"

    for field in REQUIRED_FIELDS:
        if field not in q:
            errs.append(f"{where} 缺少必填字段 {field}")
    if errs:
        return errs

    for field in q:
        if field not in ALLOWED_FIELDS:
            errs.append(f"{where} 出现未知字段 {field}（拼写错误？）")

    # id 与 topicId
    m = ID_RE.match(str(q["id"]))
    if not m:
        errs.append(f"{where} id 必须形如 <topicId>_q<N>")
    elif m.group("topic") != q["topicId"]:
        errs.append(f"{where} id 前缀与 topicId「{q['topicId']}」不一致")

    if q["topicId"] not in topic_ids:
        errs.append(f"{where} topicId「{q['topicId']}」不在 topics.json 中")
    elif q["topicId"] in external:
        errs.append(f"{where} topicId「{q['topicId']}」是 external 节点，不该有题")

    # 枚举值
    if q["difficulty"] not in DIFFICULTIES:
        errs.append(f"{where} difficulty 非法：{q['difficulty']}（可选 {'/'.join(DIFFICULTIES)}）")
    if q["type"] not in TYPES:
        errs.append(f"{where} type 非法：{q['type']}（可选 {'/'.join(TYPES)}）")

    # 文本字段
    for field in ("prompt", "answer", "explanation"):
        if not isinstance(q[field], str) or not q[field].strip():
            errs.append(f"{where} {field} 必须是非空字符串")

    # 配图
    fig = q.get("figure")
    if fig is not None:
        if not isinstance(fig, str) or not SVG_RE.search(fig):
            errs.append(f"{where} figure 必须是内联 <svg> 字符串")
        elif "viewBox" not in fig:
            errs.append(f"{where} figure 的 <svg> 缺少 viewBox")
        elif re.search(r"(src|href)\s*=", fig):
            errs.append(f"{where} figure 不能引用外部资源（src/href）")

    # 按题型检查
    t = q["type"]
    if t == "choice":
        choices = q.get("choices")
        if not isinstance(choices, list) or not 3 <= len(choices) <= 4:
            errs.append(f"{where} choice 题需要 3–4 个选项")
        else:
            keys, texts = [], []
            for c in choices:
                if not isinstance(c, dict) or "key" not in c or "text" not in c:
                    errs.append(f"{where} 每个选项都要有 key 和 text")
                    continue
                keys.append(c["key"])
                texts.append(str(c["text"]).strip())
                cf = c.get("figure")
                if cf is not None and (not isinstance(cf, str) or not SVG_RE.search(cf)):
                    errs.append(f"{where} 选项 {c['key']} 的 figure 必须是内联 <svg>")
            if keys != [chr(ord("A") + i) for i in range(len(keys))]:
                errs.append(f"{where} 选项 key 必须依次为 A、B、C、D，实际 {keys}")
            if len(set(texts)) != len(texts):
                errs.append(f"{where} 选项文字有重复")
            if any(not x for x in texts):
                errs.append(f"{where} 选项文字不能为空")
            if q["answer"] not in keys:
                errs.append(f"{where} answer「{q['answer']}」不是任何一个选项的 key")
            if q.get("hideChoiceText") and not all(c.get("figure") for c in choices if isinstance(c, dict)):
                errs.append(f"{where} 用了 hideChoiceText，但并非每个选项都有 figure")
    elif t == "numeric":
        parts = split_answers(q["answer"])
        if not parts:
            errs.append(f"{where} numeric 题 answer 不能为空")
        for p in parts:
            if parse_number(p) is None:
                errs.append(f"{where} numeric 的 answer「{p}」不是数字（分数写作 a/b）")
        if q.get("unordered") and len(parts) < 2:
            errs.append(f"{where} unordered 只用于多答案题")
    elif t == "short":
        if "accept" in q and not (isinstance(q["accept"], list) and all(isinstance(x, str) for x in q["accept"])):
            errs.append(f"{where} accept 必须是字符串数组")
    elif t == "self":
        if "accept" in q:
            errs.append(f"{where} self 题不需要 accept")

    if "verify" in q and not isinstance(q["verify"], str):
        errs.append(f"{where} verify 必须是字符串（Python 表达式）")

    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description="校验题库格式")
    ap.add_argument("--questions", default=None, help="题目文件，默认 data/questions.json")
    ap.add_argument("--topics", default=None, help="知识点文件，默认 data/topics.json")
    ap.add_argument("--quiet", action="store_true", help="只打印问题，不打印统计")
    args = ap.parse_args()

    questions = load_questions(args.questions) if args.questions else load_questions()
    topics = load_topics(args.topics) if args.topics else load_topics()

    topic_ids = {t["id"] for t in topics}
    external = {t["id"] for t in topics if t.get("external")}
    topic_name = {t["id"]: t.get("name", "") for t in topics}

    errors: list[str] = []
    seen: dict[str, int] = {}
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            errors.append(f"[{i}] 不是 JSON 对象")
            continue
        errors.extend(check_question(q, i, topic_ids, external))
        qid = q.get("id")
        if qid in seen:
            errors.append(f"[{i}] id 重复：{qid}（首次出现在第 {seen[qid]} 条）")
        else:
            seen[qid] = i

    if not args.quiet:
        by_type = collections.Counter(q.get("type") for q in questions if isinstance(q, dict))
        by_diff = collections.Counter(q.get("difficulty") for q in questions if isinstance(q, dict))
        by_subject = collections.Counter(
            next((t.get("subject", "?") for t in topics if t["id"] == q.get("topicId")), "?")
            for q in questions if isinstance(q, dict)
        )
        covered = {q.get("topicId") for q in questions if isinstance(q, dict)}
        topic_sem = {t["id"]: t.get("semester", "") for t in topics}
        empty_topics = [t["id"] for t in topics if t["id"] not in covered and not t.get("external")]

        print(f"题目总数：{len(questions)}")
        print("  按学科：" + "，".join(f"{k} {v}" for k, v in by_subject.most_common()))
        print("  按题型：" + "，".join(f"{k} {v}" for k, v in by_type.most_common()))
        print("  按难度：" + "，".join(f"{k} {v}" for k, v in by_diff.most_common()))
        by_sem = collections.Counter(
            q.get("semester")
            or (topic_sem.get(q.get("topicId")) or "(未标学期)")
            for q in questions if isinstance(q, dict)
        )
        sem_order = [k for k in ("上册", "下册", "全册") if by_sem.get(k)]
        sem_rest = [k for k in by_sem if k not in ("上册", "下册", "全册")]
        print("  按学期：" + "，".join(f"{k} {by_sem[k]}" for k in sem_order + sem_rest))
        print(f"知识点：共 {len(topic_ids)} 个，已有题 {len(covered & topic_ids)} 个，还没有题 {len(empty_topics)} 个")
        if empty_topics and len(empty_topics) <= 20:
            print("  待补题：" + "、".join(f"{tid}({topic_name.get(tid, '')})" for tid in empty_topics))
        with_verify = sum(1 for q in questions if isinstance(q, dict) and q.get("verify"))
        numeric_choice = by_type.get("numeric", 0) + by_type.get("choice", 0)
        if numeric_choice:
            print(f"  带 verify 的题：{with_verify}（占全部 {with_verify / len(questions):.0%}）")

    if errors:
        print(f"\n发现 {len(errors)} 个问题：")
        for e in errors[:200]:
            print("  ✗ " + e)
        if len(errors) > 200:
            print(f"  …… 其余 {len(errors) - 200} 条省略")
        return 1

    print("\n✓ 格式校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
