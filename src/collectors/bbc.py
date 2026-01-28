"""BBC Business 新闻采集器"""

from src.models import SourceType
from .rss_base import RSSCollector


class BBCCollector(RSSCollector):
    """BBC Business RSS 采集器"""

    RSS_URL = "https://feeds.bbci.co.uk/news/business/rss.xml"
    SOURCE_NAME = "BBC"
    SOURCE_TYPE = SourceType.INTERNATIONAL
    LANGUAGE = "en"
