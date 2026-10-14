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

## 十五个用例

| 用例 | 覆盖场景 | 期望结论 |
| --- | --- | --- |
| `danger_promotion` | 危险动作＋鼓励模仿，同一事件 | `R_DANGER_PROMOTION` = SUPPORTED / FLAG |
| `warning_context` | 同一危险动作，旁白明确警示不要模仿 | NOT_SUPPORTED / NONE（警示不进入鼓励语义） |
| `unrelated_promotion` | 两条线索指向不同事件，关系服务答 `unrelated` | NOT_SUPPORTED / NONE（H1 对照） |
| `unrelated_without_relation_service` | 同上，但没有关系服务 | INSUFFICIENT / REVIEW（保守转人工） |
| `news_violence` | 新闻语境下的冲突画面 | `R_VIOLENCE` = SUPPORTED / REVIEW |
| `privacy_screen_text` | 仅屏幕文字出现疑似手机号 | `R_PRIVACY_EXPOSURE` = SUPPORTED / FLAG |
| `credential_claim` | 自称专业资质＋绝对化营销表述 | `R_MARKETING_CLAIM` = SUPPORTED / VERIFY_EXTERNAL |
| `self_harm_cue` | 口播出现自伤相关线索，未描述实施方法 | `R_SELF_HARM` = SUPPORTED / FLAG |
| `sexual_content_cue` | 屏幕文字出现性暗示内容 | `R_SEXUAL_CONTENT` = SUPPORTED / FLAG |
| `hate_harassment_cue` | 口播出现针对群体的贬损表述 | `R_HATE_HARASSMENT` = SUPPORTED / REVIEW |
| `fraud_scam_cue` | 口播引导参与无法核实的高收益活动 | `R_FRAUD_SCAM` = SUPPORTED / REVIEW |
| `controlled_goods_cue` | 画面展示受控商品并提示可交易 | `R_CONTROLLED_GOODS` = SUPPORTED / REVIEW |
| `minors_protection_cue` | 画面出现疑似未成年人风险线索 | `R_MINORS_PROTECTION` = SUPPORTED / FLAG |
| `partial_coverage` | 覆盖 PARTIAL、音轨损坏 | 十类全部 UNKNOWN / RECHECK，**不得判为安全** |
| `clean_negative` | 普通宠物日常，无任何线索 | 十类全部 NOT_SUPPORTED / NONE |

后六个用例由 `_single_cue_case` 生成，四镜结构完全一致，两个用例之间的差异只有
线索内容与期望策略，便于逐步 diff 阅读。它们的期望处置由
`config/policies_v03.json` 的 `disposition` 决定：`FLAG` 类策略使报告总评为
`BLOCKED`，`REVIEW` 类为 `MANUAL_REVIEW`。

**覆盖矩阵（`--matrix`）现在十条策略全部有用例覆盖，无缺口。**
`python -m unittest` 中的 `test_every_policy_is_exercised_by_some_case`
会守住这一点，另有 `test_studied_risks_have_a_case_beyond_partial_coverage`
确保四条重点风险不只依赖 `partial_coverage` 的 RECHECK。

## 曾经固定的缺陷（均已修复）

样例数据不只是"能跑通"，它还固定过三个会影响实验结论的问题。三者都已修复，
用例继续留在数据集里作为回归保护。

### 缺陷 A（已修复）：降级审核报告在"无事件归属"的 finding 上崩溃

`src/audit_report.py` 的 `build_fallback_audit_report` 在构造无 `event_id` 的计划时，
会执行 `ids = [item for item in ids if cues.get(item, {}).get("event_id") == event_id]`。
当 `event_id is None` 时该过滤条件对所有观察都为假，于是证据被清空，产出的计划
`supporting_evidence: []`，随即被 `validate_audit_report` 拒绝，函数改为抛异常。

触发条件很宽：任何 `disposition != NONE` 却没有任何事件归属的 finding。例如

* `MISSING_SEMANTIC_RELATION`（supporting/counter 均为空）→ `unrelated_*`；
* 覆盖不完整导致十类全部 `INCOMPLETE_OBSERVATION` → `partial_coverage`。

后果：**覆盖不完整的视频——恰恰是最需要降级路径的场景——会因为降级报告自身崩溃而 500**。

修复：全局计划不再按事件过滤证据；仍无证据时以一条真实事实为锚点，并在该证据上
显式写明"没有可直接定位的观察证据"，不再产出空证据的问题条目。
`unrelated_promotion`、`unrelated_without_relation_service`、`partial_coverage`
三个用例现在都能正常出报告。

### 缺陷 B（已修复）：关系服务的 `unrelated` 结论被丢弃

`src/pead_engine.py` 在 `MISSING_SEMANTIC_RELATION` 分支产出的 finding，
`supporting_ids` 与 `counter_ids` 都是空的；而 `src/relation_fusion.py` 的每个分支
都建立在"pair 的两个证据 id 出现在这两个列表之一"的前提上，因此
`assess_joint` 永远进不了"语义核验判定无关 → 不构成风险"的分支。
`unrelated_promotion` 用例里关系服务给出 `choice=unrelated, confidence=0.94`，
最终仍是 `INSUFFICIENT / REVIEW`。

这与 `docs/04` 的 H1 直接相关：**在"时间接近但语义无关"这个 PEAD 最该发挥作用的场景上，
实现无法把语义否证转成"不成立"，只能全量转人工。**

修复：当该策略的全部候选对都被语义核验回答为 `unrelated`、且 PEAD 基线未给出
`SUPPORTED` 时，判为 `NOT_SUPPORTED / NONE`，并把两个线索记为 `counter_ids`
（reason_code `RELATION_UNRELATED_CONFIRMED`），使结论仍然可回溯。

现在两个用例构成对照，可直接作为 H1 的证据：

| 用例 | 关系服务 | `R_DANGER_PROMOTION` 处置 |
| --- | --- | --- |
| `unrelated_promotion` | 回答 `unrelated` | `NOT_SUPPORTED` / `NONE` |
| `unrelated_without_relation_service` | 未配置 | `INSUFFICIENT` / `REVIEW` |

同一份证据，只有"关系服务是否作答"不同，结论就从人工复核变为不成立——
这正是 PEAD 相对"无约束大模型"应有的增量。

### 缺陷 C（已修复）：未评估的维度被给予高分

`src/audit_report.py` 的 `_analysis_dimension` 在某一类分析问题为空时，
一律返回 `status=PASS, score=90`。降级报告里 `material_completeness`、
`narrative_structure`、`hook_clarity`、`subject_presentation` 因此都会拿到 90 分 PASS，
即使模型根本没有对这几个维度给出任何证据。这与
`prompts/audit_report_system.md` 自己的第 25 条要求相矛盾：

> 没有 finding 不等于所有维度满分；分数必须由本维度输入证据决定。

修复：新增 `_evaluated_sections`，只有引用了可追溯证据（`evidence_refs` 或已定位
问题）的分析区块才算"已评估"；已评估且无问题才给 `PASS/90`，未评估则给
`MANUAL_REVIEW/40` 并在摘要中写明"未对…完成评估"。同时

* `build_fallback_audit_report` 在存在未评估维度时总评改为 `MANUAL_REVIEW`，
  不再在维度未被评估的情况下给出 `PUBLISHABLE`；
* `validate_audit_report` 的总评一致性规则接受这一新状态（此前它强制要求
  "无 finding 且覆盖完整 ⇒ PUBLISHABLE"，与上面的结论直接冲突）。

效果：`clean_negative`、`warning_context` 仍为 `PUBLISHABLE`（维度确有证据支撑），
而没有任何内容分析证据的视频不再被"打上 90 分放行"。

## 尚未处理的一致性问题

以下问题在修复 A/C 的过程中观察到，但**未改动**，留待确认：

`build_fallback_audit_report` 的 `audit_coverage` 维度，在某一模态没有任何
已定位事实时，仍然给该模态 100 分 / PASS，摘要却写着"该模态未记录可辨认证据，
不能据此推断不存在内容"。摘要与分数不一致，建议改为与缺陷 C 相同的处理方式：
未记录证据的模态应给 `MANUAL_REVIEW`，而不是 PASS。

## 扩展方式

1. 在 `fixtures/cases.py` 里按现有模式新增 `_case_xxx()`，并登记进 `CASES`；
2. 跑 `python -m fixtures.generate`，再跑 `python -m fixtures.validate`；
3. 期望值以**实际行为**为准写进 `expectations.json`；若实际行为不符合设计意图，
   在 `what_it_tests` 里写清楚差异，并在本文件"已固定的缺陷"一节记录，不要为了让它通过而改数据。

`expectations.json` 是人工维护的，生成器只负责原样写出；`generate.py` 不会根据运行结果
反推期望值——否则用例就失去断言意义了。
