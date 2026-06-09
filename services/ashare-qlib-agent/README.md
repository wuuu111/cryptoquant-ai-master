# Fund Rotation Agent

一个面向个人使用的基金 / ETF 轮动 Agent。当前主线已经切到基金，不再把原始股票量化流水线作为默认入口。

核心流程是：

1. 用 `AkShare` 抓基金列表、净值 / ETF 日线、申赎状态、基准指数
2. 选择性落地为本地 CSV 与 PostgreSQL
3. 计算基金特征和因子分数
4. 输出带 Agent 解释、风险审查和调仓建议的日频 cycle

## 我应该怎么用

最推荐的使用方式分两种：

1. 本地可复验模式
- 不依赖真实 PostgreSQL
- 用本地样例基金数据 + SQLite
- 适合第一次启动、联调前后端、演示页面

2. 真实数据模式
- 用 `AkShare` + 本地 PostgreSQL
- 适合你每天真正跑一次同步、查看建议、留存 cycle

如果你只是想先把工具跑起来，先走“本地可复验模式”。

当前仓库默认启动已经切到真实基金数据配置 `config.real-local.yaml`。也就是说，不显式传 `--config`、不显式设置 `FUND_AGENT_CONFIG` 时，会默认走 `AkShare + 本地 SQLite` 这条路径。

## 快速开始

先安装环境：

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
conda create -p .conda python=3.10 -y
.conda/bin/python -m pip install -e ".[api,research,storage,dev]"
cd frontend
npm install
cd ..
```

### 方式 A: 本地可复验模式

这条路径已经验证过，适合先确认 CLI、后端接口和前端页面都能工作。

1. 生成本地样例基金数据

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m ashare_qlib_agent.cli --config config.local-verify.yaml sample-fund-data
```

2. 把样例数据写入本地 SQLite，并生成一轮最新 cycle

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python - <<'PY'
import pandas as pd
from ashare_qlib_agent.settings import RuntimeSettings
from ashare_qlib_agent.fund_data_loader import FundDataLoader
from ashare_qlib_agent.fund_store import FundStore
from ashare_qlib_agent.fund_live_cycle import cycle_from_settings

settings = RuntimeSettings.load("config.local-verify.yaml")
bundle = FundDataLoader(settings.data_dir, settings.fund_data).load()
store = FundStore.from_settings(settings)
report = {
    "as_of": str(pd.to_datetime(bundle.fund_nav["date"]).max().date()),
    "fund_count": int(bundle.fund_pool["fund_code"].nunique()),
    "nav_rows": int(len(bundle.fund_nav)),
    "benchmark_rows": int(len(bundle.benchmark)),
    "files": [],
    "skipped": [],
}
store.write_sync_data(bundle.fund_pool, bundle.fund_nav, bundle.fund_metadata, bundle.benchmark, report)
cycle = cycle_from_settings(settings)
print(cycle["cycle_id"])
PY
```

3. 启动后端

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
FUND_AGENT_CONFIG=config.local-verify.yaml ./.conda/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8710
```

4. 启动前端

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

5. 打开页面

- 前端: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- 后端健康检查: [http://127.0.0.1:8710/health](http://127.0.0.1:8710/health)

这时你会看到：

- 首页“今日建议”
- 金额优先的调仓建议卡
- 精简多 agent 决策链
- “我的基金”页中的持仓对比、候选基金和完整协作时间线

### 方式 B: 真实数据模式

如果你要每天真正使用，建议走这条：

1. 设置本地 PostgreSQL 连接串

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
export FUND_POSTGRES_DATABASE_URL='postgresql+psycopg://postgres:password@127.0.0.1:5432/postgres'
export FUND_AGENT_CONFIG=config.postgres.yaml
```

`config.postgres.yaml` 里现在还有两段和个人使用直接相关：

```yaml
account:
  default_account_id: default
  base_currency: CNY

fund_graph:
  enabled: true
  llm_enabled: true
```

- `account.default_account_id`：默认账户 ID
- `fund_graph.llm_enabled`：是否启用 graph 工作流里的 LLM 协作层

2. 跑一次真实验证

```bash
./.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml verify-postgres
```

3. 启动后端

```bash
FUND_AGENT_CONFIG=config.postgres.yaml ./.conda/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8710
```

4. 启动前端

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

5. 每日使用

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
./.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml run-scheduler --run-once
./.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml latest-cycle
```

或者直接在前端里点击“跑一轮今日周期”。

6. 第一次进入页面后，先去“我的基金”页做账户初始化

- 输入你的 `目标总资产`
- 输入你的 `现金余额`
- 点击 `保存账户口径`

保存后，系统会把这份账户账本作为默认预算口径。之后：

- 首页“跑一轮今日周期”会按这份账户预算生成调仓建议
- “一键调仓”会把建议写入本地账本，不会直连券商
- “手工记账”支持按基金代码录入 `BUY / SELL`
- 收益、现金、持仓和交易流水会一起更新

### 方式 C: 个人部署模式

如果你已经进入长期使用阶段，更推荐这一条。它的目标不是“开发联调”，而是把前后端和 SQLite 持久化到一台自己的机器里。

默认提供的是：

- 前端静态站点 + 反向代理
- 后端 `FastAPI`
- 本地 SQLite 持久化
- `data / registry / orders` 目录挂载

启动步骤：

1. 准备部署环境变量

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent
cp .env.deploy.example .env.deploy
```

2. 按需修改 `.env.deploy`

- `FUND_AGENT_HTTP_PORT`：对外访问端口，默认 `8780`
- `ASHARE_LLM_API_KEY`：如果你想保留 LLM 解释层，就填这里
- `FUND_AGENT_CONFIG`：默认就是 `config.personal.example.yaml`

3. 启动部署

```bash
docker compose -f docker-compose.personal.yml up -d --build
```

4. 打开页面

- 前端: [http://127.0.0.1:8780](http://127.0.0.1:8780)
- 后端健康检查: [http://127.0.0.1:8780/api/health](http://127.0.0.1:8780/api/health)

说明：

- 默认配置文件是 `config.personal.example.yaml`
- 数据会持久化到宿主机的 `data/`、`registry/`、`orders/`
- 如果你希望每天自动跑一轮，把 `config.personal.example.yaml` 里的 `scheduler.enabled` 改成 `true`
- 前端部署和本地开发现在都统一走 `/api`，不需要再单独传 `VITE_API_BASE`

## 每天怎么操作

个人使用时，推荐就是这 4 步：

1. 启动后端
2. 启动前端
3. 第一次先到“我的基金”页保存账户总资产和现金
4. 回到首页看“今日建议”，需要时点“跑一轮今日周期”

然后看这几个区域：

- 首页顶部：今天到底要不要调仓
- 建议卡：先看金额，再看目标权重和原因
- 建议卡里的 `一键调仓`：把本条建议写入本地账本
- 风险审查：有没有阻断项
- 我的基金：当前持仓 vs 目标组合、收益、交易流水
- 手工买卖入口：通过基金代码手工补记 `BUY / SELL`
- 完整多智能体协作：市场判断、评分、组合、风控、复核是怎么串起来的

## CLI 使用说明

最常用命令有这几个：

```bash
cd /Users/wuuu/Downloads/cryptoquant-ai-master/services/ashare-qlib-agent

# 生成本地样例数据
./.conda/bin/python -m ashare_qlib_agent.cli --config config.local-verify.yaml sample-fund-data

# 真实 AkShare 同步
./.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml sync-fund-data

# 看基金特征快照
./.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml fund-features --limit 10

# 跑一轮基金 cycle
./.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml fund-cycle --account-id default

# 读最近一轮 cycle
./.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml latest-cycle

# 运行一次定时任务逻辑
./.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml run-scheduler --run-once --account-id default
```

说明：

- `fund-cycle` 在启用数据库后，会优先读取 PostgreSQL 里的账户账本，而不是要求你手工传 `portfolio-file`
- `fund-cycle` 和 `run-scheduler` 都支持 `--account-id`
- `portfolio-file` 仍然保留，主要用于测试、对比或临时覆盖

## 当前主入口

CLI:

```bash
.conda/bin/python -m ashare_qlib_agent.cli sync-fund-data
.conda/bin/python -m ashare_qlib_agent.cli fund-features --limit 10
.conda/bin/python -m ashare_qlib_agent.cli fund-cycle --portfolio-file examples/fund_portfolio.json
.conda/bin/python -m ashare_qlib_agent.cli latest-cycle
.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml verify-postgres
.conda/bin/python -m ashare_qlib_agent.cli run-scheduler --run-once
```

HTTP:

```bash
python app/stdlib_server.py --port 8710
```

FastAPI:

```bash
uvicorn app.main:app --reload --port 8710
```

Docker Compose:

```bash
docker compose -f docker-compose.personal.yml up -d --build
docker compose -f docker-compose.personal.yml logs -f
docker compose -f docker-compose.personal.yml down
```

如果你想显式固定默认配置文件，可以先设置：

```bash
export FUND_AGENT_CONFIG=config.real-local.yaml
```

如果走本地 PostgreSQL 路线，建议改成：

```bash
export FUND_POSTGRES_DATABASE_URL='postgresql+psycopg://postgres:password@127.0.0.1:5432/postgres'
export FUND_AGENT_CONFIG=config.postgres.yaml
```

## 本地依赖

建议环境：

```bash
conda create -p .conda python=3.10 -y
.conda/bin/python -m pip install -e ".[api,research,dev]"
```

如果要连接 PostgreSQL：

```bash
.conda/bin/python -m pip install -e ".[api,research,storage,dev]"
```

`sync-fund-data` 依赖外网访问 `AkShare` 上游接口。离线演示可以先生成本地样例数据：

```bash
.conda/bin/python -m ashare_qlib_agent.cli --config config.example.yaml sample-fund-data
```

## 生成的数据文件

同步或样例生成后，主流程读取以下文件：

- `data/fund_pool.csv`
- `data/fund_nav_daily.csv`
- `data/fund_metadata.csv`
- `data/benchmark_index.csv`

启用 `database.enabled=true` 后，同步结果还会写入 PostgreSQL，`fund-features`、`fund-cycle` 和 `latest-cycle` 会优先从数据库读取。

## 账户、收益和 LLM 说明

当前个人使用的主口径是 PostgreSQL 账本：

- `GET/POST /account`
- `GET /positions`
- `GET/POST /trades`
- `POST /suggestions/{suggestion_id}/apply`

含义如下：

- `account`：你的总资产基线和现金余额
- `positions`：当前基金持仓快照
- `trades`：手工买卖和一键调仓都会写这里
- 收益：按交易流水计算 `累计投入 / 当前总资产 / 已实现收益 / 未实现收益 / 总收益率`

LLM 说明：

- 当前基金主流程使用旧的 `llm.py + collaboration.py + graph workflow` 做解释、批评和 Supervisor 裁决
- 硬风控和账本更新仍然是确定性规则，不允许 LLM 绕过
- 如果没有配置 `ASHARE_LLM_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`，系统会自动退回规则 fallback
- 如果 LLM 连接超时，本轮 cycle 会快速降级，不会一直把前端刷新按钮卡住

## 可用命令

`sample-fund-data`
- 生成一套本地可直接运行的基金样例 CSV

`sync-fund-data`
- 从 `AkShare` 抓基金和基准数据，并按配置写入本地 CSV / PostgreSQL

`fund-features`
- 查看最新一日的基金特征快照

`fund-cycle`
- 生成日频基金投研结果、Agent 解释、风险审查和调仓建议

`latest-cycle`
- 读取最近一次持久化的 cycle 结果

`run-scheduler`
- 运行定时任务，可 `--run-once` 单次执行，也可常驻按间隔运行

`serve`
- 启动 fund-only 的标准库 HTTP 服务

## 持仓文件

`fund-cycle` 支持读取你的当前持仓：

```bash
.conda/bin/python -m ashare_qlib_agent.cli \
  --config config.real-local.yaml \
  fund-cycle \
  --portfolio-file examples/fund_portfolio.json
```

样例文件：

- `examples/fund_portfolio.json`
- `examples/fund_cycle_request.json`

## 配置

默认配置在：

- `config.real-local.yaml`
- `config.example.yaml`
- `config.fund.example.yaml`
- `config.postgres.yaml`
- `config.local-verify.yaml`
- `config.personal.example.yaml`

关键字段：

- `start_date`: 抓历史净值起点
- `fund_data.benchmark_index_code`: 基准指数代码，默认 `000300`
- `fund_data.fund_codes`: 指定只抓这几个基金
- `fund_data.fund_type_keywords`: 不指定基金代码时，用类型关键字筛选基金
- `fund_data.max_funds`: 最多抓多少只基金
- `fund_data.portfolio_mode`: `conservative / balanced / aggressive`
- `database.url`: PostgreSQL 连接串，例如 `postgresql+psycopg://postgres:password@127.0.0.1:5432/postgres`
- `database.mirror_csv`: 启用数据库后是否继续保留 CSV 镜像
- `scheduler.interval_minutes`: 定时任务间隔
- `scheduler.sync_before_cycle`: 定时任务是否先同步 AkShare
- `scheduler.portfolio_file`: 定时任务使用的持仓 JSON
- `config.postgres.yaml` 支持 `${FUND_POSTGRES_DATABASE_URL}` 这类环境变量占位符

## 本地 PostgreSQL 验证

建议先导出环境变量：

```bash
export FUND_POSTGRES_DATABASE_URL='postgresql+psycopg://postgres:password@127.0.0.1:5432/postgres'
export FUND_AGENT_CONFIG=config.postgres.yaml
```

然后运行：

```bash
.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml verify-postgres
```

这个命令会执行：

- 真实 AkShare 同步
- 真实 PostgreSQL 落库
- 真实 `fund-cycle`
- `latest-cycle` 回读
- 数据表行数核验

如果只想复验数据库读写和 cycle，不重新抓 AkShare：

```bash
.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml verify-postgres --skip-sync
```

要跑真实定时任务：

```bash
.conda/bin/python -m ashare_qlib_agent.cli --config config.postgres.yaml run-scheduler --run-once
```

## HTTP 接口

`GET /health`

`GET /fund-features`

`GET /latest-cycle`

`POST /sync-fund-data`

请求体示例：

```json
{
  "config_path": "config.real-local.yaml",
  "start_date": "20240101",
  "end_date": "20260603"
}
```

`POST /fund-cycle`

请求体示例：

```json
{
  "config_path": "config.real-local.yaml",
  "portfolio": {
    "cash": 150000,
    "equity": 500000,
    "positions": [
      {
        "symbol": "EQCORE",
        "market_value": 180000,
        "weight": 0.36,
        "category": "equity",
        "fund_type": "ETF"
      }
    ]
  }
}
```

`POST /scheduler/run-once`

## 当前边界

- 主路径已经是基金版，不再维护股票 CLI / 股票 HTTP 作为默认能力
- 仓库里还保留了一些旧股票模块，但它们不再属于当前支持路径
- 当前基金数据同步优先面向个人使用，不追求机构级全市场覆盖

## 验证

```bash
.conda/bin/python -m mypy ashare_qlib_agent
.conda/bin/python -m pytest tests -q
```
