# 样例数据集（fixtures）

面向 `backend/` 四个模型阶段协议的可复用 mock 数据。**不调用任何网络**，也不复制流水线的校验逻辑——
每个样例都送进项目自己的校验器（`clean_video_parse`、`clean_issue_locator`、
`relation_client.validate_response`、`validate_audit_report`），校验不过就无法生成。

存在两个目的：

1. **没有 API Key 也能演示和调试**——覆盖核心研究场景与关键边界行为；
2. **把当前实现的真实行为固定下来**——包括下面记录的三个缺陷，修好后测试会主动报错提醒更新。

## 快速使用

```bash
cd backend

python -m fixtures.generate            # 按用例定义重新生成全部 JSON
python -m fixtures.generate --check    # 校验已提交的 JSON 是否与定义一致（防漂移）
python -m fixtures.validate            # 让每个样例走真实流水线，并核对期望值
python -m fixtures.validate --matrix   # 额外打印“哪条规则被哪个样例覆盖”
```

在代码里复用：

```python
from fixtures import cases, validate

state = validate.simulate(                                  # 离线跑完整条链
    validate.load("danger_promotion", "video_parse_response.json"),
    validate.load("danger_promotion", "issue_locator_response.json"),
    cases.DURATION_MS,
    relation_raw=validate.load("danger_promotion", "relation_response.json"),
)
state["findings"]        # PEAD 的十类结论
state["event_findings"]  # 事件级审计记录
state["audit_report"]    # 九维度审核报告（可能为 None，见下）
```

`tests/test_fixture_pack.py` 把上述内容接进了单元测试，`python -m unittest discover -s tests -v`
即可防漂移。

## 目录结构

```
fixtures/
├── README.md              本文件
├── cases.py               9 个用例的定义（人类维护的源头）
├── _build.py              构造原语（fact / shot / event / cue / trace …）
├── simulate.py            离线复刻 pipeline._run_models 的编排
├── generate.py            生成静态 JSON（写盘 / --check）
├── validate.py            真实校验 + 期望值核对 + 覆盖矩阵
├── manifest.json          全部用例的索引与结论摘要
└── cases/<case>/          每个用例的静态 JSON
    ├── video_parse_response.json      阶段1 原始回包
    ├── issue_locator_response.json    阶段2 原始回包
    ├── relation_response.json         阶段3 原始回包（有候选对时才生成）
    ├── audit_report_response.json     阶段4 回包（协议合法；部分用例为 null）
    ├── expectations.json              人工维护的断言
    └── case.json                      标题、目的、本次运行的实际结论
```

> `demo_video_parse_response.json` / `demo_issue_locator_response.json` 是 `/api/demo`
> 正在使用的旧样例，未纳入本数据集的用例管理。

## 九个用例

| 用例 | 覆盖场景 | 期望结论 |
| --- | --- | --- |
| `danger_promotion` | 危险动作＋鼓励模仿，同一事件 | `R_DANGER_PROMOTION` = SUPPORTED / FLAG |
| `warning_context` | 同一危险动作，旁白明确警示不要模仿 | NOT_SUPPORTED / NONE（警示不进入鼓励语义） |
| `unrelated_promotion` | 两条线索指向不同事件，关系服务答 `unrelated` | 目前停在 INSUFFICIENT / REVIEW（见缺陷 B） |
| `unrelated_without_relation_service` | 同上，但没有关系服务 | INSUFFICIENT / REVIEW（保守转人工） |
| `news_violence` | 新闻语境下的冲突画面 | `R_VIOLENCE` = SUPPORTED / REVIEW |
| `privacy_screen_text` | 仅屏幕文字出现疑似手机号 | `R_PRIVACY_EXPOSURE` = SUPPORTED / FLAG |
| `credential_claim` | 自称专业资质＋绝对化营销表述 | `R_MARKETING_CLAIM` = SUPPORTED / VERIFY_EXTERNAL |
| `partial_coverage` | 覆盖 PARTIAL、音轨损坏 | 十类全部 UNKNOWN / RECHECK，**不得判为安全** |
| `clean_negative` | 普通宠物日常，无任何线索 | 十类全部 NOT_SUPPORTED / NONE |

覆盖矩阵（`--matrix`）显示 `R_SELF_HARM`、`R_SEXUAL_CONTENT`、`R_HATE_HARASSMENT`、
`R_FRAUD_SCAM`、`R_CONTROLLED_GOODS`、`R_MINORS_PROTECTION` 目前只由
`partial_coverage` 的 RECHECK 覆盖，**尚无正面用例**——需要时按同样方式补充。

## 三个已固定的缺陷

样例数据不只是"能跑通"，它还固定了当前实现中三个会影响实验结论的问题。修改相关代码后
`tests/test_fixture_pack.py` 会失败并提示更新，这是有意为之。

### 缺陷 A：降级审核报告在"无事件归属"的 finding 上崩溃

`src/audit_report.py` 的 `build_fallback_audit_report` 在构造无 `event_id` 的计划时，
会执行 `ids = [item for item in ids if cues.get(item, {}).get("event_id") == event_id]`。
当 `event_id is None` 时该过滤条件对所有观察都为假，于是证据被清空，产出的计划
`supporting_evidence: []`，随即被 `validate_audit_report` 拒绝，函数改为抛异常。

触发条件很宽：任何 `disposition != NONE` 却没有任何事件归属的 finding。例如

* `MISSING_SEMANTIC_RELATION`（supporting/counter 均为空）→ `unrelated_promotion`；
* 覆盖不完整导致十类全部 `INCOMPLETE_OBSERVATION` → `partial_coverage`。

后果：**覆盖不完整的视频——恰恰是最需要降级路径的场景——会因为降级报告自身崩溃而 500**，
而不是给出"需要补充观察"的报告。`partial_coverage` 用例就是最小复现。

### 缺陷 B：关系服务的 `unrelated` 结论被丢弃

`src/pead_engine.py` 在 `MISSING_SEMANTIC_RELATION` 分支产出的 finding，
`supporting_ids` 与 `counter_ids` 都是空的；而 `src/semantic_fusion.py` 的每个分支
都建立在"pair 的两个证据 id 出现在这两个列表之一"的前提上，因此
`assess_joint` 永远进不了"Jev 判定无关 → 不构成风险"的分支。

`unrelated_promotion` 用例里关系服务给出 `choice=unrelated, confidence=0.94`（`semantic_gate`
也返回 `unrelated`），最终仍是 `INSUFFICIENT / REVIEW`。

这与 `docs/04` 的 H1 直接相关：**在"时间接近但语义无关"这个 PEAD 最该发挥作用的场景上，
当前实现无法把语义否证转成"不成立"，只能转人工复核。** 修好后该用例应回落到
`NOT_SUPPORTED / NONE`。

### 缺陷 C：未评估的维度被给予高分

`src/audit_report.py` 的 `_analysis_dimension` 在某一类分析问题为空时，返回
`status=PASS, score=90, summary="未记录已定位的…问题"`。于是没有任何素材分析证据的
降级报告里，`material_completeness`、`narrative_structure`、`hook_clarity`、
`subject_presentation` 都会拿到 90 分 PASS。

这与 `prompts/audit_report_system.md` 自己的第 25 条要求相矛盾：

> 没有 finding 不等于所有维度满分；分数必须由本维度输入证据决定。

演示态下即可复现（`/api/demo` 的 `audit_report.dimension_scores`）。建议无证据维度改为
`MANUAL_REVIEW` 或明确标注"未评估"，而不是 90 分。

## 扩展方式

1. 在 `fixtures/cases.py` 里按现有模式新增 `_case_xxx()`，并登记进 `CASES`；
2. 跑 `python -m fixtures.generate`，再跑 `python -m fixtures.validate`；
3. 期望值以**实际行为**为准写进 `expectations.json`；若实际行为不符合设计意图，
   在 `what_it_tests` 里写清楚差异，并在本文件"已固定的缺陷"一节记录，不要为了让它通过而改数据。

`expectations.json` 是人工维护的，生成器只负责原样写出；`generate.py` 不会根据运行结果
反推期望值——否则用例就失去断言意义了。
