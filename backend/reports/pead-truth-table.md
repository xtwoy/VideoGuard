# PEAD 穷举真值表

> 由 `python -m fixtures.truth_table --write` 生成，请勿手工编辑。

上游阶段为 mock 数据，PEAD 与结果融合为真实代码。本表证明决策函数的性质（枚举范围内全定义、确定性、符合协议、单对保守性、结论不依赖标注用词），不度量真实视频上的准确率。

显式警示与模型鼓励回答冲突时必须转人工；不同事件独立裁决。

注意：本表仅枚举当前合成用例。上游遗漏的警示无法凭空补齐。

关系回答取值：`encourages_same`、`insufficient`、`unrelated`、`warns_same`

## `danger_promotion`

候选对 2 个，共 16 种组合。

| pair_0 | pair_1 | judgement | disposition | reason_code |
| --- | --- | --- | --- | --- |
| encourages_same | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| encourages_same | unrelated | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | warns_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| insufficient | encourages_same | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| insufficient | insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| insufficient | unrelated | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| insufficient | warns_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| unrelated | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| unrelated | insufficient | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| unrelated | unrelated | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| unrelated | warns_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| warns_same | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| warns_same | insufficient | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| warns_same | unrelated | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| warns_same | warns_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |

可达结论：

- `CONFLICTED` / `REVIEW` — `CONFLICTING_STANCE`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `SUPPORTED` / `FLAG` — `RELATION_LINK_ASSISTED`

## `warning_context`

候选对 2 个，共 16 种组合。

| pair_0 | pair_1 | judgement | disposition | reason_code |
| --- | --- | --- | --- | --- |
| encourages_same | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| encourages_same | insufficient | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| encourages_same | unrelated | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| encourages_same | warns_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| insufficient | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| insufficient | insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| insufficient | unrelated | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| insufficient | warns_same | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| unrelated | insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| unrelated | warns_same | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| warns_same | insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| warns_same | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | warns_same | NOT_SUPPORTED | NONE | NO_SUPPORTING_RELATION |

可达结论：

- `CONFLICTED` / `REVIEW` — `CONFLICTING_STANCE`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `NOT_SUPPORTED` / `NONE` — `NO_SUPPORTING_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`

## `unrelated_promotion`

候选对 1 个，共 4 种组合。

| pair_0 | judgement | disposition | reason_code |
| --- | --- | --- | --- |
| encourages_same | CONFLICTED | REVIEW | RELATION_REFERENT_DISAGREEMENT |
| insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | NOT_SUPPORTED | NONE | NO_SUPPORTING_RELATION |

可达结论：

- `CONFLICTED` / `REVIEW` — `RELATION_REFERENT_DISAGREEMENT`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `NOT_SUPPORTED` / `NONE` — `NO_SUPPORTING_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`

## `unrelated_without_relation_service`

候选对 1 个，共 4 种组合。

| pair_0 | judgement | disposition | reason_code |
| --- | --- | --- | --- |
| encourages_same | CONFLICTED | REVIEW | RELATION_REFERENT_DISAGREEMENT |
| insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | NOT_SUPPORTED | NONE | NO_SUPPORTING_RELATION |

可达结论：

- `CONFLICTED` / `REVIEW` — `RELATION_REFERENT_DISAGREEMENT`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `NOT_SUPPORTED` / `NONE` — `NO_SUPPORTING_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`

## `relation_override_conflict`

候选对 1 个，共 4 种组合。

| pair_0 | judgement | disposition | reason_code |
| --- | --- | --- | --- |
| encourages_same | CONFLICTED | REVIEW | RELATION_REFERENT_DISAGREEMENT |
| insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | NOT_SUPPORTED | NONE | NO_SUPPORTING_RELATION |

可达结论：

- `CONFLICTED` / `REVIEW` — `RELATION_REFERENT_DISAGREEMENT`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `NOT_SUPPORTED` / `NONE` — `NO_SUPPORTING_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`

## `relation_wrong_encouragement`

候选对 2 个，共 16 种组合。

| pair_0 | pair_1 | judgement | disposition | reason_code |
| --- | --- | --- | --- | --- |
| encourages_same | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| encourages_same | insufficient | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| encourages_same | unrelated | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| encourages_same | warns_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| insufficient | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| insufficient | insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| insufficient | unrelated | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| insufficient | warns_same | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| unrelated | insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| unrelated | warns_same | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| warns_same | insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| warns_same | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | warns_same | NOT_SUPPORTED | NONE | NO_SUPPORTING_RELATION |

可达结论：

- `CONFLICTED` / `REVIEW` — `CONFLICTING_STANCE`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `NOT_SUPPORTED` / `NONE` — `NO_SUPPORTING_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`

## `counter_context_tagging`

候选对 1 个，共 4 种组合。

| pair_0 | judgement | disposition | reason_code |
| --- | --- | --- | --- |
| encourages_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| insufficient | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| unrelated | CONFLICTED | REVIEW | CONFLICTING_STANCE |
| warns_same | CONFLICTED | REVIEW | CONFLICTING_STANCE |

可达结论：

- `CONFLICTED` / `REVIEW` — `CONFLICTING_STANCE`

## 结论不依赖标注用词

- `warning_context` 可达结论：[('CONFLICTED', 'REVIEW'), ('INSUFFICIENT', 'REVIEW'), ('NOT_SUPPORTED', 'NONE')]
- `counter_context_tagging` 可达结论：[('CONFLICTED', 'REVIEW')]
- 两者均未出现 FLAG：True

两者内容同为‘动作＋警示’，仅警示的标注用词不同。counter_context_tagging 含鼓励线索，warning_context 不含，因此不要求完全相同，只要求都不出现 FLAG。

## 检查结果

未发现问题。
