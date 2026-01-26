"""数据模型定义"""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class NewsCategory(str, Enum):
    """新闻分类"""
    MACRO = "macro"
    INDUSTRY = "industry"
    COMPANY = "company"
    INTERNATIONAL = "international"
    OTHER = "other"


Signal = Literal["买入", "卖出", "观望"]
PositionLevel = Literal["重仓", "标配", "轻仓", "空仓"]
PositionChange = Literal["加仓", "减仓", "持有"]
AssetType = Literal["股票", "债券", "货币", "黄金"]


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
    collected_at: datetime = Field(default_factory=lambda: datetime.now())

    @property
    def count(self) -> int:
        return len(self.items)


class GlobalEvent(BaseModel):
    """全球事件及A股影响"""
    event: str = Field(..., description="事件描述")
    region: str = Field(..., description="地区：美国/欧洲/亚太/国内")
    a_stock_impact: str = Field(..., description="对A股的传导影响")
    affected_sectors: list[str] = Field(default_factory=list, description="受影响板块")


class SectorOpportunity(BaseModel):
    """板块机会分析"""
    name: str = Field(..., description="板块名称")
    signal: Signal = Field(..., description="信号：买入/卖出/观望")
    heat: int = Field(default=50, ge=0, le=100, description="热度 0-100")
    crowding: int = Field(default=50, ge=0, le=100, description="拥挤度 0-100，越高越危险")
    logic: str = Field(..., description="投资逻辑")
    contrarian_note: str = Field(default="", description="反人性提示")
    key_etf: list[str] = Field(default_factory=list, description="相关ETF")


class PositionAdvice(BaseModel):
    """仓位建议"""
    asset_type: AssetType = Field(..., description="资产类型：股票/债券/货币/黄金")
    current_position: PositionLevel = Field(..., description="建议仓位：重仓/标配/轻仓/空仓")
    change: PositionChange = Field(..., description="变化：加仓/减仓/持有")
    reason: str = Field(..., description="理由")


class PolicyInsight(BaseModel):
    """政策解读"""
    title: str = Field(..., description="政策/事件标题")
    summary: str = Field(..., description="政策内容摘要")
    investment_logic: str = Field(..., description="投资逻辑分析")
    contrarian_view: str = Field(..., description="反人性视角：大众会怎么想，我们应该怎么做")
    action_suggestion: str = Field(..., description="具体操作建议")
    related_sectors: list[str] = Field(default_factory=list, description="相关板块")


class InvestmentReport(BaseModel):
    """投资决策报告"""
    period: Literal["morning", "evening"] = Field(..., description="报告周期")
    generated_at: datetime = Field(default_factory=lambda: datetime.now())

    # 核心决策
    one_liner: str = Field(..., description="今日一句话决策")
    market_emotion: int = Field(default=50, ge=0, le=100, description="市场情绪 0-100，0极度恐惧 100极度贪婪")
    emotion_suggestion: str = Field(..., description="情绪建议：别人贪婪我恐惧...")

    # 全球→A股
    global_events: list[GlobalEvent] = Field(default_factory=list, description="全球事件")

    # 板块机会
    sector_opportunities: list[SectorOpportunity] = Field(default_factory=list)

    # 政策解读
    policy_insights: list[PolicyInsight] = Field(default_factory=list, description="政策深度解读")

    # 仓位建议
    position_advices: list[PositionAdvice] = Field(default_factory=list)

    # 风险提示
    risk_warnings: list[str] = Field(default_factory=list, description="风险警示")

    # 新闻来源
    news_sources: list[NewsItem] = Field(default_factory=list)
