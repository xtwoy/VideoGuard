# VideoGuard-E v0.6｜工程收口与团队文档版
> **文档导航：** 本版包含团队讨论和开发文档，**未创建比赛作品报告**。先读[`docs/00_文档导航与使用说明.md`](docs/00_文档导航与使用说明.md)，其中包含：选题论证、PRD、系统设计、创新验证、开发交接。v0.6 保持原有原生前端 + FastAPI + SQLite 架构，并修正了 Jev 未配置时的降级状态标记。  
> **团队转发稿：** [`docs/团队立项讨论简报.docx`](docs/团队立项讨论简报.docx)。


**一条主线：视频 → Omni观察 → Jev辅助语义判断（有Key且需要时） → 本队PEAD审核 → Qwen Max原因与修改意见 → SQLite → HTML报告。**

## 当前审核范围

系统目前按十类内容安全风险线索进行审核：危险行为诱导、暴力或危险行为画面、个人隐私暴露、营销及资质声称、自伤风险、性内容风险、仇恨与骚扰、诈骗与高风险诱导、受控商品风险、未成年人保护。所有结果均为辅助审核线索，不能直接替代事实或法律认定。

专为2026年中国研究生网络安全创新大赛·创意作品赛的短期原型而做。**前后端分离，不使用React、复杂后端队列、训练框架或多表关系系统。**

## 目录

```text
VideoGuard-E-v0.6/
├── frontend/
│   ├── index.html               # 中文上传与结果页
│   ├── style.css
│   └── app.js                   # 仅通过HTTP API访问后端
├── backend/
│   ├── main.py                  # FastAPI 4个基础接口：健康、上传、查询、报告；外加一个演示接口
│   ├── pipeline.py              # Omni→Jev→PEAD→Max 单条主线
│   ├── report.py                # 可单独打开和打印的HTML报告
│   ├── database.py              # SQLite一张reviews表
│   ├── src/                     # 复用v0.3的PEAD与模型API适配器
│   ├── config/policies_v03.json
│   ├── prompts/
│   ├── tests/                    # 单元测试 + smoke_live.py 真实 HTTP 冒烟检查
│   ├── requirements.txt
│   ├── pyproject.toml            # uv 项目定义（不打包，仅用于锁定依赖）
│   ├── uv.lock                   # 已固定的依赖版本组合
│   └── .env.example
└── README.md
```

## 快速运行

先安装Python 3.11+、FFmpeg（需要`ffprobe`命令）和Python依赖。

### 方式一：uv（推荐，已在本机验证）

```bash
cd backend
uv sync --python 3.11            # 按 uv.lock 创建 .venv 并安装固定版本
copy .env.example .env           # 在 .env 填入有效密钥；Jev 为可选独立密钥
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

**终端2：启动独立前端**

```bash
cd frontend
python -m http.server 5173 --bind 127.0.0.1
```

浏览器访问：`http://127.0.0.1:5173`

> **ffprobe 是硬依赖。** 不在 PATH 时，所有真实上传都会以 422 失败（`无法使用ffprobe检查视频`），而单元测试仍可能全绿，容易误判环境正常。Windows 可用 `winget install Gyan.FFmpeg` 安装，或确认 `ffprobe -version` 有输出。

**没有API Key怎么办？** 点击页面上的「查看合成示例」即可验证完整的UI、SQLite记录、风险展示、HTML报告，但该模式**没有分析真实视频，不能用作算法效果证据**。

## 真实视频路径

在`backend/.env`里配置：

```ini
DASHSCOPE_API_KEY=你自己的百炼密钥
DASHSCOPE_BASE_URL=你自己业务空间所在地域的兼容接口Base_URL
TYPESAFE_API_KEY=你自己的TypeSafe_Jev密钥（可选）
VIDEOGUARD_DB=./data/reviews.db
```

- 首版上传文件：MP4/MOV/WebM、大小不超过6MB、时长不超过3分钟。为了避免OSS对象存储权限开发，Omni使用官网支持的本地视频Base64输入；超过上限请先合法压缩视频。
- 自动从视频内读取时长，使用`ffprobe`读取容器元数据；**不会额外做OCR、ASR或逐帧推理**。
- Omni属于阿里API。TypeSafe Jev属于**另一家厂商**，不能用百炼密钥调用；无Jev Key时系统保守分流，模型状态与语义检查均明确标记`SKIPPED_NO_KEY`，不会伪装为接口失败。
- Qwen Max按需对风险产生原因和修改建议。若其输出非法或请求失败，只用**显式标记的规则模板建议**，不假装Max已生成。
- 服务器不会把上传视频二进制保存到SQLite；只保存SHA256、文件名、脱敏模型观察和审核结果。原始视频只留在浏览器本地预览，刷新后无法重新播放旧记录；HTML报告保留证据时间戳及文字说明。
- 只供**单机本地实验**（127.0.0.1），无账号权限、在线公网部署、多人并发队列。不要把API密钥放到前端，素材须有授权；同时向阿里及TypeSafe传送数据前需符合隐私/数据合规要求。

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

前端JavaScript静态语法检查：

```bash
node --check ../frontend/app.js
```

当前 22 项后端测试覆盖上传大小/格式/时长、未授权上传、无密钥失败、Jev 降级状态、脱敏、模型失败、数据库读写、HTML注入、事件级审计、十类审核策略与页面Demo。**真实阿里Omni、TypeSafe Jev、Qwen Max API还必须用自己的Key另行联调。**

**端到端冒烟检查（推荐在联调前后各跑一次）**，需要后端已在运行，且依赖系统`ffmpeg`：

```bash
# 终端1：启动后端后
.venv/Scripts/python.exe tests/smoke_live.py --base http://127.0.0.1:8000
```

它用真实 HTTP（非 TestClient）驱动接口，自建一段临时视频，检查：服务可用、合成示例与 HTML 报告内容及信息泄露、上传校验（授权/扩展名/空文件）、真实视频的时长探测、无密钥时是否正确 fail-closed 并落库 ERROR。有可用密钥时，同一脚本会走通真实模型路径。

官方API参考：
- [Qwen Omni](https://help.aliyun.com/zh/model-studio/qwen-omni)
- [Qwen3.8 Max](https://help.aliyun.com/zh/model-studio/qwen3-8-max)
- [TypeSafe Jev API](https://docs.typesafe.ai/api)
