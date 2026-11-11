# 全国中考题库（31 省 · 七/八/九年级 · 九科）

一个自用的中考练习题库：题目存成 JSON，自带校验脚本和单文件练习页，可以按 **地区 + 学科 + 年级 + 难度** 筛题。

当前规模：**1604 道题 / 118 个知识点 / 31 个省级行政区**，覆盖语文、数学、英语、物理、化学、生物、历史、地理、道德与法治九科，每个省 45–57 题。

| 学科 | 题数 | 学科 | 题数 | 学科 | 题数 |
|---|---|---|---|---|---|
| 数学 | 617 | 物理 | 344 | 语文 | 181 |
| 化学 | 115 | 地理 | 109 | 英语 | 70 |
| 历史 | 70 | 生物 | 57 | 道德与法治 | 41 |

按年级：七年级 388、八年级 605、九年级 611（物理从八年级起、化学从九年级起，符合实际开课顺序）。
全部题目带 `verify`，运行 `python scripts/verify_questions.py` 自动核验，当前 `mismatch = 0`、`error = 0`。

## ⚠️ 先说清楚：这批题的来源

**这不是各省中考的原卷影印题。** 公开渠道没有可以机读（JSON/文本）的分省中考真题——能拿到的只有 PDF 试卷扫描件，要变成能判断对错的题库得先 OCR、切题、配答案，错误率不可控。

所以这批题的定位是**仿真题**：

- **理科**（数学、物理、化学）按中考常见题型和考点编写，数值随机生成，答案由脚本用公式算出来、再和答案字段比对，**算错会当场报错**；
- **文科**（语文、英语、历史、地理、生物、道德与法治）按教材知识点编写，答案来自教材原文、名句原文、省会/简称等确定事实；
- `region` 字段表示**这道题归在哪个省的题库下练习**，不代表它是该省某年的原题；`source` 统一写「中考仿真题」。

如果你想用真正的历年真题：把试卷（PDF / Word / 图片都行）给我，我按同一套字段拆成 JSON 替换进去，`region` 标成对应省份和年份即可。

## 在线访问（仓库已公开，所有人可只读获取）

### 一、题库 JSON —— 给 App / 电视端 / 脚本加载

| 地址 | 说明 |
|---|---|
| `https://cdn.jsdelivr.net/gh/siyagang/shiti-bank@main/q.json` | **推荐**。最短、无参数、`Content-Type: application/json` |
| `https://cdn.jsdelivr.net/gh/siyagang/shiti-bank@main/data/questions.json` | 内容相同，规范路径版 |
| `https://raw.githubusercontent.com/siyagang/shiti-bank/main/data/questions.json` | GitHub 原始直链，`Content-Type` 是 `text/plain`，部分 App 会因此判成「不是 JSON」，不推荐 |

响应是 **1604 条题目的 JSON 数组**（约 780 KB），字段说明见 `docs/questions.md`。

### 二、练习页（网页界面）

| 地址 | 说明 |
|---|---|
| `https://shiti-bank.app.workbuddy.host/?sharecode=GJYV32MJU5` | 手机 / 电脑打开的交互练习页，**返回 HTML，不能当数据源** |
| `https://shiti-bank.app.workbuddy.host/data/questions.json?sharecode=GJYV32MJU5` | 同一站点的 JSON 直链，`sharecode` 不能省，去掉直接 403「链接不完整」 |

### 三、改题怎么生效

改 `data/questions.json` → 跑 `python scripts/build_zhongkao.py`（会顺带同步根目录的 `q.json`）→ `git push`。
jsDelivr 有缓存：`@main` 通常在几分钟内刷新；急用可以加 `?v=时间戳` 绕过缓存，或请求 `https://purge.jsdelivr.net/gh/siyagang/shiti-bank@main/q.json` 手动清。

> 根目录的 `q.json` 只是 `data/questions.json` 的副本，为了 CDN 地址更短、电视遥控器好输入；改数据请改 `data/questions.json`。

如果 `git push` 报 `schannel: failed to receive handshake` 或 `CONNECT tunnel failed, response 502`（`github.com:443` 被网络挡住，但 `api.github.com` 正常），可以用 `scripts/push_via_api.py` 走 API 提交：

```bash
GH_TOKEN=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill | sed -n 's/^password=//p') \
  python scripts/push_via_api.py "提交说明"
```

网络恢复后执行 `git fetch origin && git reset --hard origin/main` 把本地对齐。

## 目录

```
.
├─ data/
│  ├─ questions.json          # 1604 道题，题目按 topicId 挂在知识点下
│  ├─ topics.json             # 118 个知识点（学科 × 七八九年级）
│  ├─ regions.json            # 31 个省级行政区
│  └─ verification_report.json# 核验报告，脚本自动生成
├─ docs/
│  └─ questions.md            # 字段规范、题型示例、verify 写法
├─ scripts/
│  ├─ build_zhongkao.py       # 生成整个题库（理科模板 + 文科素材）
│  ├─ zk_data.py              # 省份表、知识点表
│  ├─ zk_cn.py                # 语文素材：名句、文学常识、成语
│  ├─ zk_humanities.py        # 英语、历史、地理素材
│  ├─ zk_science_liberal.py   # 生物、道德与法治素材
│  ├─ validate.py             # 格式校验
│  ├─ verify_questions.py     # 答案核验
│  ├─ add_question.py         # 加一道题
│  ├─ import_csv.py           # 从 Excel 导出的 CSV 批量加题
│  └─ qbank.py                # 公共工具
├─ templates/新题模板.csv      # 批量导入的列名示例（带 region）
├─ practice.html              # 练习页，单文件、无需构建
└─ 打开练习页.bat              # Windows 一键起本地服务并打开练习页
```

## 一、本地跑起来

双击 `打开练习页.bat`，或者：

```bash
python -m http.server 8000
# 浏览器打开 http://localhost:8000/practice.html
```

> 直接双击 `practice.html` 会因为浏览器限制读不到本地 JSON，页面会提示手动选文件。

练习页的筛选项：**地区 / 学科 / 年级 / 难度 / 题量**。选「江苏 + 数学 + 九年级」就只出江苏的九年级数学题；答完自动判分、给解析，答错的题进错题本（存在浏览器 localStorage，按设备各自记录）。

## 二、重建 / 扩充题库

```bash
python scripts/build_zhongkao.py     # 重新生成 topics / questions / regions
python scripts/validate.py           # 格式校验
python scripts/verify_questions.py   # 答案核验，mismatch 必须为 0
```

生成逻辑全在 `scripts/build_zhongkao.py` 里，改起来很直接：

- **加题量**：改各省每个模板的题目数量，或往 `zk_*.py` 的素材表里加行；
- **加省份**：在 `zk_data.py` 的 `PROVINCES` 里加一行（id、名称、类型、简称）；
- **加知识点**：在 `zk_data.py` 的 `TOPIC_TABLE` 里加 `(名称, 章节)`；
- **加理科题型**：在 `math_g7 / math_g8 / math_g9 / physics_g8 / physics_g9 / chemistry_g9` 里加一个 `yield`，`answer` 和 `verify` 用同一个公式算，保证两者不会打架。

生成时按题干去重，重复的直接跳过（本次跳过了 72 道），所以题库里没有重题。

## 三、加自己的一两道题

```bash
python scripts/add_question.py                    # 交互式，回车跳过可选项
python scripts/import_csv.py 新题.csv --dry-run    # 先试跑，再正式导入
```

CSV 列名见 `templates/新题模板.csv`，其中 `region` 填省份名（如「江苏」），练习页的地区筛选靠它。加完记得跑一次校验和核验。

## 四、字段格式

一道题长这样（完整规范见 [`docs/questions.md`](docs/questions.md)）：

```json
{
  "id": "zk_math_g9_01_q3",
  "topicId": "zk_math_g9_01",
  "difficulty": "standard",
  "type": "numeric",
  "prompt": "方程 x² + 3x - 10 = 0 的解是（　）。",
  "answer": "-5，2",
  "explanation": "因式分解得 (x + 5)(x - 2) = 0，所以 x₁ = -5，x₂ = 2。",
  "region": "江苏",
  "source": "中考仿真题",
  "unordered": true,
  "verify": "roots2(1,3,-10)"
}
```

`region` 是这次新增的字段；`verify` 是一个受限的 Python 表达式，核验脚本会求值后和 `answer` 比对。

## 五、免责与版权

- 题目由脚本按考纲和教材知识点编写，**不是原卷真题**，也没有教师逐题审核；
- 答案经过 `verify` 自动核验，但自动核验只能保证「表达式算出来的结果和答案一致」，不能保证题干表述、选项设置完全没毛病；
- 仅限个人练习使用，不要用于商业分发。

如果发现某道题有问题，告诉我题号（`id`），我改或删。
