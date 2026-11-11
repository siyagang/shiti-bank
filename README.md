# 我的中小学题库

一个**自己用的**题库仓库：题目存成 JSON，格式与
[`xiaoyang111222/cn-math-taxonomy`](https://github.com/xiaoyang111222/cn-math-taxonomy) 的 `data/questions.json` 完全一致，
那套工具、页面、CDN 取数方式都能直接复用；同时自带校验脚本和一个能直接用的练习页。

- `data/questions.json` — 题目（一个对象一道题）
- `data/topics.json` — 知识点（题目按 topicId 挂在知识点下）
- `practice.html` — 练习页，下拉筛选 + 判分 + 错题本，单文件、无需构建
- `scripts/` — 校验、核验、加题、批量导入、外部题库导入

当前规模：**4495 道题 / 1431 个知识点**，其中 **初中 4271 道**，覆盖九科：

| 英语 | 数学 | 语文 | 历史 | 道德与法治 | 物理 | 生物 | 地理 | 化学 |
|---|---|---|---|---|---|---|---|---|
| 942 | 735 | 712 | 523 | 372 | 330 | 249 | 231 | 177 |

另高中 204 道、小学 20 道。4465 道来自开源题库、30 道是自建示例；4482 道带 `verify`，核验结果 `mismatch = 0`。练习页按「自建题 / 外部题库」区分，可只刷自己写的题。

字段说明见 [`docs/questions.md`](docs/questions.md)。

## 目录

```
.
├─ data/
│  ├─ questions.json          # 4495 道题（30 道手写示例 + 4465 道外部导入）
│  ├─ topics.json             # 1431 个知识点
│  ├─ import_map.json         # 来源知识点 → 本地 id 的映射，保证重复导入不换号
│  └─ verification_report.json# 核验报告，脚本自动生成
├─ docs/
│  └─ questions.md            # 字段规范 + verify 写法 + 校验规则
├─ scripts/
│  ├─ validate.py             # 格式校验
│  ├─ verify_questions.py     # 用 verify 表达式核验答案
│  ├─ add_question.py         # 加一道题（交互 / JSON）
│  ├─ import_csv.py           # 从 Excel 导出的 CSV 批量导入
│  ├─ import_external.py      # 从同格式开源题库导入中学题目（可重复运行）
│  └─ qbank.py                # 上面几个共用的工具
├─ templates/
│  └─ 新题模板.csv             # 批量导入的列名示例
├─ practice.html              # 练习页
└─ 打开练习页.bat             # Windows 一键起本地服务并打开练习页
```

> 本仓库已推送到 `github.com/siyagang/shiti-bank`（Private）。下面的建仓步骤留作换新仓库时的参考。

## 一、把它变成你的 GitHub 仓库

### 方式 A：网页点一遍（不用装任何东西）

1. 打开 https://github.com/new
2. 仓库名填 `shiti-bank`，选 **Private**（题库含答案，强烈建议私有），**不要**勾选自动生成 README
3. 创建后，在本地这个目录里依次执行（把 `你的用户名` 换掉）：

```bash
git init -b main
git add .
git commit -m "初始化题库"
git remote add origin https://github.com/你的用户名/shiti-bank.git
git push -u origin main
```

第一次 push 会要求登录：密码位置填 **Personal Access Token**（GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens，勾选该仓库的 Contents: Read and write），不要填账号密码。

### 方式 B：装了 GitHub CLI 的话一条命令

```bash
gh auth login
gh repo create shiti-bank --private --source=. --push
```

## 二、本地跑起来

```bash
python scripts/validate.py          # 格式校验，出错会列出来
python scripts/verify_questions.py  # 答案核验，mismatch 必须为 0
```

> 最省事：**双击 `打开练习页.bat`**，它会在后台起 `http.server` 并自动打开浏览器。
>
> 手动的话：
>
> ```bash
> python -m http.server 8000          # 然后打开 http://localhost:8000/practice.html
> ```
>
> 直接双击 `practice.html` 会因为浏览器限制读不到本地 JSON，页面会提示你手动选文件；用上面的方式或部署到 Pages 就没有这个问题。

## 三、往里加题

**加一道（交互式，最省事）**

```bash
python scripts/add_question.py
```

会列出所有知识点让你选编号，然后逐项问题型、难度、题干、答案、解析、verify。id 自动生成。

**加一道（一条 JSON，适合让 AI 批量出题后粘进来）**

```bash
python scripts/add_question.py --json '{"topicId":"cnm_p003","type":"numeric","prompt":"8 × 9 = ?","answer":"72","explanation":"口诀「八九七十二」。","verify":"8*9"}'
```

**加一批（Excel → CSV）**

1. 照 `templates/新题模板.csv` 的列名整理表格
2. Excel 里「另存为 → CSV UTF-8」
3. 先试跑看有没有格式问题，再去掉 `--dry-run` 真写：

```bash
python scripts/import_csv.py 新题.csv --dry-run
python scripts/import_csv.py 新题.csv
```

同 `topicId` + 同题干的题默认跳过，不会重复入库。

**加完记得**

```bash
python scripts/validate.py && python scripts/verify_questions.py
git add -A && git commit -m "新增 12 道分数题" && git push
```

## 四、批量导入中学题目（外部题库）

`scripts/import_external.py` 从同格式的开源题库（[`xiaoyang111222/cn-math-taxonomy`](https://github.com/xiaoyang111222/cn-math-taxonomy)，13915 道题、3442 个知识点）里挑「中学」题进库。第一次运行会自动把来源数据下到 `data/_source/`（已 gitignore，不进仓库）。

```bash
python scripts/import_external.py --dry-run   # 只统计会导多少题
python scripts/import_external.py --write     # 实际写入
```

它只收满足下面全部条件的题，所以入库的都是「能自证答案」的：

| 条件 | 原因 |
|---|---|
| 有 `verify` 且当场算出的结果与 `answer` 一致 | 答案机器复核过，不靠人眼 |
| 题干不含「如图 / 下图 / 表中」 | 不带配图的题必须自包含 |
| 题干 8–130 字、单行、无 `（1）①②` 子问 | 便于在手机上直接作答 |
| 选择题 3–4 个选项、文字不重复、≤45 字 | 选项要能一屏放下 |
| 学科 / 学段命中 `QUOTAS` 配额，每知识点最多 4 题 | 按学科配比、按知识点铺开，不让某个点刷屏 |

当前配额（每轮上限）：英语初中 1300、数学 900、语文 900、历史 620、道德与法治 460、物理 400、生物 280、地理 260、化学 220；高中三项设为 0（本轮只扩初中，改回数字即可扩高中）。

重跑是**增量**的：按题干判重，已导入的不会重复进库；新题题号接在已有题号后面，知识点 id 走 `data/import_map.json` 的固定映射，不会因为重跑而换号。

每道导入的题都带 `"source": "cn-math-taxonomy 开源题库（中学）"`，所以：

```bash
# 只看导入的题
python -c "import json;q=json.load(open('data/questions.json',encoding='utf-8'));print(sum(1 for x in q if x.get('source')))"

# 整批删掉（只留自己写的）
python -c "
import json
p='data/questions.json'
q=[x for x in json.load(open(p,encoding='utf-8')) if not x.get('source')]
json.dump(q,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
"
python scripts/validate.py   # 删完会提示有些知识点没题了，按需再清 topics.json
```

> 来源仓库没有 LICENSE 文件，严格说是「保留所有权利」。这批题只适合自己私下练习用，不要转载、不要再发布。

## 五、把练习页放到线上

仓库 **Settings → Pages → Source 选 `main` / `root`**，一会儿就能用
`https://你的用户名.github.io/shiti-bank/practice.html` 在手机和电脑上做题。
错题本存在浏览器 localStorage 里，按设备各自记录。

> 私有仓库的 Pages 需要 GitHub Pro；不想公开题库就别开，直接用本地服务或「发布为应用」的私有链接。

## 六、手机 / 别的程序怎么读这份题库

仓库公开后，任何地方都能直接拉最新数据（jsDelivr 会缓存，更新后几分钟生效）：

```
https://cdn.jsdelivr.net/gh/你的用户名/shiti-bank@main/data/questions.json
https://cdn.jsdelivr.net/gh/你的用户名/shiti-bank@main/data/topics.json
```

私有仓库不能用 CDN，但可以 `git clone` 后用本地路径读。写法参考：

```js
const qs = await (await fetch('https://cdn.jsdelivr.net/gh/你的用户名/shiti-bank@main/data/questions.json')).json();
```

因为这个格式和开头那个仓库一样，你也可以直接把它的页面（`index.html`、`diagnose/`）拿过来，
把里面的数据地址换成自己的 CDN 链接，就有一套自己的诊断 / 练习工具了。

## 七、扩建路线（按需要来，不必一次做完）

1. **先铺知识点，再灌题**：`topics.json` 里按「学科 → 学段 → 年级 → 章节」列清楚，一个知识点对应课堂上一节能讲完的内容（大约 1–3 道题的量），别粒度太细。
2. **每个知识点先 2 题打底**：一题 `basic` 一题 `standard`，保证任何点都能自测。
3. **只给能算的题写 `verify`**：写不出来就别硬凑，靠人工或 AI 复核。`mismatch` 保持 0，比题量重要。
4. **题库过千后考虑索引页**：按学段 / 学科 / 章节 / 难度做筛选和组卷，`practice.html` 的筛选逻辑可以直接抄。
5. **想多学科**：语文、英语题照样能用这套字段（示例里已经有了），只是 `verify` 大多用不上，答案靠 `accept` 覆盖常见写法。

## 免责

答案经过 `verify` 自动核验（`mismatch = 0`），但没有教师逐题审核；自动核验只能保证「表达式算出来的数和答案一致」，不能保证题干表述、选项设置完全没毛病。
自己往里加的题，正确性由你自己负责——尤其是语文、英语这类没法用表达式验的题，做完记得再读一遍。
外部导入的题版权归原出处，仅限个人练习使用。
