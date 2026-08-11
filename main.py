# -*- coding: utf-8 -*-
"""
华为云DNS智能解析分流脚本
============================
通过华为云国际站API，为不同运营商线路创建A记录解析，实现IP分流。

功能:
- 从本地文本文件读取各线路IP列表
- 每个记录集包含50个IP，根据IP总数动态创建记录集数量
- 支持中国移动、中国联通、中国电信、境外、默认五条线路
- 使用华为云官方SDK进行API调用
- 自动去重，避免重复IP导致记录集创建失败
- 获取IP成功后才会删除旧记录集并创建新的，失败则保留现有记录集

使用方法:
    1. 修改 config.py 中的配置项
    2. 安装依赖: pip install huaweicloudsdkcore huaweicloudsdkdns requests
    3. 运行: python main.py
"""

import re
import sys
import time
from typing import List, Tuple, Set

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkdns.v2 import DnsClient
from huaweicloudsdkdns.v2.region.dns_region import DnsRegion
from huaweicloudsdkdns.v2.model import (
    CreateRecordSetWithLineRequest,
    CreateRecordSetWithLineRequestBody,
    ListRecordSetsWithLineRequest,
    DeleteRecordSetsRequest,
)

# 导入配置
from config import (
    HUAWEI_AK, HUAWEI_SK, HUAWEI_REGION,
    ZONE_ID, ZONE_NAME, HOST_RECORD,
    IP_LIST_FILES, LINE_IDS,
    TTL, RECORD_TYPE,
    IPS_PER_RECORDSET,
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

    for line_key, path in IP_LIST_FILES.items():
        if not path or "/path/to/" in path:
            errors.append(f"IP_LIST_FILES['{line_key}'] 未配置有效文件路径")

    if errors:
        print("[错误] 配置验证失败，请检查 config.py:")
        for err in errors:
            print(f"  - {err}")
        return False
    return True


def read_ip_list(file_path: str, line_name: str = "") -> List[str]:
    """
    从本地文件读取IP列表

    每行格式: IP地址 [注释内容]
    忽略空行和注释，只提取有效的IPv4地址
    自动去重，保留首次出现的顺序

    Args:
        file_path: IP列表文件路径
        line_name: 线路名称（用于日志输出）

    Returns:
        IP列表，失败时返回空列表
    """
    prefix = f"[{line_name}] " if line_name else ""
    print(f"  {prefix}正在读取: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"  {prefix}[错误] 文件不存在: {file_path}")
        return []
    except Exception as e:
        print(f"  {prefix}[错误] 读取文件失败: {e}")
        return []

    ip_pattern = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

    ips = []
    seen = set()
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = ip_pattern.match(line)
        if match:
            ip = match.group(1)
            parts = ip.split(".")
            if all(0 <= int(p) <= 255 for p in parts):
                if ip not in seen:
                    seen.add(ip)
                    ips.append(ip)

    print(f"  {prefix}成功读取 {len(ips)} 个有效IP (已去重)")
    return ips


def deduplicate_ips_across_recordsets(chunks: List[List[str]]) -> List[List[str]]:
    """
    跨记录集去重

    华为云会检测同一域名下所有记录集中的重复IP并拒绝创建。
    此函数确保同一域名+同一类型下，所有记录集中的IP全局唯一。

    去重策略:
    1. 保留首次出现的IP
    2. 后续记录集中若出现已使用过的IP，自动丢弃

    Args:
        chunks: 分块后的IP列表

    Returns:
        去重后的分块IP列表
    """
    global_seen: Set[str] = set()
    result_chunks = []

    for idx, chunk in enumerate(chunks):
        unique_chunk = []
        duplicates = []

        for ip in chunk:
            if ip in global_seen:
                duplicates.append(ip)
            else:
                global_seen.add(ip)
                unique_chunk.append(ip)

        if duplicates:
            print(f"    [去重] 记录集 {idx + 1} 丢弃 {len(duplicates)} 个重复IP")

        result_chunks.append(unique_chunk)

    total_before = sum(len(c) for c in chunks)
    total_after = sum(len(c) for c in result_chunks)
    if total_before != total_after:
        print(f"    [去重汇总] 共丢弃 {total_before - total_after} 个重复IP")

    return result_chunks


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


def list_recordsets_with_line(client: DnsClient, zone_id: str) -> List[dict]:
    """
    使用 v2.1 ListRecordSetsWithLine API 列出带线路信息的记录集

    Returns:
        记录集列表
    """
    recordsets = []
    marker = None

    while True:
        request = ListRecordSetsWithLineRequest()
        request.zone_id = zone_id
        request.limit = 500
        if marker:
            request.marker = marker

        try:
            response = client.list_record_sets_with_line(request)
            for rs in response.recordsets:
                line = getattr(rs, "line", None)
                recordsets.append({
                    "id": rs.id,
                    "name": rs.name,
                    "type": rs.type,
                    "line": line,
                    "records": getattr(rs, "records", []),
                    "description": getattr(rs, "description", ""),
                })

            if not response.links or not getattr(response.links, "next", None):
                break
            next_link = response.links.next
            if "marker=" in next_link:
                marker = next_link.split("marker=")[1].split("&")[0]
            else:
                break
        except exceptions.ClientRequestException as e:
            print(f"  [错误] 获取记录集列表失败: [{e.status_code}] {e.error_msg}")
            break
        except Exception as e:
            print(f"  [错误] 获取记录集列表异常: {e}")
            break

    return recordsets


def delete_recordset(client: DnsClient, zone_id: str, recordset_id: str) -> Tuple[bool, str]:
    """
    删除指定记录集（使用 v2.1 API）

    Returns:
        (success: bool, message: str)
    """
    request = DeleteRecordSetsRequest()
    request.zone_id = zone_id
    request.recordset_id = recordset_id

    try:
        response = client.delete_record_sets(request)
        return True, f"删除成功 (status: {getattr(response, 'status', 'unknown')})"
    except exceptions.ClientRequestException as e:
        return False, f"API错误 [{e.status_code}] {e.error_code}: {e.error_msg}"
    except Exception as e:
        return False, f"异常: {str(e)}"


def cleanup_old_recordsets(
    client: DnsClient,
    zone_id: str,
    fqdn: str,
    record_type: str,
    line_id: str,
) -> int:
    """
    清理指定域名+类型+线路的旧记录集

    Returns:
        删除的记录集数量
    """
    print(f"  正在清理旧记录集...")

    all_recordsets = list_recordsets_with_line(client, zone_id)

    to_delete = []
    for rs in all_recordsets:
        if (rs["name"] == fqdn and 
            rs["type"] == record_type and 
            rs["line"] == line_id):
            to_delete.append(rs)

    if not to_delete:
        print(f"  未发现需要清理的旧记录集")
        return 0

    print(f"  发现 {len(to_delete)} 个旧记录集，准备删除...")

    deleted_count = 0
    for rs in to_delete:
        ip_count = len(rs.get("records", []))
        print(f"    删除记录集: {rs['id']} ({rs['name']} | 线路:{rs['line']} | {ip_count} 个IP)")
        success, msg = delete_recordset(client, zone_id, rs["id"])
        if success:
            deleted_count += 1
            print(f"      [成功] {msg}")
        else:
            print(f"      [失败] {msg}")
        time.sleep(0.3)

    print(f"  清理完成: 成功删除 {deleted_count}/{len(to_delete)} 个旧记录集")
    return deleted_count


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
    file_path: str,
    fqdn: str,
) -> bool:
    """
    处理单个线路的解析记录创建

    流程:
    1. 从本地文件读取IP列表
    2. 检查IP数量是否足够（至少1个）
    3. 清理旧记录集
    4. 分块并去重
    5. 创建新记录集（动态计算记录集数量）

    Args:
        line_key: 线路标识
        line_name: 线路中文名
        line_id: 华为云线路ID
        file_path: IP列表文件路径
        fqdn: 完整域名

    Returns:
        是否全部成功
    """
    print(f"\n{'='*60}")
    print(f"处理线路: {line_name} ({line_key}) -> 华为云线路ID: {line_id}")
    print(f"{'='*60}")

    # ========== 第1步: 读取IP列表 ==========
    ips = read_ip_list(file_path, line_name)

    if not ips:
        print(f"  [跳过] {line_name} 线路未读取到任何IP，保留现有记录集不变")
        return False

    # 计算记录集数量
    total_ips = len(ips)
    recordset_count = (total_ips + IPS_PER_RECORDSET - 1) // IPS_PER_RECORDSET  # 向上取整
    print(f"  共 {total_ips} 个IP，将创建 {recordset_count} 个记录集（每个最多 {IPS_PER_RECORDSET} 个IP）")

    # ========== 第2步: 清理旧记录集 ==========
    cleanup_old_recordsets(
        client=client,
        zone_id=ZONE_ID,
        fqdn=fqdn,
        record_type=RECORD_TYPE,
        line_id=line_id,
    )

    # ========== 第3步: 分块 + 跨记录集去重 ==========
    chunks = chunk_ips(ips, IPS_PER_RECORDSET)

    print(f"  正在进行跨记录集去重...")
    chunks = deduplicate_ips_across_recordsets(chunks)

    # ========== 第4步: 创建新记录集 ==========
    all_success = True
    actual_recordsets = 0
    for idx, chunk in enumerate(chunks):
        if not chunk:
            print(f"\n  [跳过] 记录集 {idx + 1} 去重后无可用IP")
            all_success = False
            continue

        actual_recordsets += 1
        desc = f"{DESCRIPTION_PREFIX} | {line_name} | 记录集 {idx + 1}/{len(chunks)} ({len(chunk)} 个IP)"
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

        time.sleep(0.5)

    print(f"\n  线路 {line_name} 处理完成: 成功创建 {actual_recordsets} 个记录集")
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
    print(f"每个记录集IP数: {IPS_PER_RECORDSET}")
    print(f"\n⚠️  安全策略: 只有IP读取成功才会删除旧记录集，失败则保留现有记录集")

    line_names = {
        "cmcc": "中国移动",
        "cucc": "中国联通",
        "ctcc": "中国电信",
        "oversea": "境外",
        "default": "默认(全网)",
    }

    print("\n正在初始化华为云DNS客户端...")
    try:
        client = create_dns_client()
        print("客户端初始化成功")
    except Exception as e:
        print(f"[错误] 客户端初始化失败: {e}")
        sys.exit(1)

    results = {}
    for line_key in ["cmcc", "cucc", "ctcc", "oversea", "default"]:
        line_id = LINE_IDS[line_key]
        file_path = IP_LIST_FILES[line_key]
        name = line_names[line_key]

        success = process_line(
            client=client,
            line_key=line_key,
            line_name=name,
            line_id=line_id,
            file_path=file_path,
            fqdn=fqdn,
        )
        results[line_key] = success

    print("\n" + "=" * 70)
    print("执行结果汇总")
    print("=" * 70)
    for line_key, success in results.items():
        status = "成功" if success else "失败/跳过"
        print(f"  {line_names[line_key]:<10} ({LINE_IDS[line_key]:<12}) -> {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n总计: {passed}/{total} 条线路处理成功")

    if passed < total:
        print("\n[提示] 部分线路因IP读取失败被跳过，现有记录集已保留，服务未中断")
        sys.exit(1)
    print("\n全部完成!")


if __name__ == "__main__":
    main()
