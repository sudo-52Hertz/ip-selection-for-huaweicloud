#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为云国际站智能DNS解析管理脚本
功能: 按运营商/地区线路自动创建智能解析 A 记录集
"""

import sys
import ipaddress
import requests

import config

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkdns.v2 import DnsClient
from huaweicloudsdkdns.v2.region.dns_region import DnsRegion
from huaweicloudsdkcore.exceptions import exceptions


class HuaweiDNSManager:
    """华为云 DNS 管理器"""

    # 线路代码 -> 中文名称映射
    LINE_MAP = {
        "CMCC": "中国移动",
        "CUCC": "中国联通",
        "CTCC": "中国电信",
        "ABROAD": "境外",
        "DEFAULT": "默认"
    }

    def __init__(self):
        self.client = self._init_client()
        self.zone_id = None
        self.full_name = self._build_full_name()

    def _init_client(self):
        """初始化华为云 DNS 客户端"""
        credentials = BasicCredentials(
            config.HW_ACCESS_KEY,
            config.HW_SECRET_KEY,
            config.HW_PROJECT_ID if config.HW_PROJECT_ID else None
        )

        client = DnsClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(DnsRegion.value_of(config.HW_REGION)) \
            .build()
        return client

    def _build_full_name(self):
        """构建完整记录集名称 (必须以点结尾)"""
        host = config.HOST_RECORD.strip()
        if host == "@" or not host:
            return f"{config.DOMAIN}."
        return f"{host}.{config.DOMAIN}."

    # ------------------------------------------------------------------
    # Zone 查询
    # ------------------------------------------------------------------
    def get_zone_id(self):
        """通过域名查询 Zone ID"""
        try:
            from huaweicloudsdkdns.v2.model import ListPublicZonesRequest

            request = ListPublicZonesRequest()
            request.name = config.DOMAIN

            response = self.client.list_public_zones(request)
            zones = response.zones if hasattr(response, 'zones') else []

            for zone in zones:
                zone_name = getattr(zone, 'name', '').rstrip('.')
                if zone_name == config.DOMAIN:
                    self.zone_id = zone.id
                    print(f"[✓] 找到 Zone: {config.DOMAIN} | ID: {self.zone_id}")
                    return self.zone_id

            print(f"[✗] 未找到域名 {config.DOMAIN} 的 Public Zone，请确认已在华为云 DNS 中添加该域名。")
            sys.exit(1)

        except exceptions.ClientRequestException as e:
            print(f"[✗] 查询 Zone 失败: {e.status_code} - {e.error_msg}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # IP 获取与清洗
    # ------------------------------------------------------------------
    @staticmethod
    def get_ips_from_url(url):
        """从 URL 获取 IP 列表，自动过滤注释与非法 IPv4"""
        print(f"  正在下载 IP 列表: {url}")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [✗] 下载失败: {e}")
            return []

        ips = []
        for raw_line in resp.text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # 忽略 # 后面的注释内容
            if '#' in line:
                line = line.split('#')[0].strip()
            if not line:
                continue

            # 仅保留合法 IPv4
            try:
                ipaddress.IPv4Address(line)
                ips.append(line)
            except ValueError:
                continue

        print(f"  [✓] 解析到 {len(ips)} 个有效 IPv4 地址")
        return ips

    # ------------------------------------------------------------------
    # 记录集查询 / 删除
    # ------------------------------------------------------------------
    def list_existing_recordsets(self):
        """列出当前 Zone 下与 full_name 匹配的 A 记录集"""
        try:
            from huaweicloudsdkdns.v2.model import ListRecordSetsByZoneRequest

            request = ListRecordSetsByZoneRequest(zone_id=self.zone_id)
            # name 支持通配符或精确匹配，视 SDK 版本而定
            request.name = self.full_name

            response = self.client.list_record_sets_by_zone(request)
            recordsets = response.recordsets if hasattr(response, 'recordsets') else []

            matched = []
            for rs in recordsets:
                if getattr(rs, 'type', '') == 'A' and getattr(rs, 'name', '') == self.full_name:
                    matched.append(rs)
            return matched

        except exceptions.ClientRequestException as e:
            print(f"[✗] 查询记录集失败: {e.error_msg}")
            return []

    def delete_recordset(self, recordset_id):
        """删除单个记录集"""
        try:
            from huaweicloudsdkdns.v2.model import DeleteRecordSetRequest

            request = DeleteRecordSetRequest(
                zone_id=self.zone_id,
                recordset_id=recordset_id
            )
            self.client.delete_record_set(request)
            return True
        except exceptions.ClientRequestException as e:
            print(f"  [✗] 删除记录集 {recordset_id} 失败: {e.error_msg}")
            return False

    def clean_old_recordsets(self, line_code=None):
        """
        清理旧 A 记录集
        :param line_code: 若指定则仅删除该线路的旧记录；None 则删除该主机记录下所有旧 A 记录
        """
        print(f"  [*] 正在清理 {self.full_name} 的旧 A 记录集...")
        existing = self.list_existing_recordsets()

        deleted = 0
        for rs in existing:
            rs_line = getattr(rs, 'line', 'DEFAULT')
            rs_id = getattr(rs, 'id', '')

            if line_code and rs_line != line_code:
                continue

            if self.delete_recordset(rs_id):
                deleted += 1

        print(f"  [✓] 已清理 {deleted} 个旧记录集")
        return deleted

    # ------------------------------------------------------------------
    # 记录集创建
    # ------------------------------------------------------------------
    def create_recordset(self, line_code, records, index=1):
        """创建单个 A 记录集"""
        try:
            from huaweicloudsdkdns.v2.model import CreateRecordSetRequest
            from huaweicloudsdkdns.v2.model.recordset_req import RecordsetReq

            body = RecordsetReq(
                name=self.full_name,
                type="A",
                ttl=config.TTL,
                records=records,
                line=line_code,
                description=f"{self.LINE_MAP.get(line_code, line_code)}-Set{index}"
            )

            request = CreateRecordSetRequest(zone_id=self.zone_id)
            request.body = body

            response = self.client.create_record_set(request)
            rs_id = getattr(response, 'id', 'unknown')
            print(f"  [✓] 创建成功 | ID: {rs_id} | 线路: {self.LINE_MAP.get(line_code)} "
                  f"| IP数: {len(records)} | TTL: {config.TTL}")
            return True

        except exceptions.ClientRequestException as e:
            print(f"  [✗] 创建失败: {e.error_msg}")
            return False

    # ------------------------------------------------------------------
    # 单线路处理
    # ------------------------------------------------------------------
    def process_line(self, line_code, line_info):
        """处理单条线路：下载 IP -> 清理旧记录 -> 分批创建新记录集"""
        line_name = line_info['name']
        url = line_info['url']

        print(f"\n{'='*60}")
        print(f"[*] 处理线路: {line_name} ({line_code})")
        print(f"{'='*60}")

        # 1. 拉取 IP
        ips = self.get_ips_from_url(url)
        expected = config.IPS_PER_RECORDSET * config.RECORDSETS_PER_LINE
        if len(ips) < expected:
            print(f"  [!] 警告: 期望 {expected} 个 IP，实际仅获取到 {len(ips)} 个")

        # 2. 清理该线路旧记录
        self.clean_old_recordsets(line_code=line_code)

        # 3. 分批创建记录集
        success = 0
        for i in range(config.RECORDSETS_PER_LINE):
            start = i * config.IPS_PER_RECORDSET
            end = start + config.IPS_PER_RECORDSET
            group = ips[start:end]

            if not group:
                print(f"  [!] 第 {i+1} 组无可用 IP，跳过")
                continue

            print(f"\n  [*] 创建第 {i+1} 个记录集 (含 {len(group)} 个 IP)...")
            if self.create_recordset(line_code, group, index=i + 1):
                success += 1

        print(f"\n[✓] {line_name} 完成: 成功 {success}/{config.RECORDSETS_PER_LINE} 个记录集")
        return success

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def run(self):
        print("=" * 60)
        print("华为云国际站智能 DNS 解析管理脚本")
        print("=" * 60)
        print(f"域名      : {config.DOMAIN}")
        print(f"主机记录  : {config.HOST_RECORD}")
        print(f"完整名称  : {self.full_name}")
        print(f"区域      : {config.HW_REGION}")
        print(f"TTL       : {config.TTL} 秒")
        print(f"每记录集  : {config.IPS_PER_RECORDSET} 个 IP")
        print(f"每线路    : {config.RECORDSETS_PER_LINE} 个记录集")
        print("=" * 60)

        # 获取 Zone ID
        self.get_zone_id()

        total_success = 0
        total_expected = len(config.LINE_CONFIG) * config.RECORDSETS_PER_LINE

        # 逐线路处理
        for line_code, line_info in config.LINE_CONFIG.items():
            total_success += self.process_line(line_code, line_info)

        print("\n" + "=" * 60)
        print(f"[*] 全部处理完毕")
        print(f"[*] 总计成功: {total_success} / {total_expected} 个记录集")
        print("=" * 60)


def main():
    try:
        manager = HuaweiDNSManager()
        manager.run()
    except KeyboardInterrupt:
        print("\n[!] 用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n[✗] 未预期错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
