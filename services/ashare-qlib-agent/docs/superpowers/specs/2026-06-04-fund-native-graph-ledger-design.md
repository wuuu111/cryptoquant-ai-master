# Fund Native Graph Ledger Dashboard Design

## Goal

把当前基金工具改造成一套个人可用的基金决策工作台：

- 以 `总资产` 为资金约束中心
- 以基金版 `graph agent + LLM` 作为多智能体协作主流程
- 以本地 PostgreSQL 作为真实状态存储
- 以统一账本记录持仓、交易流水、收益
- 以前端工作台承载“今日建议 / 我的基金 / 一键调仓 / 手工买卖 / 收益查看”

这套系统只给出研究和执行建议，不直连券商，不自动下真实订单。

## Scope

本轮设计覆盖 5 个子系统：

1. 基金版 graph/LLM 决策主流程
2. 统一资金账本、持仓和交易流水
3. 收益计算
4. 一键调仓和手工买卖入口
5. 延续旧前端风格的基金多智能体工作台

本轮不做：

- 券商 API 对接
- 自动成交回报同步
- 基金外的股票/期货/加密货币支持
- 多账户支持
- 实盘自动下单

## Product Principles

### 1. 单一真相来源

不能继续保留“调仓建议一套持仓、前端展示另一套持仓”的双账本结构。

系统必须只有一套真实账户状态：

- `总资产`
- `现金`
- `当前基金持仓`
- `交易流水`

所有建议、收益、前端展示、手工修正都围绕这一套账本运转。

### 2. LLM 参与协作，不拥有硬执行权

LLM 和 graph agent 负责：

- 市场解读
- 评分解释
- 组合争议
- 风险解释
- Supervisor 裁决
- 最终 review 总结

但 LLM 不能：

- 绕过硬风控
- 绕过数据质量失败
- 直接改写账本
- 直接触发真实交易

### 3. 手工执行优先

用户仍然在券商端手工完成真实买卖。

系统中的“一键调仓”含义是：

- 按建议直接更新本地账本
- 视为用户确认已按该金额执行

系统还必须保留手工买卖入口，允许用户修正实际成交。

### 4. 首页先回答行动，不先讲理论

首页第一屏必须先告诉用户：

- 今天该不该动
- 动哪些基金
- 每只基金调多少
- 为什么被批准或阻断

多智能体协作需要保留，但要作为“协作对话台”呈现，而不是抢占首页最上层。

## Architecture

### Overview

系统主链路改成基金版原生 graph 流程，不再让当前基金规则链和旧股票 graph 双轨并行作为主逻辑。

整体结构：

1. `AkShare / PostgreSQL`
2. `Fund Native Graph Workflow`
3. `Ledger + PnL Engine`
4. `HTTP / FastAPI API`
5. `Fund Dashboard Frontend`

### Decision Workflow

新的基金决策图以旧 `graph_agent.py`、`llm.py`、`collaboration.py` 的协作框架为骨架，但节点语义全部切换为基金版。

核心节点：

1. `FundDataAgent`
- 从 PostgreSQL 读取基金池、净值、元数据、基准指数
- 产出基金版 `MarketSnapshot`

2. `FundMarketDetectAgent`
- 基于 benchmark、基金候选池状态、广度和风险开关判断：
  - `BULL_TREND`
  - `BEAR_TREND`
  - `RANGE`
  - `RISK_OFF`
- 输出确定性的 `gate`
- LLM 只做解释，不改 gate

3. `FundFactorAgent`
- 用当前基金规则因子生成基础分
- LLM 给出排序解释、争议点和候选补充
- 最终分数仍由规则层输出

4. `FundPortfolioAgent`
- 基于：
  - 账户总资产
  - 现金
  - 当前持仓
  - `portfolio_mode`
  - 市场门控
- 生成目标权重和目标金额

5. `FundRiskAgent`
- 负责硬风控
- 包括：
  - 申购/赎回关闭
  - NAV 陈旧
  - QDII/商品约束
  - 防御仓位约束
  - 换手率约束
- 被阻断的建议不能被 LLM 放行

6. `FundCriticAgent`
- 汇总前面节点是否存在矛盾
- 给 Supervisor 提供 opposing evidence

7. `FundSupervisorAgent`
- 结合 deterministic evidence + LLM judgement
- 判断：
  - 直接进入执行建议
  - 退回 Portfolio / Risk / Factor 节点重算
  - 直接转 review

8. `FundExecutionAgent`
- 输出建议动作，不下单
- 动作类型：
  - `INCREASE`
  - `DECREASE`
  - `HOLD`
  - `BLOCKED`
- 输出建议金额、目标权重、理由

9. `FundReviewAgent`
- 给出最终摘要
- 生成前端首页 Hero、风险摘要、协作结论

10. `FundLedgerAgent`
- 不参与选基逻辑
- 专门负责：
  - 账户账本更新
  - 一键调仓落账
  - 手工买卖落账
  - 收益计算

### Workflow Principle

决策层与账本层分离：

- `Fund Native Graph Workflow` 负责给出“该怎么调”
- `FundLedgerAgent` 负责记录“实际记成什么”

## Data Model

### 1. Account Book

单账户版本使用一个统一账户对象，替代当前散落的 `portfolio-file` 和 `manual_holdings.json`。

建议字段：

- `account_id`
- `account_name`
- `base_currency`
- `target_total_assets`
- `cash_balance`
- `created_at`
- `updated_at`

说明：

- `target_total_assets` 是用户设定的“资金总数”
- 调仓建议按这个总额给出目标金额
- `cash_balance` 表示当前账本里的剩余现金

### 2. Fund Position

建议字段：

- `symbol`
- `fund_name`
- `category`
- `fund_type`
- `units`
- `avg_cost`
- `last_nav`
- `market_value`
- `weight`
- `cost_value`
- `unrealized_pnl`
- `unrealized_pnl_rate`
- `updated_at`

说明：

- 这是一张派生状态表
- 由交易流水和最新净值计算
- 用户不直接编辑这张表

### 3. Fund Trade Ledger

建议字段：

- `trade_id`
- `account_id`
- `symbol`
- `fund_name`
- `side` (`BUY` / `SELL`)
- `amount`
- `units`
- `price`
- `source` (`manual` / `suggestion_apply`)
- `suggestion_id` nullable
- `trade_time`
- `note`
- `created_at`

说明：

- 所有一键调仓和手工买卖都写到这张流水
- 收益必须以这张流水为准

### 4. Cycle Suggestion

在现有 cycle 结果持久化基础上，建议补充：

- `suggestion_id`
- `cycle_id`
- `symbol`
- `action`
- `current_weight`
- `target_weight`
- `delta_weight`
- `current_value`
- `target_value`
- `delta_value`
- `blocked`
- `reason`
- `applied` boolean
- `applied_trade_id` nullable

说明：

- 前端点击“一键调仓”后，把建议状态标记为已应用，并关联到账本流水

## PnL Model

收益采用完整版账本口径。

### Required Metrics

账户页必须显示：

- `累计投入`
- `当前总资产`
- `现金余额`
- `持仓总市值`
- `已实现收益`
- `未实现收益`
- `总收益`
- `总收益率`

### Definitions

1. `累计投入`
- 外部净流入资金
- 第一版可简化为：
  - 初始总资产 + 后续显式加款 - 显式取现

2. `当前总资产`
- `现金余额 + 当前全部持仓市值`

3. `已实现收益`
- 卖出成交相对于持仓成本的已兑现盈亏

4. `未实现收益`
- 当前持仓浮盈浮亏

5. `总收益`
- `已实现收益 + 未实现收益`

6. `总收益率`
- `总收益 / 累计投入`

## User Flows

### Flow A: 日常使用

1. 系统同步 AkShare 数据
2. graph workflow 跑一轮周期
3. 首页显示今日建议
4. 用户查看批准/阻断理由
5. 用户决定：
   - 一键调仓
   - 手工买卖
   - 暂不执行

### Flow B: 一键调仓

1. 用户在建议卡点击“一键调仓”
2. 后端校验：
   - 建议未应用
   - 非阻断建议
   - 现金足够或卖出逻辑成立
3. 写入交易流水
4. 重算持仓
5. 重算收益
6. 更新前端

### Flow C: 手工买卖

1. 用户在“我的基金”页打开手工买卖入口
2. 输入基金代码或基金名
3. 选择 `BUY / SELL`
4. 输入金额或份额、成交净值
5. 提交后写入交易流水
6. 更新持仓和收益

### Flow D: 协作查看

1. 首页只展示精简结论
2. 用户可展开“多 Agent 协作对话台”
3. 查看：
   - Market 发言
   - Factor 发言
   - Portfolio 发言
   - Risk 反对意见
   - Supervisor 裁决

## Frontend Design

### Visual Direction

沿用现有基金前端的工作台气质：

- 纸张质感
- 暖色背景
- serif + mono 的信息层次
- 类终端 / 类研究台的视觉氛围

不走通用 BI 大屏风格。

### Page 1: 今日建议

首页第一屏必须包含：

1. `Hero`
- 今日结论
- 总资产
- 建议调仓总额
- regime / gate
- Supervisor 最终裁决

2. `建议卡列表`
- 基金代码
- 基金名称
- 动作
- 建议金额
- 当前/目标权重
- 风险状态
- 按钮：
  - `一键调仓`
  - `手动调整`
  - `查看协作理由`

3. `多 Agent 协作对话台`
- 表现形式参考旧前端风格
- 不是简单步骤条
- 更像多 agent 轮流发言、Risk 插话、Supervisor 裁决

4. `风险审查摘要`

5. `候选基金预览`

### Page 2: 我的基金

必须包含：

1. `收益总览`
- 总资产
- 累计投入
- 已实现收益
- 未实现收益
- 总收益率

2. `持仓与收益表`
- 基金
- 成本
- 当前市值
- 浮盈亏
- 当前权重
- 目标权重
- 操作按钮

3. `手工记账入口`
- 通过代码或基金名查询
- 方向：
  - `BUY`
  - `SELL`
- 输入金额 / 份额 / 成交净值

4. `交易流水`
- 展示最近的手工和一键调仓记录

## API Design

### Keep

- `GET /health`
- `GET /fund-features`
- `GET /latest-cycle`
- `POST /sync-fund-data`
- `POST /scheduler/run-once`

### Replace / Add

1. `GET /account`
- 返回账户总览、收益摘要、现金状态

2. `POST /account`
- 更新账户基线
- 至少支持修改 `target_total_assets`

3. `GET /positions`
- 返回当前基金持仓和收益

4. `GET /trades`
- 返回交易流水

5. `POST /trades`
- 手工买卖记账

6. `POST /fund-cycle`
- 支持基于统一账户账本跑一轮，而不是读取旧 `portfolio-file`

7. `POST /suggestions/{id}/apply`
- 一键应用某条建议到本地账本

8. `GET /agent-dialogue/latest`
- 返回最近一次周期的多 agent 对话数据

## Storage

以本地 PostgreSQL 为唯一持久化主库。

建议新增或调整表：

- `fund_accounts`
- `fund_positions`
- `fund_trade_ledger`
- `fund_cycle_runs`
- `fund_rebalance_suggestions`
- `fund_agent_dialogues`

CSV 保留作为数据镜像或导入导出手段，不再作为账户真相来源。

## LLM Integration Rules

旧 `llm.py` 和 `graph_agent.py` 需要继续使用，但基金版必须遵守以下边界：

1. LLM 不能绕过硬风控
2. LLM 不能直接写账本
3. LLM 不能直接决定真实成交
4. LLM 输出必须结构化
5. Supervisor 必须优先尊重 deterministic risk/data guardrails

## Migration Strategy

### Phase 1

- 建立统一账户账本和交易流水
- 让收益跑通
- 前端接到新的账户和收益 API

### Phase 2

- 把基金主决策流程迁移到 `Fund Native Graph`
- 接入旧 LLM 和 Supervisor 机制

### Phase 3

- 接通建议应用
- 前端支持一键调仓和手工买卖

### Phase 4

- 把首页多 agent 协作台替换成正式基金版对话工作流展示

## Testing Requirements

必须覆盖：

1. 账户总资产驱动的目标金额计算
2. 一键调仓写流水后持仓和收益更新
3. 手工买卖写流水后持仓和收益更新
4. 被阻断建议不可应用
5. graph supervisor 在基金场景下的路由结果
6. 前端首页建议按钮与持仓页收益显示

## Risks

1. 旧 `graph_agent.py` 仍带股票语义，迁移时容易混入旧字段
2. 当前前端持仓展示与后端建议账本未打通，改造期间容易出现临时不一致
3. 若不以交易流水为中心做收益，会导致收益口径失真
4. 若一键调仓与手工记账走两套逻辑，后续维护成本会快速上升

## Recommendation

按 `Fund Native Graph + Unified Ledger` 路线实施：

- graph/LLM 成为基金决策主流程
- 本地 PostgreSQL 成为唯一状态真相
- 前端延续旧工作台风格，但首页更聚焦行动建议
- 多 agent 以协作对话台方式呈现，而不是普通步骤条
