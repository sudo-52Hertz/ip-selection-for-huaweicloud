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
# 3. 解析线路IP列表URL配置
# ============================================
# 每个线路的IP列表通过网页API获取，格式为纯文本，一行一个IP
# 每行格式: IP地址 [注释内容]  (注释会被自动忽略)
# 每个URL应返回至少150个有效IP地址

IP_LIST_URLS = {
    # 中国移动线路
    "cmcc": "https://your-api.example.com/ips/cmcc.txt",
    # 中国联通线路
    "cucc": "https://your-api.example.com/ips/cucc.txt",
    # 中国电信线路
    "ctcc": "https://your-api.example.com/ips/ctcc.txt",
    # 境外线路
    "oversea": "https://your-api.example.com/ips/oversea.txt",
    # 默认线路 (全网默认，兜底)
    "default": "https://your-api.example.com/ips/default.txt",
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

# 每个线路下的记录集数量
RECORDSETS_PER_LINE = 3

# 每个记录集包含的IP数量
IPS_PER_RECORDSET = 50

# 记录集描述前缀
DESCRIPTION_PREFIX = "Auto-created by script"
