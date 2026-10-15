# 开源接入与自查修正版提交命令

适用于已包含原证据图版、尚未提交 PyArg 升级的仓库；包含开源接入与本轮修复。若已提交上一份 PyArg 包，请改用 REVIEW_FIX_COMMITS.md，不要两套重复执行。

在原仓库根目录执行。每条命令都是单行；每组 add 成功后再执行 commit。已提交的组跳过。代码包不包含原仓库 Git 历史。

如暂存区已有混合内容，可先执行 `git restore --staged .`，工作区修改保留。

## 审核业务与配套回归

```powershell
git add -- "backend/config/pead_rules_v1.json" "backend/fixtures/README.md" "backend/fixtures/compare_pead.py" "backend/fixtures/frozen_report_inputs.json" "backend/fixtures/generate.py" "backend/main.py" "backend/pipeline.py" "backend/pyproject.toml" "backend/report.py" "backend/requirements.txt" "backend/src/argumentation.py" "backend/src/audit_report.py" "backend/src/evidence_graph.py" "backend/src/pead_engine.py" "backend/src/pead_rules.py" "backend/src/relation_client.py" "backend/src/relation_fusion.py" "backend/tests/smoke_live.py" "backend/tests/test_parameters.py" "backend/tests/test_pead_rules.py" "backend/tests/test_pead_self_review.py" "backend/uv.lock" "backend/reports/mock-pead-comparison.json"
git commit -m "feat(pead): 接入开源论证求解并完善证据裁决与报告约束" -m "接入 PyArg 与 NetworkX，使用经校验的规则配置和不可变快照驱动审核。统一事件作用域，保留警示及不确定证据，实施构图预算和配置保护；使关系核验、逐事件处置、整改动作和报告状态保持一致。同步依赖、冻结输入、回归测试和对照结果。"
```

## 验证记录与演示

```powershell
git add -- "backend/reports/mock-pead-comparison.md" "backend/reports/pead-graph-demo.html" "backend/reports/pead-graph-warning-regression.html" "backend/reports/pead-self-review-comparison.log" "backend/reports/pead-self-review-drift.log" "backend/reports/pead-self-review-fixtures.log" "backend/reports/pead-self-review-http-smoke.log" "backend/reports/pead-self-review-server.log" "backend/reports/pead-self-review-tests.log" "backend/reports/pead-self-review-truth-table.log" "backend/reports/pead-self-review-validation.json" "backend/reports/pead-truth-table.json" "backend/reports/pead-truth-table.md" "backend/reports/pead-upgrade-comparison.log" "backend/reports/pead-upgrade-fixtures.log" "backend/reports/pead-upgrade-http-smoke.log" "backend/reports/pead-upgrade-server.log" "backend/reports/pead-upgrade-tests.log" "backend/reports/pead-upgrade-truth-table.log" "backend/reports/pead-upgrade-validation.json"
git commit -m "test(pead): 补充开源接入和自查修复的验证记录" -m "保存 Mock 对照、边界与组合枚举、后端回归、真实 HTTP 与 ffprobe 失败路径记录，更新合成演示报告并明确未验证真实模型效果。"
```

## 交接说明与变更清单

```powershell
git add -- "HANDOFF.md" "README.md" "REVIEW_FIX_COMMITS.md" "THIRD_PARTY.md" "UPGRADE_CHANGES.json" "UPGRADE_COMMITS.md" "docs/00_文档导航与使用说明.md" "docs/07_PEAD证据图与开源参考.md" "docs/08_PEAD开源引擎接入与规则工程化.md" "docs/09_PEAD自查与缺陷修复.md"
git commit -m "docs(pead): 完善开源归属、规则工程化及自查交接" -m "说明开源组件实际用途与团队贡献，记录已复现缺陷、修复依据、运行复现方法及剩余边界，提供选择性暂存的单行 PowerShell 提交命令。"
```

提交完成后检查 `git status --short`；需要推送时单独执行：

```powershell
git push -u origin HEAD
```
