# 评测报告 — {{model}}

- 方案: `{{plan}}`
- 模型: `{{model}}`
- 时间: {{timestamp}}

## 总览

| 任务 | 指标 | 得分 | 样本数 |
|---|---|---|---|
{% for t in tasks %}| {{t.id}} | {{t.metric}} | {{t.score}} | {{t.n}} |
{% endfor %}

## 维度汇总

| 维度 | 平均得分 | 数据集数 |
|---|---|---|
{% for d in dims %}| {{d.dim}} | {{d.avg}} | {{d.count}} |
{% endfor %}

## 说明
- `SKIPPED` 任务表示该 runner 需专用执行环境（代码沙箱/SWE-bench docker/agent 工具），见 `scripts/` 对应脚本。
- 样本数 `n` 为有效计分样本；快速方案 n<=200 仅用于排序参考。
- 跨模型对比仅限同一 plan + 同一数据集版本。
