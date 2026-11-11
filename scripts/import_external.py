"""从同格式的开源题库导入「中学」题目：python scripts/import_external.py

默认读 data/_source/ 下的 questions.json 与 topics.json（同 xiaoyang111222/cn-math-taxonomy 的格式），
按学科配额挑题、按知识点评分挑题，合并进 data/questions.json 与 data/topics.json。

设计原则：
- 只收能自证答案的题（必须有 verify），答案能被 scripts/verify_questions.py 复核；
- 只收不依赖配图的题（题干里出现「如图 / 下图 / 表中」直接跳过），保证题干自包含；
- 每题都带 source 字段，标明来源，便于日后溯源或整批删除；
- 可重复运行：已导入过的题（按题干文本判重）不会重复进库。

用法：
    python scripts/import_external.py --dry-run      # 只看会导入多少题
    python scripts/import_external.py --write        # 实际写入
    python scripts/import_external.py --source D:/tmp/src --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qbank import (  # noqa: E402
    DATA_DIR, QUESTIONS_PATH, TOPICS_PATH, load_questions, load_topics,
    parse_number, save_questions,
)
from verify_questions import verify_one  # noqa: E402

SOURCE_DIR = DATA_DIR / "_source"
SOURCE_URLS = {
    "questions.json": "https://cdn.jsdelivr.net/gh/xiaoyang111222/cn-math-taxonomy@main/data/questions.json",
    "topics.json": "https://cdn.jsdelivr.net/gh/xiaoyang111222/cn-math-taxonomy@main/data/topics.json",
}
SOURCE_LABEL = "cn-math-taxonomy 开源题库（中学）"

# 学科配额：(subject, stage) -> 题数上限
QUOTAS = {
    ("math", "j"): 160,
    ("math", "h"): 100,
    ("physics", "j"): 80,
    ("physics", "h"): 60,
    ("chemistry", "j"): 70,
    ("english", "j"): 60,
    ("english", "h"): 40,
    ("chinese", "j"): 60,
    ("history", "j"): 40,
    ("geography", "j"): 40,
    ("biology", "j"): 40,
    ("morality", "j"): 30,
}
PER_TOPIC_CAP = 4

SUBJECTS = {
    "m": "math", "c": "chinese", "e": "english", "p": "physics", "k": "chemistry",
    "b": "biology", "h": "history", "g": "geography", "s": "science", "d": "morality",
}
# 出题优先级：例题式（standard）> 综合（advanced）> 一步到位（basic）> 竞赛味（challenge）
DIFF_RANK = {"standard": 0, "advanced": 1, "basic": 2, "challenge": 3}

BANNED_PROMPT = re.compile(
    r"如图|下图|上图|右图|左图|图中|表中|表格中|统计图|折线|扇形图|条形图"
    r"|（1）|\(1\)|①|②|③"
    r"|<svg|</|\\frac|\\dfrac|\$"
)


def subject_of(topic_id: str) -> str:
    m = re.match(r"cn([a-z])", topic_id)
    return SUBJECTS.get(m.group(1), "") if m else ""


def stage_of(grade) -> str:
    try:
        g = int(grade)
    except (TypeError, ValueError):
        return ""
    return "p" if 1 <= g <= 6 else ("j" if 7 <= g <= 9 else ("h" if 10 <= g <= 12 else ""))


def norm_prompt(text: str) -> str:
    return re.sub(r"\s+", "", str(text))


SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def polish(text: str) -> str:
    """把 x^2 这类写法换成上标，页面上更好读（只动展示文本，不动 answer / verify）。"""
    return re.sub(r"\^(-?\d+)", lambda m: m.group(1).translate(SUP), str(text))


def fetch_source(src: Path) -> tuple[list[dict], list[dict]]:
    """读取来源题库；目录不存在时从 CDN 拉一份到 data/_source/。"""
    if not (src / "questions.json").exists():
        src.mkdir(parents=True, exist_ok=True)
        import urllib.request
        for name, url in SOURCE_URLS.items():
            print(f"下载 {url}")
            urllib.request.urlretrieve(url, src / name)
    questions = json.loads((src / "questions.json").read_text(encoding="utf-8"))
    topics = json.loads((src / "topics.json").read_text(encoding="utf-8"))
    return questions, topics


def eligible(q: dict, topic: dict) -> bool:
    """一道题是否值得收：能自证、题干自包含、选项干净。"""
    if q.get("type") not in ("choice", "numeric"):
        return False
    if not q.get("verify"):
        return False
    prompt = str(q.get("prompt") or "")
    if not 8 <= len(prompt) <= 130 or "\n" in prompt:
        return False
    if BANNED_PROMPT.search(prompt):
        return False
    if not str(q.get("explanation") or "").strip():
        return False
    answer = str(q.get("answer") or "").strip()
    if not answer or answer in ("略", "见解析", "答案不唯一"):
        return False
    if q["type"] == "numeric":
        parts = re.split(r"[，,；;]", answer)
        if not all(parse_number(p) for p in parts if p.strip()):
            return False
    else:
        choices = q.get("choices") or []
        if not 3 <= len(choices) <= 4:
            return False
        keys = [c.get("key") for c in choices]
        if keys != [chr(ord("A") + i) for i in range(len(keys))]:
            return False
        texts = [str(c.get("text") or "").strip() for c in choices]
        if len(set(texts)) != len(texts) or any(not t or len(t) > 45 for t in texts):
            return False
        if answer not in keys:
            return False
    # 答案必须能被 verify 当场算对，否则不入库（宁可少收，不收可疑题）
    status, _ = verify_one(q)
    return status == "verified"


def collect(src_questions: list[dict], src_topics: list[dict], existing_prompts: set[str]):
    topics = {t["id"]: t for t in src_topics}
    pool: dict[str, list[dict]] = defaultdict(list)
    seen_prompt = set(existing_prompts)

    for q in src_questions:
        t = topics.get(q.get("topicId", ""))
        if not t:
            continue
        grade = t.get("grade")
        stage = stage_of(grade)
        subject = t.get("subject") or subject_of(t.get("id", ""))
        if stage not in ("j", "h") or (subject, stage) not in QUOTAS:
            continue
        if not eligible(q, t):
            continue
        key = norm_prompt(q["prompt"])
        if key in seen_prompt:
            continue
        seen_prompt.add(key)
        item = dict(q)
        item["_subject"] = subject
        item["_stage"] = stage
        item["_grade"] = int(grade)
        pool[t["id"]].append(item)

    for tid in pool:
        pool[tid].sort(key=lambda x: (DIFF_RANK.get(x.get("difficulty"), 9),
                                      hashlib.md5(str(x["id"]).encode()).hexdigest()))
    return pool


def pick(pool: dict[str, list[dict]]) -> list[dict]:
    """按知识点轮转取题，避免某个知识点占满配额。"""
    left = dict(QUOTAS)
    taken: list[dict] = []
    per_topic = Counter()
    queues = {tid: list(items) for tid, items in pool.items()}
    order = sorted(queues, key=lambda tid: (tid[:3], tid))
    while any(queues.values()):
        progressed = False
        for tid in order:
            queue = queues[tid]
            if not queue:
                continue
            q = queue.pop(0)
            quota_key = (q["_subject"], q["_stage"])
            if left.get(quota_key, 0) <= 0 or per_topic[tid] >= PER_TOPIC_CAP:
                continue
            left[quota_key] -= 1
            per_topic[tid] += 1
            taken.append(q)
            progressed = True
        if not progressed:
            break
    return taken


def build_topics(taken: list[dict], src_topics: list[dict], our_topics: list[dict]):
    """把被选中的题所属知识点转成本地格式，处理 id 冲突。"""
    src = {t["id"]: t for t in src_topics}
    used_ids = {t["id"] for t in our_topics}
    rename: dict[str, str] = {}
    new_topics = []

    for tid in sorted({q["topicId"] for q in taken}):
        t = src[tid]
        new_id = tid
        if new_id in used_ids:  # 与本地点位撞号：加后缀，避免覆盖自己的知识点
            new_id = f"{tid}x"
            while new_id in used_ids:
                new_id += "x"
        used_ids.add(new_id)
        rename[tid] = new_id
        new_topics.append({
            "id": new_id,
            "name": t.get("name", ""),
            "subject": t.get("subject") or subject_of(tid),
            "domain": t.get("domain", ""),
            "grade": int(t.get("grade") or 0),
            "semester": t.get("semester", ""),
            "chapter": t.get("chapter", ""),
            "type": t.get("type", "conceptual"),
            "description": re.sub(r"\s+", " ", str(t.get("description") or ""))[:180],
            "mastery_criteria": t.get("mastery_criteria") or [],
            "diagnostic_question": t.get("diagnostic_question") or {},
        })
    return new_topics, rename


def build_questions(taken: list[dict], rename: dict[str, str], our_questions: list[dict]):
    out = []
    counter = Counter()
    for q in taken:
        tid = rename[q["topicId"]]
        counter[tid] += 1
        item = {
            "id": f"{tid}_q{100 + counter[tid]}",
            "topicId": tid,
            "difficulty": q["difficulty"],
            "type": q["type"],
            "prompt": polish(q["prompt"]).strip(),
            "answer": str(q["answer"]).strip(),
            "explanation": polish(q["explanation"]).strip(),
            "source": SOURCE_LABEL,
        }
        if q["type"] == "choice":
            item["choices"] = [
                {"key": c["key"], "text": polish(str(c["text"]).strip())} for c in q["choices"]
            ]
        if q.get("unordered"):
            item["unordered"] = True
        if q.get("accept") and q["type"] == "numeric":
            item["accept"] = list(q["accept"])
        item["verify"] = q["verify"]
        # 上标改写后要再核一次：选择题的 verify 比对的是选项文字，改写可能让答案对不上
        if verify_one(item)[0] != "verified":
            continue
        out.append(item)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="导入开源中学题目")
    ap.add_argument("--source", default=str(SOURCE_DIR), help="来源目录（含 questions.json / topics.json）")
    ap.add_argument("--write", action="store_true", help="实际写入 data/ 下两个 json")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写入")
    args = ap.parse_args()

    src_questions, src_topics = fetch_source(Path(args.source))
    our_questions = load_questions(QUESTIONS_PATH)
    our_topics = load_topics(TOPICS_PATH)

    existing_prompts = {norm_prompt(q.get("prompt", "")) for q in our_questions}
    pool = collect(src_questions, src_topics, existing_prompts)
    taken = pick(pool)

    by_subject = Counter((q["_subject"], q["_stage"]) for q in taken)
    print(f"来源题目 {len(src_questions)} 道，可用候选 {sum(len(v) for v in pool.values())} 道")
    print("本次选中：")
    for (subject, stage), n in sorted(by_subject.items(), key=lambda kv: -kv[1]):
        print(f"  {subject:9s} {stage}  {n:4d}")
    print(f"  合计 {len(taken)} 道，涉及知识点 {len({q['topicId'] for q in taken})} 个")

    if args.dry_run or not args.write:
        print("\n（未写入；加 --write 生效）")
        return 0

    new_topics, rename = build_topics(taken, src_topics, our_topics)
    new_questions = build_questions(taken, rename, our_questions)
    used = {q["topicId"] for q in new_questions}
    new_topics = [t for t in new_topics if t["id"] in used]  # 没题的知识点不落库

    topics_all = our_topics + new_topics
    questions_all = our_questions + new_questions
    TOPICS_PATH.write_text(json.dumps(topics_all, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_questions(questions_all)
    print(f"\n写入完成：题目 {len(our_questions)} 题 → {len(questions_all)} 题；"
          f"知识点 {len(our_topics)} 个 → {len(topics_all)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
