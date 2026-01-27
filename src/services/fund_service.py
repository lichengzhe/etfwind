"""基金数据服务 - 获取 ETF/LOF 实时行情和历史数据"""

import httpx
from loguru import logger
from typing import Optional


class FundService:
    """基金数据服务"""

    def __init__(self):
        self.timeout = 10.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://quote.eastmoney.com/",
        }

    async def get_fund_info(self, code: str) -> Optional[dict]:
        """获取基金实时信息"""
        try:
            # 判断市场：5开头上海，1开头深圳
            if code.startswith("5"):
                secid = f"1.{code}"
            else:
                secid = f"0.{code}"

            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                # 获取实时行情
                resp = await client.get(
                    "https://push2.eastmoney.com/api/qt/stock/get",
                    params={
                        "secid": secid,
                        "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f170,f171",
                    },
                )
                data = resp.json().get("data", {})
                if not data:
                    return None

                # 获取近5日K线计算涨跌幅
                kline_resp = await client.get(
                    "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                    params={
                        "secid": secid,
                        "fields1": "f1,f2,f3",
                        "fields2": "f51,f52,f53,f54,f55,f56",
                        "klt": "101",
                        "fqt": "1",
                        "end": "20500101",
                        "lmt": "6",
                    },
                )
                klines = kline_resp.json().get("data", {}).get("klines", [])

                return self._parse_fund_data(data, klines)

        except Exception as e:
            logger.warning(f"获取基金 {code} 数据失败: {e}")
            return None

    def _parse_fund_data(self, data: dict, klines: list) -> dict:
        """解析基金数据"""
        # 实时数据
        price = data.get("f43", 0) / 1000  # 当前价
        change_pct = data.get("f170", 0) / 100  # 涨跌幅%
        volume = data.get("f47", 0)  # 成交量
        amount = data.get("f48", 0)  # 成交额

        # 计算近5日涨跌幅
        week_change = 0
        if len(klines) >= 5:
            try:
                # kline格式: 日期,开,收,高,低,成交量
                today_close = float(klines[-1].split(",")[2])
                five_days_ago_close = float(klines[-5].split(",")[2])
                week_change = (today_close - five_days_ago_close) / five_days_ago_close * 100
            except (IndexError, ValueError):
                pass

        # 资金热度：根据成交额判断
        heat = self._calc_heat(amount)

        return {
            "code": data.get("f57", ""),
            "name": data.get("f58", ""),
            "price": round(price, 3),
            "change_pct": round(change_pct, 2),
            "week_change": round(week_change, 2),
            "volume": volume,
            "amount": amount,
            "amount_yi": round(amount / 100000000, 2),  # 亿元
            "heat": heat,
        }

    def _calc_heat(self, amount: float) -> str:
        """根据成交额计算热度"""
        yi = amount / 100000000
        if yi >= 50:
            return "极热"
        elif yi >= 20:
            return "较热"
        elif yi >= 5:
            return "一般"
        else:
            return "冷清"

    async def batch_get_funds(self, codes: list[str]) -> dict[str, dict]:
        """批量获取基金信息（实时行情+多周期涨跌幅）"""
        if not codes:
            return {}

        # 构建 secids: 5开头上海(1.)，其他深圳(0.)
        secids = []
        code_to_secid = {}
        for code in codes:
            if code.startswith("5"):
                secid = f"1.{code}"
            else:
                secid = f"0.{code}"
            secids.append(secid)
            code_to_secid[code] = secid

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                # 1. 批量获取实时行情（含资金流向）
                resp = await client.get(
                    "https://push2.eastmoney.com/api/qt/ulist.np/get",
                    params={
                        "secids": ",".join(secids),
                        "fields": "f12,f14,f2,f3,f6,f62,f184",
                    },
                )
                data = resp.json().get("data", {})
                diff = data.get("diff", [])

                result = {}
                for item in diff:
                    code = item.get("f12", "")
                    if code:
                        # f62: 主力净流入（元），f184: 主力净占比（需/100）
                        flow = item.get("f62", 0) or 0
                        flow_yi = round(flow / 100000000, 2)
                        flow_pct = round((item.get("f184", 0) or 0) / 100, 2)
                        result[code] = {
                            "code": code,
                            "name": item.get("f14", ""),
                            "price": round(item.get("f2", 0) / 1000, 3),
                            "change_pct": round(item.get("f3", 0) / 100, 2),
                            "change_5d": 0,
                            "change_20d": 0,
                            "amount_yi": round(item.get("f6", 0) / 100000000, 2),
                            "flow_yi": flow_yi,  # 主力净流入（亿）
                            "flow_pct": flow_pct,  # 主力净占比%
                        }

                # 2. 并发获取K线计算多周期涨跌幅
                import asyncio
                tasks = []
                for code in result.keys():
                    tasks.append(self._get_kline_changes(client, code_to_secid.get(code, "")))

                if tasks:
                    kline_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for code, kline_data in zip(result.keys(), kline_results):
                        if isinstance(kline_data, dict):
                            result[code]["change_5d"] = kline_data.get("change_5d", 0)
                            result[code]["change_20d"] = kline_data.get("change_20d", 0)

                return result
        except Exception as e:
            logger.warning(f"批量获取基金数据失败: {e}")
            return {}

    async def _get_kline_changes(self, client, secid: str) -> dict:
        """获取K线计算5日和20日涨跌幅"""
        try:
            resp = await client.get(
                "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                params={
                    "secid": secid,
                    "fields1": "f1,f2,f3",
                    "fields2": "f51,f52,f53,f54,f55,f56",
                    "klt": "101",
                    "fqt": "1",
                    "end": "20500101",
                    "lmt": "25",
                },
            )
            klines = resp.json().get("data", {}).get("klines", [])
            if not klines:
                return {}

            # kline格式: 日期,开,收,高,低,成交量
            today_close = float(klines[-1].split(",")[2])

            change_5d = 0
            change_20d = 0

            if len(klines) >= 6:
                close_5d = float(klines[-6].split(",")[2])
                change_5d = round((today_close - close_5d) / close_5d * 100, 2)

            if len(klines) >= 21:
                close_20d = float(klines[-21].split(",")[2])
                change_20d = round((today_close - close_20d) / close_20d * 100, 2)

            return {"change_5d": change_5d, "change_20d": change_20d}
        except Exception:
            return {}


# 单例
fund_service = FundService()
