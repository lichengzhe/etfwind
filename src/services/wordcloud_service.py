"""词云生成服务"""

import io
import base64
from pathlib import Path
from wordcloud import WordCloud
from loguru import logger


# 中文字体路径
FONT_PATHS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",  # macOS
    "/System/Library/Fonts/Hiragino Sans GB.ttc",  # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Ubuntu
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",  # Ubuntu alt
]


def find_font() -> str | None:
    """查找可用的中文字体"""
    for path in FONT_PATHS:
        if Path(path).exists():
            return path
    return None


def generate_wordcloud(
    words: list[dict],
    width: int = 400,
    height: int = 200,
    background: str = "#ffffff",
) -> bytes | None:
    """生成词云图片

    Args:
        words: [{"word": "避险", "weight": 5}, ...]
        width: 图片宽度
        height: 图片高度
        background: 背景色

    Returns:
        PNG 图片字节，失败返回 None
    """
    if not words:
        return None

    # 转换为 wordcloud 需要的格式 {word: weight}
    freq = {w["word"]: w["weight"] for w in words if w.get("word")}
    if not freq:
        return None

    font_path = find_font()
    if not font_path:
        logger.warning("未找到中文字体，词云可能显示乱码")

    try:
        wc = WordCloud(
            font_path=font_path,
            width=width,
            height=height,
            background_color=background,
            color_func=_color_func,
            prefer_horizontal=0.9,
            min_font_size=12,
            max_font_size=60,
            relative_scaling=0.5,
        )
        wc.generate_from_frequencies(freq)

        # 输出为 PNG
        buf = io.BytesIO()
        wc.to_image().save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"生成词云失败: {e}")
        return None


def generate_wordcloud_base64(words: list[dict], **kwargs) -> str | None:
    """生成词云并返回 base64 编码"""
    data = generate_wordcloud(words, **kwargs)
    if data:
        return base64.b64encode(data).decode()
    return None


def _color_func(word, font_size, position, orientation, **kwargs):
    """自定义颜色函数 - 暖色调"""
    colors = [
        "#dc2626",  # 红
        "#ea580c",  # 橙
        "#d97706",  # 琥珀
        "#ca8a04",  # 黄
        "#65a30d",  # 绿
    ]
    # 根据字号选择颜色（大字用红色）
    if font_size > 40:
        return colors[0]
    elif font_size > 30:
        return colors[1]
    elif font_size > 20:
        return colors[2]
    else:
        return colors[3]
