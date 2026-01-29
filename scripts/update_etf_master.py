"""更新 ETF Master 数据

用法：
    python scripts/update_etf_master.py

功能：
    1. 从新浪获取全量 ETF 列表
    2. 按成交额筛选活跃 ETF
    3. 自动分类到板块
    4. 保存到 config/etf_sectors.json
"""

import json
import re
from pathlib import Path
import httpx

# 板块关键词映射
SECTOR_KEYWORDS = {
    "黄金": ["黄金", "金ETF", "上海金"],
    "有色": ["有色", "金属ETF", "稀土", "铜", "铝", "锌"],
    "芯片": ["芯片", "半导体", "集成电路", "半导设备"],
    "证券": ["证券", "券商", "非银"],
    "银行": ["银行"],
    "医药": ["医疗", "医药", "生物", "创新药"],
    "白酒": ["酒ETF", "白酒"],
    "消费": ["消费", "食品"],
    "军工": ["军工", "国防", "卫星", "航天", "航空"],
    "新能源": ["新能源", "光伏", "风电", "清洁能源"],
    "锂电池": ["锂电", "电池", "储能"],
    "汽车": ["汽车", "智能车", "新能车"],
    "房地产": ["房地产", "地产"],
    "煤炭": ["煤炭"],
    "钢铁": ["钢铁"],
    "石油": ["石油", "油气"],
    "化工": ["化工"],
    "电力": ["电力", "电网", "电气"],
    "农业": ["农业", "养殖", "畜牧"],
    "家电": ["家电"],
    "机器人": ["机器人"],
    "人工智能": ["人工智能", "AI"],
    "软件": ["软件", "云计算", "计算机"],
    "通信": ["通信", "5G"],
    "互联网": ["互联网"],
    "游戏": ["游戏", "动漫"],
    "传媒": ["传媒", "影视"],
    "环保": ["环保", "碳中和"],
    "恒生科技": ["恒生科技"],
    "港股": ["港股", "香港", "恒生互联", "恒生医疗", "恒生生物"],
}

# 排除关键词
EXCLUDE_KEYWORDS = [
    "债", "货币", "添益", "日利", "短融",
    "500", "300", "1000", "50ETF", "科创50", "创业板ETF",
    "A500", "中证A", "综指", "红利",
    "纳指", "标普", "日经", "德国", "法国", "中韩", "中概",
    "沙特", "巴西", "越南", "印度",
    "恒生指数", "国企", "央企",
    "保证金", "自由现金", "期货", "豆粕", "能源化工",
    "上证", "深证", "中小板",
]


def fetch_all_etfs() -> list[dict]:
    """从新浪获取全量 ETF"""
    all_etfs = []
    with httpx.Client(timeout=30) as client:
        for page in range(1, 10):
            resp = client.get(
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData",
                params={
                    "page": page,
                    "num": 100,
                    "sort": "amount",
                    "asc": 0,
                    "node": "etf_hq_fund",
                },
                headers={"Referer": "https://finance.sina.com.cn"},
            )
            data = resp.json()
            if not data:
                break
            for item in data:
                all_etfs.append({
                    "code": item.get("code", ""),
                    "name": item.get("name", ""),
                    "amount": float(item.get("amount", 0)),
                })
            if len(data) < 100:
                break
    print(f"获取到 {len(all_etfs)} 个 ETF")
    return all_etfs


def should_exclude(name: str) -> bool:
    """检查是否应排除"""
    return any(kw in name for kw in EXCLUDE_KEYWORDS)


def classify_etf(name: str) -> str | None:
    """根据名称分类到板块"""
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return sector
    return None


def build_sector_map(etfs: list[dict], min_amount: float = 5e6) -> dict:
    """构建板块映射"""
    sector_map = {}

    for etf in etfs:
        name = etf["name"]
        code = etf["code"]
        amount = etf["amount"]

        # 排除宽基/债券等
        if should_exclude(name):
            continue

        # 成交额过滤
        if amount < min_amount:
            continue

        # 分类
        sector = classify_etf(name)
        if not sector:
            continue

        if sector not in sector_map:
            sector_map[sector] = []

        sector_map[sector].append({
            "code": code,
            "name": name,
            "amount_yi": round(amount / 1e8, 2),
        })

    # 每个板块按成交额排序，保留前5个
    for sector in sector_map:
        sector_map[sector].sort(key=lambda x: x["amount_yi"], reverse=True)
        sector_map[sector] = sector_map[sector][:5]
        # 移除 amount_yi 字段
        for etf in sector_map[sector]:
            del etf["amount_yi"]

    return sector_map


def main():
    # 获取 ETF 列表
    etfs = fetch_all_etfs()

    # 构建板块映射
    sector_map = build_sector_map(etfs, min_amount=5e6)

    # 添加元数据
    from datetime import datetime
    sector_map["_meta"] = {
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "note": "运行 python scripts/update_etf_master.py 更新",
    }

    # 统计
    total_etfs = sum(len(v) for k, v in sector_map.items() if not k.startswith("_"))
    print(f"\n共 {len(sector_map) - 1} 个板块，{total_etfs} 个 ETF")
    for sector, etfs in sorted(sector_map.items()):
        if sector.startswith("_"):
            continue
        print(f"  {sector}: {len(etfs)} 个")

    # 保存
    output_file = Path(__file__).parent.parent / "config" / "etf_sectors.json"
    output_file.write_text(json.dumps(sector_map, ensure_ascii=False, indent=2))
    print(f"\n已保存到 {output_file}")


if __name__ == "__main__":
    main()
