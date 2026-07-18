---
name: coding-testing
dimension: coding
---

# 代码能力评测 Skill

## 何时使用
评测函数级代码生成与真实软件工程修复能力。

## 探针设计
- HumanEval/MBPP：补全函数体，仅输出代码，`temperature=0`。
- LiveCodeBench：竞赛编程，含时间戳防污染分片。
- SWE-bench Verified：真实 GitHub issue 修复，需 repo 级环境。

## 判分要点
- pass@1：在沙箱内导入生成的代码 + 跑官方测试用例，全过=1。
- SWE-bench：apply 补丁 → 跑 `FAIL_TO_PASS` 单测转 PASS 且 `PASS_TO_PASS` 不退步。
- 多次采样 pass@k 用无偏估计公式，别用简单平均。

## 常见坑
- ❌ 直接在主机执行生成代码：RCE 风险，必须 docker/容器/进程隔离。
- ❌ 不限制输出 token，模型把测试也生成出来污染运行。
- ❌ HumanEval 用 train 污染：注意数据集 split；LiveCodeBench 按日期切防泄漏。
- ❌ SWE-bench 不装依赖：每个 instance 需对应 base image，耗时与成本极高，先用 n<=20 冒烟。

## 最小执行
```bash
# 需要 docker；骨架阶段跳过，runner=code_exec 未实现
python datasets/coding/fetch.py --dataset humaneval
python scripts/run_code_eval.py --benchmark coding_humaneval --model <id>   # 待实现
```

## 与本仓库映射
- 定义：`suites/coding/definition.yaml`
- runner：`code_exec` / `swe_docker`（骨架未实现，跳过）
- 指标：`pass_at_1` / `swe_resolved`
