# 华为云DNS智能解析分流脚本

通过华为云国际站API，为不同运营商线路创建A记录解析，实现IP智能分流。

## 功能特性

- **五线路分流**: 中国移动、中国联通、中国电信、境外、默认(全网)
- **自动IP获取**: 从网页API自动获取各线路IP列表，支持注释过滤
- **智能去重**: 自动检测并丢弃重复IP，避免华为云拒绝创建记录集
- **自动清理旧记录**: 每次运行先删除该域名+该类型+该线路的旧记录集，再创建新的，避免累加
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

### 执行流程

```
对于每条线路:
  1. 清理旧记录集 —— 删除该域名+A记录+该线路的所有旧记录集
  2. 获取新IP —— 从URL获取IP列表，过滤注释，URL内去重
  3. 分块去重 —— 将IP分为3组，跨记录集全局去重
  4. 创建新记录集 —— 调用华为云API创建新记录集
```

### 清理规则

脚本会**精确匹配**并删除以下条件的旧记录集：
- `name` 等于目标FQDN（如 `www.example.com.`）
- `type` 等于 `A`
- `line` 等于当前线路ID（如 `Yidong`）

**不会误删**其他子域名、其他记录类型（如CNAME、MX）、或其他线路的记录集。

### 去重机制

脚本内置**两级去重**机制：

**第一级：URL获取时去重**
从网页API获取IP列表时，同一URL内的重复IP会被自动去重，保留首次出现的顺序。

```
成功获取 152 个有效IP (已去重)
```

**第二级：跨记录集去重**
同一域名下，华为云会检测所有记录集中的重复IP。脚本在创建记录集前，会在**同一域名+同一类型**范围内进行全局去重：

```
正在进行跨记录集去重...
[去重] 记录集 2 丢弃 3 个重复IP: ['1.2.3.4', '1.2.3.5', '1.2.3.6']
[去重汇总] 共丢弃 5 个重复IP
```

> **注意**: 如果去重后某个记录集的IP数量不足，脚本会正常创建（使用可用IP），不会强制凑够50个。

## 注意事项

1. **⚠️ 自动删除**: 每次运行会先删除旧记录集，请确保这是预期行为
2. **IP数量**: 如果URL返回的IP不足150个，脚本会取前N个，并发出警告
3. **API限流**: 脚本内置0.3~0.5秒间隔，避免触发API限流
4. **安全性**: 建议通过环境变量传递AK/SK，而非硬编码在配置文件中

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `配置验证失败` | 检查 `config.py` 中必填项是否已填写 |
| `获取IP列表失败` | 检查URL是否可访问，网络是否正常 |
| `API错误 401` | AK/SK错误或已过期，请重新创建 |
| `API错误 404` | Zone ID错误，请在控制台确认 |
| `API错误 400` | 线路ID或域名格式错误 |
| `记录集创建失败(重复IP)` | 脚本已自动去重，如仍失败请检查IP源数据 |
| `旧记录集删除失败` | 检查AK/SK是否有DNS写权限 |

## 参考文档

- [华为云DNS创建记录集API](https://support.huaweicloud.com/api-dns/dns_api_64001.html)
- [华为云DNS删除记录集API](https://support.huaweicloud.com/api-dns/dns_api_64005.html)
- [华为云DNS查询记录集API](https://support.huaweicloud.com/api-dns/dns_api_64003.html)
- [华为云DNS解析线路类型](https://support.huaweicloud.com/api-dns/zh-cn_topic_0085546214.html)
- [华为云Python SDK](https://support.huaweicloud.com/sdk-dns/dns_05_0001.html)
