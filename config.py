# -*- coding: utf-8 -*-
"""
华为云DNS智能解析分流配置
所有需要修改的配置项都集中在此文件中
=====================================
修改此文件后，运行 main.py 即可生效
"""

# ============================================
# 1. 华为云API认证信息
# ============================================
# 华为云国际站 Access Key (AK)
# 在华为云控制台 "我的凭证" -> "访问密钥" 中创建
HUAWEI_AK = "YOUR_ACCESS_KEY_HERE"

# 华为云国际站 Secret Key (SK)
HUAWEI_SK = "YOUR_SECRET_KEY_HERE"

# 区域 (Region)
# 华为云国际站常用区域: ap-southeast-1(新加坡), ap-southeast-3(曼谷), 
#                      ap-southeast-4(雅加达), af-south-1(约翰内斯堡) 等
# 请根据您的域名所在区域填写
HUAWEI_REGION = "ap-southeast-1"

# ============================================
# 2. 域名与主机记录配置
# ============================================
# 域名ID (Zone ID)
# 在华为云DNS控制台 -> 域名列表中查看
ZONE_ID = "YOUR_ZONE_ID_HERE"

# 域名名称 (必须以点号结尾的FQDN格式)
# 例如: "example.com."
ZONE_NAME = "example.com."

# 主机记录 (子域名前缀)
# 例如: "www" 表示 www.example.com
#       "" 或 "@" 表示主域名 example.com
#       "api" 表示 api.example.com
HOST_RECORD = "www"

# ============================================
# 3. 解析线路IP列表文件路径配置
# ============================================
# 每个线路的IP列表存储在本地文本文件中
# 文件格式: 一行一个IP，IP后面可以有注释（会被自动忽略）
# 每个文件中的IP数量不固定，脚本会自动按50个IP分块创建记录集

IP_LIST_FILES = {
    # 中国移动线路
    "cmcc": "/path/to/cmcc_ips.txt",
    # 中国联通线路
    "cucc": "/path/to/cucc_ips.txt",
    # 中国电信线路
    "ctcc": "/path/to/ctcc_ips.txt",
    # 境外线路
    "oversea": "/path/to/oversea_ips.txt",
    # 默认线路 (全网默认，兜底)
    "default": "/path/to/default_ips.txt",
}

# ============================================
# 4. 解析线路ID映射 (华为云DNS线路标识)
# ============================================
# 华为云DNS线路ID对照表:
#   Yidong    -> 中国移动
#   Liantong  -> 中国联通
#   Dianxin   -> 中国电信
#   Abroad    -> 境外
#   default_view -> 全网默认
LINE_IDS = {
    "cmcc": "Yidong",       # 中国移动
    "cucc": "Liantong",     # 中国联通
    "ctcc": "Dianxin",      # 中国电信
    "oversea": "Abroad",    # 境外
    "default": "default_view",  # 全网默认
}

# ============================================
# 5. 解析记录参数配置
# ============================================
# TTL时间 (秒)，全部设定为60秒
TTL = 60

# 解析记录类型 (A记录)
RECORD_TYPE = "A"

# 每个记录集包含的IP数量
IPS_PER_RECORDSET = 50

# 记录集描述前缀
DESCRIPTION_PREFIX = "Auto-created by script"
