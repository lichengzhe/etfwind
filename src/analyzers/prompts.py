"""AI 分析 Prompt 模板"""

SYSTEM_PROMPT = """你是一位专注A股市场的逆向投资分析师。

## 核心身份
- 目标用户：国内投资者，只投A股和国内基金
- 思维方式：反人性、反直觉，别人贪婪我恐惧，别人恐惧我贪婪
- 全球视野：关注国际事件如何传导影响A股

## 分析原则
1. 以事件为中心：每个重要事件讲完整故事（发生什么→为什么重要→怎么操作）
2. 逆向思维：当市场一致看好时保持警惕，当市场恐慌时寻找机会
3. 风险优先：宁可错过机会，不可盲目追高
4. 聚焦重点：只分析真正影响市场的3-5个核心事件"""

INVESTMENT_ANALYSIS_PROMPT = """请根据以下财经新闻，生成投资决策参考。

## 当前时间
{current_time}

## 新闻内容
{news_content}

## 输出要求
请严格按照以下JSON格式输出：

```json
{{
  "market_narrative": "市场全景分析（150-200字）：1)当前所处阶段（牛市初期/中期/末期、熊市、震荡市等）及判断依据；2)近期主要矛盾（政策、资金、情绪、外围等）；3)未来1-2周关键变量和可能演绎路径；4)逆向思考：市场共识是什么，哪里可能出错",
  "one_liner": "今日一句话决策建议（20字内，直接告诉该怎么做）",
  "market_emotion": 65,
  "focus_events": [
    {{
      "title": "沪银夜盘暴涨超9%，贵金属情绪高涨",
      "sector": "贵金属",
      "time": "09:30",
      "analysis": "沪银夜盘涨幅罕见，单日涨超9%触及涨停。这一走势与全球避险情绪升温密切相关。从历史规律看，贵金属单日暴涨往往是短期情绪顶点，后续大概率进入震荡消化阶段。",
      "suggestion": "持有者逢高减仓，未持有者勿追高",
      "related_funds": [
        {{"code": "518880", "name": "黄金ETF"}},
        {{"code": "161226", "name": "白银LOF"}}
      ],
      "source_ids": [1, 3, 5],
      "importance": 1
    }}
  ],
  "risk_warnings": [
    "注意：市场情绪过热时往往是阶段顶部",
    "警惕：某某板块连续上涨后获利盘压力大"
  ]
}}
```

## 重要提示
- focus_events 需要5-6个当日最重要的事件，按重要性排序（importance: 1最重要）
- sector：事件所属板块（如：贵金属、AI算力、新能源、消费、医药、地产、金融等）
- time：事件发生或报道的大致时间（如：09:30、盘前、夜盘）
- analysis：综合分析（60-80字），包含事件背景和市场影响
- suggestion：一句话投资建议（15字内）
- related_funds：推荐1-2只相关ETF/LOF，只需代码和名称
- source_ids：【必填】引用新闻的序号列表，如 [1, 3, 5] 表示引用第1、3、5条新闻，至少引用1条
- 所有建议针对A股市场
"""

INCREMENTAL_ANALYSIS_PROMPT = """请根据新增新闻更新今日投资报告。

## 当前报告状态
{existing_report}

## 新增新闻
{new_news}

## 历史背景
{history_context}

## 更新要求
1. 评估新增新闻是否包含重要事件，决定是否需要加入 focus_events
2. 保持 focus_events 数量在5-6个，按重要性排序
3. 每个事件必须包含：title、sector、time、analysis、suggestion、related_funds、source_ids
4. source_ids 是【必填】字段，引用新闻序号列表如 [1, 3]，至少引用1条新闻
5. 更新 market_narrative（150-200字的市场全景分析，包含阶段判断、主要矛盾、未来变量、逆向思考）
6. 更新 market_emotion 和 one_liner（如果市场情绪有变化）
7. 输出完整的更新后报告（JSON格式同上）
"""

HISTORY_SUMMARY_PROMPT = """请根据以下报告数据，生成{period_type}市场摘要。

## 报告数据
{reports_data}

## 输出要求
请用100字以内总结：
1. 市场整体趋势（bullish/bearish/neutral）
2. 关键事件（最多3个）
3. 主要板块表现

输出JSON格式：
```json
{{
  "summary": "摘要内容",
  "key_events": ["事件1", "事件2"],
  "market_trend": "neutral"
}}
```
"""
