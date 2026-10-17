# VideoGuard-E｜PEAD 开源引擎与规则工程化版

> **2026-10-14 Mock 验证修订：** 已修复问题定位空/缺项/非法回答被当成无风险、关系无效回包错误标记 LIVE，以及关系校验在 `python -O` 下失效的问题。新增同输入有/无 PEAD 对照、输入快照和回归测试。先读 [`docs/06_Mock验证与失败路径修复.md`](docs/06_Mock验证与失败路径修复.md)。本次没有调用真实云端模型，也不声称真实视频准确率改善。
>
> **后续证据图增强：** 危险诱导进入事件级论证裁决，新增来源合并、支持／反驳关系、逐事件结论和证据移除检验；原先同一事件警示被忽略的 Mock 反例已修复。先读 [`docs/07_PEAD证据图与开源参考.md`](docs/07_PEAD证据图与开源参考.md)。

> **本轮开源接入：** PyArg 已进入危险诱导的实际求解路径，NetworkX 提供循环与防御解释，新增可校验的规则文件、优先级、不可变规则快照和决策追踪。运行前重新安装后端依赖，详见 [`docs/08_PEAD开源引擎接入与规则工程化.md`](docs/08_PEAD开源引擎接入与规则工程化.md)。本轮仍是 Mock 验证，未证明真实模型效果提升。

> **自查修订：** 当前引擎为 `pead-pyarg-rules-v2.1`，规则集为 `1.1.0`。已修复事件作用域、未定位警示、配置保护、构图预算及报告一致性问题；最新验证见 [`docs/09_PEAD自查与缺陷修复.md`](docs/09_PEAD自查与缺陷修复.md)。

**团队：小白**（团队形象：<img src="docs/assets/team-mascot.png" alt="小白团队形象" width="220" align="middle">）

> **文档导航：** 本版包含团队讨论和开发文档，**未创建比赛作品报告**。先读[`docs/00_文档导航与使用说明.md`](docs/00_文档导航与使用说明.md)，其中包含：选题论证、PRD、系统设计、创新验证、开发交接。v0.6 使用 Next.js 前端 + FastAPI + SQLite 架构。  
> **团队转发稿：** [`docs/团队立项讨论简报.docx`](docs/团队立项讨论简报.docx)。


**一条主线：视频解析 → 问题定位/关系判断（按需） → 本队PEAD审核 → 问题汇总与整改建议 → SQLite → HTML报告。**

各 AI 阶段按职责命名，具体模型或供应商均通过适配器与环境配置替换，不是系统协议的一部分。

## 当前审核范围

系统目前按十类内容安全风险线索进行审核：危险行为诱导、暴力或危险行为画面、个人隐私暴露、营销及资质声称、自伤风险、性内容风险、仇恨与骚扰、诈骗与高风险诱导、受控商品风险、未成年人保护。所有结果均为辅助审核线索，不能直接替代事实或法律认定。

**十类共用同一套输入与同一份裁决契约，但判断深度不同，不应理解为十类都经过证据论证：**

| 策略 | 判断方式 |
| --- | --- |
| 危险行为诱导 | PEAD 证据图 + 可废止论证 + 关系门控（唯一使用论证求解的策略） |
| 暴力或危险行为画面 | 动作线索 + 同事件语境核对（区分新闻/影视/教育语境） |
| 个人隐私暴露 | 线索 + 模态与时间定位过滤 |
| 营销及资质声称 | 资质线索引向外部核验，营销线索引向人工复核 |
| 其余六类（自伤、性内容、仇恨骚扰、诈骗、受控商品、未成年人保护） | 按配置的线索标签直接映射为判断与处置，不含同事件语境核对 |

因此"覆盖十类"指的是**覆盖十类线索与处置路径**，不等于十类都具备同等的证据关联能力。

专为2026年中国研究生网络安全创新大赛·创意作品赛的短期原型而做。**前后端分离，前端采用 Next.js 16（App Router）+ React 19 + TypeScript + Tailwind CSS 4；不引入复杂后端队列、训练框架或多表关系系统。**

## 目录

```text
VideoGuard-E-v0.6/
├── frontend/
│   ├── app/                     # Next.js App Router 页面与 Tailwind CSS 4
│   ├── package.json             # Next.js 16 / React 19 / TypeScript 依赖
│   ├── package-lock.json        # 前端锁定依赖版本
│   └── .env.example             # NEXT_PUBLIC_API_BASE_URL 示例
├── backend/
│   ├── main.py                  # FastAPI 接口：健康、上传审核、查询、报告、合成示例
│   ├── pipeline.py              # 事实解析→问题定位→PEAD/关系核验→审核报告 单条主线
│   ├── report.py                # 可单独打开和打印的审核报告（五维评分）
│   ├── database.py              # SQLite一张reviews表
│   ├── src/                     # PEAD、结果融合、各阶段适配器、报告校验、脱敏
│   ├── config/policies_v03.json
│   ├── prompts/                 # 各阶段系统提示词与输出协议 schema
│   ├── fixtures/                # 18 个可复用样例用例 + 生成/校验工具
│   ├── tests/                   # 单元测试 + smoke_live.py 真实 HTTP 冒烟检查
│   ├── requirements.txt
│   ├── pyproject.toml            # uv 项目定义（不打包，仅用于锁定依赖）
│   ├── uv.lock                   # 已固定的依赖版本组合
│   └── .env.example
├── docs/assets/                  # 团队形象等文档配图
└── README.md
```

## 快速运行

先安装Python 3.11+、FFmpeg（需要`ffprobe`命令）和Python依赖。

> **已验证的环境**：以下步骤在一个全新克隆、仅有系统 Python 的目录里完整跑通过
> （`uv sync` → 75 项后端测试 → 18 个样例用例 → 真值表 → 端到端冒烟 29 项 →
> `npm ci` → `tsc --noEmit` → `next build`），运行在 **Python 3.11.15** 与 Node 24 上。

### 方式一：uv（推荐，已在本机验证）

```bash
cd backend
uv sync --python 3.11            # 按 uv.lock 创建 .venv 并安装固定版本
copy .env.example .env           # 在 .env 填入当前阶段服务配置
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

> **若 `uv sync` 报 `Failed to parse .../pyproject.toml`**：uv 会从当前目录**向上**
> 查找项目根，如果上级目录里恰好有一个同名文件（例如把仓库克隆到系统临时目录下），
> 它会读到那个文件。把仓库放在一个干净的父目录里即可，或直接把 `backend` 目录作为
> 克隆目标。

`uv.lock` 已固定本机验证通过的版本组合（fastapi 0.143.0 / starlette 1.7.0 / pydantic 2.14.1 / openai 2.54.0 / python-multipart 0.0.32），换机器也能复现同一套依赖。

**已知依赖风险：** 当前 starlette 会对 `httpx` 报 `StarletteDeprecationWarning`（提示改用 `httpx2`）。本版测试全绿，但若日后升级后 `tests/test_mvp.py` 出现 `TestClient` 导入失败，先检查 `httpx`/`starlette` 这一对版本，而不是怀疑业务代码。

**前期 Mock 修订的历史记录：** Python 3.12 按现有 uv.lock 安装依赖后，120 项后端测试与29项真实 HTTP/ffprobe 冒烟通过（未配置真实模型，只验证无密钥失败路径）；前端类型检查通过。生产构建因沙盒 Node 的 `uv_resident_set_memory` 读取报 ENOENT 而未完成，前端源码未修改。详见 `backend/reports/mock-validation-summary.json`。

### 方式二：系统 Python

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

若 Windows 上 `python` 指向不可用的解释器，改用 uv 方式；uv 会把 `ffprobe` 之外的依赖全部装进 `backend/.venv`，不污染系统环境。

**终端2：启动 Next.js 前端**

```bash
cd frontend
npm ci
copy .env.example .env.local
npm run dev -- --hostname 127.0.0.1 --port 5173
```

浏览器访问：`http://127.0.0.1:5173`

`NEXT_PUBLIC_API_BASE_URL` 默认指向 `http://127.0.0.1:8000`。本机出现端口冲突时，也可临时以 `http://127.0.0.1:5173/?api=http://127.0.0.1:8001` 覆盖 API 地址；该覆盖只适用于本地演示，不把密钥交给浏览器。

> **ffprobe 是硬依赖。** 不在 PATH 时，所有真实上传都会以 422 失败（`无法使用ffprobe检查视频`），而单元测试仍可能全绿，容易误判环境正常。Windows 可用 `winget install Gyan.FFmpeg` 安装，或确认 `ffprobe -version` 有输出。

**没有API Key怎么办？** 点击页面上的「查看合成示例」即可验证完整的UI、SQLite记录、风险展示、HTML报告，但该模式**没有分析真实视频，不能用作算法效果证据**。

## 真实视频路径

在`backend/.env`里配置：

```ini
VIDEO_MODEL_API_KEY=当前模型服务的密钥
VIDEO_MODEL_BASE_URL=当前模型服务的 OpenAI 兼容 Base URL
VIDEO_PARSE_MODEL=当前视频解析模型（必填）
ISSUE_LOCATOR_API_KEY=问题定位服务密钥（真实路径必填）
ISSUE_LOCATOR_ENDPOINT=问题定位服务地址（真实路径必填）
ISSUE_LOCATOR_MODEL=问题定位模型标识（真实路径必填）
AUDIT_REPORT_MODEL=当前审核报告模型（可选；未配置或输出无效时使用受约束的本地报告生成器）
RELATION_MODEL_API_KEY=当前关系判断服务的密钥（可选）
RELATION_MODEL_ENDPOINT=当前关系判断服务地址（可选）
RELATION_MODEL_ID=当前关系判断模型标识（可选）
VIDEOGUARD_DB=./data/reviews.db
```

- 首版上传文件：MP4/MOV/WebM、大小不超过6MB、时长不超过3分钟。视频解析阶段使用 OpenAI 兼容接口的本地视频 Base64 输入；超过上限请先合法压缩视频。
- 自动从视频内读取时长，使用`ffprobe`读取容器元数据；**不会额外做OCR、ASR或逐帧推理**。
- 当前适配器可接入视频解析、问题定位、关系判断和审核报告四类能力；关系判断为可选阶段，未配置时系统保守分流并明确标记跳过，不会伪装为接口失败。现行版本不保留旧协议或旧环境变量回退。
- 审核报告阶段只编排既有视频事实与 PEAD 判断，输出五维评分、问题、证据、时间范围、整改动作和验收条件；五个维度分别是审核覆盖、证据可追溯性、风险控制、语境完整性和音视频可读性，全部围绕内容安全与证据可靠性，不评价内容制作质量。总评取最低维度分，作为保守下限而非质量评分。若输出非法或请求失败，使用同一协议的受约束本地报告生成器，不假装 AI 已生成。
- 服务器不会把上传视频二进制保存到SQLite；只保存SHA256、文件名、脱敏模型观察和审核结果。原始视频只留在浏览器本地预览，刷新后无法重新播放旧记录；HTML报告保留证据时间戳及文字说明。
- 只供**单机本地实验**（127.0.0.1），无账号权限、在线公网部署、多人并发队列。不要把API密钥放到前端，素材须有授权；向任何外部模型服务传送数据前需符合隐私/数据合规要求。

## API（最小）

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/health` | 服务可用状态 |
| POST | `/api/reviews` | `multipart/form-data`：`video`、`title`、`consent=true` |
| GET | `/api/reviews/{id}` | 查询SQLite保存的审核结果 |
| GET | `/api/reviews/{id}/report` | 下载单文件HTML报告 |
| POST | `/api/demo` | 离线**合成示例**，非真实视频检测 |

所有AI审核结果都是辅助判断，不是执法认定。**模型观察是机器报告的线索，不等于独立验证后的事实。**

## 测试

在`backend`目录运行（虚拟环境解释器或系统解释器均可）：

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

前端 TypeScript 严格检查和生产构建：

```bash
cd ../frontend
npm ci
npm run lint
npm run build
```

后端测试数量以实际运行输出及 `backend/reports/pead-upgrade-tests.log` 为准：

| 文件 | 项数 | 覆盖 |
| --- | --- | --- |
| `tests/test_mvp.py` | 17 | 四阶段协议：分镜连续编号、FULL 覆盖连续性、画质证据不得跨分镜、问题定位引用校验、关系请求/响应类型、审核报告维度证据、整改计划覆盖、不相连证据范围、内嵌报告模式 |
| `tests/test_http_surface.py` | 19 | HTTP 上传校验、持久化、错误脱敏、HTML 转义，以及空定位回答经过真实管线必须落库 ERROR |
| `tests/test_audit_report_regressions.py` | 14 | 报告引用、维度聚合、未观察模态与反证来源 |
| `tests/test_fixture_pack.py` + `test_event_audit.py` | 14 | 样例回归、十条策略覆盖、真值表与事件级审计 |
| `tests/test_parameters.py` | 12 | 共享阈值、参数来源及策略一致性 |
| `tests/test_locator_failures.py` | 16 | 空/缺项/错类型/非法概率/超时/截断、明确降级、合法否定及 Python 优化模式 |
| `tests/test_mock_comparison.py` | 8 | 同输入、无外部调用、公平控制组、穷举覆盖、反例修复与统计核对 |
| `tests/test_evidence_graph.py` | 20 | Grounded 语义独立穷举核对、来源合并、事件隔离、冲突裁决、证据移除、报告和精简模型输入 |

**Mock 对照复现：** 在 `backend` 运行 `python -m fixtures.compare_pead --write`，生成 `reports/mock-pead-comparison.{md,json,csv}` 与输入快照；`--check` 检查输出无漂移。Windows 可运行 `run_mock_checks.cmd`，Linux/macOS 可运行 `sh run_mock_checks.sh`。完整测试需要先安装项目依赖；对照脚本本身无需 API Key。

**任何实际接入的视频解析、问题定位或问题汇总服务，都必须使用自己的 Key 单独联调。**
`ffprobe` 相关路径由 `tests/smoke_live.py` 覆盖（单元测试中一律打桩，因此套件不需要 ffprobe）。

**端到端冒烟检查（推荐在联调前后各跑一次）**，需要后端已在运行，且依赖系统`ffmpeg`：

```bash
# 终端1：启动后端后
.venv/Scripts/python.exe tests/smoke_live.py --base http://127.0.0.1:8000
```

**样例数据集（无 API Key 也能演示与调试）**，18 个用例覆盖十条风险策略、核心研究场景与关键边界行为：

```bash
.venv/Scripts/python.exe -m fixtures.validate          # 走真实流水线并核对期望值
.venv/Scripts/python.exe -m fixtures.validate --matrix # 查看规则覆盖矩阵
.venv/Scripts/python.exe -m fixtures.generate --check  # 防止样例与用例定义漂移
```

每条样例都送进项目自己的协议校验器，校验不过无法生成，因此样例与协议不会脱节。
详情与已修复缺陷的记录见 [`backend/fixtures/README.md`](backend/fixtures/README.md)。

它用真实 HTTP（非 TestClient）驱动接口，自建一段临时视频，检查：服务可用、合成示例与 HTML 报告内容及信息泄露、上传校验（授权/扩展名/空文件）、真实视频的时长探测、无密钥时是否正确 fail-closed 并落库 ERROR。有可用密钥时，同一脚本会走通真实模型路径。

当前模型服务的接口文档应由实际部署配置维护；不将某一家供应商或模型名称写入流程协议。
