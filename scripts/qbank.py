"""qbank 公共工具：加载题库、数值解析、字段白名单。

被 validate.py / verify_questions.py / add_question.py / import_csv.py 共用。
"""
from __future__ import annotations

import json
import re
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
QUESTIONS_PATH = DATA_DIR / "questions.json"
TOPICS_PATH = DATA_DIR / "topics.json"
REPORT_PATH = DATA_DIR / "verification_report.json"

TYPES = ("numeric", "choice", "short", "self")

REQUIRED_FIELDS = ("id", "topicId", "type", "prompt", "answer", "explanation")

# 允许出现的字段，防止手滑写出 xxxxx / expanation 这类拼错的键
ALLOWED_FIELDS = {
    "id", "topicId", "type", "prompt", "answer", "explanation",
    "choices", "figure", "hideChoiceText", "accept", "verify", "unordered",
    "tags", "source", "note", "region", "semester",
}

ID_RE = re.compile(r"^(?P<topic>.+)_q(?P<n>\d+)$")


def load_questions(path: Path | str = QUESTIONS_PATH) -> list[dict]:
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit(f"{path} 顶层必须是 JSON 数组")
    return data


def load_topics(path: Path | str = TOPICS_PATH) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data


def save_questions(questions: list[dict], path: Path | str = QUESTIONS_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_number(text):
    """把答案字符串解析成 Fraction / float。

    支持整数、小数、分数（a/b）、负号。无法解析（如 "增函数"）返回 None。
    """
    if text is None:
        return None
    if isinstance(text, (int, float, Fraction)):
        return Fraction(text) if isinstance(text, int) else text
    s = str(text).strip().replace(" ", "")
    if not s:
        return None
    s = s.replace("−", "-").replace("／", "/")
    # 全角数字转半角
    s = s.translate({ord(c): ord(c) - 0xFEE0 for c in "０１２３４５６７８９．"})
    try:
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        pass
    try:
        return float(s)
    except ValueError:
        return None


def split_answers(answer) -> list[str]:
    """把 "2，3" / "2,3" 拆成多答案列表。"""
    if answer is None:
        return []
    s = str(answer).strip()
    if not s:
        return []
    parts = re.split(r"[，,；;]", s)
    return [p.strip() for p in parts if p.strip()]


def next_id(topic_id: str, questions: list[dict]) -> str:
    """生成该知识点下一个可用的题号：<topicId>_q<N>。"""
    used = 0
    for q in questions:
        if q.get("topicId") != topic_id:
            continue
        m = ID_RE.match(str(q.get("id", "")))
        if m and m.group("topic") == topic_id:
            used = max(used, int(m.group("n")))
    return f"{topic_id}_q{used + 1}"
