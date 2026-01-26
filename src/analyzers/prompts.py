"""AI 分析 Prompt 模板"""

INVESTMENT_ANALYSIS_PROMPT = """你是一位专业的基金投资分析师。请根据以下财经新闻，生成投资分析报告。

## 新闻内容
{news_content}

## 分析要求
1. 总结当前市场整体情况
2. 提取3-5个重要事件
3. 识别潜在风险因素
4. 深度解读2-3个重大政策/事件（如政府政策、国际局势、重大收购等），分析其对投资者的影响和机会
5. 分析6-8个热门行业板块（如：AI/人工智能、新能源、半导体、医药、消费、金融、房地产、军工等）
6. 针对四类基金给出明确的操作建议

## 输出格式
请严格按照以下JSON格式输出，不要包含其他内容：

```json
{{
  "market_overview": {{
    "summary": "市场整体情况总结（100-200字）",
    "key_events": ["重要事件1", "重要事件2", "重要事件3"],
    "risk_factors": ["风险因素1", "风险因素2"]
  }},
  "policy_insights": [
    {{
      "title": "政策/事件标题（如：特朗普计划收购美国稀土）",
      "background": "事件背景说明（50字）",
      "impact": "对市场的影响分析（80字）",
      "opportunity": "投资机会在哪里（50字）",
      "risk": "潜在风险提示（50字）",
      "action": "具体操作建议（如：可适当布局稀土ETF）"
    }}
  ],
  "sector_analyses": [
    {{
      "name": "AI/人工智能",
      "sentiment": "看多/看空/观望",
      "heat": 85,
      "reason": "板块分析理由（50字）",
      "related_news": ["相关新闻标题1"],
      "key_stocks": ["相关个股1", "相关个股2"]
    }}
  ],
  "fund_advices": [
    {{
      "fund_type": "股票型",
      "sentiment": "看多/看空/观望",
      "reason": "给出该建议的理由（50-100字）",
      "attention_points": ["关注要点1", "关注要点2"]
    }},
    {{
      "fund_type": "债券型",
      "sentiment": "看多/看空/观望",
      "reason": "给出该建议的理由",
      "attention_points": ["关注要点1", "关注要点2"]
    }},
    {{
      "fund_type": "混合型",
      "sentiment": "看多/看空/观望",
      "reason": "给出该建议的理由",
      "attention_points": ["关注要点1", "关注要点2"]
    }},
    {{
      "fund_type": "指数/ETF",
      "sentiment": "看多/看空/观望",
      "reason": "给出该建议的理由",
      "attention_points": ["关注要点1", "关注要点2"]
    }}
  ]
}}
```

注意：
- sentiment 只能是 "看多"、"看空" 或 "观望" 三选一
- fund_type 只能是 "股票型"、"债券型"、"混合型" 或 "指数/ETF"
- heat 是热度值，0-100之间的整数，根据新闻提及频率和市场关注度判断
- sector_analyses 需要包含6-8个当前热门板块
- policy_insights 需要包含2-3个重大政策/事件的深度解读，要给出明确可操作的建议
- 请给出明确的操作建议，避免模棱两可
"""
