"""自动核验答案：python scripts/verify_questions.py

对带 verify 字段的题，在受限环境里求值，再与 answer 比对：
  - numeric：求值结果是数（或数的元组 / 列表），与 answer 逐项比较；
  - choice：求值结果与「正确选项的文字」比较（选项是数就按数值比）。

verify 里能用的东西：
  四则运算、** // %、比较、min/max/sum/sorted/abs/round、Fraction、
  sqrt/pi/e/sin/cos/tan、comb/perm/gcd/lcm/ceil/floor、
  mean/median/pvariance、len/range、
  solve2(a1,b1,c1,a2,b2,c2)  解二元一次方程组，返回 (x, y) 精确分数
  roots2(a,b,c)              解 ax²+bx+c=0，返回排序后的实根元组（无实根返回空元组）

没有 import、没有属性访问、没有赋值。表达式长度和节点数都有上限。
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qbank import (  # noqa: E402
    REPORT_PATH, load_questions, parse_number, split_answers,
)

MAX_LEN = 400
MAX_NODES = 300

SAFE_NODES = {
    "Expression", "BinOp", "UnaryOp", "Constant", "Name", "Load", "Call", "keyword",
    "List", "Tuple", "Compare", "BoolOp", "IfExp", "Subscript", "Slice",
    "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow",
    "UAdd", "USub", "Not", "And", "Or",
    "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE",
}

TOL = 1e-9


class Unsafe(Exception):
    pass


def _isqrt_fraction(d: Fraction) -> Fraction | None:
    """分数开平方，能开尽就返回精确分数，否则返回 None。"""
    num, den = d.numerator, d.denominator
    if num < 0:
        return None
    rn, rd = math.isqrt(num), math.isqrt(den)
    if rn * rn == num and rd * rd == den:
        return Fraction(rn, rd)
    return None


def solve2(a1, b1, c1, a2, b2, c2):
    """解 a1x + b1y = c1；a2x + b2y = c2（或 a1x + b1 = c1 形式自行整理）。"""
    a1, b1, c1 = Fraction(a1), Fraction(b1), Fraction(c1)
    a2, b2, c2 = Fraction(a2), Fraction(b2), Fraction(c2)
    det = a1 * b2 - a2 * b1
    if det == 0:
        raise ValueError("方程组无唯一解")
    x = (c1 * b2 - c2 * b1) / det
    y = (a1 * c2 - a2 * c1) / det
    return (x, y)


def roots2(a, b, c):
    """解 ax² + bx + c = 0，返回排序后的实根元组（重根只出现一次）。"""
    a, b, c = Fraction(a), Fraction(b), Fraction(c)
    if a == 0:
        raise ValueError("二次项系数不能为 0")
    d = b * b - 4 * a * c
    if d < 0:
        return ()
    root = _isqrt_fraction(d)
    if root is None:
        sd = math.sqrt(float(d))
        r1, r2 = (-float(b) - sd) / (2 * float(a)), (-float(b) + sd) / (2 * float(a))
    else:
        r1, r2 = (-b - root) / (2 * a), (-b + root) / (2 * a)
    if r1 == r2:
        return (r1,)
    return tuple(sorted((r1, r2)))


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _pvariance(xs):
    xs = list(xs)
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


ENV = {
    "Fraction": Fraction,
    "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "log": math.log, "exp": math.exp, "hypot": math.hypot,
    "comb": math.comb, "perm": math.perm, "gcd": math.gcd, "lcm": math.lcm,
    "ceil": math.ceil, "floor": math.floor,
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "sorted": sorted, "len": len, "range": range, "int": int, "float": float,
    "mean": _mean, "median": _median, "pvariance": _pvariance,
    "solve2": solve2, "roots2": roots2,
}


def safe_eval(expr: str):
    if len(expr) > MAX_LEN:
        raise Unsafe(f"表达式过长（>{MAX_LEN} 字符）")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise Unsafe(f"语法错误：{exc.msg}") from exc

    count = 0
    for node in ast.walk(tree):
        count += 1
        if count > MAX_NODES:
            raise Unsafe("表达式过于复杂")
        name = type(node).__name__
        if name not in SAFE_NODES:
            raise Unsafe(f"不允许的语法：{name}")
        if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name):
            raise Unsafe("只能调用白名单函数")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in ENV:
                raise Unsafe(f"未知名称：{node.id}")
    return eval(compile(tree, "<verify>", "eval"), {"__builtins__": {}}, dict(ENV))


def num_equal(a, b) -> bool:
    """数值比较：整数 / 分数精确比，浮点按相对容差。"""
    try:
        fa = a if isinstance(a, Fraction) else Fraction(a)
        fb = b if isinstance(b, Fraction) else Fraction(b)
        if not isinstance(a, float) and not isinstance(b, float):
            return fa == fb
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()
    try:
        return math.isclose(float(a), float(b), rel_tol=TOL, abs_tol=TOL)
    except (TypeError, ValueError):
        return False


def results_equal(got, want, unordered: bool) -> bool:
    """把求值结果和答案列表比较。"""
    got_list = list(got) if isinstance(got, (list, tuple)) else [got]
    if len(got_list) != len(want):
        return False

    def norm(g, w):
        gn, wn = parse_number(g), parse_number(w)
        if gn is not None and wn is not None:
            return num_equal(gn, wn)
        return str(g).strip() == str(w).strip()

    if unordered:
        remaining = list(got_list)
        for w in want:
            for i, g in enumerate(remaining):
                if norm(g, w):
                    remaining.pop(i)
                    break
            else:
                return False
        return not remaining
    return all(norm(g, w) for g, w in zip(got_list, want))


def check_string(got: str, q: dict, option_text: str) -> tuple[bool, str]:
    """choice 题：verify 返回的文字要和正确选项一致，且不能有第二个选项也叫这个名字。"""
    got = str(got).strip()
    gn, on = parse_number(got), parse_number(option_text)
    ok = num_equal(gn, on) if (gn is not None and on is not None) else got == str(option_text).strip()
    if not ok:
        return False, f"求值得到「{got}」，正确选项文字是「{option_text}」"

    for c in q.get("choices") or []:
        if c.get("key") == q.get("answer"):
            continue
        text = str(c.get("text", "")).strip()
        cn = parse_number(text)
        same = num_equal(gn, cn) if (gn is not None and cn is not None) else text == got
        if same:
            return False, f"选项 {c['key']}「{text}」与求值结果相同，存在双解"
    return True, ""


def verify_one(q: dict) -> tuple[str, str]:
    """返回 (状态, 说明)。状态 ∈ verified / mismatch / unverifiable / error。"""
    expr = q.get("verify")
    if not expr:
        return "unverifiable", "没有 verify"

    try:
        got = safe_eval(expr)
    except Unsafe as exc:
        return "error", f"verify 不被允许：{exc}"
    except Exception as exc:  # noqa: BLE001 - 求值期异常都算表达式问题
        return "error", f"verify 求值失败：{type(exc).__name__}: {exc}"

    if q.get("type") == "choice":
        option_text = next(
            (str(c.get("text", "")) for c in q.get("choices") or [] if c.get("key") == q.get("answer")),
            None,
        )
        if option_text is None:
            return "error", "找不到正确选项"
        ok, msg = check_string(got, q, option_text)
        return ("verified", "") if ok else ("mismatch", msg)

    if q.get("type") == "numeric":
        want = split_answers(q.get("answer"))
        if not want:
            return "error", "answer 为空"
        if results_equal(got, want, bool(q.get("unordered"))):
            return "verified", ""
        shown = got if isinstance(got, (list, tuple)) else [got]
        return "mismatch", f"求值得到 {shown}，answer 是 {want}"

    if q.get("type") == "short":
        want = [q.get("answer", "")] + list(q.get("accept") or [])
        got_s = str(got).strip()
        if any(got_s == str(w).strip() for w in want):
            return "verified", ""
        return "mismatch", f"求值得到「{got_s}」，answer / accept 都不含它"

    return "unverifiable", f"{q.get('type')} 题不做自动核验"


def main() -> int:
    ap = argparse.ArgumentParser(description="用 verify 表达式核验答案")
    ap.add_argument("--file", default=None, help="只核验某个题目文件")
    ap.add_argument("--report", default=str(REPORT_PATH), help="核验报告输出路径")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    questions = load_questions(args.file) if args.file else load_questions()

    stats = {"verified": 0, "mismatch": 0, "unverifiable": 0, "error": 0}
    details = {k: [] for k in stats}
    for q in questions:
        status, msg = verify_one(q)
        stats[status] += 1
        if status in ("mismatch", "error") or (status == "unverifiable" and q.get("verify")):
            details[status].append({"id": q.get("id"), "topicId": q.get("topicId"), "reason": msg})

    report = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "source": args.file or "data/questions.json",
        "total": len(questions),
        "stats": stats,
        "verified_ids": [q.get("id") for q in questions if q.get("verify") and verify_one(q)[0] == "verified"],
        "mismatch": details["mismatch"],
        "error": details["error"],
        "unverifiable": details["unverifiable"],
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        print(f"核验 {len(questions)} 题")
        print(f"  auto_verified {stats['verified']}")
        print(f"  mismatch      {stats['mismatch']}")
        print(f"  error         {stats['error']}")
        print(f"  unverifiable  {stats['unverifiable']}")
        for bucket in ("mismatch", "error"):
            for item in details[bucket][:20]:
                print(f"  ! {item['id']}: {item['reason']}")
        print(f"报告已写入 {args.report}")

    return 1 if (stats["mismatch"] or stats["error"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
