"""基金数据服务 - 获取 ETF/LOF 实时行情和历史数据"""

import asyncio
import time
import httpx
from loguru import logger
from typing import Optional


class FundService:
    """基金数据服务"""

    def __init__(self):
        self.timeout = 15.0
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        # K线缓存: {secid: (timestamp, data)}
        self._kline_cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl = 300  # 5分钟

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

    async def _fetch_batch_with_retry(self, client, secids: list, max_retries: int = 3) -> list:
        """带重试的批量获取，失败时回退到单个查询"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    await asyncio.sleep(1 * attempt)  # 递增延迟
                resp = await client.get(
                    "https://push2.eastmoney.com/api/qt/ulist.np/get",
                    params={
                        "secids": ",".join(secids),
                        "fields": "f12,f14,f2,f3,f6,f8,f62,f184",
                    },
                )
                text = resp.text
                if not text or text.strip() == "":
                    logger.warning(f"批量API返回空响应，重试 {attempt + 1}/{max_retries}")
                    continue
                data = resp.json().get("data", {})
                diff = data.get("diff", [])
                if diff:
                    return diff
                logger.warning(f"批量API返回空数据，重试 {attempt + 1}/{max_retries}")
            except Exception as e:
                logger.warning(f"批量API请求失败: {e}，重试 {attempt + 1}/{max_retries}")

        # 批量失败，回退到新浪API
        logger.info("东方财富API失败，回退到新浪财经API")
        return await self._fetch_from_sina(client, secids)

    async def _fetch_from_sina(self, client, secids: list) -> list:
        """使用新浪财经API作为回退方案"""
        # 转换 secid 为新浪格式: 1.518880 -> sh518880, 0.159915 -> sz159915
        sina_codes = []
        for secid in secids:
            market, code = secid.split(".")
            prefix = "sh" if market == "1" else "sz"
            sina_codes.append(f"{prefix}{code}")

        try:
            resp = await client.get(
                f"https://hq.sinajs.cn/list={','.join(sina_codes)}",
                headers={"Referer": "https://finance.sina.com.cn"},
            )
            text = resp.text
            results = []
            for line in text.strip().split("\n"):
                if "=" not in line or '""' in line:
                    continue
                # 解析: var hq_str_sh518880="黄金ETF,10.883,..."
                var_part, data_part = line.split("=", 1)
                code = var_part.split("_")[-1][2:]  # 去掉 sh/sz 前缀
                data = data_part.strip('"').strip(";").split(",")
                if len(data) < 10:
                    continue
                results.append({
                    "f12": code,
                    "f14": data[0],  # 名称
                    "f2": int(float(data[3]) * 1000),  # 当前价 * 1000
                    "f3": int((float(data[3]) - float(data[2])) / float(data[2]) * 10000) if float(data[2]) else 0,  # 涨跌幅 * 100
                    "f6": int(float(data[9])),  # 成交额
                    "f8": 0,  # 换手率（新浪无此数据）
                    "f62": 0,  # 主力流入（新浪无此数据）
                    "f184": 0,  # 主力占比（新浪无此数据）
                })
            return results
        except Exception as e:
            logger.warning(f"新浪API也失败: {e}")
            return []

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
                # 1. 批量获取实时行情（含资金流向），带重试
                diff = await self._fetch_batch_with_retry(client, secids)

                result = {}
                for item in diff:
                    code = item.get("f12", "")
                    if code:
                        # f62: 主力净流入（元），f184: 主力净占比（需/100）
                        flow = item.get("f62", 0) or 0
                        flow_yi = round(flow / 100000000, 2)
                        flow_pct = round((item.get("f184", 0) or 0) / 100, 2)
                        turnover = round((item.get("f8", 0) or 0) / 100, 2)
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
                            "turnover": turnover,  # 换手率%
                        }

                # 2. 并发获取K线计算多周期涨跌幅
                tasks = []
                for code in result.keys():
                    tasks.append(self._get_kline_changes(client, code_to_secid.get(code, "")))

                if tasks:
                    kline_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for code, kline_data in zip(result.keys(), kline_results):
                        if isinstance(kline_data, dict):
                            result[code]["change_5d"] = kline_data.get("change_5d", 0)
                            result[code]["change_20d"] = kline_data.get("change_20d", 0)
                            result[code]["kline"] = kline_data.get("kline", [])

                return result
        except Exception as e:
            logger.warning(f"批量获取基金数据失败: {e}")
            return {}

    async def _get_kline_changes(self, client, secid: str) -> dict:
        """获取K线计算5日和20日涨跌幅，返回近20日收盘价（带缓存）"""
        # 检查缓存
        now = time.time()
        if secid in self._kline_cache:
            cached_time, cached_data = self._kline_cache[secid]
            if now - cached_time < self._cache_ttl:
                return cached_data
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
            closes = [float(k.split(",")[2]) for k in klines]
            today_close = closes[-1]

            change_5d = 0
            change_20d = 0

            if len(closes) >= 6:
                change_5d = round((today_close - closes[-6]) / closes[-6] * 100, 2)

            if len(closes) >= 21:
                change_20d = round((today_close - closes[-21]) / closes[-21] * 100, 2)

            # 返回近20日收盘价用于sparkline
            kline_data = closes[-20:] if len(closes) >= 20 else closes

            result = {
                "change_5d": change_5d,
                "change_20d": change_20d,
                "kline": kline_data,
            }
            # 存入缓存
            self._kline_cache[secid] = (now, result)
            return result
        except Exception:
            return {}


# 单例
fund_service = FundService()
