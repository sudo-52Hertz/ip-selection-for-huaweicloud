#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为云国际站智能DNS解析 - 统一配置文件
⚠️ 只需修改本文件，无需改动主程序
"""

# ==================== 华为云认证配置 ====================
# 华为云国际站 Access Key ID
HW_ACCESS_KEY = "your-access-key-id"

# 华为云国际站 Secret Access Key
HW_SECRET_KEY = "your-secret-access-key"

# 华为云国际站区域代码
# 常用国际站区域: ap-southeast-1(新加坡), ap-southeast-3(曼谷), ap-south-1(孟买) 等
# DNS 为全局服务，但 API 调用需指定一个区域端点
HW_REGION = "ap-southeast-1"

# 项目 ID (Project ID)
# 在华为云控制台 "My Credentials / 我的凭证" 中获取；国际站部分区域可留空
HW_PROJECT_ID = ""


# ==================== DNS 解析配置 ====================
# 用于解析的域名 (不要带末尾的点，例如: example.com)
DOMAIN = "example.com"

# 主机记录
# 例如填 "cdn" 将解析为 cdn.example.com
# 填 "@" 或留空字符串表示主域名 example.com
HOST_RECORD = "cdn"

# TTL 时间 (秒)，固定 60
TTL = 60

# 每个记录集包含的 IP 数量 (华为云 A 记录单个记录集上限 50 个)
IPS_PER_RECORDSET = 50

# 每个线路创建的记录集数量 (3 个记录集 × 50 IP = 150 IP)
RECORDSETS_PER_LINE = 3


# ==================== 线路 IP 列表配置 ====================
# 各线路的 IP 列表 URL
# 要求: 纯文本，一行一个 IP，# 后面为注释（脚本会自动忽略注释）
# line 字段说明:
#   CMCC   -> 中国移动
#   CUCC   -> 中国联通
#   CTCC   -> 中国电信
#   ABROAD -> 境外
#   DEFAULT-> 默认
LINE_CONFIG = {
    "CMCC": {
        "name": "中国移动",
        "url": "https://your-api-server.com/ips/cmcc.txt"
    },
    "CUCC": {
        "name": "中国联通",
        "url": "https://your-api-server.com/ips/cucc.txt"
    },
    "CTCC": {
        "name": "中国电信",
        "url": "https://your-api-server.com/ips/ctcc.txt"
    },
    "ABROAD": {
        "name": "境外",
        "url": "https://your-api-server.com/ips/abroad.txt"
    },
    "DEFAULT": {
        "name": "默认",
        "url": "https://your-api-server.com/ips/default.txt"
    }
}
