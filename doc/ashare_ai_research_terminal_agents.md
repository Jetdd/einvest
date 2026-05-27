# A股智能投研终端：AI Agent 学习与产品设计说明

> 版本：v0.1  
> 目标：将“量化复盘框架 + A股投研库 + 卖方研报 RAG + 股票标签系统”整合为一个可交互、可商业化的 A 股中线交易决策产品。  
> 适用对象：AI Agent、Codex、投研系统开发者、产品设计者。  
> 用户定位：中线交易者，通常持股周期不超过 3 个月，关注个股基本面、行业景气度、市场情绪、交易结构和催化剂。

---

## 0. 产品一句话定位

本产品不是普通研报库，也不是普通 AI 问答工具，而是：

> **一个结合卖方研报、行情数据、量化市场状态和 AI RAG 的 A 股中线交易决策系统。**

用户的典型使用路径：

```text
看市场状态
  ↓
看当前强势行业 / 概念 / 风格
  ↓
点进感兴趣的股票
  ↓
看到系统生成的标签、交易状态、景气度、催化剂和风险
  ↓
阅读对应的最新卖方研报和 AI 摘要
  ↓
形成自己的交易决策
```

最终形态：

```text
量化 Dashboard + 股票 Wiki + 研报 RAG + 标签系统 + 交易计划生成器
```

---

## 1. 核心原则

### 1.1 量化指标负责判断，AI 负责解释

不要把所有量化框架、研报、PDF 都直接塞进 RAG 里，让 AI 每次临时理解。

错误方式：

```text
把所有研报、框架文档、PDF 全部塞进 RAG
  ↓
用户提问
  ↓
AI 临时检索大量文本
  ↓
AI 临时总结
  ↓
token 消耗大、结果不稳定、难以回测
```

正确方式：

```text
行情 / 财务 / 板块 / 情绪数据
        ↓
Feature Engine 计算指标
        ↓
Tag Engine 生成标签
        ↓
Snapshot 固化每日状态
        ↓
AI 读取标签、证据和研报摘要
        ↓
AI 负责解释、归因和生成交易建议
```

核心原则：

> **量化指标负责“判断”，AI 负责“解释”。**

---

## 2. 产品五层架构

整个系统分成五层：

```text
1. Data Layer          数据层
2. Feature Layer       指标层
3. Tag Layer           标签层
4. Knowledge Layer     研报 / 公司知识库层
5. Product Layer       Dashboard + AI Chat 层
```

---

# 3. Data Layer：数据层

数据层负责接入原始数据，不直接做业务判断。

## 3.1 数据源

可接入：

```text
DM
Wind
RiceQuant
本地行情数据库
卖方研报 PDF / Word / Markdown
公告数据
财务数据
估值数据
```

## 3.2 股票行情数据

需要字段：

```text
symbol
trade_date
open
high
low
close
pre_close
pct_chg
volume
amount
turnover
float_mkt_cap
limit_up
limit_down
is_limit_up
is_limit_down
is_st
is_paused
```

## 3.3 指数行情数据

建议覆盖：

```text
上证指数
深证成指
创业板指
科创50
沪深300
中证500
中证1000
中证2000
万得全A
等权全A / 平均股价指数
```

字段：

```text
index_code
trade_date
open
high
low
close
pre_close
volume
amount
pct_chg
```

## 3.4 板块 / 概念数据

需要维护：

```text
申万一级行业
申万二级行业
申万三级行业
Wind 概念
通达信概念
自定义主题池
```

重点自定义主题池示例：

```text
AI算力
CPO
铜缆高速连接
液冷
PCB
存储
先进封装
半导体设备
半导体材料
机器人
固态电池
低空经济
稀土
电网设备
核电
高股息
资源品
涨价链
```

## 3.5 财务与估值数据

字段：

```text
revenue
revenue_yoy
net_profit
net_profit_yoy
gross_margin
net_margin
roe
operating_cashflow
free_cashflow
inventory
accounts_receivable
capex
pe_ttm
pb
ps
peg
ev_ebitda
valuation_percentile_3y
valuation_percentile_5y
```

## 3.6 研报数据

每篇研报需要结构化为：

```yaml
report_id:
ticker:
company_name:
broker:
analyst:
publish_date:
title:
rating:
previous_rating:
target_price:
previous_target_price:
eps_forecast:
revenue_forecast:
profit_forecast:
main_points:
positive_evidence:
negative_evidence:
risk_factors:
file_path:
```

---

# 4. Feature Layer：指标层

Feature Layer 是产品壁垒之一。  
这一层将行情、板块、财务、情绪、研报变化转化为可解释的量化指标。

指标分为五类：

```text
A. 市场状态指标
B. 板块景气指标
C. 主题 / 概念指标
D. 个股交易指标
E. 信号验证指标
```

---

## 4.1 市场状态指标

目标：回答以下问题：

```text
现在市场能不能做？
应该重仓还是轻仓？
当前是趋势行情、震荡行情、修复行情，还是退潮行情？
```

### 4.1.1 核心指标

```text
CCI14
CCI84
MST-5
MST-13
MST-50
MA5 站上率
MA13 站上率
MA50 站上率
全市场成交额
平均换手率
涨跌家数
涨停数量
跌停数量
昨日涨停今日收益
连板高度
市场风险评分
历史相似时期胜率
```

### 4.1.2 市场状态标签

根据指标生成：

```yaml
market_tags:
  - 市场偏强
  - 市场震荡
  - 流动性充足
  - 流动性匮乏
  - 广度修复
  - 广度恶化
  - 情绪高潮
  - 情绪退潮
  - 适合进攻
  - 适合防守
```

### 4.1.3 市场状态输出

AI 输出时必须给出：

```text
当前市场状态：
- 市场温度：
- 风险灯：
- 流动性状态：
- 市场广度：
- 情绪状态：
- 推荐仓位：
- 适合的交易风格：
```

---

## 4.2 板块景气指标

目标：回答：

```text
现在什么行业最强？
哪个板块在加速？
哪个板块只是反弹？
哪个板块已经高潮？
```

### 4.2.1 核心指标

```text
SC30
SC3
SC60
RSV
RSV_mom
板块 N 日涨幅排名
Top7 排名迁移
板块热力图
RRG 相对轮动
风格价量共振
板块成交额占比
板块换手率
板块内涨停数量
板块内 MA 站上率
```

### 4.2.2 指标解释

```text
SC30:
  用于观察板块中期趋势。
  高于 80 通常代表中期强势或偏热。
  低于 25 通常代表冰点或超卖。

SC3:
  用于观察短期动量。
  高位可能代表短期加速或过热。
  低位可能代表短期冷却或回调。

SC60:
  用于观察更长周期趋势。

RSV:
  可用 N 日区间位置或横截面分位构造。
  用于衡量板块当前强度在历史区间中的位置。

RRG:
  用于判断板块处于领涨、转弱、落后、转强哪个象限。

Top7 排名迁移:
  用于判断板块是否新晋强势、连续强势、掉出强势榜或重新回归。
```

### 4.2.3 板块景气标签

```yaml
sector_cycle_tags:
  - 景气上行
  - 高景气延续
  - 短期加速
  - 短期过热
  - 高低切
  - 主线抱团
  - 主线缩容
  - 补涨扩散
  - 排名新晋
  - 连续强势
  - 掉出强势榜
```

---

## 4.3 主题 / 概念指标

目标：让用户快速看到当前主线在哪里。

每个主题生成一张状态卡片：

```yaml
theme_card:
  theme: "CPO"
  heat_score: 86
  sc30: 91
  sc3: 74
  rank_5d: 3
  rank_change: "+5"
  liquidity_share: "高"
  crowding_status: "高拥挤"
  phase: "主线高潮中段"
  trading_view: "趋势仍强，但追高性价比下降"
```

### 4.3.1 主题状态

每个主题至少包含：

```text
主题名称
所属大板块
主题成分股数量
主题日涨跌幅
主题 3 日涨跌幅
主题 5 日涨跌幅
主题 20 日涨跌幅
主题成交额
主题成交额占全市场比例
主题 SC3
主题 SC30
主题热力值
主题 RRG 象限
主题拥挤度
主题阶段
```

### 4.3.2 主题阶段

```yaml
theme_phase:
  - 酝酿
  - 启动
  - 主升
  - 加速
  - 高潮
  - 分歧
  - 退潮
  - 修复
```

---

## 4.4 个股交易指标

目标：回答：

```text
这只股票现在是趋势股、补涨股、超跌反弹股，还是情绪龙头？
```

### 4.4.1 个股指标模块

```text
趋势牛卡位买点
高胜率抄底指标
情绪龙头 / 擒龙捉妖
容量抱团成交额集中度
个股是否属于 top 主线
个股是否进入成交额 top 股票
个股是否触发买讯
个股相对行业强弱
个股相对主题强弱
个股估值分位
个股研报上修
个股业绩预期变化
```

### 4.4.2 个股交易标签

```yaml
stock_trading_tags:
  - 主线核心
  - 容量核心
  - 趋势强化
  - 放量突破
  - 缩量回调
  - 右侧确认
  - 左侧修复
  - 超跌反弹
  - 情绪龙头
  - 高拥挤
  - 交易风险升高
```

---

## 4.5 信号验证指标

目标：让每个信号有历史验证，而不是主观判断。

AI 不应只说：

```text
这个信号看起来不错。
```

而应输出：

```text
历史上类似状态出现 126 次，
未来 5 日上涨概率 63%，
平均收益 2.4%，
最大回撤 -4.8%，
当前赔率中等偏高。
```

### 4.5.1 信号事件表

```sql
signal_event(
    signal_id,
    trade_date,
    object_type,
    object_id,
    signal_name,
    direction,
    strength,
    suggested_action,
    state_before,
    state_after
)
```

### 4.5.2 信号结果表

```sql
signal_outcome(
    signal_id,
    horizon,
    future_ret,
    benchmark_ret,
    excess_ret,
    max_drawdown,
    is_correct
)
```

### 4.5.3 历史状态统计

```sql
state_forward_return_stats(
    state_id,
    horizon,
    sample_count,
    win_rate,
    avg_return,
    median_return,
    odds_ratio,
    max_drawdown
)
```

---

# 5. Tag Layer：标签层

标签系统是产品核心资产。

标签不应只是自然语言描述，而应该是：

```text
静态标签 + 动态标签 + 证据标签 + 交易标签
```

---

## 5.1 一只股票的标签结构

以中际旭创为例，结构如下：

```yaml
ticker: "300308.SZ"
name: "中际旭创"

static_tags:
  industry:
    - 通信
    - 光模块
  theme:
    - AI算力
    - CPO
    - 数据中心
    - 英伟达产业链
  supply_chain_role:
    - AI数据中心上游核心零部件

fundamental_tags:
  - 海外客户占比较高
  - AI需求驱动
  - 高速光模块放量
  - 业绩弹性较高

sector_tags:
  - 所属主题景气上行
  - CPO板块强势
  - AI算力主线延续

trading_tags:
  - 主线核心
  - 容量核心
  - 趋势强
  - 机构关注度高
  - 交易拥挤度偏高

valuation_tags:
  - 估值处于高位
  - 需要业绩兑现支撑

risk_tags:
  - 海外客户集中
  - AI资本开支波动
  - 估值回撤风险
  - 交易拥挤风险

ai_summary_tags:
  current_action: "观察回调买点"
  thesis_status: "valid"
  pricing_status: "partially_priced"
  conviction: 4
```

---

## 5.2 标签分类

### 5.2.1 静态标签

变化较慢：

```text
行业
产业链位置
主营业务
商业模式
客户结构
公司属性
```

### 5.2.2 动态标签

变化较快：

```text
行业景气度
估值位置
交易拥挤度
催化剂
评级
买入区间
市场是否定价
```

### 5.2.3 证据标签

用于解释标签来源：

```text
来自财务数据
来自行情数据
来自板块指标
来自研报
来自公告
来自回测结果
```

### 5.2.4 交易标签

用于中线交易判断：

```text
主线核心
容量核心
强趋势
回调观察
右侧确认
左侧埋伏
超跌反弹
高拥挤
追高风险
逻辑证伪
```

---

## 5.3 核心标签快照表

最重要的数据库表：

```sql
stock_tag_snapshot(
    trade_date,
    symbol,
    tag_category,
    tag_name,
    tag_value,
    tag_score,
    confidence,
    evidence_type,
    evidence_id,
    source,
    created_at
)
```

示例：

```text
2026-05-25 | 300308.SZ | sector | AI算力 | true | 95 | high | sector_feature | CPO_SC30_20260525
2026-05-25 | 300308.SZ | trading | 高拥挤 | true | 82 | medium | amount_feature | amount_rank_20260525
2026-05-25 | 300308.SZ | fundamental | 业绩上修 | true | 76 | high | research_report | report_20260525_001
```

该表用途：

```text
1. 每天追踪标签变化
2. 回测标签是否有效
3. 给客户解释标签来源
4. AI 回答可以引用 evidence
5. 未来可以做标签 alpha
```

---

# 6. Knowledge Layer：研报 RAG 与公司知识库

## 6.1 不要直接让 AI 读所有研报

错误方式：

```text
用户问中际旭创
  ↓
AI 读取所有中际旭创研报
  ↓
AI 长文本总结
```

问题：

```text
token 消耗大
速度慢
结论不稳定
无法追踪来源
难以回测
```

---

## 6.2 正确方式：两级 RAG

### 第一级：结构化摘要库

每篇研报先被压缩成结构化数据：

```yaml
report_id: "report_20260525_001"
ticker: "300308.SZ"
broker: "XX证券"
analyst: "XXX"
publish_date: "2026-05-25"
title: "AI光模块需求持续超预期"

rating: "buy"
target_price: 180
previous_target_price: 150

core_points:
  - 800G/1.6T需求持续增长
  - 海外云厂商资本开支上修
  - 公司份额和盈利能力维持高位

positive_evidence:
  - 订单能见度提升
  - 毛利率好于预期
  - 产能扩张顺利

negative_evidence:
  - 估值处于历史较高区间
  - 客户集中度较高

impacted_tags:
  add:
    - AI算力
    - 业绩上修
    - 高景气延续
  remove: []

impact_on_thesis: "强化原逻辑"
impact_on_rating: "维持"
```

大多数用户问题只需要读取结构化摘要，不需要读取研报全文。

### 第二级：原文 chunk 检索

只有当用户追问细节时，才检索原文 chunk：

```text
这篇研报具体怎么测算目标价？
毛利率假设是多少？
海外客户订单依据是什么？
券商对 2026 年 EPS 的预测是多少？
```

此时才进入原文 RAG。

---

## 6.3 研报摘要表

```sql
report_summary(
    report_id,
    ticker,
    company_name,
    broker,
    analyst,
    publish_date,
    title,
    rating,
    previous_rating,
    target_price,
    previous_target_price,
    core_points_json,
    positive_evidence_json,
    negative_evidence_json,
    risk_factors_json,
    impacted_tags_json,
    impact_on_thesis,
    impact_on_rating,
    file_path,
    created_at
)
```

---

# 7. Product Layer：产品页面设计

## 7.1 页面一：市场总览

目标：回答“今天适不适合交易”。

模块：

```text
市场状态：
- 市场温度
- 风险灯
- v5 节点
- 推荐仓位
- 今日策略提示

流动性：
- 全 A 成交额
- 估算全天成交额
- 平均换手率
- 流动性分位数

广度：
- MST-5
- MST-13
- MST-50
- MA5 / MA13 / MA50 站上率

情绪：
- 涨停数量
- 跌停数量
- 昨日涨停今日表现
- 连板高度
```

---

## 7.2 页面二：行业 / 板块 / 概念雷达

目标：回答“当前主线在哪里”。

模块：

```text
大板块强度：
- 科技
- 新能源
- 消费
- 周期
- 金融
- 高股息

主题热力图：
- AI算力
- CPO
- 存储
- 液冷
- 机器人
- 固态电池
- 稀土
- 电网

Top7 排名迁移：
- 今日 Top7
- 昨日 Top7
- 前日 Top7
- 新晋
- 连续
- 掉出

RRG 轮动：
- 领涨
- 转弱
- 落后
- 转强
```

---

## 7.3 页面三：个股详情页

用户输入：

```text
中际旭创
```

页面展示：

```text
1. 公司业务卡片
2. 所属产业链
3. 当前标签
4. 所属主题强度
5. 量化交易状态
6. 最新卖方观点
7. 财务和估值
8. 催化剂
9. 风险点
10. AI 交易计划
```

页面结构：

```text
顶部：
- 股票名 / 代码 / 当前价格 / 涨跌幅 / 市值 / 估值

左侧：
- 标签
- 主题归属
- 景气度评分
- 拥挤度评分
- 研报一致预期

中间：
- K线 + 成交额
- 所属板块强度
- 相对行业表现
- RRG位置

右侧：
- AI总结
- 买入 / 观察 / 回避结论
- 证据引用
- 最新研报列表
```

---

## 7.4 页面四：AI 问答 / RAG

客户可以问：

```text
中际旭创现在还能买吗？
CPO板块是不是过热了？
最近哪些AI算力公司被卖方上修？
当前市场适合追高还是等回调？
帮我找出景气上行但估值还没完全定价的股票。
```

AI 回答必须基于：

```text
1. 当前 dashboard snapshot
2. 个股 tag snapshot
3. 研报结构化摘要
4. 相关原文 chunk
5. 财务估值数据
6. 行情交易信号
```

回答模板：

```text
结论：
证据：
量化状态：
基本面逻辑：
卖方观点：
估值位置：
交易计划：
风险和证伪：
后续跟踪指标：
```

---

## 7.5 页面五：研报库

功能：

```text
按股票筛选
按行业筛选
按主题筛选
按券商筛选
按发布日期筛选
按评级变化筛选
按目标价上修筛选
按核心标签筛选
```

每篇研报展示：

```text
AI 摘要
核心图表
目标价
盈利预测
核心假设
相对上一份研报变化
原文阅读入口
```

注意事项：

```text
卖方研报原文展示、下载、二次分发需要确认数据供应商和券商授权。
产品上可以先做摘要 + 引用 + 权限控制，不要默认开放全文。
```

---

# 8. 景气度系统设计

景气度不应只依赖研报，也不应只依赖量价。

建议定义：

```text
行业景气度 = 产业数据 + 板块量价 + 卖方上修 + 公司业绩验证
```

## 8.1 景气度评分

```yaml
prosperity_score:
  sector_price_score: 0-100
  liquidity_score: 0-100
  earnings_revision_score: 0-100
  report_sentiment_score: 0-100
  event_catalyst_score: 0-100
  final_score: 0-100
```

## 8.2 建议权重

适合 A 股中线交易的初始权重：

```text
板块量价强度：30%
研报上修 / 盈利预测变化：25%
产业催化剂：20%
公司业绩验证：15%
交易拥挤惩罚：-10% 到 -30%
```

## 8.3 景气度标签

```yaml
prosperity_label:
  - 景气上行
  - 高景气延续
  - 景气拐点
  - 景气验证不足
  - 景气已充分定价
  - 景气退潮
```

---

# 9. 交易标签规则设计

交易标签应由量化指标直接生成，而不是 AI 主观判断。

## 9.1 示例规则

```yaml
trading_tag_rules:
  强趋势:
    condition:
      - stock_ret_20d > industry_ret_20d
      - above_ma5 = true
      - above_ma13 = true
      - amount_percentile_60d > 70

  主线核心:
    condition:
      - stock_theme in top_sector_list
      - stock_amount_rank_in_theme <= 5
      - theme_sc30 > 80

  高拥挤:
    condition:
      - crowding_strength > 80
      - stock_amount_percentile > 90
      - sector_top_amount_share > threshold

  回调观察:
    condition:
      - thesis_status = valid
      - sector_sc30 > 70
      - stock_drawdown_from_high between 8% and 18%
      - no_fundamental_negative_event

  追高风险:
    condition:
      - stock_ret_10d > 25%
      - sector_sc3 > 85
      - liquidity_score falling
```

## 9.2 AI 解释方式

AI 不应说：

```text
我觉得这只股票比较强。
```

AI 应说：

```text
系统给该股票打上“主线核心 + 高拥挤 + 趋势强”的标签。

原因：
1. 所属主题仍在强势区。
2. 个股成交额处于高分位。
3. 短期涨幅较大，拥挤度偏高。

因此结论不是简单买入，而是更适合等待回调后的右侧确认。
```

---

# 10. 数据库表设计

## 10.1 原始数据表

```sql
security_master(
    symbol,
    name,
    exchange,
    list_date,
    delist_date,
    is_st,
    board
);

trade_calendar(
    trade_date,
    is_open
);

stock_daily_bar(
    symbol,
    trade_date,
    open,
    high,
    low,
    close,
    pre_close,
    volume,
    amount,
    turnover,
    float_mkt_cap,
    limit_up,
    limit_down,
    paused
);

stock_intraday_bar(
    symbol,
    datetime,
    open,
    high,
    low,
    close,
    volume,
    amount
);

index_daily_bar(
    index_code,
    trade_date,
    open,
    high,
    low,
    close,
    pre_close,
    volume,
    amount
);

sector_master(
    sector_id,
    sector_name,
    sector_type,
    parent_sector_id,
    source
);

sector_constituent(
    sector_id,
    symbol,
    start_date,
    end_date,
    weight
);
```

## 10.2 派生指标表

```sql
stock_feature_daily(
    symbol,
    trade_date,
    ret_1d,
    ret_5d,
    ret_20d,
    ma5,
    ma13,
    ma50,
    above_ma5,
    above_ma13,
    above_ma50,
    amount_percentile,
    limit_status,
    buy_signal_flags
);

sector_feature_daily(
    sector_id,
    trade_date,
    ret_1d,
    ret_3d,
    ret_5d,
    ret_20d,
    amount,
    turnover,
    sc3,
    sc30,
    sc60,
    rsv,
    rsv_mom,
    phase,
    risk_level
);

market_breadth_daily(
    trade_date,
    up_count,
    down_count,
    limit_up_count,
    limit_down_count,
    ma5_above_pct,
    ma13_above_pct,
    ma50_above_pct,
    mst5,
    mst13,
    mst50,
    breadth_ratio
);

market_liquidity_daily(
    trade_date,
    total_amount,
    avg_turnover,
    liquidity_score,
    liquidity_band
);

market_state_daily(
    trade_date,
    market_state,
    v5_node,
    star_rating,
    cycle_phase,
    position_base,
    position_flex,
    position_config,
    market_temperature
);
```

## 10.3 Dashboard 快照表

```sql
dashboard_snapshot(
    snapshot_time,
    trade_date,
    market_state_json,
    risk_json,
    liquidity_json,
    breadth_json,
    position_json,
    leading_sectors_json,
    stock_pool_json
);
```

---

# 11. MVP 路线

## 11.1 MVP 1：日频版

第一版不要追求盘中实时，先做日终更新。

功能：

```text
1. 市场状态 dashboard
2. 板块热力图
3. 主题 Top7 排名
4. 个股标签页
5. 研报摘要 RAG
6. AI 问答
```

优先指标：

```text
CCI
流动性
MST
MA 站上率
SC30
SC3
板块热力图
容量抱团
RRG
市场状态机
历史回测评分
```

---

## 11.2 MVP 2：盘中快照

日频版稳定后，加入盘中 5 分钟更新：

```text
估算全天成交额
实时流动性
主题强度变化
成交额 top 股票变化
情绪温度变化
```

盘中架构：

```text
实时行情
  ↓
5 分钟 feature snapshot
  ↓
dashboard_snapshot
  ↓
前端刷新
```

---

## 11.3 MVP 3：客户交互式 AI

最后再加入完整 AI 交互：

```text
用户输入股票
  ↓
AI 自动读取个股标签
  ↓
读取最新研报摘要
  ↓
读取财务估值
  ↓
读取市场和板块状态
  ↓
输出交易结论
```

---

# 12. 技术架构建议

## 12.1 MVP 技术栈

```text
数据存储：
- DuckDB
- Parquet
- PostgreSQL 可选

前端：
- Streamlit

后端：
- FastAPI

向量库：
- pgvector
- Qdrant 可选

计算：
- Python
- Polars
- Pandas
- NumPy

任务调度：
- cron
- Prefect
- Airflow 可选
```

## 12.2 成熟版本技术栈

```text
数据存储：
- PostgreSQL
- ClickHouse
- S3 / MinIO

向量库：
- Qdrant
- Milvus
- pgvector

前端：
- React
- Next.js

后端：
- FastAPI
- Celery / Redis

AI：
- LLM API
- RAG Pipeline
- Evidence Citation
- Answer Audit Log
```

---

# 13. Agent 开发任务拆分

不要让 Codex 直接“学习所有研报”。  
应让 Codex 分模块生成系统。

建议任务文件：

```text
1. data_schema.sql
2. factor_spec.yaml
3. tag_schema.yaml
4. report_ingestion.py
5. feature_engine.py
6. tag_engine.py
7. stock_card_generator.py
8. rag_retriever.py
9. streamlit_dashboard.py
10. ai_answer_prompt.md
```

三个最重要文件：

```text
factor_spec.yaml     # 每个指标怎么算
tag_schema.yaml      # 每个标签怎么生成
rag_contract.md      # AI 回答时必须读取哪些上下文
```

---

# 14. AI Agent 行为规范

## 14.1 Agent 不能做的事

```text
不能只根据研报给出买入建议
不能把卖方观点直接当事实
不能忽略当前市场状态
不能忽略板块景气和交易拥挤度
不能输出没有证据的标签
不能把长期看好等同于当前可以买入
不能在没有数据支持时声称“已被市场定价”或“未被定价”
```

## 14.2 Agent 必须做的事

```text
读取个股标签
读取市场状态
读取板块景气度
读取最新研报摘要
读取估值和财务数据
读取交易信号和历史验证结果
给出结论、证据、风险、证伪条件和跟踪指标
```

## 14.3 标准回答结构

用户问：

```text
中际旭创现在还能买吗？
```

Agent 应输出：

```text
结论：
- 当前是否适合买入：
- 更适合左侧还是右侧：
- 建议仓位：

核心依据：
- 基本面：
- 行业景气：
- 量化交易状态：
- 卖方研报变化：
- 估值位置：

交易计划：
- 理想买入区间：
- 目标价：
- 止损条件：
- 持有周期：
- 后续跟踪指标：

风险：
- 基本面风险：
- 估值风险：
- 交易拥挤风险：
- 逻辑证伪条件：
```

---

# 15. 产品商业化卖点

不要把产品定位成普通“研报库”。

更好的定位：

```text
A股智能投研终端
A股中线交易雷达
AI Stock Analyst for China A-shares
A股景气度与交易信号平台
A股产业趋势 + 交易情绪系统
```

核心卖点：

```text
1. 不只是总结研报，而是把研报变成结构化标签。
2. 不只是看基本面，而是结合市场状态、板块轮动和交易情绪。
3. 不只是 AI 问答，而是有量化指标和历史信号验证。
4. 不只是股票池，而是可追踪、可解释、可更新的交易决策系统。
```

真正壁垒：

```text
自己的标签体系
量化状态机
卖方研报结构化
历史验证结果
```

RAG 只是前端交互方式，不是核心壁垒。

---

# 16. 下一步执行建议

## 16.1 第一优先级

先建三张核心表：

```text
1. stock_tag_snapshot
2. sector_feature_daily
3. report_summary
```

只要这三张表跑起来，产品就已经有雏形。

## 16.2 第二优先级

实现以下基础模块：

```text
市场状态：
- CCI
- 流动性
- MST
- MA 站上率

板块强度：
- SC30
- SC3
- 主题 Top7
- RRG

个股标签：
- 主线核心
- 强趋势
- 高拥挤
- 回调观察
- 研报上修
```

## 16.3 第三优先级

接入 AI 问答：

```text
用户问题
  ↓
解析股票 / 主题 / 市场问题类型
  ↓
检索对应 tag snapshot
  ↓
检索 dashboard snapshot
  ↓
检索 report_summary
  ↓
必要时检索原文 chunk
  ↓
生成结构化回答
```

---

# 17. 推荐目录结构

```text
ashare_ai_research_terminal/
├── AGENTS.md
├── README.md
├── config/
│   ├── factor_spec.yaml
│   ├── tag_schema.yaml
│   ├── rag_contract.md
│   └── theme_universe.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   ├── parquet/
│   └── reports/
├── sql/
│   ├── data_schema.sql
│   ├── feature_schema.sql
│   └── tag_schema.sql
├── src/
│   ├── data_ingestion/
│   ├── feature_engine/
│   ├── tag_engine/
│   ├── report_engine/
│   ├── rag_engine/
│   ├── dashboard/
│   └── api/
├── apps/
│   ├── streamlit_dashboard.py
│   └── fastapi_server.py
├── notebooks/
│   ├── feature_validation.ipynb
│   └── signal_backtest.ipynb
└── docs/
    ├── product_design.md
    ├── label_system.md
    └── ai_answer_examples.md
```

---

# 18. 最终目标

这个系统最终要能回答：

```text
为什么这个股票被打上 AI算力 / 主线核心 / 高拥挤 标签？
最近哪些研报强化了这个逻辑？
当前价格是否已经定价？
什么条件下这个逻辑会证伪？
当前市场环境是否支持买入？
如果买，应该怎么买、持有多久、如何止损？
```

最终产品不是资料库，而是：

> **A 股中线交易决策系统。**
