# VideoGuard-E v0.6｜工程收口与团队文档版

**团队：小白**（团队形象：<img src="docs/assets/team-mascot.png" alt="小白团队形象" width="220" align="middle">）

> **文档导航：** 本版包含团队讨论和开发文档，**未创建比赛作品报告**。先读[`docs/00_文档导航与使用说明.md`](docs/00_文档导航与使用说明.md)，其中包含：选题论证、PRD、系统设计、创新验证、开发交接。v0.6 使用 Next.js 前端 + FastAPI + SQLite 架构。  
> **团队转发稿：** [`docs/团队立项讨论简报.docx`](docs/团队立项讨论简报.docx)。


**一条主线：视频解析 → 问题定位/关系判断（按需） → 本队PEAD审核 → 问题汇总与整改建议 → SQLite → HTML报告。**

各 AI 阶段按职责命名，具体模型或供应商均通过适配器与环境配置替换，不是系统协议的一部分。

## 当前审核范围

系统目前按十类内容安全风险线索进行审核：危险行为诱导、暴力或危险行为画面、个人隐私暴露、营销及资质声称、自伤风险、性内容风险、仇恨与骚扰、诈骗与高风险诱导、受控商品风险、未成年人保护。所有结果均为辅助审核线索，不能直接替代事实或法律认定。

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
│   ├── report.py                # 可单独打开和打印的九维度审核报告
│   ├── database.py              # SQLite一张reviews表
│   ├── src/                     # PEAD、结果融合、各阶段适配器、报告校验、脱敏
│   ├── config/policies_v03.json
│   ├── prompts/                 # 各阶段系统提示词与输出协议 schema
│   ├── fixtures/                # 9 个可复用样例用例 + 生成/校验工具
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

### 方式一：uv（推荐，已在本机验证）

```bash
cd backend
uv sync --python 3.11            # 按 uv.lock 创建 .venv 并安装固定版本
copy .env.example .env           # 在 .env 填入当前阶段服务配置
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

`uv.lock` 已固定本机验证通过的版本组合（fastapi 0.143.0 / starlette 1.7.0 / pydantic 2.14.1 / openai 2.54.0 / python-multipart 0.0.32），换机器也能复现同一套依赖。

**已知依赖风险：** 当前 starlette 会对 `httpx` 报 `StarletteDeprecationWarning`（提示改用 `httpx2`）。本版测试全绿，但若日后升级后 `tests/test_mvp.py` 出现 `TestClient` 导入失败，先检查 `httpx`/`starlette` 这一对版本，而不是怀疑业务代码。

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
VIDEO_PARSE_MODEL=当前视频解析模型（可选，适配器默认值可覆盖）
AUDIT_REPORT_MODEL=当前审核报告模型（可选；未配置或输出无效时使用受约束的本地报告生成器）
RELATION_MODEL_API_KEY=当前关系判断服务的密钥（可选）
RELATION_MODEL_ENDPOINT=当前关系判断服务地址（可选）
RELATION_MODEL_ID=当前关系判断模型标识（可选）
VIDEOGUARD_DB=./data/reviews.db
```

- 首版上传文件：MP4/MOV/WebM、大小不超过6MB、时长不超过3分钟。视频解析阶段使用 OpenAI 兼容接口的本地视频 Base64 输入；超过上限请先合法压缩视频。
- 自动从视频内读取时长，使用`ffprobe`读取容器元数据；**不会额外做OCR、ASR或逐帧推理**。
- 当前适配器可接入视频解析、问题定位、关系判断和审核报告四类能力；关系判断为可选阶段，未配置时系统保守分流并明确标记跳过，不会伪装为接口失败。现行版本不保留旧协议或旧环境变量回退。
- 审核报告阶段只编排既有视频事实与 PEAD 判断，输出九维评分、问题、证据、时间范围、整改动作和验收条件；评分覆盖审核/证据/安全/语境，以及素材完整性、结构、开头信息建立、主体展示和音画可读性。若输出非法或请求失败，使用同一协议的受约束本地报告生成器，不假装 AI 已生成。
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

后端测试当前 52 项，分四部分：

| 文件 | 项数 | 覆盖 |
| --- | --- | --- |
| `tests/test_mvp.py` | 17 | 四阶段协议：分镜连续编号、FULL 覆盖连续性、画质证据不得跨分镜、问题定位引用校验、关系请求/响应类型、审核报告维度证据、整改计划覆盖、不相连证据范围、内嵌报告模式 |
| `tests/test_http_surface.py` | 18 | HTTP 接口与失败路径：上传校验（授权/空文件/扩展名/容器签名/6MB 边界）、文件名净化、成功落库与 SHA256、模型失败必须落 ERROR 且不得读成安全、错误摘要不泄露密钥、失败记录仍可导出报告、HTML 转义 |
| `tests/test_audit_report_regressions.py` | 10 | 已修复缺陷的回归：无事件归属的 finding 仍能出报告、每个问题都带证据、父维度必须聚合子项、未观察模态不得评为通过、未评估维度阻止可发布结论 |
| `tests/test_fixture_pack.py` + `test_event_audit.py` | 7 | 样例数据集回归与事件级审计 |

**任何实际接入的视频解析、问题定位或问题汇总服务，都必须使用自己的 Key 单独联调。**
`ffprobe` 相关路径由 `tests/smoke_live.py` 覆盖（单元测试中一律打桩，因此套件不需要 ffprobe）。

**端到端冒烟检查（推荐在联调前后各跑一次）**，需要后端已在运行，且依赖系统`ffmpeg`：

```bash
# 终端1：启动后端后
.venv/Scripts/python.exe tests/smoke_live.py --base http://127.0.0.1:8000
```

**样例数据集（无 API Key 也能演示与调试）**，9 个用例覆盖核心研究场景与关键边界行为：

```bash
.venv/Scripts/python.exe -m fixtures.validate          # 走真实流水线并核对期望值
.venv/Scripts/python.exe -m fixtures.validate --matrix # 查看规则覆盖矩阵
.venv/Scripts/python.exe -m fixtures.generate --check  # 防止样例与用例定义漂移
```

每条样例都送进项目自己的协议校验器，校验不过无法生成，因此样例与协议不会脱节。
详情与已修复缺陷的记录见 [`backend/fixtures/README.md`](backend/fixtures/README.md)。

它用真实 HTTP（非 TestClient）驱动接口，自建一段临时视频，检查：服务可用、合成示例与 HTML 报告内容及信息泄露、上传校验（授权/扩展名/空文件）、真实视频的时长探测、无密钥时是否正确 fail-closed 并落库 ERROR。有可用密钥时，同一脚本会走通真实模型路径。

当前模型服务的接口文档应由实际部署配置维护；不将某一家供应商或模型名称写入流程协议。
