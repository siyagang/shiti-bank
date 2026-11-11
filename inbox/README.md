# inbox：把要导入的 CSV 放在这里

每天自动更新时会把本目录下的 `*.csv` 导入题库，导入前先做预检，通过后归档到 `inbox/_done/日期/`。

CSV 列名（顺序随意，多余列忽略）：

```
topicId,region,semester,type,difficulty,prompt,answer,explanation,choices,verify,accept,unordered
```

- 模板：`templates/新题模板.csv`，直接复制改名再填
- `topicId` 必须是 `data/topics.json` 里已有的，如 `zk_math_g9_01`
- 选择题用 `choices`（`|` 分隔），`answer` 写正确项文字
- 短答题用 `answer` + `accept`（等价答案 `|` 分隔）
- 与已有题重复（同 topicId + 同题干）会被自动跳过
