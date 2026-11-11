# 题库格式说明

三个文件：`data/questions.json`（题目）、`data/topics.json`（知识点）、`data/regions.json`（省级行政区）。
都是 UTF-8、无 BOM 的 JSON；`questions.json` 顶层是数组，一个对象一道题。

知识点 id 的规则是 `zk_<学科>_g<年级>_<序号>`，例如：

- `zk_math_g9_01` —— 数学 · 九年级 · 一元二次方程
- `zk_physics_g8_05` —— 物理 · 八年级 · 质量与密度
- `zk_chinese_g7_01` —— 语文 · 七年级 · 名句默写

年级和学科由知识点决定，题目不必重复写；`region` 写省份，练习页的「地区」筛选读它。

## 一、questions.json 的字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 必须是 `<topicId>_q<N>`，如 `zk_math_g9_01_q3`。脚本按此规则自动生成，不要手写别的格式 |
| `topicId` | 是 | 所属知识点 id，必须存在于 `topics.json`；学科和年级都由它决定 |
| `region` | 否 | 省份名，如 `江苏`、`内蒙古`。练习页的地区下拉靠它筛题 |
| `difficulty` | 是 | `basic`（直接套定义 / 一步计算）、`standard`（课本例题，2–3 步）、`advanced`（综合、多步、易错）、`challenge`（超纲或竞赛味） |
| `type` | 是 | `numeric` 数值题、`choice` 选择题、`short` 短答题、`self` 开放题（自评） |
| `prompt` | 是 | 题干。**必须自包含**：不写「如上图」「同上题」，几何条件用文字写全 |
| `answer` | 是 | 一律字符串。numeric 填一个数（整数 / 小数 / 分数 `a/b` / 负数），多解用全角「，」分隔；choice 填选项字母；short 填标准短答；self 填参考答案 |
| `explanation` | 是 | 1–3 句中文解析，答题后显示 |
| `choices` | choice 必填 | `[{"key":"A","text":"…"}, …]`，3–4 个，key 依次 A、B、C、D，文字不能重复 |
| `figure` | 否 | 题干配图，**内联 SVG 字符串**，只写 `viewBox`，颜色用 `currentColor`，不引用外网图片 |
| `hideChoiceText` | 否 | 仅选择题。每个选项都有 `figure` 时设为 `true`，页面上只画图不显示文字（防泄题） |
| `accept` | 否 | short（也可给 numeric）的等价答案数组，如 `["三十六","36"]` |
| `verify` | 否 | 一条 Python 表达式，用来自动核验 `answer`，见下文 |
| `unordered` | 否 | numeric 多答案且顺序无关时设 `true`（如方程的两个根） |
| `tags` / `source` / `note` | 否 | 自用扩展字段：标签、出处（教材/试卷）、备注 |

选择题的选项也可以带 `figure`（同上规则）。写得越像「几个图形选一个」，越要配 `hideChoiceText`。

生成器写出的题统一带 `"source": "中考仿真题"`：这是按中考题型和教材知识点编写的仿真题，**不是原卷真题**，`region` 只表示归在哪个省下练习。自己手写的题可以不写 `source`。

## 二、四种题型的完整示例

**numeric**

```json
{
  "id": "zk_math_g8_02_q1",
  "topicId": "zk_math_g8_02",
  "region": "江苏",
  "source": "中考仿真题",
  "difficulty": "basic",
  "type": "numeric",
  "prompt": "直角三角形的两条直角边分别是 3 和 4，斜边长是（　）。",
  "answer": "5",
  "explanation": "由勾股定理，斜边² = 3² + 4² = 25，所以斜边 = 5。",
  "verify": "sqrt(3**2+4**2)"
}
```

**choice**

```json
{
  "id": "zk_morality_g8_01_q5",
  "topicId": "zk_morality_g8_01",
  "region": "浙江",
  "source": "中考仿真题",
  "difficulty": "standard",
  "type": "choice",
  "prompt": "我国的最高国家权力机关是（　）。",
  "choices": [
    {"key": "A", "text": "国务院"},
    {"key": "B", "text": "全国人民代表大会"},
    {"key": "C", "text": "最高人民法院"},
    {"key": "D", "text": "最高人民检察院"}
  ],
  "answer": "B",
  "explanation": "全国人民代表大会是我国最高国家权力机关。",
  "verify": "'全国人民代表大会'"
}
```

**short**（答案可以有多种写法）

```json
{
  "id": "zk_chinese_g8_01_q7",
  "topicId": "zk_chinese_g8_01",
  "region": "广东",
  "source": "中考仿真题",
  "difficulty": "standard",
  "type": "short",
  "prompt": "补写古诗文名句：「大漠孤烟直，______。」（《使至塞上》王维）",
  "answer": "长河落日圆",
  "accept": ["长河落日圆。"],
  "explanation": "出自《使至塞上》王维，原句是「大漠孤烟直，长河落日圆」。"
}
```

**self**（开放题，页面上自评）

```json
{
  "id": "zk_math_g7_01_q9",
  "topicId": "zk_math_g7_01",
  "difficulty": "standard",
  "type": "self",
  "prompt": "用「春」组一个词语，再用这个词语写一句完整的话。",
  "answer": "参考答案：春天。春天来了，小草绿了。",
  "explanation": "答案不唯一，看是否成词、句子是否完整。"
}
```

## 三、verify 怎么写

`verify` 是给机器看的「解题过程」，`scripts/verify_questions.py` 会在受限环境里求值，再和 `answer` 比。

能用的东西：

- 运算：`+ - * / // % **`、比较、`and / or / not`、条件表达式
- 常量与函数：`Fraction`、`sqrt`、`pi`、`e`、`sin cos tan`、`log`、`comb`、`perm`、`gcd`、`lcm`、`ceil`、`floor`、`abs`、`round`、`min`、`max`、`sum`、`sorted`、`len`、`range`
- 统计：`mean`、`median`、`pvariance`（除以 n 的方差，题目里要写明口径）
- 两个专用函数：
  - `solve2(a1,b1,c1,a2,b2,c2)`：解 `a1x+b1y=c1`、`a2x+b2y=c2`，返回精确分数 `(x, y)`
  - `roots2(a,b,c)`：解 `ax²+bx+c=0`，返回排序后的实根元组，无实根时返回 `()`

不能用：`import`、属性访问（`x.real`）、赋值、lambda、推导式。

比对规则：

- **numeric**：求值结果和 `answer` 逐项比。整数与分数**精确比**，浮点容差 1e-9。多答案时按 `unordered` 决定顺序是否要紧。
- **choice**：求值结果和**正确选项的文字**比（选项是数就按数值比，否则要求文字完全一致），同时要求没有第二个选项等于它——防止两个选项都对。
- **short**：结果等于 `answer` 或 `accept` 里任意一项才算通过。

所以：

- 答案是数 → 写算式：`"(6+4)*2"`、`"Fraction(1,4)"`、`"sqrt(13**2-5**2)"`、`"2**5"`
- 答案是选项文字 → 写成字符串：`"'15'"`、`"'长方形'"`
- 心里没底、只是推理题 → 不写 `verify`，让脚本算「无法核验」，别硬凑

## 四、topics.json 与 regions.json

```json
{
  "id": "zk_math_g9_01",
  "name": "一元二次方程",
  "subject": "math",
  "grade": 9,
  "semester": "",
  "chapter": "第二十一章 一元二次方程",
  "type": "conceptual"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | `zk_<学科>_g<年级>_<两位序号>`，如 `zk_math_g9_01` |
| `name` | 是 | 知识点名称 |
| `subject` | 是 | `math` / `chinese` / `english` / `physics` / `chemistry` / `biology` / `history` / `geography` / `morality` |
| `grade` | 是 | `7` / `8` / `9`，练习页的年级筛选读它 |
| `chapter` | 否 | 教材章节 |
| `semester` | 否 | `上` / `下`，本库暂未填 |
| `type` | 否 | `conceptual` 概念 / `procedural` 方法 / `strategic` 综合 |

题目不写年级和学科，全部由 `topicId` 决定，避免两处填写不一致。

`regions.json` 一共 31 条，一条一个省级行政区：

```json
{
  "id": "jiangsu",
  "name": "江苏",
  "type": "省",
  "short": "苏",
  "subjects": ["chinese", "math", "english", "physics", "chemistry",
               "biology", "history", "geography", "morality"],
  "note": "地理、生物一般在八年级结业考试，成绩计入中考的方式各省不同；本库按知识点所属年级归类，供按年级刷题使用。"
}
```

`name` 与题目里的 `region` 一一对应；练习页的地区下拉是按 `questions.json` 里出现过的 `region` 生成的，改 `regions.json` 不会立刻影响页面。

## 五、校验规则

`python scripts/validate.py` 会检查：id 唯一且与 topicId 对应、topicId 存在且不是 external、difficulty / type 合法、必填字段非空、没有拼错的未知字段、选择题选项 3–4 个且 key 依次 A–D、answer 是某个 key、选项文字不重复、numeric 的 answer 能解析成数、figure 是内联 SVG 且没引用外网、`hideChoiceText` 只用在每个选项都有图时。

`python scripts/verify_questions.py` 会检查：每条 `verify` 能否安全求值、求值结果与 answer 是否一致、选择题有没有双解。

两条都通过，才算这道题进了库。
