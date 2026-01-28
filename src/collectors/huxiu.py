"""虎嗅网 科技新闻采集器"""

from src.models import SourceType
from .rss_base import RSSCollector


class HuxiuCollector(RSSCollector):
    """虎嗅网 RSS 采集器"""

    RSS_URL = "https://www.huxiu.com/rss/0.xml"
    SOURCE_NAME = "虎嗅"
    SOURCE_TYPE = SourceType.DOMESTIC
    LANGUAGE = "zh"
