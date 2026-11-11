"""生成「全国省市中考仿真题库」：python scripts/build_zhongkao.py

产物：
  data/topics.json     按 学科 × 七八九年级 的知识点
  data/questions.json  新题库（理科按模板参数化生成，文科按素材分配省份）
  data/regions.json    31 个省级行政区的考情说明

所有题目都带 region 字段，练习页可据此按省份筛选。
"""
from __future__ import annotations

import json
import random
import sys
import zlib
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qbank import TOPICS_PATH, QUESTIONS_PATH  # noqa: E402
from zk_cn import IDIOMS, LITERATURE, POEMS  # noqa: E402
from zk_data import PROVINCES, PROVINCE_NAMES, build_topics, topic_id  # noqa: E402
from zk_humanities import ENGLISH, GEOGRAPHY, HISTORY  # noqa: E402
from zk_science_liberal import BIOLOGY, MORALITY  # noqa: E402

REGIONS_PATH = QUESTIONS_PATH.parent / "regions.json"
ROOT_Q_PATH = QUESTIONS_PATH.parent.parent / "q.json"
DIFFS = ("basic", "standard", "advanced")


def stable(*parts) -> int:
    """跨进程稳定的哈希，用作随机种子（内置 hash 每个进程都不一样）。"""
    return zlib.crc32("|".join(str(p) for p in parts).encode("utf-8"))


# ------------------------------------------------------------------ 工具
def frac_str(x) -> str:
    """把 Fraction 写成 3 或 3/4 这种形式。"""
    x = Fraction(x)
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def num(x) -> str:
    """数值转字符串：整数不带小数点，小数最多两位。"""
    if isinstance(x, Fraction):
        return frac_str(x)
    f = float(x)
    if abs(f - round(f)) < 1e-9:
        return str(int(round(f)))
    return f"{f:.2f}".rstrip("0").rstrip(".")


def xterm(k: int) -> str:
    """把一次项系数写成 " + 3x" / " - x" / ""。"""
    if k == 0:
        return ""
    return (" + " if k > 0 else " - ") + ("" if abs(k) == 1 else str(abs(k))) + "x"


def cterm(k: int) -> str:
    """把常数项写成 " + 5" / " - 5" / ""。"""
    return "" if k == 0 else (" + " if k > 0 else " - ") + str(abs(k))


def factor(p: int) -> str:
    """把根 p 写成因式 (x - p) / (x + p)。"""
    return f"(x - {p})" if p >= 0 else f"(x + {abs(p)})"


def build_choice(rng: random.Random, correct: str, distractors: list[str]):
    """打乱选项，返回 (choices, 正确项 key)。"""
    opts = [correct]
    for d in distractors:
        if d and d not in opts:
            opts.append(d)
    if len(opts) < 3:
        return None
    opts = opts[:4]
    rng.shuffle(opts)
    choices = [{"key": chr(ord("A") + i), "text": t} for i, t in enumerate(opts)]
    key = next(c["key"] for c in choices if c["text"] == correct)
    return choices, key


# ------------------------------------------------------------------ 数学
def math_g7(rng: random.Random):
    a, b, c = rng.randint(2, 9), rng.randint(2, 9), rng.randint(2, 9)
    yield dict(topic=0, difficulty="basic", type="numeric",
               prompt=f"计算：-{a} + {b} × (-{c}) 的值是（　）。",
               answer=num(-a - b * c), verify=f"-{a}+{b}*(-{c})",
               explanation=f"先算乘法：{b}×(-{c}) = -{b * c}；再算加法：-{a} + (-{b * c}) = {-a - b * c}。")

    a, b = rng.randint(2, 5), rng.randint(2, 5)
    p_, q_ = rng.randint(1, 6), rng.randint(1, 6)
    k = rng.randint(-6, 9)
    val = a * (k - p_) - b * (k + q_)
    yield dict(topic=1, difficulty="standard", type="numeric",
               prompt=f"当 x = {k} 时，代数式 {a}(x - {p_}) - {b}(x + {q_}) 的值是（　）。",
               answer=num(val), verify=f"{a}*({k}-{p_})-{b}*({k}+{q_})",
               explanation=f"原式 = {a}x - {a * p_} - {b}x - {b * q_} = {a - b}x - {a * p_ + b * q_}，"
                           f"代入 x = {k} 得 {val}。")

    x0 = rng.randint(-6, 8)
    aa = rng.randint(2, 7)
    bb = rng.randint(-9, 9)
    cc = aa * x0 + bb
    sign = "+" if bb >= 0 else "-"
    yield dict(topic=2, difficulty="standard", type="numeric",
               prompt=f"方程 {aa}x {sign} {abs(bb)} = {cc} 的解是 x = （　）。",
               answer=num(x0), verify=f"({cc}-({bb}))/{aa}",
               explanation=f"移项得 {aa}x = {cc - bb}，两边同除以 {aa}，得 x = {x0}。")

    x0, y0 = rng.randint(-4, 6), rng.randint(-4, 6)
    if x0 == y0:
        y0 += 1
    a1, b1 = rng.randint(1, 3), rng.randint(1, 3)
    a2, b2 = rng.randint(1, 3), rng.randint(-3, -1)
    c1 = a1 * x0 + b1 * y0
    c2 = a2 * x0 + b2 * y0
    yield dict(topic=5, difficulty="advanced", type="numeric", unordered=True,
               prompt=(f"解方程组：{a1}x {'+' if b1 >= 0 else '-'} {abs(b1)}y = {c1}；"
                       f"{a2}x {b2:+d}y = {c2}。则 x = （　），y = （　）。"),
               answer=f"{x0}，{y0}", verify=f"solve2({a1},{b1},{c1},{a2},{b2},{c2})",
               explanation=f"两式联立消元可解得 x = {x0}，y = {y0}。")

    a = rng.randint(2, 6)
    b = rng.randint(1, 9)
    k = rng.randint(0, 4)
    c = a * k + b + rng.randint(1, a - 1)
    while (c + b) % a == 0:  # 保证解不是整数，floor 才等于「最大整数解」
        c += 1
    lim = Fraction(c + b, a)
    ans = lim.numerator // lim.denominator
    yield dict(topic=6, difficulty="advanced", type="numeric",
               prompt=f"不等式 {a}x - {b} < {c} 的最大整数解是（　）。",
               answer=num(ans), verify=f"floor(({c}+({b}))/{a})",
               explanation=f"移项得 {a}x < {c + b}，即 x < {frac_str(lim)}，"
                           f"所以最大整数解是 {ans}。")

    d = rng.randint(20, 89)
    yield dict(topic=4, difficulty="basic", type="numeric",
               prompt=f"两条平行线被第三条直线所截，若其中一个同旁内角是 {d}°，则另一个同旁内角是（　）°。",
               answer=num(180 - d), verify=f"180-{d}",
               explanation=f"两直线平行，同旁内角互补，所以另一个角是 180° - {d}° = {180 - d}°。")

    nums = [rng.randint(60, 100) for _ in range(5)]
    total = sum(nums)
    target = round(total / 5) * 5
    nums[0] += target - total
    yield dict(topic=7, difficulty="basic", type="numeric",
               prompt=f"某小组 5 名同学的成绩分别为 {'、'.join(str(n) for n in nums)} 分，"
                      f"他们的平均分是（　）分。",
               answer=num(sum(nums) // 5), verify="mean([" + ",".join(str(n) for n in nums) + "])",
               explanation=f"平均分 = ({' + '.join(str(n) for n in nums)}) ÷ 5 = {sum(nums) // 5}。")


def math_g8(rng: random.Random):
    a = rng.randint(2, 12)
    b = rng.randint(2, 12)
    yield dict(topic=0, difficulty="basic", type="numeric",
               prompt=f"计算：(√{a})² + √({b * b}) = （　）。",
               answer=num(a + b), verify=f"{a}+sqrt({b * b})",
               explanation=f"(√{a})² = {a}，√({b * b}) = {b}，所以结果为 {a + b}。")

    m_, n_ = rng.randint(2, 10), rng.randint(1, 9)
    if n_ >= m_:
        n_ = m_ - 1
    k_ = rng.choice([1, 2])
    a, b, c = (m_ * m_ - n_ * n_) * k_, 2 * m_ * n_ * k_, (m_ * m_ + n_ * n_) * k_
    yield dict(topic=1, difficulty="standard", type="numeric",
               prompt=f"直角三角形的两条直角边分别为 {a} 和 {b}，则斜边长为（　）。",
               answer=num(c), verify=f"sqrt({a}**2+{b}**2)",
               explanation=f"由勾股定理，斜边 = √({a}² + {b}²) = √{a * a + b * b} = {c}。")

    x1 = rng.randint(1, 5)
    k = rng.randint(-4, 5)
    if k == 0:
        k = 2
    b0 = rng.randint(-6, 6)
    y1 = k * x1 + b0
    yield dict(topic=3, difficulty="standard", type="numeric",
               prompt=f"一次函数 y = kx + b 的图象经过点 (0, {b0}) 和 ({x1}, {y1})，则 k = （　）。",
               answer=num(k), verify=f"({y1}-({b0}))/{x1}",
               explanation=f"把两点坐标代入得 b = {b0}，{k}×{x1} + {b0} = {y1}，所以 k = {k}。")

    x0 = rng.randint(2, 12)
    bb = rng.randint(2, 9)
    aa = x0 * bb
    yield dict(topic=6, difficulty="standard", type="numeric",
               prompt=f"分式方程 {aa}/x = {bb} 的解是 x = （　）。",
               answer=num(x0), verify=f"{aa}/{bb}",
               explanation=f"两边同乘 x 得 {aa} = {bb}x，所以 x = {x0}；检验分母不为 0。")

    a1, a2 = rng.randint(30, 80), rng.randint(30, 70)
    if a1 + a2 >= 170:
        a2 = 170 - a1
    yield dict(topic=5, difficulty="basic", type="numeric",
               prompt=f"在△ABC 中，∠A = {a1}°，∠B = {a2}°，则∠C = （　）°。",
               answer=num(180 - a1 - a2), verify=f"180-{a1}-{a2}",
               explanation=f"三角形内角和为 180°，所以∠C = 180° - {a1}° - {a2}° = {180 - a1 - a2}°。")

    a, b = rng.randint(3, 12), rng.randint(4, 15)
    yield dict(topic=2, difficulty="basic", type="numeric",
               prompt=f"平行四边形相邻两边的长分别为 {a} cm 和 {b} cm，它的周长是（　）cm。",
               answer=num(2 * (a + b)), verify=f"2*({a}+{b})",
               explanation=f"平行四边形对边相等，周长 = 2×({a} + {b}) = {2 * (a + b)} cm。")

    nums = sorted(rng.sample(range(60, 101), 5))
    yield dict(topic=4, difficulty="standard", type="numeric",
               prompt=f"一组数据 {'、'.join(str(n) for n in nums)} 的中位数是（　）。",
               answer=num(nums[2]), verify=f"median([{','.join(str(n) for n in nums)}])",
               explanation=f"数据已按从小到大排列，共 5 个数，中位数是第 3 个数 {nums[2]}。")


def math_g9(rng: random.Random):
    p, q = rng.sample(range(-7, 8), 2)
    b = -(p + q)
    c = p * q
    yield dict(topic=0, difficulty="standard", type="numeric", unordered=True,
               prompt=f"方程 x²{xterm(b)}{cterm(c)} = 0 的解是（　）。",
               answer=f"{min(p, q)}，{max(p, q)}", verify=f"roots2(1,{b},{c})",
               explanation=f"因式分解得 {factor(p)}{factor(q)} = 0，所以 x₁ = {p}，x₂ = {q}。")

    a = rng.choice([1, 2, 3, -1])
    h = rng.randint(-6, 6)
    k = rng.randint(-15, 15)
    bb = -2 * a * h
    cc = a * h * h + k
    head = "x²" if a == 1 else ("-x²" if a == -1 else f"{a}x²")
    ask = "最小值" if a > 0 else "最大值"
    yield dict(topic=1, difficulty="advanced", type="numeric",
               prompt=f"二次函数 y = {head}{xterm(bb)}{cterm(cc)} 的{ask}是（　）。",
               answer=num(k), verify=f"({cc})-({bb})**2/(4*({a}))",
               explanation=f"配方得 y = {a}(x - {h})² + {k}，"
                           + ("所以最小值是 " if a > 0 else "所以最大值是 ") + f"{k}。")

    x0 = rng.choice([1, 2, 3, 4, 5, 6, -1, -2, -3, -4, -5, -6])
    y0 = rng.randint(2, 15)
    kk = x0 * y0
    yield dict(topic=5, difficulty="standard", type="numeric",
               prompt=f"反比例函数 y = k/x 的图象经过点 ({x0}, {y0})，则 k = （　）。",
               answer=num(kk), verify=f"{x0}*{y0}",
               explanation=f"把点坐标代入得 k = xy = {x0}×{y0} = {kk}。")

    d = 2 * rng.randint(10, 89)
    yield dict(topic=3, difficulty="standard", type="numeric",
               prompt=f"在⊙O 中，一条弧所对的圆心角是 {d}°，则它所对的圆周角是（　）°。",
               answer=num(d // 2), verify=f"{d}/2",
               explanation=f"同弧所对的圆周角等于圆心角的一半，即 {d}° ÷ 2 = {d // 2}°。")

    m, n = rng.choice([(1, 2), (2, 3), (3, 4), (2, 5), (3, 5), (4, 5), (1, 3), (3, 7)])
    small = m * rng.randint(1, 12)
    large = n * (small // m)
    yield dict(topic=6, difficulty="advanced", type="numeric",
               prompt=f"两个相似三角形的相似比是 {m}∶{n}，较小三角形的一边长为 {small}，"
                      f"则较大三角形对应边的长是（　）。",
               answer=num(large), verify=f"{small}*{n}/{m}",
               explanation=f"相似三角形对应边成比例，较大三角形的对应边 = {small} × {n}/{m} = {large}。")

    r = rng.randint(2, 10)
    w = rng.randint(2, 12)
    g = Fraction(r, r + w)
    yield dict(topic=4, difficulty="standard", type="numeric",
               prompt=f"一个不透明的袋子里有 {r} 个红球和 {w} 个白球，它们除颜色外都相同。"
                      f"从中任意摸出一个球，摸到红球的概率是（　）。",
               answer=frac_str(g), verify=f"Fraction({r},{r + w})",
               explanation=f"共有 {r + w} 个球，其中红球 {r} 个，概率 = {frac_str(g)}。")

    k1, k2, k3 = rng.randint(1, 4), rng.randint(1, 4), rng.randint(1, 4)
    val = Fraction(k1, 2) + Fraction(k2, 2) + k3
    yield dict(topic=7, difficulty="basic", type="numeric",
               prompt=f"计算：{k1}sin30° + {k2}cos60° + {k3}tan45° = （　）。",
               answer=num(val),
               verify=f"{k1}*sin(pi/6)+{k2}*cos(pi/3)+{k3}*tan(pi/4)",
               explanation=f"sin30° = 1/2，cos60° = 1/2，tan45° = 1，"
                           f"所以原式 = {num(Fraction(k1, 2))} + {num(Fraction(k2, 2))} + {k3} = {num(val)}。")


def math_items(pidx: int, rng: random.Random):
    out = []
    for gen, grade in ((math_g7, 7), (math_g8, 8), (math_g9, 9)):
        for it in gen(rng):
            it["grade"] = grade
            out.append(it)
    return out


# ------------------------------------------------------------------ 物理
def physics_g8(rng: random.Random):
    s, t = rng.randint(100, 900), rng.randint(10, 30)
    yield dict(topic=0, difficulty="basic", type="numeric",
               prompt=f"一辆汽车在 {t} s 内行驶了 {s} m，它的平均速度是（　）m/s。",
               answer=num(Fraction(s, t)), verify=f"{s}/{t}",
               explanation=f"v = s/t = {s} m ÷ {t} s = {num(Fraction(s, t))} m/s。")

    rho = rng.choice([1, 1.5, 2, 2.5, 2.7, 3, 4, 5, 7.8, 7.9, 8.9])
    V = rng.randrange(100, 401, 50)
    m = rho * V
    mtxt = num(m)
    yield dict(topic=5, difficulty="standard", type="numeric",
               prompt=f"某物体的质量是 {mtxt} g，体积是 {V} cm³，它的密度是（　）g/cm³。",
               answer=num(rho), verify=f"{mtxt}/{V}",
               explanation=f"ρ = m/V = {mtxt} g ÷ {V} cm³ = {num(rho)} g/cm³。")

    F, S = rng.randint(20, 200), rng.randint(2, 20)
    yield dict(topic=7, difficulty="standard", type="numeric",
               prompt=f"一个物体对地面的压力是 {F} N，受力面积是 {S} cm²，它对地面的压强是（　）Pa。",
               answer=num(Fraction(F, S) * 10000), verify=f"{F}/({S}/10000)",
               explanation=f"S = {S} cm² = {num(Fraction(S, 10000))} m²，"
                           f"p = F/S = {F} ÷ {num(Fraction(S, 10000))} = {num(Fraction(F, S) * 10000)} Pa。")

    V = rng.randint(2, 50) / 10
    Fb = 1000 * 10 * V
    yield dict(topic=8, difficulty="standard", type="numeric",
               prompt=f"一个体积为 {num(V)} m³ 的物体全部浸没在水中，它受到的浮力是（　）N。"
                      f"（ρ水 = 1.0×10³ kg/m³，g 取 10 N/kg）",
               answer=num(Fb), verify=f"1000*10*{V}",
               explanation=f"F浮 = ρ水gV排 = 1000 × 10 × {num(V)} = {num(Fb)} N。")

    a = rng.randint(10, 79)
    yield dict(topic=3, difficulty="basic", type="numeric",
               prompt=f"一束光射到平面镜上，入射光线与镜面的夹角是 {a}°，则反射角是（　）°。",
               answer=num(90 - a), verify=f"90-{a}",
               explanation=f"入射角 = 90° - {a}° = {90 - a}°，反射角等于入射角，也是 {90 - a}°。")

    F2, L1, L2 = rng.randint(20, 80), rng.randint(2, 6), rng.randint(1, 5)
    yield dict(topic=10, difficulty="advanced", type="numeric",
               prompt=f"杠杆平衡时，阻力是 {F2} N，阻力臂是 {L2} m，动力臂是 {L1} m，则动力是（　）N。",
               answer=num(Fraction(F2 * L2, L1)), verify=f"{F2}*{L2}/{L1}",
               explanation=f"由 F₁L₁ = F₂L₂ 得 F₁ = {F2}×{L2} ÷ {L1} = {num(Fraction(F2 * L2, L1))} N。")


def physics_g9(rng: random.Random):
    U, R = rng.randint(2, 24), rng.randint(2, 40)
    yield dict(topic=3, difficulty="standard", type="numeric",
               prompt=f"一段导体两端的电压是 {U} V，电阻是 {R} Ω，通过它的电流是（　）A。",
               answer=num(Fraction(U, R)), verify=f"{U}/{R}",
               explanation=f"由 I = U/R 得 I = {U} V ÷ {R} Ω = {num(Fraction(U, R))} A。")

    U, I = rng.choice([3, 6, 9, 12, 18, 24, 36, 48, 110, 220]), rng.choice([0.2, 0.4, 0.5, 0.8, 1, 1.2, 1.5, 2, 2.5, 3, 4, 5])
    yield dict(topic=4, difficulty="standard", type="numeric",
               prompt=f"一个用电器两端的电压是 {U} V，通过的电流是 {num(I)} A，它的电功率是（　）W。",
               answer=num(U * I), verify=f"{U}*{I}",
               explanation=f"P = UI = {U} × {num(I)} = {num(U * I)} W。")

    P, t = rng.randint(1, 30) / 10, rng.randint(1, 8)
    yield dict(topic=4, difficulty="basic", type="numeric",
               prompt=f"一台功率为 {num(P)} kW 的电器工作 {t} h，消耗的电能是（　）kW·h。",
               answer=num(P * t), verify=f"{P}*{t}",
               explanation=f"W = Pt = {num(P)} kW × {t} h = {num(P * t)} kW·h。")

    m = rng.randint(1, 6)
    dt = rng.choice([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80])
    yield dict(topic=0, difficulty="advanced", type="numeric",
               prompt=f"质量为 {m} kg 的水温度升高 {dt} ℃，吸收的热量是（　）J。"
                      f"（水的比热容取 4.2×10³ J/(kg·℃)）",
               answer=num(4200 * m * dt), verify=f"4200*{m}*{dt}",
               explanation=f"Q = cmΔt = 4200 × {m} × {dt} = {4200 * m * dt} J。")

    R1, R2 = rng.randint(2, 30), rng.randint(2, 30)
    yield dict(topic=2, difficulty="basic", type="numeric",
               prompt=f"两个电阻 R₁ = {R1} Ω、R₂ = {R2} Ω 串联接入电路，总电阻是（　）Ω。",
               answer=num(R1 + R2), verify=f"{R1}+{R2}",
               explanation=f"串联电路总电阻等于各电阻之和：R = {R1} + {R2} = {R1 + R2} Ω。")

    G, h, F, s = rng.randint(40, 90), rng.choice([1, 2]), rng.randint(20, 60), rng.choice([2, 3, 4])
    eta = Fraction(G * h, F * s) * 100
    yield dict(topic=5, difficulty="advanced", type="numeric",
               prompt=f"用滑轮组把重 {G} N 的物体匀速提高 {num(h)} m，拉力为 {F} N，"
                      f"绳子自由端移动 {num(s)} m，该滑轮组的机械效率是（　）%。",
               answer=num(eta), verify=f"{G}*{h}/({F}*{s})*100",
               explanation=f"W有 = Gh = {G}×{num(h)} = {num(G * h)} J，"
                           f"W总 = Fs = {F}×{num(s)} = {num(F * s)} J，"
                           f"η = W有/W总 = {num(eta)}%。")


def physics_items(pidx: int, rng: random.Random):
    out = []
    for gen, grade in ((physics_g8, 8), (physics_g9, 9)):
        for it in gen(rng):
            it["grade"] = grade
            out.append(it)
    return out


# ------------------------------------------------------------------ 化学
FORMULAS = [
    ("H₂O", 18, "H-1，O-16", "2*1+16"),
    ("CO₂", 44, "C-12，O-16", "12+2*16"),
    ("NaCl", 58.5, "Na-23，Cl-35.5", "23+35.5"),
    ("CaCO₃", 100, "Ca-40，C-12，O-16", "40+12+3*16"),
    ("H₂SO₄", 98, "H-1，S-32，O-16", "2*1+32+4*16"),
    ("NaOH", 40, "Na-23，O-16，H-1", "23+16+1"),
    ("CuSO₄", 160, "Cu-64，S-32，O-16", "64+32+4*16"),
    ("KMnO₄", 158, "K-39，Mn-55，O-16", "39+55+4*16"),
    ("C₆H₁₂O₆", 180, "C-12，H-1，O-16", "6*12+12*1+6*16"),
    ("Fe₂O₃", 160, "Fe-56，O-16", "2*56+3*16"),
    ("Ca(OH)₂", 74, "Ca-40，O-16，H-1", "40+2*(16+1)"),
    ("KNO₃", 101, "K-39，N-14，O-16", "39+14+3*16"),
    ("HCl", 36.5, "H-1，Cl-35.5", "1+35.5"),
    ("O₂", 32, "O-16", "2*16"),
    ("N₂", 28, "N-14", "2*14"),
    ("NH₃", 17, "N-14，H-1", "14+3*1"),
    ("CH₄", 16, "C-12，H-1", "12+4*1"),
    ("Na₂CO₃", 106, "Na-23，C-12，O-16", "2*23+12+3*16"),
    ("NaHCO₃", 84, "Na-23，H-1，C-12，O-16", "23+1+12+3*16"),
    ("KClO₃", 122.5, "K-39，Cl-35.5，O-16", "39+35.5+3*16"),
    ("CuO", 80, "Cu-64，O-16", "64+16"),
    ("SO₂", 64, "S-32，O-16", "32+2*16"),
    ("H₂O₂", 34, "H-1，O-16", "2*1+2*16"),
    ("C₂H₅OH", 46, "C-12，H-1，O-16", "2*12+6*1+16"),
    ("CH₃COOH", 60, "C-12，H-1，O-16", "2*12+4*1+2*16"),
    ("Mg(OH)₂", 58, "Mg-24，O-16，H-1", "24+2*(16+1)"),
    ("Al₂O₃", 102, "Al-27，O-16", "2*27+3*16"),
    ("MgO", 40, "Mg-24，O-16", "24+16"),
    ("Fe₃O₄", 232, "Fe-56，O-16", "3*56+4*16"),
]


def chemistry_g9(rng: random.Random):
    formula, mr, rel, expr = rng.choice(FORMULAS)
    coef = rng.choice([1, 2, 3])
    total = Fraction(mr) * coef
    head = "" if coef == 1 else f"{coef}"
    what = "相对分子质量" if coef == 1 else "相对分子质量之和"
    yield dict(topic=3, difficulty="basic" if coef == 1 else "standard", type="numeric",
               prompt=f"{head}{formula} 的{what}是（　）。（相对原子质量：{rel}）",
               answer=num(total), verify=f"({expr})*{coef}",
               explanation=f"{formula} 的相对分子质量为 {num(Fraction(mr))}，"
                           f"乘以系数 {coef} 得 {num(total)}。")

    ms, mw = rng.randint(10, 60), rng.randint(40, 200)
    w = Fraction(ms, ms + mw) * 100
    yield dict(topic=8, difficulty="standard", type="numeric",
               prompt=f"把 {ms} g 食盐完全溶解在 {mw} g 水中，所得溶液的溶质质量分数是（　）%。",
               answer=num(w), verify=f"{ms}/({ms}+{mw})*100",
               explanation=f"溶质质量分数 = {ms} ÷ ({ms} + {mw}) × 100% = {num(w)}%。")

    m1, c1 = rng.randrange(100, 501, 50), rng.randrange(10, 61, 5)
    c2 = rng.choice([c for c in range(5, c1, 5)] or [c1 // 2])
    add = Fraction(m1 * c1, c2) - m1
    yield dict(topic=8, difficulty="advanced", type="numeric",
               prompt=f"要把 {m1} g 溶质质量分数为 {c1}% 的溶液稀释成 {c2}%，需要加水（　）g。",
               answer=num(add), verify=f"{m1}*{c1}/{c2}-{m1}",
               explanation=f"稀释前后溶质质量不变：{m1}×{c1}% = x×{c2}%，得 x = {num(Fraction(m1 * c1, c2))} g，"
                           f"需加水 {num(add)} g。")

    mc = rng.randrange(50, 1501, 25)
    cao = Fraction(mc * 56, 100)
    yield dict(topic=4, difficulty="advanced", type="numeric",
               prompt=f"高温煅烧 {mc} g 碳酸钙，可以得到氧化钙（　）g。",
               answer=num(cao), verify=f"{mc}*56/100",
               explanation=f"CaCO₃ →(高温) CaO + CO₂↑，设生成氧化钙 x g："
                           f"{mc}/100 = x/56，得 x = {num(cao)} g。")


def chemistry_items(pidx: int, rng: random.Random):
    out = []
    for it in chemistry_g9(rng):
        it["grade"] = 9
        out.append(it)
    return out


# ------------------------------------------------------------------ 文科
def cn_items(rng: random.Random):
    """语文：名句默写（short）、文学常识（choice）、成语（choice）。"""
    out = []
    for idx, (grade, up, down, src) in enumerate(POEMS):
        accepts = [down, down.replace("，", ","), down.replace("，", ""), down.replace("，", "；")]
        out.append(dict(
            grade=grade, topic=idx % 2, difficulty="standard", type="short",
            prompt=f"补写古诗文名句：「{up}，______。」（{src}）",
            answer=down, accept=[a for a in accepts if a != down],
            verify=repr(down),
            explanation=f"出自{src}，原句是「{up}，{down}」。",
        ))

    authors = sorted({a for _, _, a, _ in LITERATURE})
    for grade, work, author, dynasty in LITERATURE:
        pool = [a for a in authors if a != author]
        rng.shuffle(pool)
        out.append(dict(
            grade=grade, topic=2, difficulty="standard", type="choice",
            prompt=f"《{work}》的作者是（　）。",
            correct=author, distractors=pool[:3], verify=repr(author),
            explanation=f"《{work}》的作者是{author}（{dynasty}）。",
        ))

    idioms = sorted({i for _, i, _ in IDIOMS})
    for grade, idiom, meaning in IDIOMS:
        pool = [i for i in idioms if i != idiom]
        rng.shuffle(pool)
        out.append(dict(
            grade=grade, topic=3, difficulty="standard", type="choice",
            prompt=f"下列成语中，意思是「{meaning}」的是（　）。",
            correct=idiom, distractors=pool[:3], verify=repr(idiom),
            explanation=f"「{idiom}」的意思是{meaning}。",
        ))
    return out


VERB_PAST = [
    ("go", "went", "上周日我去了公园。", "Last Sunday I ____ to the park."),
    ("see", "saw", "昨天我在街上看见了他。", "I ____ him in the street yesterday."),
    ("buy", "bought", "她昨天买了一本词典。", "She ____ a dictionary yesterday."),
    ("take", "took", "他昨天花了两小时做作业。", "It ____ him two hours to finish his homework yesterday."),
    ("eat", "ate", "我们昨天中午吃了面条。", "We ____ noodles for lunch yesterday."),
    ("write", "wrote", "他昨晚给母亲写了一封信。", "He ____ a letter to his mother last night."),
    ("give", "gave", "老师昨天给了我一本新书。", "The teacher ____ me a new book yesterday."),
    ("come", "came", "他昨天来得很早。", "He ____ very early yesterday."),
]

VERB_THIRD = [
    ("go", "goes", "他每天骑自行车上学。", "He ____ to school by bike every day."),
    ("study", "studies", "她每天晚上学习英语。", "She ____ English every evening."),
    ("watch", "watches", "我弟弟每天晚上看电视。", "My brother ____ TV every evening."),
    ("do", "does", "他每天下午做运动。", "He ____ sports every afternoon."),
    ("have", "has", "她每天七点吃早饭。", "She ____ breakfast at seven every day."),
    ("carry", "carries", "他每天背着书包上学。", "He ____ a schoolbag to school every day."),
]

ADJ_CMP = [
    ("big", "bigger", "我的书包比你的大。", "My schoolbag is ____ than yours."),
    ("easy", "easier", "这道题比那道题容易。", "This question is ____ than that one."),
    ("hot", "hotter", "今天比昨天热。", "It is ____ today than yesterday."),
    ("careful", "more careful", "他比我细心。", "He is ____ than me."),
    ("popular", "more popular", "这首歌比那首流行。", "This song is ____ than that one."),
]


def english_extra(rng: random.Random):
    """按词表扩充英语题，避免英语题量偏少。"""
    out = []
    for base, past, zh, sent in VERB_PAST:
        options = [past, base, base + "ed" if not base.endswith("e") else base + "d", "has " + past]
        out.append(dict(grade=8, topic=0, difficulty="standard", type="choice",
                        prompt=sent + f"（{zh}）",
                        correct=past, distractors=options[1:], verify=repr(past),
                        explanation=f"yesterday / last 等过去时间状语，用一般过去时，{base} 的过去式是 {past}。"))
    for base, third, zh, sent in VERB_THIRD:
        out.append(dict(grade=7, topic=1, difficulty="basic", type="choice",
                        prompt=sent + f"（{zh}）",
                        correct=third, distractors=[base, base + "ing", "to " + base],
                        verify=repr(third),
                        explanation=f"every day 表示一般现在时，主语第三人称单数，动词用 {third}。"))
    for base, cmp_, zh, sent in ADJ_CMP:
        out.append(dict(grade=8, topic=1, difficulty="standard", type="choice",
                        prompt=sent + f"（{zh}）",
                        correct=cmp_, distractors=[base, "more " + base if "more" not in cmp_ else base + "est", "the " + base],
                        verify=repr(cmp_),
                        explanation=f"than 提示比较级，{base} 的比较级是 {cmp_}。"))
    return out


def geo_admin_items():
    """省会题 + 简称题，由省份表派生。"""
    out = []
    capitals = {
        "北京": "北京", "天津": "天津", "河北": "石家庄", "山西": "太原", "内蒙古": "呼和浩特",
        "辽宁": "沈阳", "吉林": "长春", "黑龙江": "哈尔滨", "上海": "上海", "江苏": "南京",
        "浙江": "杭州", "安徽": "合肥", "福建": "福州", "江西": "南昌", "山东": "济南",
        "河南": "郑州", "湖北": "武汉", "湖南": "长沙", "广东": "广州", "广西": "南宁",
        "海南": "海口", "重庆": "重庆", "四川": "成都", "贵州": "贵阳", "云南": "昆明",
        "西藏": "拉萨", "陕西": "西安", "甘肃": "兰州", "青海": "西宁", "宁夏": "银川",
        "新疆": "乌鲁木齐",
    }
    all_caps = sorted(set(capitals.values()))
    kinds = {p[1]: p[2] for p in PROVINCES}
    for name, cap in capitals.items():
        if kinds.get(name) == "直辖市":
            continue
        others = [c for c in all_caps if c != cap][:24]
        rng = random.Random(stable(name, "cap"))
        rng.shuffle(others)
        label = "首府" if kinds.get(name) == "自治区" else "省会"
        out.append(dict(grade=8, topic=0, difficulty="basic", type="choice",
                        prompt=f"{name}的{label}是（　）。",
                        correct=cap, distractors=others[:3], verify=repr(cap),
                        explanation=f"{name}的行政中心是{cap}。"))
    short_of = {p[1]: p[3] for p in PROVINCES}
    all_short = sorted(set(short_of.values()))
    for name, short in short_of.items():
        rng = random.Random(stable(name, "short"))
        others = [s for s in all_short if s != short]
        rng.shuffle(others)
        out.append(dict(grade=8, topic=0, difficulty="basic", type="choice",
                        prompt=f"{name}的简称是（　）。",
                        correct=short, distractors=others[:3], verify=repr(short),
                        explanation=f"{name}的简称是{short}。"))
    return out


def table_items(rows, subject: str, rng: random.Random, grade_topic_fallback=0):
    out = []
    for grade, tidx, stem, correct, distractors, expl in rows:
        out.append(dict(grade=grade, topic=tidx, difficulty="standard", type="choice",
                        prompt=stem, correct=correct, distractors=distractors,
                        verify=repr(correct), explanation=expl))
    return out


# ------------------------------------------------------------------ 组装
def assign_regions(items: list[dict], province: str, seed: int) -> list[dict]:
    """把一批题按顺序分给各省，尽量让每个省都拿到不同年级的题。"""
    for it in items:
        it["region"] = province
    return items


def main() -> int:
    topics = build_topics()
    topic_ids = {t["id"]: t for t in topics}

    rng = random.Random(20261111)
    questions: list[dict] = []
    counters: dict[str, int] = {}
    seen_prompts: set[str] = set()
    skipped = [0]

    def nonlocal_skip():
        skipped[0] += 1

    def add(meta: dict, region: str):
        tid = topic_id(meta["subject"], meta["grade"], min(meta["topic"], 99))
        tinfo = topic_ids.get(tid)
        if tinfo is None:  # 该年级没有这么多知识点，落到最后一个
            same = [t for t in topics if t["subject"] == meta["subject"] and t["grade"] == meta["grade"]]
            tinfo = same[-1]
            tid = tinfo["id"]
        if meta["prompt"] in seen_prompts:  # 题干重复直接跳过，宁可少一题也不出重题
            nonlocal_skip()
            return
        seen_prompts.add(meta["prompt"])
        counters[tid] = counters.get(tid, 0) + 1
        item = {
            "id": f"{tid}_q{counters[tid]}",
            "topicId": tid,
            "difficulty": meta["difficulty"],
            "type": meta["type"],
            "prompt": meta["prompt"],
            "answer": "",
            "explanation": meta["explanation"],
            "region": region,
            "semester": tinfo.get("semester", ""),
            "source": "中考仿真题",
        }
        if meta["type"] == "choice":
            built = build_choice(rng, meta["correct"], meta["distractors"])
            if built is None:
                counters[tid] -= 1
                return
            item["choices"], item["answer"] = built
        else:
            item["answer"] = meta["answer"]
            if meta.get("accept"):
                item["accept"] = meta["accept"]
            if meta.get("unordered"):
                item["unordered"] = True
        if meta.get("verify"):
            item["verify"] = meta["verify"]
        questions.append(item)

    # 理科：每个省一套，参数随省份变化
    for i, (pid, name, kind, _short) in enumerate(PROVINCES):
        chosen: list[dict] | None = None
        for attempt in range(40):
            r2 = random.Random(1000 + i * 131 + attempt * 17)
            cand: list[dict] = []
            for meta in math_items(i, r2):
                meta["subject"] = "math"
                cand.append(meta)
            for meta in physics_items(i, r2):
                meta["subject"] = "physics"
                cand.append(meta)
            for meta in chemistry_items(i, r2):
                meta["subject"] = "chemistry"
                cand.append(meta)
            texts = [m["prompt"] for m in cand]
            if len(set(texts)) == len(texts) and not (set(texts) & seen_prompts):
                chosen = cand
                break
        if chosen is None:  # 四十次都没排重成功，仍然入库，避免整省缺失
            chosen = cand
        for meta in chosen:
            add(meta, name)

    # 文科：题目总量少于省份数 × 科目，按顺序轮转分配省份
    human: list[tuple[str, list[dict]]] = [
        ("chinese", cn_items(random.Random(7))),
        ("english", [dict(grade=g, topic=t, difficulty="standard", type="choice", prompt=p,
                          correct=c, distractors=ds, verify=repr(c), explanation=e)
                     for g, t, p, c, ds, e in ENGLISH] + english_extra(random.Random(11))),
        ("history", [dict(grade=g, topic=t, difficulty="standard", type="choice", prompt=p,
                          correct=c, distractors=ds, verify=repr(c), explanation=e)
                     for g, t, p, c, ds, e in HISTORY]),
        ("geography", [dict(grade=g, topic=t, difficulty="standard", type="choice", prompt=p,
                            correct=c, distractors=ds, verify=repr(c), explanation=e)
                       for g, t, p, c, ds, e in GEOGRAPHY] + geo_admin_items()),
        ("biology", [dict(grade=g, topic=t, difficulty="standard", type="choice", prompt=p,
                          correct=c, distractors=ds, verify=repr(c), explanation=e)
                     for g, t, p, c, ds, e in BIOLOGY]),
        ("morality", [dict(grade=g, topic=t, difficulty="standard", type="choice", prompt=p,
                           correct=c, distractors=ds, verify=repr(c), explanation=e)
                      for g, t, p, c, ds, e in MORALITY]),
    ]

    for subject, items in human:
        random.Random(stable(subject)).shuffle(items)
        items.sort(key=lambda d: d["grade"])
        for j, meta in enumerate(items):
            meta["subject"] = subject
            add(meta, PROVINCE_NAMES[j % len(PROVINCE_NAMES)])

    # 写盘
    TOPICS_PATH.write_text(json.dumps(topics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    QUESTIONS_PATH.write_text(json.dumps(questions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 根目录 q.json 是 questions.json 的副本，供手机/电视 App 用更短的地址取数据，勿手改
    ROOT_Q_PATH.write_text(QUESTIONS_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    regions = [{
        "id": pid,
        "name": name,
        "type": kind,
        "short": short,
        "subjects": ["chinese", "math", "english", "physics", "chemistry",
                     "biology", "history", "geography", "morality"],
        "note": "地理、生物一般在八年级结业考试，成绩计入中考的方式各省不同；"
                "本库按知识点所属年级归类，供按年级刷题使用。",
    } for pid, name, kind, short in PROVINCES]
    REGIONS_PATH.write_text(json.dumps(regions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"知识点 {len(topics)} 个，题目 {len(questions)} 道，省份 {len(regions)} 个"
          + (f"，因题干重复跳过 {skipped[0]} 道" if skipped[0] else ""))
    import collections
    print("  按学科：" + "，".join(f"{k} {v}" for k, v in collections.Counter(
        topic_ids[q["topicId"]]["subject"] for q in questions).most_common()))
    print("  按年级：" + "，".join(f"{k} {v}" for k, v in sorted(collections.Counter(
        topic_ids[q["topicId"]]["grade"] for q in questions).items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
