"""Reuters 新闻采集器"""

from src.models import SourceType
from .rss_base import RSSCollector


class ReutersCollector(RSSCollector):
    """Reuters RSS 采集器"""

    RSS_URL = "https://reutersagency.com/feed/?taxonomy=best-topics&post_type=best"
    SOURCE_NAME = "Reuters"
    SOURCE_TYPE = SourceType.INTERNATIONAL
    LANGUAGE = "en"
