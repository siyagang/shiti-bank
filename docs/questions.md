# 题库格式说明

两个文件：`data/questions.json`（题目）和 `data/topics.json`（知识点）。
都是 UTF-8、无 BOM 的 JSON；`questions.json` 顶层是数组，一个对象一道题。

## 一、questions.json 的字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 必须是 `<topicId>_q<N>`，如 `cnm_p001_q3`。脚本按此规则自动生成，不要手写别的格式 |
| `topicId` | 是 | 所属知识点 id，必须存在于 `topics.json` |
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

## 二、四种题型的完整示例

**numeric**

```json
{
  "id": "cnm_j002_q1",
  "topicId": "cnm_j002",
  "difficulty": "basic",
  "type": "numeric",
  "prompt": "直角三角形的两条直角边分别是 3 和 4，斜边长是多少？",
  "answer": "5",
  "explanation": "由勾股定理，斜边² = 3² + 4² = 25，所以斜边 = 5。",
  "verify": "sqrt(3**2+4**2)"
}
```

**choice**

```json
{
  "id": "cnm_p002_q2",
  "topicId": "cnm_p002",
  "difficulty": "standard",
  "type": "choice",
  "prompt": "9 + 6 等于多少？",
  "choices": [
    {"key": "A", "text": "13"},
    {"key": "B", "text": "14"},
    {"key": "C", "text": "15"},
    {"key": "D", "text": "16"}
  ],
  "answer": "C",
  "explanation": "9 差 1 凑成 10，6 分成 1 和 5，9 + 1 = 10，10 + 5 = 15。",
  "verify": "'15'"
}
```

**short**（答案可以有多种写法）

```json
{
  "id": "cnm_h002_q2",
  "topicId": "cnm_h002",
  "difficulty": "standard",
  "type": "short",
  "prompt": "函数 f(x) = 2x + 1 在 R 上是增函数还是减函数？",
  "answer": "增函数",
  "accept": ["单调递增", "递增", "增"],
  "explanation": "斜率 2 > 0，所以在 R 上单调递增。"
}
```

**self**（开放题，页面上自评）

```json
{
  "id": "cnc_p002_q2",
  "topicId": "cnc_p002",
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

## 四、topics.json 的字段

```json
{
  "id": "cnm_p001",
  "name": "1到5各数的认识",
  "subject": "math",
  "domain": "数与代数",
  "grade": 1,
  "semester": "上",
  "chapter": "一年级上册 第1单元 5以内数的认识和加、减法",
  "type": "conceptual",
  "description": "能在数量和数字之间来回，认读并写出 1 到 5。",
  "mastery_criteria": ["能按顺序数出 1 到 5", "能说出一个数的前一个和后一个"],
  "diagnostic_question": {"question": "2 和 3 合起来是几？", "answer": "5"}
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 学科前缀 + 学段字母 + 三位序号，见下表 |
| `name` | 是 | 知识点名称 |
| `subject` | 是 | `math` / `chinese` / `english` / `physics` / `chemistry` / `biology` / `history` / `geography` / `science` / `morality` |
| `domain` | 是 | 课标领域，如「数与代数」「图形与几何」「识字与写字」 |
| `grade` | 是 | 1–12 的整数 |
| `semester` | 是 | `上` / `下` |
| `chapter` | 否 | 教材章节，便于按册复习 |
| `type` | 否 | `conceptual` 概念 / `procedural` 方法 / `strategic` 综合 |
| `description` | 否 | 一句话说明这个点要会什么 |
| `mastery_criteria` | 否 | 掌握标准，写给自己看，出题时当检查清单 |
| `diagnostic_question` | 否 | 一道快速自测题，可被 q1 沿用 |
| `external` | 否 | `true` 表示只是分类节点（如「小学」这种目录层级），**不允许挂题** |

### id 前缀约定

`cnm_p001` = 中国（cn）+ 数学（m）+ 小学（p）+ 001。

| 学段字母 | 含义 | 示例 |
|---|---|---|
| `p` | 小学 | `cnm_p001` |
| `j` | 初中 | `cnm_j001` |
| `h` | 高中 | `cnm_h001` |

学科字母：`m` 数学、`c` 语文、`e` 英语、`p` 物理（与学段字母位置不同，在全名里靠前缀区分：`cnp_h001` 是高中物理）、`k` 化学、`b` 生物、`h` 历史、`g` 地理、`s` 科学、`d` 道德与法治。

新增学科时，只要 `subject` 和前缀对得上，脚本不用改。

## 五、校验规则

`python scripts/validate.py` 会检查：id 唯一且与 topicId 对应、topicId 存在且不是 external、difficulty / type 合法、必填字段非空、没有拼错的未知字段、选择题选项 3–4 个且 key 依次 A–D、answer 是某个 key、选项文字不重复、numeric 的 answer 能解析成数、figure 是内联 SVG 且没引用外网、`hideChoiceText` 只用在每个选项都有图时。

`python scripts/verify_questions.py` 会检查：每条 `verify` 能否安全求值、求值结果与 answer 是否一致、选择题有没有双解。

两条都通过，才算这道题进了库。
