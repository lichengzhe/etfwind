"""自由時報即時新聞 RSS 採集器"""

from src.models import SourceType
from .rss_base import RSSCollector


class LTNCollector(RSSCollector):
    """自由時報即時新聞 RSS 採集器"""

    RSS_URL = "https://news.ltn.com.tw/rss/all.xml"
    SOURCE_NAME = "自由時報"
    SOURCE_TYPE = SourceType.DOMESTIC
    LANGUAGE = "zh-TW"
