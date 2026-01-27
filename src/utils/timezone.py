"""统一时间处理模块

设计原则：
- 存储：统一用 UTC
- 显示：统一转北京时间
- 业务逻辑（如"今日"）：统一用北京时间判断
"""

from datetime import datetime, date, timezone, timedelta

# 北京时区 (UTC+8)
BEIJING_TZ = timezone(timedelta(hours=8))


def now_beijing() -> datetime:
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ)


def now_utc() -> datetime:
    """获取当前 UTC 时间"""
    return datetime.now(timezone.utc)


def today_beijing() -> date:
    """获取北京时间的今天日期"""
    return now_beijing().date()


def parse_datetime(dt_str: str) -> datetime:
    """解析各种格式的时间字符串为 UTC datetime"""
    if not dt_str:
        return None
    try:
        # ISO 格式 with Z
        if dt_str.endswith("Z"):
            dt_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        # 如果没有时区信息，假设是 UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def utc_to_beijing(dt) -> datetime:
    """将 UTC 时间转换为北京时间"""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = parse_datetime(dt)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BEIJING_TZ)


def format_beijing(dt, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化为北京时间字符串"""
    beijing_dt = utc_to_beijing(dt)
    if beijing_dt is None:
        return ""
    return beijing_dt.strftime(fmt)


def format_time_only(dt) -> str:
    """只显示时间 HH:MM"""
    return format_beijing(dt, "%H:%M")


def to_utc_iso(dt: datetime) -> str:
    """转换为 UTC ISO 格式字符串（用于存储）"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(timezone.utc).isoformat()
