# Rcon命令插件

<div align="center">

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)

</div>

## 📋 功能列表

### 1. RCON 连接管理

| 指令 | 说明 |
|------|------|
| `/rcon连接` | 测试连接 RCON 服务器 |
| `/rcon断开连接` | 断开当前 RCON 连接 |
| `/rcon状态` | 查看 RCON 连接状态 |
| `/rcon发送命令 <命令>` | 向服务器发送任意 RCON 命令 |
| `/rcon配置信息` | 查看当前 RCON 配置 |

### 2. 玩家监控

| 指令 | 说明 |
|------|------|
| `/玩家监控状态` | 查看监控开关、状态、检查间隔、通知群聊 |
| `/玩家监控启动` | 手动启动玩家监控 |
| `/玩家监控停止` | 手动停止玩家监控 |

**自动通知**：当玩家数量发生变化时，自动向配置的通知群聊发送通知。

### 3. 玩家查询

| 指令 | 说明 |
|------|------|
| `/查询玩家` | 显示当前在线人数和总注册人数 |
| `/玩家列表` | 显示所有玩家的详细信息列表（自动分截） |

### 4. WebUI 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `rcon_address` | string | `127.0.0.1` | RCON 服务器地址 |
| `rcon_port` | int | `18890` | RCON 服务器端口 |
| `rcon_password` | string | 空 | RCON 连接密码 |
| `player_monitor.enabled` | bool | `false` | 是否启用玩家监控 |
| `player_monitor.check_interval` | int | `60` | 检查间隔（秒） |
| `player_monitor.notify_group_id` | string | `720937751` | 通知目标群聊 ID |

## 🔧 使用方法

### 快速开始

1. 在 WebUI 中配置 RCON 服务器地址、端口和密码
2. 发送 `/rcon连接` 测试连接
3. 发送 `/玩家监控启动` 启动监控

### 配置玩家监控

1. 在 WebUI 中设置 `player_monitor.enabled` 为 `true`
2. 设置 `player_monitor.check_interval`（建议 30-300 秒）
3. 设置 `player_monitor.notify_group_id` 为目标群聊 ID
4. 重启插件或发送 `/玩家监控启动`

## 📊 玩家列表显示

发送 `/玩家列表` 会显示：

```
📋 玩家列表 (24人 | 在线1人)
━━━━━━━━━━━━━━━━━━━━━━
🟢 半痕 [巅峰阁] Lv.55 104.0h
⚪ Shell [巅峰阁] Lv.44 34.2h
⚪ LL [巅峰阁] Lv.17 3.0h
⚪ jojo [] Lv.2 0.1h
...
```

当内容超过 2000 字符时，会自动分截成多条消息发送。

## 🐔 联系作者

- **反馈**：欢迎在 [GitHub Issues](https://github.com/1592363624/astrbot_plugin_zanwo_shell/issues) 提交问题或建议
- QQ群：91219736
- Telegram：[巅峰阁](https://t.me/ShellDFG)
