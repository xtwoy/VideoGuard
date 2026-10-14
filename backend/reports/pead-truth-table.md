# PEAD 穷举真值表

> 由 `python -m fixtures.truth_table --write` 生成，请勿手工编辑。

上游阶段为 mock 数据，PEAD 与结果融合为真实代码。本表证明决策函数的性质（全定义、确定性、符合协议、单调保守、结论不依赖标注用词），不度量真实视频上的准确率。

两种 FLAG 的语义不同，读表时注意：

- `warning_context` 只有警示线索、**没有**鼓励线索：出现 FLAG 表示 PEAD 采纳了提供方的回答，而它没有结构性理由怀疑——错在输入，不在规则。
- `relation_wrong_encouragement` 同一事件内同时有鼓励与警示：出现 FLAG 是**真实误报**，反证存在却用不上，因为两条线索共享同一 referent_key。

关系回答取值：`encourages_same`、`insufficient`、`unrelated`、`warns_same`

## `danger_promotion`

候选对 2 个，共 16 种组合。

| pair_0 | pair_1 | judgement | disposition | reason_code |
| --- | --- | --- | --- | --- |
| encourages_same | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | insufficient | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| encourages_same | unrelated | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| encourages_same | warns_same | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| insufficient | encourages_same | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| insufficient | insufficient | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| insufficient | unrelated | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| insufficient | warns_same | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| unrelated | encourages_same | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| unrelated | insufficient | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| unrelated | unrelated | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| unrelated | warns_same | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| warns_same | encourages_same | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| warns_same | insufficient | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| warns_same | unrelated | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |
| warns_same | warns_same | CONFLICTED | REVIEW | RELATION_DISPUTES_BASELINE |

可达结论：

- `CONFLICTED` / `REVIEW` — `RELATION_DISPUTES_BASELINE`
- `SUPPORTED` / `FLAG` — `RELATION_LINK_ASSISTED`

## `warning_context`

候选对 2 个，共 16 种组合。

| pair_0 | pair_1 | judgement | disposition | reason_code |
| --- | --- | --- | --- | --- |
| encourages_same | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | insufficient | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | unrelated | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | warns_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| insufficient | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| insufficient | insufficient | INSUFFICIENT | REVIEW | RELATION_AMBIGUITY |
| insufficient | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| insufficient | warns_same | INSUFFICIENT | REVIEW | RELATION_AMBIGUITY |
| unrelated | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| unrelated | insufficient | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| unrelated | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| unrelated | warns_same | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| warns_same | insufficient | INSUFFICIENT | REVIEW | RELATION_AMBIGUITY |
| warns_same | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | warns_same | NOT_SUPPORTED | NONE | NO_SUPPORTING_RELATION |

可达结论：

- `INSUFFICIENT` / `REVIEW` — `RELATION_AMBIGUITY`
- `NOT_SUPPORTED` / `NONE` — `NO_SUPPORTING_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`
- `SUPPORTED` / `FLAG` — `RELATION_LINK_ASSISTED`

## `unrelated_promotion`

候选对 1 个，共 4 种组合。

| pair_0 | judgement | disposition | reason_code |
| --- | --- | --- | --- |
| encourages_same | CONFLICTED | REVIEW | RELATION_REFERENT_DISAGREEMENT |
| insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |

可达结论：

- `CONFLICTED` / `REVIEW` — `RELATION_REFERENT_DISAGREEMENT`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`

## `unrelated_without_relation_service`

候选对 1 个，共 4 种组合。

| pair_0 | judgement | disposition | reason_code |
| --- | --- | --- | --- |
| encourages_same | CONFLICTED | REVIEW | RELATION_REFERENT_DISAGREEMENT |
| insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |

可达结论：

- `CONFLICTED` / `REVIEW` — `RELATION_REFERENT_DISAGREEMENT`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`

## `relation_override_conflict`

候选对 1 个，共 4 种组合。

| pair_0 | judgement | disposition | reason_code |
| --- | --- | --- | --- |
| encourages_same | CONFLICTED | REVIEW | RELATION_REFERENT_DISAGREEMENT |
| insufficient | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |
| unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | INSUFFICIENT | REVIEW | MISSING_SEMANTIC_RELATION |

可达结论：

- `CONFLICTED` / `REVIEW` — `RELATION_REFERENT_DISAGREEMENT`
- `INSUFFICIENT` / `REVIEW` — `MISSING_SEMANTIC_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`

## `relation_wrong_encouragement`

候选对 2 个，共 16 种组合。

| pair_0 | pair_1 | judgement | disposition | reason_code |
| --- | --- | --- | --- | --- |
| encourages_same | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | insufficient | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | unrelated | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| encourages_same | warns_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| insufficient | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| insufficient | insufficient | INSUFFICIENT | REVIEW | RELATION_AMBIGUITY |
| insufficient | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| insufficient | warns_same | INSUFFICIENT | REVIEW | RELATION_AMBIGUITY |
| unrelated | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| unrelated | insufficient | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| unrelated | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| unrelated | warns_same | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | encourages_same | SUPPORTED | FLAG | RELATION_LINK_ASSISTED |
| warns_same | insufficient | INSUFFICIENT | REVIEW | RELATION_AMBIGUITY |
| warns_same | unrelated | NOT_SUPPORTED | NONE | RELATION_UNRELATED_CONFIRMED |
| warns_same | warns_same | NOT_SUPPORTED | NONE | NO_SUPPORTING_RELATION |

可达结论：

- `INSUFFICIENT` / `REVIEW` — `RELATION_AMBIGUITY`
- `NOT_SUPPORTED` / `NONE` — `NO_SUPPORTING_RELATION`
- `NOT_SUPPORTED` / `NONE` — `RELATION_UNRELATED_CONFIRMED`
- `SUPPORTED` / `FLAG` — `RELATION_LINK_ASSISTED`

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

- `warning_context` 可达结论：[('INSUFFICIENT', 'REVIEW'), ('NOT_SUPPORTED', 'NONE'), ('SUPPORTED', 'FLAG')]
- `counter_context_tagging` 可达结论：[('CONFLICTED', 'REVIEW')]
- 两者均未出现 FLAG：False

两者内容同为‘动作＋警示’，仅警示的标注用词不同。counter_context_tagging 含鼓励线索，warning_context 不含，因此不要求完全相同，只要求都不出现 FLAG。

## 检查结果

未发现问题。
