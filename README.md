# MT5 Python Connector

一个用于在 Windows 云电脑上运行的 Flask 应用，接收 TradingView webhook 信号并转发到 MetaTrader 5 (MT5) 进行自动交易。

## 功能特性

- 接收 TradingView webhook 警报并自动执行交易
- 支持开仓（买入/卖出）和平仓操作
- 支持设置止损（SL）和止盈（TP）
- 自动管理 MT5 连接
- 完整的日志记录
- RESTful API 管理界面
- 支持多种信号格式

## 项目结构

```
mt5_python_connector/
├── app.py                  # Flask 主应用
├── config.py               # 配置文件
├── mt5_client.py          # MT5 客户端封装
├── tradingview_parser.py   # TradingView 信号解析器
├── requirements.txt        # Python 依赖
├── .env.example           # 环境变量示例
└── README.md              # 本文档
```

## 安装步骤

### 1. 环境要求

- Windows Server/云电脑（已安装 MT5）
- Python 3.9+
- MetaTrader 5 交易终端

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

复制环境变量配置文件并编辑：

```bash
copy .env.example .env
```

编辑 `.env` 文件：

```env
# MT5 路径（根据实际路径修改）
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# 默认交易手数
DEFAULT_LOT=0.1

# 服务器端口（云服务器建议使用 80）
PORT=80

# 开启认证（建议生产环境开启）
ENABLE_AUTH=True
AUTH_TOKEN=your_secure_token_here
```

### 4. 确保 MT5 允许外部连接

在 MT5 终端中：
1. 打开 `工具` → `选项` → `EA交易`
2. 勾选 `允许 DLL 导入`
3. 勾选 `允许 WebRequest`
4. 添加本地 URL: `http://127.0.0.1`

### 5. 运行

```bash
python app.py
```

或使用 Gunicorn（生产环境推荐）：

```bash
gunicorn -w 1 -b 0.0.0.0:80 app:app
```

## TradingView 配置

### Webhook URL

在 TradingView Alert 中设置 Webhook URL：

```
http://your_server_ip:80/webhook
```

如果开启了认证：

```
http://your_server_ip:80/webhook
```

同时在 Alert 的 JSON payload 或 Headers 中添加认证令牌。

### 支持的信号格式

#### 格式 1：标准 JSON

```json
{
    "action": "buy",
    "symbol": "EURUSD",
    "volume": 0.1,
    "sl": 1.0800,
    "tp": 1.0900,
    "comment": "Pine Script Signal"
}
```

#### 格式 2：简化 JSON

```json
{
    "signal": "buy EURUSD 0.1 sl=1.0800 tp=1.0900"
}
```

#### 格式 3：纯文本

```
buy EURUSD 0.1
```

或：

```
EURUSD buy 0.1
```

### 字段说明

| 字段 | 必填 | 说明 | 示例 |
|------|------|------|------|
| action | 是 | 交易动作 | `buy`, `sell`, `close` |
| symbol | 是 | 交易品种 | `EURUSD`, `XAUUSD` |
| volume | 否 | 交易手数（默认 0.1） | `0.1`, `1.0` |
| sl | 否 | 止损价格 | `1.0800` |
| tp | 否 | 止盈价格 | `1.0900` |
| comment | 否 | 订单备注 | `TV Alert` |

### 支持的交易品种

- **外汇**: EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD, EURGBP, EURJPY, GBPJPY
- **贵金属**: XAUUSD, XAGUSD
- **原油**: USOIL, UKOIL
- **指数**: US100, US30, GER40

## API 端点

### 交易端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/webhook` | 接收 TradingView 信号 |
| GET | `/positions` | 获取所有持仓 |
| DELETE | `/positions` | 平所有持仓 |
| DELETE | `/position/<ticket>` | 平指定持仓 |

### 信息端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/symbol/<symbol>` | 获取品种信息 |
| POST | `/connect` | 手动连接 MT5 |
| POST | `/disconnect` | 断开 MT5 连接 |

### 请求示例

#### 健康检查

```bash
curl http://localhost:80/health
```

#### 获取持仓

```bash
curl http://localhost:80/positions
```

#### 平指定持仓

```bash
curl -X DELETE http://localhost:80/position/123456
```

#### 获取品种信息

```bash
curl http://localhost:80/symbol/EURUSD
```

## 安全建议

1. **启用认证**: 在 `.env` 中设置 `ENABLE_AUTH=True` 并配置 `AUTH_TOKEN`
2. **防火墙**: 只开放必要端口（80/443）
3. **HTTPS**: 生产环境建议使用 Nginx 反向代理并配置 SSL
4. **日志监控**: 定期检查 `trading.log` 文件

## 生产环境部署

### 使用 Nginx + Gunicorn

1. 安装 Nginx
2. 配置 Nginx 反向代理：

```nginx
server {
    listen 443 ssl;
    server_name your_domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. 使用 systemd 管理服务：

```ini
[Unit]
Description=MT5 Trading Connector
After=network.target

[Service]
User=your_user
WorkingDirectory=/path/to/mt5_python_connector
Command=gunicorn -w 1 -b 127.0.0.1:80 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## 故障排除

### MT5 连接失败

1. 确认 MT5 终端已运行
2. 检查 MT5 路径配置是否正确
3. 确认 MT5 允许 DLL 导入

### 信号解析失败

1. 检查 TradingView 发送的数据格式
2. 查看 `trading.log` 中的详细日志
3. 确认品种名称拼写正确

### 交易执行失败

1. 检查账户余额是否充足
2. 确认手数在允许范围内
3. 检查品种交易时间是否允许

## 许可证

MIT License
