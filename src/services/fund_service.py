"""基金数据服务 - 获取 ETF/LOF 实时行情和历史数据"""

import asyncio
import json
import re
import time
import httpx
from loguru import logger
from typing import Optional

from src.config import settings

# 板块关键词映射（用于从 ETF 名称中提取板块）
# 格式: 板块名 -> [关键词列表]
# 注意：匹配顺序很重要，更具体的关键词应该放在前面
SECTOR_KEYWORDS = {
    # 科技类
    "芯片": ["芯片", "集成电路"],
    "半导体": ["半导体"],
    "人工智能": ["人工智能", "AI ETF", "AIETF"],
    "云计算": ["云计算", "大数据"],
    "通信": ["通信ETF", "5G"],
    "机器人": ["机器人"],
    # 新能源类
    "光伏": ["光伏"],
    "新能源车": ["新能源车", "新能源汽车", "智能汽车", "智能车"],
    "新能源": ["新能源ETF"],
    "锂电池": ["锂电池", "电池ETF"],
    # 军工
    "军工": ["军工", "国防", "航天航空", "航空航天"],
    # 医药类
    "创新药": ["创新药"],
    "医药": ["医药", "医疗", "生物制药"],
    # 金融类
    "证券": ["证券ETF", "券商ETF"],
    "银行": ["银行ETF"],
    "保险": ["保险ETF"],
    # 地产
    "房地产": ["房地产", "地产ETF"],
    # 消费类
    "白酒": ["白酒", "酒ETF"],
    "食品饮料": ["食品ETF", "饮料"],
    "消费": ["消费ETF"],
    "家电": ["家电"],
    # 农业
    "农业": ["农业ETF", "养殖", "畜牧", "猪"],
    # 资源类
    "黄金": ["黄金ETF"],
    "贵金属": ["贵金属", "白银"],
    "有色": ["有色金属", "铜ETF", "铝ETF", "稀土"],
    "煤炭": ["煤炭"],
    "钢铁": ["钢铁"],
    "石油": ["石油", "油气"],
    # 其他
    "汽车": ["汽车ETF", "汽车零部件"],
    "恒生科技": ["恒生科技"],
    "港股": ["港股通", "H股ETF"],
    "科技": ["科技ETF", "TMT"],
    "互联网": ["互联网"],
    "游戏": ["游戏ETF"],
    "传媒": ["传媒ETF"],
    "电力": ["电力ETF", "电网"],
    "环保": ["环保", "碳中和"],
}


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
        # ETF列表缓存: {sector: [(code, name, amount), ...]}
        self._etf_list_cache: dict[str, list] = {}
        self._etf_cache_time: float = 0
        self._etf_cache_ttl = 86400  # 24小时

    async def _fetch_all_etfs(self) -> list[dict]:
        """获取所有 ETF 列表（新浪为主，东方财富为备）"""
        # 优先使用新浪 API
        etfs = await self._fetch_etfs_from_sina()
        if etfs:
            return etfs
        # 回退到东方财富
        logger.info("新浪API失败，尝试东方财富API")
        return await self._fetch_etfs_from_eastmoney()

    async def _fetch_etfs_from_sina(self) -> list[dict]:
        """从新浪财经获取 ETF 列表"""
        all_etfs = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for page in range(1, 16):
                    resp = await client.get(
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
                        code = item.get("code", "")
                        if code:
                            all_etfs.append({
                                "code": code,
                                "name": item.get("name", ""),
                                "amount": item.get("amount", 0),
                            })
                    if len(data) < 100:
                        break
            logger.info(f"新浪API获取到 {len(all_etfs)} 个ETF")
            return all_etfs
        except Exception as e:
            logger.warning(f"新浪ETF列表API失败: {e}")
            return []

    async def _fetch_etfs_from_eastmoney(self) -> list[dict]:
        """从东方财富获取 ETF 列表（备用）"""
        all_etfs = []
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                    for page in range(1, 15):
                        resp = await client.get(
                            "https://push2.eastmoney.com/api/qt/clist/get",
                            params={
                                "pn": page,
                                "pz": 100,
                                "fs": "b:MK0021,b:MK0023,b:MK0024",
                                "fid": "f6",
                                "po": 1,
                                "fields": "f12,f14,f6",
                            },
                        )
                        data = resp.json().get("data", {})
                        diff = data.get("diff", {})
                        if not diff:
                            break
                        items = diff.values() if isinstance(diff, dict) else diff
                        for item in items:
                            if item.get("f12"):
                                all_etfs.append({
                                    "code": item.get("f12", ""),
                                    "name": item.get("f14", ""),
                                    "amount": item.get("f6", 0),
                                })
                    logger.info(f"东方财富API获取到 {len(all_etfs)} 个ETF")
                    return all_etfs
            except Exception as e:
                logger.warning(f"东方财富ETF列表失败(尝试{attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                all_etfs = []
        return all_etfs

    async def _fetch_etf_raw_info(self, client: httpx.AsyncClient, code: str) -> dict:
        """获取 ETF 原始信息"""
        try:
            url = f"https://fundf10.eastmoney.com/jbgk_{code}.html"
            resp = await client.get(url, timeout=10)
            text = resp.text

            info = {}
            # 基金全称
            m = re.search(r'基金全称</th><td[^>]*>([^<]+)', text)
            if m:
                info["full_name"] = m.group(1).strip()
            # 基金简称
            m = re.search(r'基金简称</th><td[^>]*>([^<]+)', text)
            if m:
                info["short_name"] = m.group(1).strip()
            # 基金管理人
            m = re.search(r'基金管理人</th><td[^>]*><a[^>]*>([^<]+)', text)
            if m:
                info["manager"] = m.group(1).strip()
            # 投资范围
            m = re.search(r'投资范围</label>.*?<p>\s*(.+?)\s*</p>', text, re.DOTALL)
            if m:
                info["scope"] = m.group(1).strip()
            # 风险收益特征
            m = re.search(r'风险收益特征</label>.*?<p>\s*(.+?)\s*</p>', text, re.DOTALL)
            if m:
                info["risk"] = m.group(1).strip()
            return info
        except Exception:
            pass
        return {}

    async def _summarize_etf_desc(self, client: httpx.AsyncClient, etf_infos: list[dict]) -> dict[str, str]:
        """用 AI 批量精炼 ETF 描述"""
        if not etf_infos:
            return {}

        etf_list = "\n".join([
            f"- {info['code']}: 全称={info.get('full_name','')}, "
            f"简称={info.get('short_name','')}, "
            f"管理人={info.get('manager','')}, "
            f"投资范围={info.get('scope','')[:200] if info.get('scope') else ''}, "
            f"风险特征={info.get('risk','')[:150] if info.get('risk') else ''}"
            for info in etf_infos
        ])

        prompt = f"""为以下ETF生成简洁描述（每个30-50字），突出投资标的和风险特征。

{etf_list}

输出JSON格式：{{"代码": "描述", ...}}"""

        try:
            resp = await client.post(
                f"{settings.claude_base_url.rstrip('/')}/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": settings.claude_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": settings.claude_model,
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60,
            )
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"].strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except Exception as e:
            logger.warning(f"AI精炼描述失败: {e}")
            return {}

    def _classify_etf(self, name: str) -> Optional[str]:
        """根据 ETF 名称识别所属板块"""
        # 排除宽基指数ETF
        exclude_keywords = ["沪深300", "中证500", "中证1000", "上证50",
                          "创业板ETF", "科创50", "科创100", "A500", "红利",
                          "深证100", "深成", "中小", "综指", "中证A"]
        for kw in exclude_keywords:
            if kw in name:
                return None

        # 排除跨境ETF（除非是专门的港股板块关键词）
        cross_border = ["香港", "纳指", "纳斯达克", "标普", "日经", "德国", "法国",
                       "中韩", "恒生互联网", "中概", "港股创新药", "港股通创新药",
                       "恒生医药", "恒生医疗"]
        if any(kw in name for kw in cross_border):
            # 只保留恒生科技和港股通（非创新药）
            if "恒生科技" in name:
                return "恒生科技"
            if "港股通" in name and "创新药" not in name:
                return "港股"
            return None

        # 排除复合型ETF（如"证券保险"）
        if "证券保险" in name:
            return None

        # 按关键词匹配板块
        for sector, keywords in SECTOR_KEYWORDS.items():
            for kw in keywords:
                if kw in name:
                    return sector
        return None

    async def get_sector_etf_map(self) -> dict[str, list[tuple[str, str]]]:
        """动态获取板块->ETF映射（按成交额排序）"""
        now = time.time()
        if self._etf_list_cache and now - self._etf_cache_time < self._etf_cache_ttl:
            return self._etf_list_cache

        etfs = await self._fetch_all_etfs()
        if not etfs:
            return self._etf_list_cache  # 返回旧缓存

        # 按板块分类
        sector_map: dict[str, list] = {}
        for etf in etfs:
            sector = self._classify_etf(etf["name"])
            if sector:
                if sector not in sector_map:
                    sector_map[sector] = []
                sector_map[sector].append((etf["code"], etf["name"], etf["amount"]))

        # 每个板块按成交额排序，只保留前5个
        for sector in sector_map:
            sector_map[sector].sort(key=lambda x: x[2], reverse=True)
            sector_map[sector] = [(code, name) for code, name, _ in sector_map[sector][:5]]

        self._etf_list_cache = sector_map
        self._etf_cache_time = now
        logger.info(f"更新ETF板块映射，共 {len(sector_map)} 个板块")
        return sector_map

    async def build_etf_master(self, top_n: int = 3) -> dict:
        """构建 ETF Master 数据（含描述）"""
        etfs = await self._fetch_all_etfs()
        if not etfs:
            return {"etfs": {}, "sectors": {}}

        # 按板块分类
        sector_map: dict[str, list] = {}
        for etf in etfs:
            sector = self._classify_etf(etf["name"])
            if sector:
                if sector not in sector_map:
                    sector_map[sector] = []
                sector_map[sector].append(etf)

        # 每个板块按成交额排序，取前N个
        result_etfs = {}
        result_sectors = {}

        for sector, etf_list in sector_map.items():
            etf_list.sort(key=lambda x: x["amount"], reverse=True)
            top_etfs = etf_list[:top_n]
            result_sectors[sector] = [e["code"] for e in top_etfs]

            for etf in top_etfs:
                if etf["code"] not in result_etfs:
                    result_etfs[etf["code"]] = {
                        "code": etf["code"],
                        "name": etf["name"],
                        "sector": sector,
                        "amount_yi": round(etf["amount"] / 1e8, 2),
                        "desc": "",
                    }

        # 批量获取原始信息
        logger.info(f"获取 {len(result_etfs)} 个ETF的信息...")
        async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
            sem = asyncio.Semaphore(5)

            async def fetch_info(code):
                async with sem:
                    info = await self._fetch_etf_raw_info(client, code)
                    info["code"] = code
                    return info

            tasks = [fetch_info(code) for code in result_etfs.keys()]
            raw_infos = await asyncio.gather(*tasks, return_exceptions=True)
            raw_infos = [r for r in raw_infos if isinstance(r, dict) and r.get("code")]

            # AI 批量精炼描述（每批20个）
            logger.info("AI精炼描述...")
            for i in range(0, len(raw_infos), 20):
                batch = raw_infos[i:i+20]
                descs = await self._summarize_etf_desc(client, batch)
                for code, desc in descs.items():
                    if code in result_etfs:
                        result_etfs[code]["desc"] = desc

        return {"etfs": result_etfs, "sectors": result_sectors}

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
                    "_from_sina": True,  # 标记来自新浪，需要单独获取K线
                })
            return results
        except Exception as e:
            logger.warning(f"新浪API也失败: {e}")
            return []

    async def _get_kline_from_sina(self, client, code: str) -> dict:
        """从新浪获取K线数据"""
        try:
            prefix = "sh" if code.startswith("5") else "sz"
            sina_code = f"{prefix}{code}"
            # 新浪日K线API
            resp = await client.get(
                f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",
                params={
                    "symbol": sina_code,
                    "scale": "240",  # 日K
                    "ma": "no",
                    "datalen": "25",
                },
                headers={"Referer": "https://finance.sina.com.cn"},
            )
            data = resp.json()
            if not data or not isinstance(data, list):
                return {}

            closes = [float(item["close"]) for item in data]
            if len(closes) < 2:
                return {}

            today_close = closes[-1]
            change_5d = 0
            change_20d = 0

            if len(closes) >= 6:
                change_5d = round((today_close - closes[-6]) / closes[-6] * 100, 2)
            if len(closes) >= 21:
                change_20d = round((today_close - closes[-21]) / closes[-21] * 100, 2)

            kline_data = closes[-20:] if len(closes) >= 20 else closes
            return {
                "change_5d": change_5d,
                "change_20d": change_20d,
                "kline": kline_data,
            }
        except Exception as e:
            logger.warning(f"新浪K线API失败 {code}: {e}")
            return {}

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
                        # 确保 code_to_secid 映射存在（新浪回退时可能缺失）
                        if code not in code_to_secid:
                            if code.startswith("5"):
                                code_to_secid[code] = f"1.{code}"
                            else:
                                code_to_secid[code] = f"0.{code}"

                # 2. 并发获取K线计算多周期涨跌幅（东方财富K线API）
                tasks = []
                codes_list = list(result.keys())
                for code in codes_list:
                    secid = code_to_secid.get(code, "")
                    tasks.append(self._get_kline_changes(client, secid))

                if tasks:
                    kline_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for code, kline_data in zip(codes_list, kline_results):
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
        if not secid:
            return {}
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
        except Exception as e:
            logger.warning(f"东方财富K线失败 {secid}: {e}，尝试新浪")
            # 回退到新浪K线API
            code = secid.split(".")[-1] if "." in secid else ""
            if code:
                return await self._get_kline_from_sina(client, code)
            return {}


    async def get_hot_etfs(self, limit: int = 10) -> list[dict]:
        """获取热门 ETF（从动态映射中获取，按成交额排序）"""
        sector_map = await self.get_sector_etf_map()
        if not sector_map:
            return []

        # 每个板块取第一个 ETF
        etf_codes = []
        for etfs in sector_map.values():
            if etfs:
                etf_codes.append(etfs[0][0])  # (code, name)

        if not etf_codes:
            return []

        data = await self.batch_get_funds(etf_codes)
        if not data:
            return []

        # 按成交额排序
        sorted_etfs = sorted(
            data.values(),
            key=lambda x: x.get("amount_yi", 0),
            reverse=True
        )
        return sorted_etfs[:limit]

    async def get_sector_etfs(self, sector: str, limit: int = 3) -> list[dict]:
        """获取板块相关ETF（动态获取，按成交额排序）"""
        # 动态获取板块映射
        sector_map = await self.get_sector_etf_map()

        # 查找匹配的板块
        codes = None
        for key, etfs in sector_map.items():
            if key in sector or sector in key:
                codes = [code for code, name in etfs]
                break

        if not codes:
            return []

        data = await self.batch_get_funds(codes[:limit])
        if not data:
            return []

        # 按成交额排序
        sorted_etfs = sorted(
            data.values(),
            key=lambda x: x.get("amount_yi", 0),
            reverse=True
        )
        return sorted_etfs[:limit]


# 单例
fund_service = FundService()
