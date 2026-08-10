# 华为云DNS智能解析分流脚本

通过华为云国际站API，为不同运营商线路创建A记录解析，实现IP智能分流。

## 功能特性

- **五线路分流**: 中国移动、中国联通、中国电信、境外、默认(全网)
- **自动IP获取**: 从网页API自动获取各线路IP列表，支持注释过滤
- **批量创建**: 每个线路自动创建3个记录集，每个记录集包含50个IP
- **华为云官方SDK**: 使用 `huaweicloudsdkdns` 官方SDK进行API调用
- **统一配置**: 所有配置集中在一个文件，修改简单

## 目录结构

```
.
├── config.py      # 统一配置文件 (只需修改此文件)
├── main.py        # 主程序
└── README.md      # 本文件
```

## 前置要求

1. **华为云国际站账号** 及 Access Key / Secret Key
2. **已添加的域名** 并获取 Zone ID
3. **Python 3.8+**

## 安装依赖

```bash
pip install huaweicloudsdkcore huaweicloudsdkdns requests
```

## 配置说明

编辑 `config.py` 文件，填写以下信息：

### 1. API认证信息

```python
HUAWEI_AK = "your-access-key"
HUAWEI_SK = "your-secret-key"
HUAWEI_REGION = "ap-southeast-1"  # 根据域名所在区域填写
```

### 2. 域名信息

```python
ZONE_ID = "your-zone-id"          # 在DNS控制台域名列表中查看
ZONE_NAME = "example.com."        # 必须以点号结尾的FQDN格式
HOST_RECORD = "www"               # 子域名前缀，空或@表示主域名
```

### 3. IP列表URL

每个线路的IP列表通过URL获取，格式要求：
- 纯文本，一行一个IP
- 每行格式: `IP地址 [注释内容]` (注释会被自动忽略)
- 每个URL应返回至少150个有效IPv4地址

```python
IP_LIST_URLS = {
    "cmcc": "https://your-api.com/ips/cmcc.txt",
    "cucc": "https://your-api.com/ips/cucc.txt",
    "ctcc": "https://your-api.com/ips/ctcc.txt",
    "oversea": "https://your-api.com/ips/oversea.txt",
    "default": "https://your-api.com/ips/default.txt",
}
```

**IP列表示例** (`cmcc.txt`):
```
1.2.3.4  # 北京移动节点
1.2.3.5  # 上海移动节点
1.2.3.6  # 广州移动节点
# 以下省略...
```

### 4. 解析线路ID (一般无需修改)

华为云DNS线路ID对照表：

| 线路 | 线路ID | 说明 |
|------|--------|------|
| 中国移动 | `Yidong` | CMCC用户 |
| 中国联通 | `Liantong` | CUCC用户 |
| 中国电信 | `Dianxin` | CTCC用户 |
| 境外 | `Abroad` | 海外用户 |
| 默认 | `default_view` | 全网默认，兜底线路 |

```python
LINE_IDS = {
    "cmcc": "Yidong",
    "cucc": "Liantong",
    "ctcc": "Dianxin",
    "oversea": "Abroad",
    "default": "default_view",
}
```

### 5. 解析参数 (一般无需修改)

```python
TTL = 60                          # TTL 60秒
RECORD_TYPE = "A"                 # A记录
RECORDSETS_PER_LINE = 3           # 每个线路3个记录集
IPS_PER_RECORDSET = 50            # 每个记录集50个IP
```

## 使用方法

### 1. 配置

```bash
# 编辑配置文件
vim config.py
```

### 2. 运行

```bash
python main.py
```

### 3. 查看结果

脚本运行后会输出各线路创建结果：

```
============================================================
执行结果汇总
============================================================
  中国移动   (Yidong      ) -> 成功
  中国联通   (Liantong    ) -> 成功
  中国电信   (Dianxin     ) -> 成功
  境外       (Abroad      ) -> 成功
  默认(全网) (default_view) -> 成功

总计: 5/5 条线路处理成功

全部完成!
```

## 工作原理

1. **获取IP**: 从配置的URL获取各线路IP列表，过滤注释和无效IP
2. **分块处理**: 将150个IP分为3组，每组50个
3. **创建记录集**: 调用华为云 `CreateRecordSetWithLine` API，为每组IP创建一个记录集
4. **线路绑定**: 每个记录集绑定到对应的运营商线路ID，确保解析请求来源正确匹配

## 注意事项

1. **IP数量**: 如果URL返回的IP不足150个，脚本会取前N个，并发出警告
2. **API限流**: 脚本内置0.5秒间隔，避免触发API限流
3. **重复运行**: 重复运行会创建新的记录集，不会覆盖旧的。如需更新，建议先在控制台删除旧记录集
4. **安全性**: 建议通过环境变量传递AK/SK，而非硬编码在配置文件中

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `配置验证失败` | 检查 `config.py` 中必填项是否已填写 |
| `获取IP列表失败` | 检查URL是否可访问，网络是否正常 |
| `API错误 401` | AK/SK错误或已过期，请重新创建 |
| `API错误 404` | Zone ID错误，请在控制台确认 |
| `API错误 400` | 线路ID或域名格式错误 |

## 参考文档

- [华为云DNS创建记录集API](https://support.huaweicloud.com/api-dns/dns_api_64001.html)
- [华为云DNS解析线路类型](https://support.huaweicloud.com/api-dns/zh-cn_topic_0085546214.html)
- [华为云Python SDK](https://support.huaweicloud.com/sdk-dns/dns_05_0001.html)
