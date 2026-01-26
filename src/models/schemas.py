"""数据模型定义"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class NewsCategory(str, Enum):
    """新闻分类"""
    MACRO = "宏观政策"
    INDUSTRY = "行业板块"
    INTERNATIONAL = "国际财经"
    COMPANY = "个股公司"
    OTHER = "其他"


class NewsItem(BaseModel):
    """新闻条目"""
    title: str = Field(..., description="新闻标题")
    content: str = Field(default="", description="新闻内容")
    source: str = Field(..., description="来源")
    url: Optional[str] = Field(default=None, description="原文链接")
    published_at: Optional[datetime] = Field(default=None, description="发布时间")
    category: NewsCategory = Field(default=NewsCategory.OTHER, description="分类")


class NewsCollection(BaseModel):
    """新闻集合"""
    items: list[NewsItem] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=datetime.now)

    @property
    def count(self) -> int:
        return len(self.items)


class FundType(str, Enum):
    """基金类型"""
    STOCK = "股票型"
    BOND = "债券型"
    MIXED = "混合型"
    INDEX = "指数/ETF"


class Sentiment(str, Enum):
    """情绪判断"""
    BULLISH = "看多"
    BEARISH = "看空"
    NEUTRAL = "观望"


class FundAdvice(BaseModel):
    """基金投资建议"""
    fund_type: FundType = Field(..., description="基金类型")
    sentiment: Sentiment = Field(..., description="情绪判断")
    reason: str = Field(..., description="理由")
    attention_points: list[str] = Field(default_factory=list, description="关注要点")


class SectorAnalysis(BaseModel):
    """行业板块分析"""
    name: str = Field(..., description="板块名称")
    sentiment: Sentiment = Field(..., description="情绪判断")
    heat: int = Field(default=50, description="热度 0-100")
    reason: str = Field(..., description="分析理由")
    related_news: list[str] = Field(default_factory=list, description="相关新闻标题")
    key_stocks: list[str] = Field(default_factory=list, description="关键个股")


class MarketOverview(BaseModel):
    """市场概览"""
    summary: str = Field(..., description="市场总结")
    key_events: list[str] = Field(default_factory=list, description="重要事件")
    risk_factors: list[str] = Field(default_factory=list, description="风险因素")


class PolicyInsight(BaseModel):
    """政策解读"""
    title: str = Field(..., description="政策/事件标题")
    background: str = Field(..., description="背景说明")
    impact: str = Field(..., description="市场影响分析")
    opportunity: str = Field(..., description="投资机会")
    risk: str = Field(..., description="潜在风险")
    action: str = Field(..., description="操作建议")


class InvestmentReport(BaseModel):
    """投资报告"""
    period: str = Field(..., description="报告周期: morning/evening")
    generated_at: datetime = Field(default_factory=datetime.now)
    market_overview: MarketOverview = Field(..., description="市场概览")
    policy_insights: list[PolicyInsight] = Field(default_factory=list, description="政策解读")
    sector_analyses: list[SectorAnalysis] = Field(default_factory=list, description="行业分析")
    fund_advices: list[FundAdvice] = Field(default_factory=list, description="基金建议")
    news_sources: list["NewsItem"] = Field(default_factory=list, description="新闻来源")
    disclaimer: str = Field(
        default="本报告由AI生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。",
        description="免责声明"
    )
