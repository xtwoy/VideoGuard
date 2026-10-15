# 新窗口交接入口（v0.6）

请先完整阅读 `docs/00_文档导航与使用说明.md`，再阅读 `docs/01_视频内容安全选题论证与团队讨论.md`、
`docs/02_需求规格说明书.md`、`docs/03_系统设计与工程实现说明.md`、
`docs/04_核心技术与实验验证计划.md` 以及 `docs/05_任务拆分与开发交接说明.md`。

**重要：** 本版不要求撰写参赛作品报告；
保持已有 Next.js 16 前端 + FastAPI + SQLite单表的一条主线架构。v0.6 已修正无 Jev Key 时的语义检查状态，`SKIPPED_NO_KEY` 不应被解释为 API 调用失败。
模型真实接口尚未联调，离线模拟不能冒充实际模型测试。

新AI接手后，先按锁文件安装环境，再运行测试（本轮工程包不包含虚拟环境）：

```bash
cd backend
.venv/Scripts/python.exe -m unittest discover -s tests -v      # 以命令实际输出为准
```

若 `.venv` 不存在或需要重建：

```bash
cd backend
uv sync --locked --python 3.11            # 按 uv.lock 复现已验证的依赖版本
```

**两个环境前提，缺任何一个都会导致"测试全绿但功能不可用"：**

1. `ffprobe` 必须在 PATH（本机已 `winget install Gyan.FFmpeg` 安装）。缺失时真实上传一律 422，而 `test_ffprobe_rejects_invalid_file` 仍会通过——它无法区分"媒体损坏"和"ffprobe 未安装"。
2. 后端运行时，建议用 `tests/smoke_live.py` 做真实 HTTP 冒烟检查（见 README「测试」），它会真实探测时长并验证无密钥时是否 fail-closed。

本次修订已完成失败路径修复与 Mock 同输入有/无 PEAD 对照，详见
`docs/06_Mock验证与失败路径修复.md` 和 `backend/reports/mock-pead-comparison.md`。
在 backend 运行 `python -m fixtures.compare_pead --check` 可验证报告无漂移。
原视频未被实际分析；同一事件的显式警示现已作为反向论证处理，错误鼓励回答会转冲突复核。上游遗漏警示的边界仍存在。

若需要真实链路，再使用真实配置联调视频解析、问题定位、可选关系判断与问题汇总服务，保留PEAD证据约束，
对合法授权视频做对照实验。完整要求请读`docs/05_任务拆分与开发交接说明.md`。

## 证据图增强更新

2026-10-14：危险诱导改为事件级证据图与 grounded 论证裁决，原融合条件分支已替换。
同一事件的显式警示现在会反驳错误鼓励回答；旧版“仍可能 FLAG”的反例记录是历史行为。
来源别名、逐事件判断、论证轨迹和证据移除检验均可查看。请以 `07_PEAD证据图与开源参考.md` 和当前生成结果为准。
仍无法补齐上游遗漏的警示，也不代表真实视频效果已经验证。

## 开源求解与规则工程化更新

当前为 `pead-pyarg-rules-v2`。实际运行依赖 PyArg 与 NetworkX，规则文件通过 Pydantic 校验。请先读 `docs/08_PEAD开源引擎接入与规则工程化.md`。不要恢复旧自研求解器作为隐式回退，也不要把本轮使用的抽象论证功能表述为已接入完整 ASPIC+。规则快照、逐条决策和攻击防御解释均随 HTTP 结果保存。依赖及锁文件必须与代码一同更新。

## 自查修订（接手前必读）

当前引擎 `pead-pyarg-rules-v2.1`、规则 `1.1.0`；以 `docs/09_PEAD自查与缺陷修复.md` 及 `backend/reports/pead-self-review-validation.json` 为当前验证口径。`pead-upgrade-*` 是上轮记录。不得恢复以对象键代替明确事件 ID 的隔离逻辑，也不得把静态判断标为模型关系已核验。新回归保留了此次复现的反例和组合枚举。
