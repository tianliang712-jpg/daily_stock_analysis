#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_stock_analysis - A股每日智能分析工具
针对田亮的股票池（66只A股，15个板块）
数据源：AKShare（免费开源）
AI分析：Gemini API
推送：企业微信群机器人

支持三种模式：
- pre_market: 竞价监测（09:15）
- noon: 午间分析（11:30）
- full: 收盘分析（15:30）
"""

import os
import json
import time
import datetime
import requests
import akshare as ak
import pandas as pd
from typing import Optional
import google.generativeai as genai

# ─── 环境变量 ────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
WECHAT_WEBHOOK = os.environ.get("WECHAT_WEBHOOK", "")
RUN_MODE = os.environ.get("RUN_MODE", "full")

# ─── 内嵌股票池（15个板块） ────────────────────
# Expanded Stock Pool (112)
STOCK_POOL = {
    "半导体芯片": [
        ("603160","汇顶科技"),
        ("603501","韦尔股份"),
        ("603986","兆易创新"),
        ("300456","赛微电子"),
        ("300458","全志科技"),
        ("300223","晶瑞股份"),
        ("300046","立立电子"),
        ("300102","乾照光电"),
        ("300373","扬杰科技"),
        ("300308","太辰光"),
        ("300805","中际旭创"),
        ("300502","新易盛")
    ],
    "新能源储能": [
        ("002460","赣锋锂业"),
        ("002594","比亚迪"),
        ("300014","亿纬锂能"),
        ("002074","国轩高科"),
        ("002812","恩捷股份"),
        ("300618","寒锐钴业"),
        ("300450","先导智能"),
        ("300274","阳光电源")
    ],
    "AI算力": [
        ("002230","科大讯飞"),
        ("300229","拓尔思"),
        ("300033","同花顺"),
        ("300017","网宿科技"),
        ("300369","宁波环球"),
        ("300454","网宿科技")
    ],
    "机器人自动化": [
        ("300124","汇川技术"),
        ("002472","新时达"),
        ("300403","汉宇集团"),
        ("002896","中科三环"),
        ("300195","长荣股份"),
        ("300154","瑞凌股份")
    ],
    "医疗健康": [
        ("300760","迈瑞医疗"),
        ("300529","健帆生物"),
        ("002007","华兰生物"),
        ("002223","鱼跃医疗"),
        ("300003","乐普医疗"),
        ("300015","爱尔眼科"),
        ("300347","泰格医药"),
        ("603259","药明康德"),
        ("002821","凯莱英")
    ],
    "军工航天": [
        ("600893","航发动力"),
        ("600316","洪都航空"),
        ("600038","中直股份"),
        ("002013","中航机电"),
        ("300034","钢研高纳"),
        ("600862","中航资本")
    ],
    "消费品牌": [
        ("000858","五粮液"),
        ("603288","海天味业"),
        ("603517","绝味食品"),
        ("603605","珀莱雅"),
        ("002507","涪陵榨菜"),
        ("002959","小熊电器")
    ],
    "金融科技": [
        ("300059","东方财富"),
        ("600570","恒生电子"),
        ("002195","二三四五"),
        ("300377","赢时胜"),
        ("002536","郑州银行"),
        ("300226","上海钢联")
    ],
    "新材料": [
        ("300285","金力泰"),
        ("002426","胜利精密"),
        ("300408","石英股份"),
        ("002643","万润股份"),
        ("300037","新纶股份"),
        ("002709","天赐材料")
    ],
    "出海跨境": [
        ("002475","立讯精密"),
        ("002832","比音勒芬"),
        ("603055","台华新材"),
        ("002293","罗莱生活"),
        ("002563","森马服饰"),
        ("002029","七匹狼"),
        ("002612","朗科智能"),
        ("002876","利尔化学")
    ],
    "光伏风电": [
        ("600438","通威股份"),
        ("002129","中环股份"),
        ("002202","金风科技"),
        ("002531","新强联"),
        ("300118","惠程科技"),
        ("600703","三安光电")
    ],
    "消费电子": [
        ("002241","歌尔股份"),
        ("002351","漫步者"),
        ("300207","欣旺达"),
        ("002045","国光电器"),
        ("002351","漫步者"),
        ("002736","国光电器")
    ],
    "农业粮食": [
        ("002311","海大集团"),
        ("002714","牧原股份"),
        ("002124","天邦股份"),
        ("600108","亚盛集团"),
        ("600598","北大荒")
    ],
    "软件云计算": [
        ("002410","广联达"),
        ("002065","东华软件"),
        ("002279","久其软件"),
        ("300184","鼎捷软件"),
        ("300322","宝信软件")
    ],
    "基础设施": [
        ("601390","中国中铁"),
        ("601668","中国建筑"),
        ("600170","上海建工"),
        ("600284","浦东建设"),
        ("002062","宏润建设")
    ],
    "其他龙头": [
        ("000001","平安银行"),
        ("000002","万 科Ａ"),
        ("000063","中兴通讯"),
        ("000333","美的集团"),
        ("000338","潍柴动力"),
        ("000651","格力电器"),
        ("000725","京东方Ａ"),
        ("002008","大族激光"),
        ("002027","分众传媒"),
        ("002236","大华股份"),
        ("002415","海康威视"),
        ("000938","紫金矿业")
    ]
}


def get_market_overview():
    """获取大盘概况"""
    result = {}
    index_map = {
        "上证指数": "sh000001",
        "创业板指": "sz399006",
        "沪深300": "sh000300",
    }
    for name, symbol in index_map.items():
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is not None and len(df) >= 2:
                latest = df.iloc[-1]
                prev = df.iloc[-2]
                close_col = [c for c in df.columns if "close" in c.lower() or "收盘" in c]
                if close_col:
                    c = close_col[0]
                    close = float(latest[c])
                    prev_close = float(prev[c])
                    chg_pct = (close - prev_close) / prev_close * 100
                    result[name] = {"close": round(close, 2), "chg_pct": round(chg_pct, 2)}
        except Exception as e:
            result[name] = {"error": str(e)[:50]}
    return result


def get_realtime_data():
    """获取实时行情（竞价/午盘用）"""
    result = {}
    try:
        # 获取大盘实时行情
        df = ak.stock_zh_a_spot_em()
        if df is not None:
            # 上证
            sh = df[df['代码'] == '000001']
            if not sh.empty:
                result['上证指数'] = {
                    'close': float(sh.iloc[0]['最新价']) if pd.notna(sh.iloc[0]['最新价']) else 0,
                    'chg_pct': float(sh.iloc[0]['涨跌幅']) if pd.notna(sh.iloc[0]['涨跌幅']) else 0,
                    'amount': float(sh.iloc[0]['成交额']) if pd.notna(sh.iloc[0]['成交额']) else 0,
                }
            # 创业板
            cy = df[df['代码'] == '399006']
            if not cy.empty:
                result['创业板指'] = {
                    'close': float(cy.iloc[0]['最新价']) if pd.notna(cy.iloc[0]['最新价']) else 0,
                    'chg_pct': float(cy.iloc[0]['涨跌幅']) if pd.notna(cy.iloc[0]['涨跌幅']) else 0,
                }
    except Exception as e:
        print(f"实时行情获取失败: {e}")
    return result


def get_stock_data(code, name):
    """获取单只股票近30日行情"""
    try:
        start = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y%m%d")
        end = datetime.date.today().strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start, end_date=end, adjust="qfq"
        )
        if df is None or df.empty or len(df) < 2:
            return None

        # 自动识别列名
        cols = {c.lower(): c for c in df.columns}
        close_col = next((cols[k] for k in cols if "close" in k or "收盘" in k), None)
        vol_col = next((cols[k] for k in cols if "volume" in k or "成交量" in k), None)
        turn_col = next((cols[k] for k in cols if "turnover" in k or "换手" in k), None)
        chg_col = next((cols[k] for k in cols if "pct_chg" in k or "涨跌幅" in k), None)

        if not close_col:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        close = float(latest[close_col])
        prev_close = float(prev[close_col])
        chg_pct = (close - prev_close) / prev_close * 100

        ma5 = float(df[close_col].tail(5).mean())

        vol_ratio = None
        if vol_col:
            vol_today = float(latest[vol_col])
            vol_5avg = float(df[vol_col].tail(5).mean())
            vol_ratio = round(vol_today / vol_5avg, 2) if vol_5avg > 0 else None

        turnover = float(latest[turn_col]) if turn_col else None

        return {
            "name": name, "code": code,
            "close": round(close, 2),
            "chg_pct": round(chg_pct, 2),
            "ma5": round(ma5, 2),
            "above_ma5": close > ma5,
            "vol_ratio": vol_ratio,
            "turnover": round(turnover, 2) if turnover else None,
        }
    except Exception as e:
        return {"name": name, "code": code, "error": str(e)[:80]}


def collect_all_stocks():
    """采集全部股票数据（去重）"""
    seen = set()
    sector_data = {}
    total = sum(len(v) for v in STOCK_POOL.values())
    done = 0

    for sector, stocks in STOCK_POOL.items():
        sector_data[sector] = []
        for code, sname in stocks:
            done += 1
            if code in seen:
                print(f"  [{done}/{total}] {sname}({code}) 跳过（已获取）")
                continue
            seen.add(code)
            data = get_stock_data(code, sname)
            if data:
                sector_data[sector].append(data)
            print(f"  [{done}/{total}] {sname}({code}) 完成")
            time.sleep(0.4)

    return sector_data


def find_opportunities(sector_data):
    """筛选机会"""
    all_stocks = []
    for sector, stocks in sector_data.items():
        for s in stocks:
            if "error" not in s:
                s_copy = s.copy()
                s_copy["sector"] = sector
                all_stocks.append(s_copy)

    sorted_up = sorted([s for s in all_stocks if s.get("chg_pct", 0) > 0],
                       key=lambda x: x["chg_pct"], reverse=True)
    sorted_down = sorted([s for s in all_stocks if s.get("chg_pct", 0) < 0],
                         key=lambda x: x["chg_pct"])
    volume_surge = sorted(
        [s for s in all_stocks if (s.get("vol_ratio") or 0) > 1.5 and s.get("chg_pct", 0) > 1],
        key=lambda x: x.get("vol_ratio", 0), reverse=True
    )

    return {
        "top_gainers":  sorted_up[:5],
        "top_losers":   sorted_down[:5],
        "volume_surge": volume_surge[:5],
        "total_up":     len([s for s in all_stocks if s.get("chg_pct", 0) > 0]),
        "total_down":   len([s for s in all_stocks if s.get("chg_pct", 0) < 0]),
        "total_flat":   len([s for s in all_stocks if s.get("chg_pct", 0) == 0]),
        "total_count":  len(all_stocks),
    }


def ai_analysis_pre_market(market):
    """竞价监测 AI 分析"""
    if not GEMINI_API_KEY:
        return "（未配置 GEMINI_API_KEY，跳过AI分析）"

    genai.configure(api_key=GEMINI_API_KEY)

    sh = market.get("上证指数", {})
    cy = market.get("创业板指", {})

    prompt = f"""你是一位专业A股短线分析师，请为投资者提供竞价时段（开盘前）的分析参考。

【隔夜外盘】
（请根据您了解的美股、港股、A50期指走势提供参考）

【大盘风向】
上证指数：开盘前点位 {sh.get('close','N/A')}（昨日 {sh.get('chg_pct','N/A'):+}%）
创业板指：开盘前点位 {cy.get('close','N/A')}（昨日 {cy.get('chg_pct','N/A'):+}%）

【竞价预估】
根据隔夜信息、板块轮动、资金流向，预判今日竞价方向：
1. 今日竞价可能高开/低开的板块
2. 开盘可能强势的标的
3. 需要避开的风险标的

请严格用中文输出（禁止英文），纯文本格式（不用markdown），总字数控制在200字以内，包含：
1. 【竞价方向】高开/低开/平开
2. 【重点关注】1-2只竞价可能强势的标的
3. 【风险提示】1条风险提示

重要：全程使用中文，不得出现英文单词。"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash", system_instruction="你是专业A股分析师，必须全程使用中文回答，禁止使用英文。")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI分析调用失败: {e}"


def ai_analysis_noon(market, opportunities, sector_data):
    """午间分析 AI"""
    if not GEMINI_API_KEY:
        return "（未配置 GEMINI_API_KEY，跳过AI分析）"

    genai.configure(api_key=GEMINI_API_KEY)

    sector_summary = []
    for sector, stocks in sector_data.items():
        valid = [s for s in stocks if "error" not in s]
        if valid:
            avg_chg = sum(s.get("chg_pct", 0) for s in valid) / len(valid)
            sector_summary.append(f"{sector}({avg_chg:+.1f}%)")

    def fmt_stocks(lst):
        if not lst:
            return "无"
        return "\n".join(
            [f"  {s['name']}({s['code']}) {s.get('chg_pct',0):+.2f}% 量比{s.get('vol_ratio','N/A')}"
             for s in lst]
        )

    sh = market.get("上证指数", {})
    cy = market.get("创业板指", {})

    prompt = f"""你是一位专业A股短线分析师，请根据以下上午盘面数据，为投资者提供午间操作建议。

【上午盘面】
上证指数: {sh.get("close","N/A")} ({sh.get("chg_pct","N/A"):+}%)
创业板指: {cy.get("close","N/A")} ({cy.get("chg_pct","N/A"):+}%)

【上午概况】
上涨{opportunities["total_up"]}只，下跌{opportunities["total_down"]}只

【板块涨跌】
{", ".join(sector_summary[:8])}

【上午领涨】
{fmt_stocks(opportunities["top_gainers"][:3])}

【放量异动】
{fmt_stocks(opportunities["volume_surge"][:3])}

请严格用中文输出（禁止英文），纯文本格式（不用markdown），总字数控制在250字以内，包含：
1. 【上午总结】盘面表现
2. 【下午展望】可能的走势
3. 【操作建议】持仓/买入/卖出/观望
4. 【下午机会】1-2只下午可能发力的标的

重要：全程使用中文，不得出现英文单词。"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash", system_instruction="你是专业A股分析师，必须全程使用中文回答，禁止使用英文。")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI分析调用失败: {e}"


def ai_analysis_full(market, opportunities, sector_data):
    """收盘分析 AI"""
    if not GEMINI_API_KEY:
        return "（未配置 GEMINI_API_KEY，跳过AI分析）"

    genai.configure(api_key=GEMINI_API_KEY)

    sector_summary = []
    for sector, stocks in sector_data.items():
        valid = [s for s in stocks if "error" not in s]
        if valid:
            avg_chg = sum(s.get("chg_pct", 0) for s in valid) / len(valid)
            sector_summary.append(f"{sector}({avg_chg:+.1f}%)")

    def fmt_stocks(lst):
        if not lst:
            return "无"
        return "\n".join(
            [f"  {s['name']}({s['code']}) {s.get('chg_pct',0):+.2f}% 量比{s.get('vol_ratio','N/A')}"
             for s in lst]
        )

    sh = market.get("上证指数", {})
    cy = market.get("创业板指", {})
    hs = market.get("沪深300", {})

    prompt = f"""你是一位专业A股短线分析师，请根据以下今日数据，为小资金个人投资者（T+1操作，偏好中小盘弹性品种）提供日终分析报告。

【大盘】
上证指数: {sh.get("close","N/A")} ({sh.get("chg_pct","N/A"):+}%)
创业板指: {cy.get("close","N/A")} ({cy.get("chg_pct","N/A"):+}%)
沪深300: {hs.get("close","N/A")} ({hs.get("chg_pct","N/A"):+}%)

【股票池概况】
共{opportunities["total_count"]}只有效：上涨{opportunities["total_up"]}只，下跌{opportunities["total_down"]}只，平盘{opportunities["total_flat"]}只

【板块平均涨跌】
{", ".join(sector_summary)}

【领涨TOP5】
{fmt_stocks(opportunities["top_gainers"])}

【放量异动（量比>1.5且涨>1%）】
{fmt_stocks(opportunities["volume_surge"])}

【调整TOP5】
{fmt_stocks(opportunities["top_losers"])}

请严格用中文输出（禁止英文），纯文本格式（不用markdown），包含以下5部分，总字数控制在350字以内：
1. 【大盘研判】1-2句，判断短线趋势
2. 【热点板块】今日最强1-2个板块及逻辑
3. 【关注标的】1-2只明日值得关注的品种和理由
4. 【操作建议】1条核心建议（控仓/轻仓/等待/止损等）
5. 【风险提示】1句话

重要：全程使用中文，不得出现英文单词。"""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash", system_instruction="你是专业A股分析师，必须全程使用中文回答，禁止使用英文。")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI分析调用失败: {e}"


def build_report_pre_market(market, ai_text):
    """竞价监测报告"""
    today = datetime.date.today().strftime("%Y年%m月%d日")
    now_time = datetime.datetime.now().strftime("%H:%M")

    sh = market.get("上证指数", {})
    cy = market.get("创业板指", {})

    report = f"""#{'='*50}
#{' '*15}竞价监测日报
#{'='*50}
{today} {now_time}

--------------
【盘前风向标】
上证指数（昨日）: {sh.get('close','N/A')}点 ({sh.get('chg_pct','N/A'):+}%)
创业板指（昨日）: {cy.get('close','N/A')}点 ({cy.get('chg_pct','N/A'):+}%)

--------------
【AI竞价预判】
{ai_text}

--------------
本报告仅供参考，投资有风险，决策需谨慎"""

    return report


def build_report_noon(market, opportunities, ai_text):
    """午间分析报告"""
    today = datetime.date.today().strftime("%Y年%m月%d日")
    now_time = datetime.datetime.now().strftime("%H:%M")

    sh = market.get("上证指数", {})
    cy = market.get("创业板指", {})

    sh_str = f"{sh.get('close','N/A')}点 ({sh.get('chg_pct','N/A'):+}%)" if "close" in sh else "获取失败"
    cy_str = f"{cy.get('close','N/A')}点 ({cy.get('chg_pct','N/A'):+}%)" if "close" in cy else "获取失败"

    # 领涨标的
    gainers_str = ""
    for s in opportunities["top_gainers"][:3]:
        mark = "+" if s.get("chg_pct", 0) > 0 else ""
        gainers_str += f"{mark}{s['name']} {s.get('chg_pct',0):+.2f}%\n"

    report = f"""#{'='*50}
#{' '*15}午间分析报告
#{'='*50}
{today} {now_time}

--------------
【上午盘面】
上证指数：{sh_str}
创业板指：{cy_str}

【涨跌概况】
涨{opportunities['total_up']} 跌{opportunities['total_down']} 平{opportunities['total_flat']}

【上午领涨】
{gainers_str.strip()}

--------------
【AI午间点评】
{ai_text}

--------------
本报告仅供参考，投资有风险，决策需谨慎"""

    return report


def build_report_full(market, opportunities, sector_data, ai_text):
    """收盘分析报告"""
    today = datetime.date.today().strftime("%Y年%m月%d日")
    now_time = datetime.datetime.now().strftime("%H:%M")

    # 大盘行情
    sh = market.get("上证指数", {})
    cy = market.get("创业板指", {})

    sh_str = f"{sh.get('close','N/A')}点 ({sh.get('chg_pct','N/A'):+}%)" if "close" in sh else "获取失败"
    cy_str = f"{cy.get('close','N/A')}点 ({cy.get('chg_pct','N/A'):+}%)" if "close" in cy else "获取失败"

    # 领涨标的
    gainers_str = ""
    for s in opportunities["top_gainers"][:3]:
        mark = "+" if s.get("chg_pct", 0) > 0 else ""
        gainers_str += f"{mark}{s['name']} {s.get('chg_pct',0):+.2f}%\n"

    # 放量异动
    surge_str = ""
    for s in opportunities["volume_surge"][:3]:
        surge_str += f"+{s['name']} +{s.get('chg_pct',0):.2f}% 量比{s.get('vol_ratio','N/A')}x\n"
    if not surge_str:
        surge_str = "今日无明显放量异动\n"

    report = f"""#{'='*50}
#{' '*15}每日股市分析
#{'='*50}
{today} {now_time} | 田亮股票池

--------------
【大盘行情】
上证指数：{sh_str}
创业板指：{cy_str}

【股票池概况】
共{opportunities["total_count"]}只 | 涨{opportunities["total_up"]} 跌{opportunities["total_down"]} 平{opportunities["total_flat"]}

【今日领涨】
{gainers_str.strip()}

【放量异动】
{surge_str.strip()}

--------------
【AI智能点评】
{ai_text}

--------------
本报告仅供参考，投资有风险，决策需谨慎"""

    return report


def send_to_wechat(content):
    """推送到企业微信群机器人"""
    if not WECHAT_WEBHOOK:
        print("未配置 WECHAT_WEBHOOK，跳过推送")
        print("=" * 60)
        print(content)
        return

    payload = {
        "msgtype": "text",
        "text": {"content": content}
    }
    try:
        resp = requests.post(WECHAT_WEBHOOK, json=payload, timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            print("企业微信推送成功！")
        else:
            print(f"推送失败: {result}")
    except Exception as e:
        print(f"推送异常: {e}")


def main():
    print("=" * 60)
    print(f"daily_stock_analysis 启动 | 模式: {RUN_MODE}")
    print(f"时间: {datetime.datetime.now()}")
    print("=" * 60)

    # 根据模式执行不同逻辑
    if RUN_MODE == "pre_market":
        # 竞价监测模式
        print("\n[竞价模式] 获取隔夜/盘前信息...")
        market = get_realtime_data()
        print(f"  盘前数据: {market}")

        print("\n[AI分析] 生成竞价预判...")
        ai_text = ai_analysis_pre_market(market)

        print("\n[生成报告]...")
        report = build_report_pre_market(market, ai_text)

        if WECHAT_WEBHOOK:
            send_to_wechat(report)

    elif RUN_MODE == "noon":
        # 午间分析模式
        print("\n[午间模式] 获取上午盘面...")
        market = get_realtime_data()
        print(f"  大盘: {market}")

        print("\n[采集数据] 获取个股上午表现...")
        sector_data = collect_all_stocks()

        print("\n[分析机会]...")
        opportunities = find_opportunities(sector_data)
        print(f"  上涨{opportunities['total_up']}只，下跌{opportunities['total_down']}只")

        print("\n[AI分析] 生成午间点评...")
        ai_text = ai_analysis_noon(market, opportunities, sector_data)

        print("\n[生成报告]...")
        report = build_report_noon(market, opportunities, ai_text)

        if WECHAT_WEBHOOK:
            send_to_wechat(report)

    else:
        # 完整模式（收盘）
        print("\n[完整模式] 获取大盘数据...")
        market = get_market_overview()
        print(f"  上证: {market.get('上证指数', {})}")

        print("\n[采集股票池数据]...")
        sector_data = collect_all_stocks()

        print("\n[分析机会]...")
        opportunities = find_opportunities(sector_data)
        print(f"  上涨{opportunities['total_up']}只，下跌{opportunities['total_down']}只")

        print("\n[AI分析+生成报告+推送]...")
        ai_text = ai_analysis_full(market, opportunities, sector_data)
        report = build_report_full(market, opportunities, sector_data, ai_text)
        send_to_wechat(report)

    # 保存本地备份
    with open("report_latest.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print("报告已保存至 report_latest.txt")
    print("完成！")


if __name__ == "__main__":
    main()
