"""把主库导出成「四选项 App 版」JSON：python scripts/make_app_json.py

产物：根目录 q_app.json（App / 电视端拉取用）

和 data/questions.json 的区别：
  - 只保留选择题与数值题，数值题现场改写成四选项（干扰项由答案生成）；
  - 短答题（short / self）无法做成选择题，直接跳过——所以语文会少掉一批名句默写；
  - 字段压平成 App 常见写法：stem / options / answerIndex / solution / term / region / edition。

term 约定：1 = 上册，2 = 下册，0 = 全册或未标学期。
随机性用了固定种子，同样的主库数据每次导出结果一致。
"""
from __future__ import annotations

import collections
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qbank import QUESTIONS_PATH, TOPICS_PATH  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "q_app.json"
SEED = 20261111


def term_of(topic: dict) -> int:
    s = topic.get("semester") or ""
    if s == "上册":
        return 1
    if s == "下册":
        return 2
    return 0          # 全册，或没标学期


NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")


def variants(ans: str) -> list[str]:
    """由数值答案生成干扰项候选。"""
    nums = NUM_RE.findall(ans)
    if not nums:
        return []
    base = nums[0]
    cands: list[str] = []
    try:
        if "/" in base:
            num, den = base.split("/")
            v = float(num) / float(den)
            for delta in (0.25, -0.25, 0.5, -0.5, 1.0, -1.0):
                cands.append(str(round(v + delta, 3)))
        else:
            v = float(base)
            iv = int(v)
            cands += [str(iv + 1), str(iv - 1), str(-iv), str(iv * 2), str(iv + 10), str(iv - 10)]
            if v != iv:
                cands += [str(round(v + 1, 2)), str(round(v - 1, 2))]
    except (ValueError, ZeroDivisionError):
        return []
    # 多值答案（如 "1，6"）整体造一个变体，避免拆散后对不上
    if len(nums) > 1:
        parts = [p.strip() for p in re.split(r"[,，;；、]", ans) if p.strip()]
        if len(parts) > 1:
            out = []
            for p in parts:
                try:
                    out.append(str(int(float(p)) + 1))
                except ValueError:
                    out.append(p + "1")
            return ["，".join(out)]
    return cands


def main() -> int:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    topics = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))
    tmap = {t["id"]: t for t in topics}
    rnd = random.Random(SEED)

    converted: list[dict] = []
    stats = collections.Counter()

    for q in questions:
        t = tmap.get(q.get("topicId"), {})
        base = {
            "id": q.get("id"),
            "grade": int(t.get("grade") or 7),
            "subject": t.get("subject") or "math",
            "topic": t.get("name") or q.get("topicId"),
            "stem": q.get("prompt"),
            "solution": [s.strip() for s in re.split(r"[；;。]", (q.get("explanation") or "").strip()) if s.strip()]
                        or [q.get("explanation") or ""],
            "explanation": (q.get("explanation") or "").strip(),
            "term": term_of(t),
            "region": q.get("region") or "national",
            "edition": "pep",
        }

        # 本来就是选择题：沿用原有选项与顺序
        if q.get("type") == "choice" and q.get("choices"):
            ch = q["choices"]
            keys = [c.get("key") for c in ch]
            ans = str(q.get("answer", "")).strip()
            idx = keys.index(ans) if ans in keys else -1
            if idx < 0:
                texts = [c.get("text") for c in ch]
                idx = texts.index(ans) if ans in texts else -1
            if idx < 0:
                stats["skip_choice"] += 1
                continue
            base.update({"options": [c.get("text") for c in ch], "answerIndex": idx})
            converted.append(base)
            stats["choice"] += 1
            continue

        ans = str(q.get("answer", "")).strip()
        if not ans:
            stats["skip_noanswer"] += 1
            continue

        if q.get("type") != "numeric":
            stats["skip_" + str(q.get("type"))] += 1
            continue

        pool = [c for c in variants(ans) if c and c != ans]
        dist: list[str] = []
        for c in pool:
            if c not in dist:
                dist.append(c)
        opts_pool = dist[:3]
        if len(opts_pool) < 3:      # 干扰项不够就用随机数补齐（与早期转换脚本保持同一随机序列）
            opts_pool += [str(rnd.randint(1, 99)) for _ in range(3 - len(opts_pool))]
        opts = [ans] + opts_pool
        rnd.shuffle(opts)
        base.update({"options": opts, "answerIndex": opts.index(ans)})
        converted.append(base)
        stats["numeric"] += 1

    payload = {
        "version": 1,
        "source": "siyagang/shiti-bank 全国中考题库（四选项 App 版）",
        "license": "自建",
        "note": "由 data/questions.json 导出：选择题原样保留；数值题改写为四选项；短答题（short/self）无法转选择题，未纳入。"
                "term：1=上册，2=下册，0=全册或未标学期。",
        "count": len(converted),
        "questions": converted,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    print(f"导出 {len(converted)} 题 → {OUT_PATH}")
    print("  来源分布：" + "，".join(f"{k} {v}" for k, v in stats.most_common()))
    print("  按学科：" + "，".join(f"{k} {v}" for k, v in collections.Counter(
        q["subject"] for q in converted).most_common()))
    print("  按学期：" + "，".join(f"term={k} {v}" for k, v in sorted(
        collections.Counter(q["term"] for q in converted).items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
