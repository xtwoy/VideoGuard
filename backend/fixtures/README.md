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
state["audit_report"]    # 五维度审核报告（可能为 None，见下）
```

`tests/test_fixture_pack.py` 把上述内容接进了单元测试，`python -m unittest discover -s tests -v`
即可防漂移。

## 目录结构

```
fixtures/
├── README.md              本文件
├── cases.py               18 个用例的定义（人类维护的源头）
├── _build.py              构造原语（fact / shot / event / cue / trace …）
├── simulate.py            离线复刻 pipeline._run_models 的编排
├── generate.py            生成静态 JSON（写盘 / --check）
├── validate.py            真实校验 + 期望值核对 + 覆盖矩阵
├── truth_table.py         穷举关系回答组合，输出 PEAD 决策真值表
├── argumentation_report.py 输出论证攻防报告（grounded 标签与攻击边）
├── argumentation_html.py   把同一套场景渲染成自包含 HTML 演示页
├── prompt_contract.py      静态校验 prompt 要求的字段与枚举是否被代码接受
├── upstream_capture.py     采集一次真实上游回包（需密钥，真实调用）
├── upstream_assumptions.py 校验 PEAD 的四项上游输入假设
├── manifest.json          全部用例的索引与结论摘要
└── cases/<case>/          每个用例的静态 JSON
    ├── video_parse_response.json      阶段1 原始回包
    ├── issue_locator_response.json    阶段2 原始回包
    ├── relation_response.json         阶段3 原始回包（有候选对时才生成）
    ├── audit_report_response.json     阶段4 回包（历史冻结；可能含已退役维度）
    ├── expectations.json              人工维护的断言
    └── case.json                      标题、目的、本次运行的实际结论
```

> `demo_video_parse_response.json` / `demo_issue_locator_response.json` 是 `/api/demo`
> 正在使用的旧样例，未纳入本数据集的用例管理。

## 十八个用例

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
| `relation_override_conflict` | 模型对**不同事件**的两条线索硬说 `encourages_same` | **CONFLICTED / REVIEW**（PEAD 否决模型） |
| `relation_wrong_encouragement` | 模型对**安全语境**错误回答 `encourages_same` | CONFLICTED / REVIEW（**证据图增强修复**） |
| `counter_context_tagging` | 同一事件内既有鼓励也有安全提醒，提醒标为 `education_context` | **CONFLICTED / REVIEW**（反证不依赖标注用词） |
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

## PEAD 的覆盖机制与它的上界

这两个用例是整套数据里唯一能回答"**为什么需要 PEAD，而不是直接信大模型**"的证据，
它们是一对对照：

| | `relation_override_conflict` | `relation_wrong_encouragement` |
| --- | --- | --- |
| 片段性质 | 危险动作与鼓励语分属**不同事件** | 安全教育短片，动作与警示**同一事件** |
| `referent_key` | 两条线索不同 → **冲突** | 两条线索相同 → 一致 |
| 模型回答 | `encourages_same`（0.94） | `encourages_same`（0.94） |
| PEAD 结论 | **CONFLICTED / REVIEW** | **CONFLICTED / REVIEW** |
| 判定依据 | `RELATION_REFERENT_DISAGREEMENT`（结构性质疑） | `CONFLICTING_STANCE`（警示与模型判断相互攻击） |

**结论一（能力）：** 当事实解析给出的 `referent_key` 相互冲突时，PEAD 会否决模型的
高置信度回答，只输出"语境冲突、转人工"，而不是给出强提示。模型置信度不能覆盖这一约束。

**结论二（本次修复）：** 显式同事件警示现在构成反向论证，模型自信回答不能消除它；相互攻击无法裁决时转为复核。
仍不能补齐上游没有报告的警示，也不能独立核实原视频。此前将上界写为两个准确率乘积的表述不成立，已经撤销。

## 穷举真值表：PEAD 决策函数的证据

单条用例只能说明"我挑的例子过了"。因为关系回答只有四种取值，每个场景的组合是**可穷举**
的，于是可以不做采样、直接把决策函数的定义域跑完：

```bash
python -m fixtures.truth_table           # 打印；检查全定义/确定性/协议合规/单调保守
python -m fixtures.truth_table --write   # 另写入 reports/pead-truth-table.{md,json}
```

当前覆盖 7 个含候选对的用例、**64 种关系回答组合**。这里上游是 mock 输入，PEAD 与结果
融合是真实代码，因此能证明的是**决策函数本身的性质**：

- **全定义** —— 每种可达组合都能得出结论，不会漏判或抛异常；
- **确定性** —— 同一输入必然得到同一结论（每条组合都跑两遍比对）；
- **符合协议** —— 结论始终是文档化的 judgement / disposition 与已知 reason code；
- **单调保守** —— 把某个回答从 `encourages_same` 弱化，绝不会让结论变强；
- **不依赖标注用词** —— 同一内容标为 `warning` 或 `education_context` 结论一致。

这些检查只覆盖当前用例及枚举范围，不能推出所有可能输入都成立，也不衡量真实视频准确率。

当前规则按论证对象处理：已有独立支持的鼓励关系可保留；另一句话被判断为无关不自动推翻它。相关警示或关系缺口仍可要求复核。

> **真值表不度量准确率。** 上游回答是合成的，因此表里没有任何数字说明 PEAD 对真实视频
> 判断得对不对。那是 H1/H2 要做、且必须用真实视频和人工标注完成的事。

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

## 论证攻防：grounded 语义实际在做什么

`R_DANGER_PROMOTION` 的裁决不是打分或阈值，而是**构造可废止论证、用 grounded
语义求解、再按显式优先级选规则**。生成一份可展示的报告：

```bash
python -m fixtures.argumentation_report           # 打印四个场景的标签与攻击
python -m fixtures.argumentation_report --write   # 写入 reports/pead-argumentation.md
python -m fixtures.argumentation_html             # 写入 reports/pead-argumentation.html
python -m fixtures.argumentation_html --check     # 校验 HTML 与当前模型一致
```

HTML 版由**同一套场景模型**渲染，因此与 markdown 报告不可能不一致；并且是**单文件自包含**：
内联 CSS、内联 SVG 攻击图、**无脚本、无外链、无字体请求**，可以直接双击打开或离线演示
（有测试守住这条约束）。

报告覆盖四种机制形态，每种都验证到 grounded 标签（`IN` / `OUT` / `UNDECIDED`）与攻击边：

| 场景 | 论证与标签 | 说明 |
| --- | --- | --- |
| 同事件「鼓励」vs「反向语境」 | `LOCAL_PROMOTION` **OUT**，`COUNTER_CONTEXT` **IN** | 两个论证互相攻击；反向语境论证没有攻击者，因此被接受，支持论证被击倒。识别出 2-环。 |
| 跨事件：模型断言同一事件 | `MODEL_PROMOTION` **OUT**，`REFERENT_CONFLICT` **IN** | 解析记录两个事件而模型答 `encourages_same`；结构冲突论证击倒模型论证，结论不被采纳。 |
| 跨事件：模型声称警示同源 | `MODEL_COUNTER` **OUT**，`COUNTER_REFERENT_CONFLICT` **IN** | 模型的**反向**论证自己因结构矛盾被击倒，于是既无支持也无有效反证，落到保守复核。 |
| 纯支持、无冲突 | 4 个论证全部 **IN**，攻击 0 条 | 输出关注标注，说明约束不会无故压制正常结论。 |

**这四行是"为什么需要 PEAD 而不是直接信大模型"的可展示证据。** 前三个场景里，
模型的回答都被**结构性约束**否决或降级，而不是被采信。

> grounded skeptical 语义的保守性：奇环会产生 `UNDECIDED`。当前规则集下攻击关系
> 主要是双向的（偶环），因此 `UNDECIDED` 在现有场景中不出现——这是**规则集的保守
> 设计**，不是求解器未生效。`fallback=False` 表示求解失败时不静默降级为"无风险"。

## 上游假设校验：把「合成快照」升级为「真实快照」

整套 fixture 是**冻结上游**的消融实验：事实解析、问题定位、关系核验都是 mock，
只有 PEAD 与报告是真实代码。**这在方法上是合法的**——固定输入、只变一个变量，
还能消除上游随机性。但它有一个前提：**上游被假定为正确**。

而 PEAD 对上游有四项硬假设，fixture 里是我们**替模型满足**的：

| 假设 | PEAD 为什么依赖它 | 不成立时 PEAD 会怎样 |
| --- | --- | --- |
| **A1** 事件带可用 `referent_key` | `SameTarget` 判定 | 无法区分「无关」与「未核验」，只能转人工 |
| **A2** 线索与事件的事件标识一致 | 事件作用域隔离 | 事件错乱，可能把别的场景的警示算到本事件 |
| **A3** 线索引用的事实真实存在 | 证据可追溯 | 视为不可靠证据，保留人工复核 |
| **A4** 解析标记的反向语境进入线索 | 冲突检测 | **看不到反证，把时间接近的鼓励误判为诱导** |

这四项**只有真实模型输出才能验证**，fixture 无论做多细都证明不了。因此提供一个
两段式流程：

```bash
# 1) 采集一次真实回包（需要配置 backend/.env，会真实调用模型）
python -m fixtures.upstream_capture --video samples/mixed.mp4 --title "演示片段"

# 2) 校验四项假设，产出报告
python -m fixtures.upstream_assumptions --write   # 写入 reports/upstream-assumptions.md
python -m fixtures.upstream_assumptions           # 只打印，不写文件
```

`upstream_snapshot.json`（真实回包）**不入库**（见 `.gitignore`），校验报告入库。

### 建议的视频设计（一段就够，自录）

一段短片同时压到四项假设：

1. **两个明显不同的事件**，让事件作用域有东西可分离（A1/A2）；
2. 其中一个事件里，**看起来有风险的动作 + 明确鼓励/挑战的话**，让诱导关系有可能成立；
3. 另一个事件里，**明确的提醒**（"请勿模仿" / "这样很危险"），用于观察反向语境是否被报告（A4）；
4. **只用你自己的声音**，不出现第三方素材，不出现真实个人信息。

### 这个报告能主张什么、不能主张什么

| 可以 | 不能 |
| --- | --- |
| 上游是否满足 PEAD 的输入假设（逐项、带指标） | 准确率 / 误报率 / 召回率 |
| 在**真实回包快照**上做消融对比，不受模型随机性影响 | 任何需要人工标注才能得出的结论 |

报告开头就写明这一点：**它只校验上游假设，不评价 PEAD 的准确率，也不判定视频内容
是否合规**。未通过项会附上影响说明与修复方向——**A1–A4 任一不成立，PEAD 都是退化为
保守复核，而不是编造结论**，所以未通过是可定位的工程问题，不会被静默变成"无风险"。

## Prompt 契约检查：prompt 要的格式，校验器是否真的接受

真实联调最怕的不是模型答得不好，而是**prompt 要的字段校验器不收**——那会让每一条真实
回包都在解析阶段失败，而且只有花了 key 才知道。这类问题可以**静态查出来**：

```bash
python -m fixtures.prompt_contract           # 打印逐项结论
python -m fixtures.prompt_contract --write   # 写入 reports/prompt-contract.md
```

检查三件事，覆盖四个阶段（事实解析 / 问题定位 / 关系核验 / 审核报告）：

1. **字段存在性** —— prompt 模板要求的字段，校验器是否接受；校验器必需的字段，
   prompt 是否要求；
2. **枚举词表** —— prompt 给出的每个取值，代码是否接受（反向缺失按严重程度区分：
   PEAD 依赖的取值缺失才算未通过，PEAD 不依赖的只记为文档缺口）；
3. **协议自洽** —— prompt 内嵌模板与独立 schema 文件描述同一形状。

**当前 34 项全部通过。** 一个已知的文档缺口：`context.target_relation` 代码接受
`SAME_EVENT | DIFFERENT_EVENT | UNCERTAIN`，而 prompt 只说明了 `SAME_EVENT` 与
`UNCERTAIN`。这不影响运行——PEAD 只在 `SAME_EVENT` 时触发匹配——因此记为缺口而非失败。

> 本检查是**静态**的：它保证 prompt 与校验器的契约一致，从而排除"真实调用必然失败"
> 的整类问题。它**不能**证明模型会遵循 prompt——那只能由一次真实调用回答。

## PEAD 的待优化项

按收益排序。已完成两项，其余为**有意未做**或待办，理由一并写明。

1. ~~**关系时间窗与置信度阈值写在三处且互不校验**~~ —— **已完成**（`src/config.py`）。
   原先 `pead_engine.MAX_RELATION_GAP_MS`、`relation_client.RELATION_GAP_MS` 与
   `policies_v03.json` 的 `max_relation_gap_ms` 各一份，配对用一个窗口、判定用另一个，
   漂移后静默失效。现在集中到单一模块，支持环境变量覆盖，配置与生效值不一致时
   **直接报错并说明两种修法**。

2. ~~**反证 provenance 缺失**~~ —— **已完成**。每个 finding 现在带
   `counter_evidence = {checked, source, found, relation_checked}`，
   报告在整改分组下渲染"反证检查"一行。此前 `counter_ids` 为空无法区分
   "检查过且确实没有"与"根本没检查"，现在两者在报告里读起来不同。

3. **关系核验只服务一条策略** —— **评估后有意不做**。
   `relation_fusion.py` 的 `POLICY = "R_DANGER_PROMOTION"` 并非疏漏：只有该策略存在
   "两条线索是否指向同一事件"这一需要核验的二元关系。`R_VIOLENCE` 的 `context_tags`
   只是把处置降级为 REVIEW，`R_PRIVACY_EXPOSURE` / `R_MARKETING_CLAIM` 是单线索，
   其余六条是直接线索——它们没有可核验的语义关系。给它们套上关系核验只会增加
   API 调用而不改变结论。**建议在有真实数据能证明收益之前不做。**

4. **四条策略仍是硬编码分支** —— 待办。`pead_engine.py` 中 R_DANGER_PROMOTION /
   R_VIOLENCE / R_PRIVACY_EXPOSURE / R_MARKETING_CLAIM 为 `if/elif` 硬编码，
   与 `policies_v03.json` 注释所称"扩展审核点不改主流程"不一致。属可维护性问题，
   不影响当前正确性。

## 自查后的输入冻结与生成器约定

模型回包是测试输入，不能随着被测审核引擎改变而自动改成新引擎的输出。既有 `audit_report_response.json` 保持原始字节，SHA-256 记录在 `frozen_report_inputs.json`；变更时必须明确审查输入及其摘要。**注意**：这些回包记录于五维度评分改造之前，其中仍可能包含已退役的电商质量维度（素材完整性、内容结构、开头信息建立、主体展示）。它们不参与报告校验，仅用于漂移检查；当前协议只接受五个安全与证据维度。视频解析、问题定位和关系回包继续由固定场景定义校验。

`generate.build_case()` 和 `--check` 默认只读；只有显式执行生成命令才写可生成文件，且不会重写冻结的报告输入。冻结报告文件丢失或摘要不符时应从版本控制恢复或明确审查更新，不会偷偷生成替代输入。模型回包中的错误检查状态和复核编辑建议由正式报告校验器按 PEAD 结果重建／规范化；原始回包保留以验证这条边界。


## 前端场景演示与截图（2026-10-17）

`fixtures.demo` 从现有冻结样例中选择 8 个场景，经过正式 `pipeline._run_models` 编排，
通过 `GET /api/demo/cases` 与 `POST /api/demo?case={id}` 接入前端。所有记录均为 DEMO，
模拟回包的阶段不会标成 LIVE；各输入文件 SHA-256 随结果保存。

在生产前端与 HTTP 服务启动后，从仓库根目录运行：

```powershell
python -X utf8 backend/fixtures/capture_demo.py
```

生成 `docs/assets/demo/` 的 8 张真实页面截图及 `backend/reports/demo-showcase/` 离线报告集。
运行步骤、场景和演示顺序见 `docs/13_演示场景与截图说明.md`。全程无需 WebSocket 或模型调用。
