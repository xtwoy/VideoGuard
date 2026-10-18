# PEAD 论证攻防报告

> 由 `python -m fixtures.argumentation_report --write` 生成，请勿手工编辑。

上游观察为 fixture 数据；证据图构造、规则集与 PyArg 求解为真实代码。本报告展示决策机制，不度量真实视频上的准确率。

求解器：PyArg 2.0.2（python-argumentation）+ NetworkX 3.6.1，语义 `GROUNDED_SKEPTICAL`，回退策略 `fallback=False`。
规则集：`PEAD_DANGER_PROMOTION` v1.1.0，指纹 `eab4e2832518c814…`。

## 1. 同事件：「鼓励」支持论证被「反向语境」击倒

同一事件内既出现鼓励又出现安全提醒，支持与反向语境论证互相攻击。无攻击者的 RELATION_MISSING 先被接受并击倒 LOCAL_PROMOTION，从而防御 COUNTER_CONTEXT，使反向语境论证被接受。

线索：`E01`、`E02`、`E03`

| 论证 | 极性 | 类型 | grounded 标签 | 前提 |
| --- | --- | --- | --- | --- |
| `LOCAL_PROMOTION:["E01","E02"]` | SUPPORT | LOCAL_PROMOTION | **OUT** | E01, E02 |
| `RELATION_MISSING:["E01","E02"]` | UNCERTAINTY | RELATION_MISSING | **IN** | E01, E02 |
| `COUNTER_CONTEXT:["E01","E03"]` | COUNTER | COUNTER_CONTEXT | **IN** | E01, E03 |

攻击关系：

- `COUNTER_CONTEXT:["E01","E03"]` → `LOCAL_PROMOTION:["E01","E02"]`
- `LOCAL_PROMOTION:["E01","E02"]` → `COUNTER_CONTEXT:["E01","E03"]`
- `RELATION_MISSING:["E01","E02"]` → `LOCAL_PROMOTION:["E01","E02"]`

裁决：**CONFLICTED / REVIEW** （`CONFLICTING_STANCE`）

标签统计：{'OUT': 1, 'IN': 2}，存在循环 [['COUNTER_CONTEXT:["E01","E03"]', 'LOCAL_PROMOTION:["E01","E02"]']]

## 2. 跨事件：模型断言同一事件，被结构冲突击倒

解析记录了两个不同事件，模型仍回答 encourages_same。REFERENT_CONFLICT 论证攻击 MODEL_PROMOTION 并将其击倒，因此不采纳模型结论。

线索：`E01`、`E02`

| 论证 | 极性 | 类型 | grounded 标签 | 前提 |
| --- | --- | --- | --- | --- |
| `MODEL_PROMOTION:["E01","E02"]` | SUPPORT | MODEL_PROMOTION | **OUT** | E01, E02 |
| `REFERENT_CONFLICT:["E01","E02"]` | UNCERTAINTY | REFERENT_CONFLICT | **IN** | E01, E02 |

攻击关系：

- `REFERENT_CONFLICT:["E01","E02"]` → `MODEL_PROMOTION:["E01","E02"]`

裁决：**CONFLICTED / REVIEW** （`RELATION_REFERENT_DISAGREEMENT`）

标签统计：{'OUT': 1, 'IN': 1}

## 3. 跨事件：模型的反向论证本身被击倒

模型回答 warns_same，声称警示针对同一事件；但两者事件不同，COUNTER_REFERENT_CONFLICT 成立并击倒 MODEL_COUNTER。此时既无支持也无有效反证，落到保守复核。

线索：`E01`、`E02`

| 论证 | 极性 | 类型 | grounded 标签 | 前提 |
| --- | --- | --- | --- | --- |
| `MODEL_COUNTER:["E01","E02"]` | COUNTER | MODEL_COUNTER | **OUT** | E01, E02 |
| `COUNTER_REFERENT_CONFLICT:["E01","E02"]` | UNCERTAINTY | COUNTER_REFERENT_CONFLICT | **IN** | E01, E02 |

攻击关系：

- `COUNTER_REFERENT_CONFLICT:["E01","E02"]` → `MODEL_COUNTER:["E01","E02"]`

裁决：**INSUFFICIENT / REVIEW** （`MISSING_SEMANTIC_RELATION`）

标签统计：{'OUT': 1, 'IN': 1}

## 4. 无攻击：纯支持（可正常标注关注）

动作与鼓励同属一个事件且无反向语境，支持论证无攻击者，因此被接受并输出关注标注。

线索：`E01`、`E02`、`E03`

| 论证 | 极性 | 类型 | grounded 标签 | 前提 |
| --- | --- | --- | --- | --- |
| `LOCAL_PROMOTION:["E01","E02"]` | SUPPORT | LOCAL_PROMOTION | **IN** | E01, E02 |
| `MODEL_PROMOTION:["E01","E02"]` | SUPPORT | MODEL_PROMOTION | **IN** | E01, E02 |
| `LOCAL_PROMOTION:["E01","E03"]` | SUPPORT | LOCAL_PROMOTION | **IN** | E01, E03 |
| `MODEL_PROMOTION:["E01","E03"]` | SUPPORT | MODEL_PROMOTION | **IN** | E01, E03 |

攻击关系：无（该事件内没有相互冲突的论证）

裁决：**SUPPORTED / FLAG** （`RELATION_LINK_ASSISTED`）

标签统计：{'IN': 4}

## 检查结果

未发现问题。
