"""TechCrunch 科技新闻采集器"""

from src.models import SourceType
from .rss_base import RSSCollector


class TechCrunchCollector(RSSCollector):
    """TechCrunch RSS 采集器"""

    RSS_URL = "https://techcrunch.com/feed/"
    SOURCE_NAME = "TechCrunch"
    SOURCE_TYPE = SourceType.INTERNATIONAL
    LANGUAGE = "en"
