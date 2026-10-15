# PEAD 开源引擎接入与规则工程化

本轮在上传的 `VideoGuard-PEAD-graph.zip` 上继续升级。危险行为诱导的引擎标识为 `pead-pyarg-rules-v2.1`，默认规则集为 `PEAD_DANGER_PROMOTION / 1.1.0`。

## 实际复用了什么

| 组件 | 实际调用 | 业务作用 |
| --- | --- | --- |
| PyArg / `python-argumentation==2.0.2` | `AbstractArgumentationFramework`、`Argument`、`Defeat`、`get_grounded_extension` | 生产审核路径实际调用开源 grounded 求解器，替换上一轮自研固定点内核 |
| `networkx==3.6.1` | `DiGraph`、`strongly_connected_components`、前驱/后继查询、弱连通分量统计 | 提取循环争议组、攻击者、已采纳的防御者，形成可核查的解释 |
| `pydantic>=2.7,<3` | 冻结模型、字段约束、整体校验 | 校验规则文件，拒绝未知条件、重复编号、歧义优先级及非法资源预算 |

这些组件已加入 `requirements.txt`、`pyproject.toml` 和 `uv.lock`，并在锁定环境下运行测试。PyArg 或其他必需组件缺失时，启动会明确失败，不会悄悄回到旧引擎。第三方信息见根目录 `THIRD_PARTY.md`。

本轮使用 PyArg 的抽象论证功能，**没有接入其 ASPIC+ 规则语言**。配置规则执行器、视频证据映射、来源合并、事件隔离和处置聚合属于项目代码。不能把整个 PEAD 称为 PyArg，也不能把标准 grounded 语义宣称为原创算法。

## 工程结构与职责

- `src/argumentation.py`：将稳定字符串 ID 转为 PyArg 对象，调用求解器，再用 NetworkX 生成解释；不包含旧版求解算法。
- `src/pead_rules.py`：读取并校验规则配置，生成不可变快照、规范化 SHA-256 指纹和规则命中轨迹。
- `config/pead_rules_v1.json`：定义论证生成规则、处置规则、优先级与求解规模预算。
- `src/evidence_graph.py`：围绕视频事件和动作构图，连接支持、反向语境与不确定论证，按配置裁决并执行有界的证据移除检验。
- `src/pead_engine.py`、`src/relation_fusion.py`：基线、关系融合及移除检验共享同一次评估的规则快照。
- `report.py`：输出采纳／反驳／未决的依据、命中规则、循环争议组和规则指纹。
- `main.py`：加载时校验默认配置；健康接口返回真实组件版本与当前规则指纹。

## 规则如何工作

规则条件只能使用预定义的布尔事实，支持 `all_of`、`any_of`、`none_of`。不接受 Python 表达式或脚本。配置来自本地工程文件，不接受外部模型生成的规则代码。

论证规则先按 `scope` 区分动作、已定位证据对、未定位证据对，再匹配事件指向、标签、冻结模型关系和定位质量。每个论证保留 `rule_ids`、原始证据 ID、来源引用、事件和目标动作。论证类型固定映射为支持、反向或不确定信息，模型回答不计为独立视频事实。

处置规则记录全部匹配结果，以最高优先级的规则决定结果。失败守护优先于普通判断；已经被采纳的支持论证可形成风险提示；存在未决的支持／警示冲突时转人工。配置中的优先级用于选择**处置规则**，不替代或加权修改 grounded 论证语义。

例如，同一动作存在明确警示，而模型回答“鼓励同一动作”：警示论证与模型支持论证相互攻击，PyArg 保留未决；处置轨迹显示冲突规则命中，最终进入人工复核。另一事件的警示不会攻击当前事件的论证。

## 配置修改与防误配

修改 `backend/config/pead_rules_v1.json` 后，更新规则集版本并执行全部检查。服务加载时校验配置，每次顶层评估读取一次；评估过程中不会重新读取文件。正在进行的评估使用旧快照，后续评估使用新快照。重启服务可在接收请求前重新验证配置。

配置可收紧支持论证的条件、增加保守规则并调整合法范围内的处置优先级；警示和不确定性生成规则受保护，不能通过改条件绕过。明确约束如下：

- 规则 ID 必须唯一；处置优先级不能相同；必须覆盖已定义论证类型和最低优先级的默认处置。
- 服务不可用、证据无效、求解超限等守护不能删除或降到普通判断之后。
- 冲突、信息缺口和覆盖不完整的保守处置不能删除或改成放行。
- `FLAG` 规则必须要求存在已采纳支持；其他 `NONE` 规则必须排除支持与信息缺口，并置于保守处置之后。
- 错误 JSON、未知条件、未知字段、非法预算立即报错，不加载一份替代默认配置掩盖问题。

这些约束防止常见误配置，不代表任意改写规则后仍能自动保证业务语义正确。论证匹配条件变更仍需要用例审查与回归。

## 输出与失败路径

`pead_audit` 新增：

| 字段 | 含义 |
| --- | --- |
| `solver` | 实际 PyArg / NetworkX 组件版本及不启用旧引擎回退的声明 |
| `ruleset` | 规则集 ID、版本和规范化 SHA-256 指纹 |
| `rule_firings` | 规则、事件、论证和事实前提的对应关系 |
| `event_decisions[].decision_trace` | 事实取值、所有规则的匹配结果及最终选中的规则 |
| `event_decisions[].argument_labels` | 开源求解结果、循环组、攻击／防御见证及是否执行求解 |
| `arguments[].explanation` | 当前论证为何被采纳、被反驳或保持未决 |
| `counterfactuals[].ruleset_sha256` | 证据移除时复用的同一规则快照 |
| `counterfactuals_skipped_reason` | 超出预算而跳过移除检验的明确原因 |

默认预算在构图时逐条执行，是每事件论证数与攻击边数上限，以及每次评估的单证据移除次数上限。资源守护不代表整个视频流水线具有硬实时或恒定内存保证。

超限事件输出 `INSUFFICIENT / REVIEW / ARGUMENTATION_RESOURCE_LIMIT`，不调用 PyArg、不生成采纳证书，并跳过本次证据移除检查。未知求解错误继续抛给既有失败处理：真实上传返回错误并保存失败记录，不能伪装成无风险。其他独立事件的已支持风险仍会保留。

## 复现方式（PowerShell，每条命令一行）

在仓库根目录安装并切换到后端：

```powershell
python -m pip install -r backend/requirements.txt
Set-Location backend
python -m unittest discover -s tests -v
python -m fixtures.validate
python -m fixtures.generate --check
python -m fixtures.truth_table
python -m fixtures.compare_pead --check
```

有 uv 时，也可在后端目录执行 `uv sync --locked --python 3.11`，再用 `uv run --no-sync python ...` 运行相应检查。测试输出是实际数量的依据。

启动服务后，`GET /api/health` 可查看 `pead.solver` 与 `pead.ruleset_sha256`。`POST /api/demo` 的 JSON、记录查询和 HTML 报告均保留同一份图和规则信息。

报告示例为 `backend/reports/pead-graph-demo.html` 与 `pead-graph-warning-regression.html`。测试记录和验证汇总为 `pead-self-review-tests.log`、`pead-self-review-validation.json`（`pead-upgrade-*` 为上一轮历史记录）。原有 Mock 对照和穷举结果已用新引擎重新生成。

## 本次验证能说明什么

- 同一份上传工程中的原始模型 Mock 回包保持不变；升级前后逐项比较已有场景的业务结论，避免通过改输入制造提升。
- 原有三节点攻击图穷举继续用独立的 complete extensions 求交集作为对照，此次实际接受核对的是 PyArg 适配结果。
- 新增测试验证实际求解器调用、无静默回退、循环与防御依据、规则变更生效、不可变快照、配置拒绝、资源边界、HTTP 保存和导出。
- 锁定环境已运行检查；Python 3.11 语法兼容性单独检查。实际执行的 Python 版本以汇总文件为准，不把语法检查冒充另一解释器上的运行测试。

本轮属于可复用组件接入和规则工程升级，未调用真实模型，未验证真实视频识别准确率，也不能补齐上游遗漏的警示。前端源码没有改动，Windows 上的启动和打包仍需在目标机器验证。

## 官方资料

- PyArg 文档：https://daphneodekerken.github.io/PyArg/
- PyArg 抽象论证 API：https://daphneodekerken.github.io/PyArg/abstract_examples.html
- PyArg 源码与许可：https://github.com/DaphneOdekerken/PyArg
- NetworkX 强连通分量：https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.strongly_connected_components.html
- Pydantic 模型配置：https://docs.pydantic.dev/latest/api/config/

## 自查修订

本轮针对上一版实际反例继续修复。事件优先使用观察中的明确 `event_id`，不再把同一对象等同同一事件；仅用于内部旧式测试的纯 `referent_key` 输入仍可运行，两种作用域不能混用。未定位的同事件警示保留为信息缺口；模型反向关系也需校验事件指向。

关系核验状态区分未要求、未检查、部分完成、全部完成和构图未完成；报告中的反证状态由领域 finding 重建，模型不能覆盖。人工复核类 finding 的动作归一为人工复核，所有需处理事件必须进入相应计划。证据移除结果分别报告整体处置和事件变化。

模型回包作为冻结输入保留，生成器检查不再改写它们。详情与反例见 `09_PEAD自查与缺陷修复.md`。
