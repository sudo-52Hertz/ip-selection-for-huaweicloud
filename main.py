# -*- coding: utf-8 -*-
"""
华为云DNS智能解析分流脚本
============================
通过华为云国际站API，为不同运营商线路创建A记录解析，实现IP分流。

功能:
- 从网页API获取各线路IP列表
- 为每个线路创建3个记录集，每个记录集包含50个IP
- 支持中国移动、中国联通、中国电信、境外、默认五条线路
- 使用华为云官方SDK进行API调用

使用方法:
    1. 修改 config.py 中的配置项
    2. 安装依赖: pip install huaweicloudsdkcore huaweicloudsdkdns requests
    3. 运行: python main.py
"""

import re
import sys
import time
import requests
from typing import List, Dict, Tuple

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkdns.v2 import DnsClient
from huaweicloudsdkdns.v2.region.dns_region import DnsRegion
from huaweicloudsdkdns.v2.model import (
    CreateRecordSetWithLineRequest,
    CreateRecordSetWithLineRequestBody,
)

# 导入配置
from config import (
    HUAWEI_AK, HUAWEI_SK, HUAWEI_REGION,
    ZONE_ID, ZONE_NAME, HOST_RECORD,
    IP_LIST_URLS, LINE_IDS,
    TTL, RECORD_TYPE,
    RECORDSETS_PER_LINE, IPS_PER_RECORDSET,
    DESCRIPTION_PREFIX,
)


def validate_config() -> bool:
    """验证配置是否已正确填写"""
    errors = []

    if HUAWEI_AK == "YOUR_ACCESS_KEY_HERE" or not HUAWEI_AK:
        errors.append("HUAWEI_AK 未配置")
    if HUAWEI_SK == "YOUR_SECRET_KEY_HERE" or not HUAWEI_SK:
        errors.append("HUAWEI_SK 未配置")
    if ZONE_ID == "YOUR_ZONE_ID_HERE" or not ZONE_ID:
        errors.append("ZONE_ID 未配置")
    if not ZONE_NAME or not ZONE_NAME.endswith("."):
        errors.append("ZONE_NAME 必须以点号(.)结尾")

    for line_key, url in IP_LIST_URLS.items():
        if "your-api.example.com" in url or not url:
            errors.append(f"IP_LIST_URLS['{line_key}'] 未配置有效URL")

    if errors:
        print("[错误] 配置验证失败，请检查 config.py:")
        for err in errors:
            print(f"  - {err}")
        return False
    return True


def fetch_ip_list(url: str) -> List[str]:
    """
    从URL获取IP列表

    每行格式: IP地址 [注释内容]
    忽略空行和注释，只提取有效的IPv4地址
    """
    print(f"  正在获取: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        ip_pattern = re.compile(
            r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        )

        ips = []
        for line in response.text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = ip_pattern.match(line)
            if match:
                ip = match.group(1)
                # 验证IP合法性
                parts = ip.split(".")
                if all(0 <= int(p) <= 255 for p in parts):
                    ips.append(ip)

        print(f"  成功获取 {len(ips)} 个有效IP")
        return ips
    except requests.RequestException as e:
        print(f"  [错误] 获取IP列表失败: {e}")
        return []


def chunk_ips(ips: List[str], chunk_size: int) -> List[List[str]]:
    """将IP列表按指定大小分块"""
    return [ips[i:i + chunk_size] for i in range(0, len(ips), chunk_size)]


def build_fqdn(host_record: str, zone_name: str) -> str:
    """构建FQDN格式的完整域名"""
    if not host_record or host_record == "@":
        return zone_name
    return f"{host_record}.{zone_name}"


def create_dns_client() -> DnsClient:
    """创建华为云DNS客户端"""
    credentials = BasicCredentials(HUAWEI_AK, HUAWEI_SK)
    client = DnsClient.new_builder() \
        .with_credentials(credentials) \
        .with_region(DnsRegion.value_of(HUAWEI_REGION)) \
        .build()
    return client


def create_recordset(
    client: DnsClient,
    zone_id: str,
    name: str,
    record_type: str,
    ttl: int,
    records: List[str],
    line: str,
    description: str,
) -> Tuple[bool, str]:
    """
    创建单条记录集

    Returns:
        (success: bool, message: str)
    """
    request = CreateRecordSetWithLineRequest()
    request.zone_id = zone_id

    request.body = CreateRecordSetWithLineRequestBody(
        name=name,
        type=record_type,
        ttl=ttl,
        records=records,
        line=line,
        description=description,
    )

    try:
        response = client.create_record_set_with_line(request)
        return True, f"记录集创建成功, ID: {response.id}"
    except exceptions.ClientRequestException as e:
        return False, f"API错误 [{e.status_code}] {e.error_code}: {e.error_msg}"
    except Exception as e:
        return False, f"异常: {str(e)}"


def process_line(
    client: DnsClient,
    line_key: str,
    line_name: str,
    line_id: str,
    url: str,
    fqdn: str,
) -> bool:
    """
    处理单个线路的解析记录创建

    Args:
        line_key: 线路标识 (cmcc/cucc/ctcc/oversea/default)
        line_name: 线路中文名
        line_id: 华为云线路ID
        url: IP列表URL
        fqdn: 完整域名

    Returns:
        是否全部成功
    """
    print(f"\n{'='*60}")
    print(f"处理线路: {line_name} ({line_key}) -> 华为云线路ID: {line_id}")
    print(f"{'='*60}")

    # 1. 获取IP列表
    ips = fetch_ip_list(url)

    if len(ips) < IPS_PER_RECORDSET * RECORDSETS_PER_LINE:
        print(f"  [警告] IP数量不足: 需要 {IPS_PER_RECORDSET * RECORDSETS_PER_LINE} 个，"
              f"实际获取 {len(ips)} 个")
        if len(ips) == 0:
            print(f"  [错误] 未获取到任何IP，跳过此线路")
            return False

    # 2. 截取所需数量的IP
    needed_ips = IPS_PER_RECORDSET * RECORDSETS_PER_LINE
    ips = ips[:needed_ips]
    print(f"  将使用 {len(ips)} 个IP创建 {RECORDSETS_PER_LINE} 个记录集")

    # 3. 分块
    chunks = chunk_ips(ips, IPS_PER_RECORDSET)

    # 4. 创建记录集
    all_success = True
    for idx, chunk in enumerate(chunks):
        if not chunk:
            continue

        desc = f"{DESCRIPTION_PREFIX} | {line_name} | 记录集 {idx + 1}/{len(chunks)}"
        print(f"\n  创建记录集 {idx + 1}/{len(chunks)} ({len(chunk)} 个IP)...")
        print(f"    域名: {fqdn}")
        print(f"    线路: {line_id}")
        print(f"    IP: {chunk[0]} ... {chunk[-1]}")

        success, msg = create_recordset(
            client=client,
            zone_id=ZONE_ID,
            name=fqdn,
            record_type=RECORD_TYPE,
            ttl=TTL,
            records=chunk,
            line=line_id,
            description=desc,
        )

        if success:
            print(f"    [成功] {msg}")
        else:
            print(f"    [失败] {msg}")
            all_success = False

        # API限流保护: 每次请求间隔0.5秒
        time.sleep(0.5)

    return all_success


def main():
    """主入口"""
    print("=" * 70)
    print("华为云DNS智能解析分流脚本")
    print("=" * 70)

    # 验证配置
    if not validate_config():
        sys.exit(1)

    # 构建FQDN
    fqdn = build_fqdn(HOST_RECORD, ZONE_NAME)
    print(f"\n目标域名: {fqdn}")
    print(f"Zone ID: {ZONE_ID}")
    print(f"Region: {HUAWEI_REGION}")
    print(f"TTL: {TTL}秒")
    print(f"每个线路记录集数: {RECORDSETS_PER_LINE}")
    print(f"每个记录集IP数: {IPS_PER_RECORDSET}")

    # 线路名称映射
    line_names = {
        "cmcc": "中国移动",
        "cucc": "中国联通",
        "ctcc": "中国电信",
        "oversea": "境外",
        "default": "默认(全网)",
    }

    # 创建DNS客户端
    print("\n正在初始化华为云DNS客户端...")
    try:
        client = create_dns_client()
        print("客户端初始化成功")
    except Exception as e:
        print(f"[错误] 客户端初始化失败: {e}")
        sys.exit(1)

    # 处理各线路
    results = {}
    for line_key in ["cmcc", "cucc", "ctcc", "oversea", "default"]:
        line_id = LINE_IDS[line_key]
        url = IP_LIST_URLS[line_key]
        name = line_names[line_key]

        success = process_line(
            client=client,
            line_key=line_key,
            line_name=name,
            line_id=line_id,
            url=url,
            fqdn=fqdn,
        )
        results[line_key] = success

    # 汇总报告
    print("\n" + "=" * 70)
    print("执行结果汇总")
    print("=" * 70)
    for line_key, success in results.items():
        status = "成功" if success else "失败"
        print(f"  {line_names[line_key]:<10} ({LINE_IDS[line_key]:<12}) -> {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n总计: {passed}/{total} 条线路处理成功")

    if passed < total:
        sys.exit(1)
    print("\n全部完成!")


if __name__ == "__main__":
    main()
