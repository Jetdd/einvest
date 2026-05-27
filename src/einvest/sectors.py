"""Hot-sector concept catalog (Wind hotconcept source).

Concept names exactly match the Wind `hotconcept` strings as stored in the
dm_data hotconcept cache at::

    {DM_INTRADAY_ROOT}/meta/symbols/stock_hotconcept.parquet

Wind concepts are sharper than rqdatac's (e.g. "光模块(CPO)" instead of the
sprawling "CPO概念") and align directly with the einvest framework's PDF
50-board list.
"""
from __future__ import annotations


HOT_CONCEPTS: dict[str, list[str]] = {
    "光通信/CPO": [
        "光模块(CPO)",
        "光电路交换机(OCS)",
        "光通信",
        "液冷服务器",
        "光芯片",
    ],
    "存储": [
        "存储器",
        "HBM",
        "长鑫存储",
    ],
    "机器人": [
        "人形机器人",
        "机器人",
        "宇树机器人",
        "减速器",
        "具身智能",
    ],
    "半导体": [
        "半导体精选",
        "第三代半导体",
        "半导体材料",
        "半导体设备",
        "芯片",
        "光刻机",
        "晶圆产业",
        "EDA",
        "GPU",
        "ASIC芯片",
        "MCU芯片",
        "先进封装",
        "汽车芯片",
        "模拟芯片",
    ],
    "AI算力": [
        "AI算力",
        "IDC(算力租赁)",
        "英伟达产业链",
        "HALO",
        "AIGC",
        "AI应用",
        "AI手机",
        "AIPC",
        "AI AGENT(小龙虾）",
        "智能体",
        "多模态模型",
        "AI医疗",
        "AI备案",
    ],
    "新能源": [
        "固态电池",
        "锂电池",
        "光伏",
        "储能",
        "BC电池",
        "HJT电池",
    ],
    "军工航天": [
        "十大军工集团",
        "商业航天",
        "卫星互联网",
        "卫星导航",
        "低空经济",
    ],
    "医药消费": [
        "创新药",
        "医疗器械精选",
        "减肥药",
        "消费电子产业",
        "医美",
        "宠物经济",
        "谷子经济",
    ],
    "数字经济": [
        "数据要素",
        "数字经济",
        "信创产业",
        "元宇宙",
        "车路云",
    ],
    "资源": [
        "稀土永磁",
        "锂矿",
        "工业金属精选",
        "煤炭开采精选",
        "黄金珠宝",
    ],
    "其他主线": [
        "量子技术",
        "PEEK材料",
        "可控核聚变",
        "华为汽车",
        "新能源汽车",
    ],
}


def all_concepts() -> list[str]:
    """Flat, deduped list of all concepts in `HOT_CONCEPTS`."""
    seen: dict[str, None] = {}
    for items in HOT_CONCEPTS.values():
        for name in items:
            seen.setdefault(name, None)
    return list(seen.keys())


# A-share main indices (rqdatac-format codes — used for CCI)
MAIN_INDICES: dict[str, str] = {
    "上证指数": "000001.XSHG",
    "深证成指": "399001.XSHE",
    "创业板指": "399006.XSHE",
    "中证全指": "000985.XSHG",
}

# Benchmarks for RRG / 风格轮动
BENCHMARKS: dict[str, str] = {
    "沪深300":  "000300.XSHG",
    "中证500":  "000905.XSHG",
    "中证1000": "000852.XSHG",
}

# All indices that should be downloaded by scripts/fetch_indices.py
ALL_INDICES: dict[str, str] = {**MAIN_INDICES, **BENCHMARKS}

# Wind 万得全A — for whole-market amount / liquidity
FULL_A_WIND = "8841388.WI"
