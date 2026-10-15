# 本轮自查修复提交命令

适用于已经提交上一份 PyArg 升级包的仓库；只提交本轮自查修复。若尚未提交开源接入升级，请改用 UPGRADE_COMMITS.md，不要两套重复执行。

在原仓库根目录执行。每条命令都是单行；每组 add 成功后再执行 commit。已提交的组跳过。代码包不包含原仓库 Git 历史。

如暂存区已有混合内容，可先执行 `git restore --staged .`，工作区修改保留。

## 审核业务与配套回归

```powershell
git add -- "backend/config/pead_rules_v1.json" "backend/fixtures/README.md" "backend/fixtures/compare_pead.py" "backend/fixtures/frozen_report_inputs.json" "backend/fixtures/generate.py" "backend/pipeline.py" "backend/report.py" "backend/src/audit_report.py" "backend/src/evidence_graph.py" "backend/src/pead_engine.py" "backend/src/pead_rules.py" "backend/src/relation_client.py" "backend/src/relation_fusion.py" "backend/tests/test_parameters.py" "backend/tests/test_pead_self_review.py" "backend/reports/mock-pead-comparison.json"
git commit -m "fix(pead): 修复事件隔离、警示裁决和报告一致性" -m "统一使用明确事件 ID，保留未定位警示并校验反向关系的作用域；保护警示生成规则和支持前提，消除论证标识碰撞，在构图时执行资源预算。修正关系核验状态，以领域裁决重建报告检查信息，保留各事件的人工复核与相应动作，拒绝风险维度和事实标识冲突；冻结模型输入并补充针对性回归。"
```

## 验证记录与演示

```powershell
git add -- "backend/reports/mock-pead-comparison.md" "backend/reports/pead-graph-demo.html" "backend/reports/pead-graph-warning-regression.html" "backend/reports/pead-self-review-comparison.log" "backend/reports/pead-self-review-drift.log" "backend/reports/pead-self-review-fixtures.log" "backend/reports/pead-self-review-http-smoke.log" "backend/reports/pead-self-review-server.log" "backend/reports/pead-self-review-tests.log" "backend/reports/pead-self-review-truth-table.log" "backend/reports/pead-self-review-validation.json" "backend/reports/pead-truth-table.json" "backend/reports/pead-truth-table.md"
git commit -m "test(pead): 保存自查反例与完整回归记录" -m "记录最小反例的修复前后结果、业务组合枚举、后端回归及真实 HTTP 与 ffprobe 检查；逐字节核对模型 Mock 回包并确认检查只读，更新可复核报告和验证汇总。"
```

## 交接说明与变更清单

```powershell
git add -- "HANDOFF.md" "README.md" "REVIEW_FIX_COMMITS.md" "UPGRADE_CHANGES.json" "UPGRADE_COMMITS.md" "docs/00_文档导航与使用说明.md" "docs/07_PEAD证据图与开源参考.md" "docs/08_PEAD开源引擎接入与规则工程化.md" "docs/09_PEAD自查与缺陷修复.md"
git commit -m "docs(pead): 说明已复现缺陷、修复依据及交接边界" -m "逐项记录上一版内部不一致及其业务影响，说明本轮校验范围、模型回包冻结、规则约束和剩余限制；提供与上轮差异清单及按业务分组的单行 PowerShell 提交命令。"
```

提交完成后检查 `git status --short`；需要推送时单独执行：

```powershell
git push -u origin HEAD
```
