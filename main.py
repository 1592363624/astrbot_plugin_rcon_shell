"""
Rcon命令插件
定时监控Rcon命令执行并发送通知
"""

import asyncio
from typing import Optional

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from .services.rcon_service import RconService, get_rcon_pool
from .services.player_monitor_service import PlayerMonitorService, PlayerInfo


@register("Rcon命令插件", "Shell", "定时监控Rcon命令执行并发送通知", "1.0.1",
          "https://github.com/1592363624/astrbot_plugin_rcon_shell")
class RconMonitorPlugin(Star):
    """RCON 命令插件，提供 RCON 连接和命令执行功能"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._rcon_service: Optional[RconService] = None
        self._player_monitor: Optional[PlayerMonitorService] = None
        self._monitor_tasks: list[asyncio.Task] = []
        self._init_player_monitor()

    def _init_player_monitor(self):
        """初始化玩家监控服务"""
        self._player_monitor = PlayerMonitorService(
            get_rcon_service_func=self._get_rcon_service,
            notify_callback=self._send_notification
        )
        player_monitor_config = self.config.get("player_monitor", {})
        if player_monitor_config.get("enabled", False):
            interval = player_monitor_config.get("check_interval", 60)
            group_id = player_monitor_config.get("notify_group_id", "720937751")
            self._player_monitor.set_check_interval(interval)
            self._player_monitor.set_notify_group_id(group_id)
            asyncio.create_task(self._player_monitor.start_monitor())

    async def _send_notification(self, message: str):
        """
        发送通知到目标群聊

        Args:
            message: 通知消息内容
        """
        if not self._player_monitor:
            return

        group_id = self._player_monitor._notify_group_id
        if not group_id:
            return

        try:
            platform = self.context.get_platform()
            if platform == "telegram":
                umo = f"telegram:group:{group_id}"
            elif platform == "qq":
                umo = f"qq:group:{group_id}"
            else:
                umo = group_id

            chain = MessageChain().message(message)
            await self.context.send_message(umo, chain)
            logger.info(f"玩家监控通知已发送到群 {group_id}")
        except Exception as e:
            logger.error(f"发送玩家监控通知失败: {e}")

    def _get_rcon_service(self) -> RconService:
        """
        获取或创建 RCON 服务实例

        Returns:
            RconService 实例
        """
        if self._rcon_service is None:
            rcon_address = self.config.get("rcon_address", "127.0.0.1")
            rcon_port = self.config.get("rcon_port", 18890)
            rcon_password = self.config.get("rcon_password", "")
            self._rcon_service = RconService(
                host=rcon_address,
                port=rcon_port,
                password=rcon_password
            )
        return self._rcon_service

    @filter.command("rcon连接")
    async def rcon_connect(self, event: AstrMessageEvent):
        """测试 RCON 连接"""
        rcon = self._get_rcon_service()
        success, msg = rcon.connect()
        if success:
            yield event.plain_result(f"✅ RCON 连接成功")
        else:
            yield event.plain_result(f"❌ RCON 连接失败: {msg}")

    @filter.command("rcon断开连接")
    async def rcon_disconnect(self, event: AstrMessageEvent):
        """断开 RCON 连接"""
        if self._rcon_service:
            self._rcon_service.disconnect()
            self._rcon_service = None
            yield event.plain_result("✅ RCON 连接已断开")
        else:
            yield event.plain_result("ℹ️ 当前没有活跃的 RCON 连接")

    @filter.command("rcon状态")
    async def rcon_status(self, event: AstrMessageEvent):
        """查看 RCON 连接状态"""
        rcon = self._get_rcon_service()
        if rcon.is_connected():
            yield event.plain_result(f"✅ RCON 已连接")
        else:
            yield event.plain_result("ℹ️ RCON 未连接，可使用 /rcon连接 连接")

    @filter.command("rcon发送命令")
    async def rcon_send(self, event: AstrMessageEvent, cmd: str):
        """
        发送 RCON 命令

        Args:
            cmd: 要执行的命令
        """
        if not cmd or not cmd.strip():
            yield event.plain_result("❌ 请提供要执行的命令\n用法: /rcon发送命令 <命令>")
            return

        rcon = self._get_rcon_service()
        success, result = await rcon.send_command_async(cmd.strip())

        if success:
            if result:
                yield event.plain_result(f"📨 命令执行成功:\n{result}")
            else:
                yield event.plain_result("📨 命令执行成功（无输出）")
        else:
            yield event.plain_result(f"❌ 命令执行失败: {result}")

    @filter.command("rcon配置信息")
    async def rcon_info(self, event: AstrMessageEvent):
        """显示当前 RCON 配置信息"""
        rcon_address = self.config.get("rcon_address", "127.0.0.1")
        rcon_port = self.config.get("rcon_port", 18890)
        rcon_password = self.config.get("rcon_password", "")
        password_display = "已设置" if rcon_password else "未设置"

        info = f"""📋 RCON 配置信息:
🔌 地址: {rcon_address}
🔢 端口: {rcon_port}
🔑 密码: {password_display}"""
        yield event.plain_result(info)

    async def _execute_rcon_command(self, command: str) -> tuple[bool, str]:
        """
        执行 RCON 命令的内部方法

        Args:
            command: 要执行的命令

        Returns:
            (是否成功, 结果或错误信息)
        """
        rcon = self._get_rcon_service()
        return await rcon.send_command_async(command)

    def execute_rcon_command_sync(self, command: str) -> tuple[bool, str]:
        """
        同步执行 RCON 命令（供定时任务等场景使用）

        Args:
            command: 要执行的命令

        Returns:
            (是否成功, 结果或错误信息)
        """
        rcon = self._get_rcon_service()
        return rcon.send_command(command)

    @filter.command("玩家监控状态")
    async def player_monitor_status(self, event: AstrMessageEvent):
        """查看玩家监控状态"""
        if not self._player_monitor:
            yield event.plain_result("❌ 玩家监控服务未初始化")
            return

        is_running = self._player_monitor.is_running()
        status_text = "运行中" if is_running else "已停止"

        player_monitor_config = self.config.get("player_monitor", {})
        enabled = player_monitor_config.get("enabled", False)
        interval = player_monitor_config.get("check_interval", 60)
        group_id = player_monitor_config.get("notify_group_id", "720937751")

        last_online, last_total = self._player_monitor.get_last_state()

        info = f"""📊 玩家监控状态:
━━━━━━━━━━━━━━━
🔔 监控开关: {'✅ 已启用' if enabled else '❌ 已禁用'}
⚡ 当前状态: {status_text}
⏱️ 检查间隔: {interval}秒
👥 通知群聊: {group_id}
━━━━━━━━━━━━━━━"""

        if last_online is not None:
            info += f"\n📈 上次在线: {last_online}人"
            if last_total is not None:
                info += f" / 总人数: {last_total}人"

        yield event.plain_result(info)

    @filter.command("玩家监控启动")
    async def player_monitor_start(self, event: AstrMessageEvent):
        """启动玩家监控"""
        if not self._player_monitor:
            yield event.plain_result("❌ 玩家监控服务未初始化")
            return

        if self._player_monitor.is_running():
            yield event.plain_result("ℹ️ 玩家监控已在运行中")
            return

        player_monitor_config = self.config.get("player_monitor", {})
        interval = player_monitor_config.get("check_interval", 60)
        self._player_monitor.set_check_interval(interval)

        await self._player_monitor.start_monitor()
        yield event.plain_result("✅ 玩家监控已启动")

    @filter.command("玩家监控停止")
    async def player_monitor_stop(self, event: AstrMessageEvent):
        """停止玩家监控"""
        if not self._player_monitor:
            yield event.plain_result("❌ 玩家监控服务未初始化")
            return

        if not self._player_monitor.is_running():
            yield event.plain_result("ℹ️ 玩家监控已停止")
            return

        await self._player_monitor.stop_monitor()
        yield event.plain_result("✅ 玩家监控已停止")

    @filter.command("查询玩家")
    async def query_players(self, event: AstrMessageEvent):
        """立即查询当前玩家数量"""
        if not self._player_monitor:
            yield event.plain_result("❌ 玩家监控服务未初始化")
            return

        yield event.plain_result("🔍 正在查询玩家信息...")

        player_info = await self._player_monitor.query_player_info()
        if player_info is None:
            yield event.plain_result("❌ 查询失败，请检查 RCON 连接")
            return

        result = f"""🎮 玩家信息:
━━━━━━━━━━━━━━━
📊 在线玩家: {player_info.online_count}人
📈 总注册人数: {player_info.total_count}人"""

        if player_info.online_names:
            names_text = ", ".join(player_info.online_names)
            result += f"\n👥 在线玩家: {names_text}"
        else:
            result += f"\n👥 当前无玩家在线"

        yield event.plain_result(result)

    @filter.command("玩家列表")
    async def player_list(self, event: AstrMessageEvent):
        """显示玩家详细信息列表（超长自动分截）"""
        if not self._player_monitor:
            yield event.plain_result("❌ 玩家监控服务未初始化")
            return

        yield event.plain_result("🔍 正在加载玩家列表...")

        player_info = await self._player_monitor.query_player_info()
        if player_info is None:
            yield event.plain_result("❌ 查询失败，请检查 RCON 连接")
            return

        if not player_info.all_players:
            yield event.plain_result("📋 暂无玩家数据")
            return

        header = f"📋 玩家列表 ({player_info.total_count}人 | 在线{player_info.online_count}人)\n"
        header += f"━━━━━━━━━━━━━━━━━━━━━━\n"

        lines = []
        for p in player_info.all_players:
            online_indicator = "🟢" if p.is_online else "⚪"
            name = p.player_name[:10] if len(p.player_name) <= 10 else p.player_name[:10]
            guild = f"[{p.guild}]" if p.guild else ""
            hours = p.total_online / 3600.0
            line = f"{online_indicator} {name} {guild} Lv.{p.level} {hours:.1f}h"
            lines.append(line)

        footer = f"\n━━━━━━━━━━━━━━━\n📊 在线: {player_info.online_count}人 / 总计: {player_info.total_count}人"

        content = header + "\n".join(lines) + footer
        max_len = 2000

        if len(content) <= max_len:
            yield event.plain_result(content)
            return

        chunks = []
        current_chunk = header
        for line in lines:
            test_chunk = current_chunk + line + "\n"
            if len(test_chunk) > max_len:
                if current_chunk != header:
                    chunks.append(current_chunk.rstrip("\n"))
                    current_chunk = header + line + "\n"
                else:
                    chunks.append(current_chunk.rstrip("\n"))
                    current_chunk = line + "\n"
            else:
                current_chunk = test_chunk

        if current_chunk.strip() != header.strip():
            chunks.append(current_chunk.rstrip("\n"))

        chunks[-1] += footer

        for chunk in chunks:
            yield event.plain_result(chunk)

    def shutdown(self):
        """插件关闭时的清理操作"""
        if self._rcon_service:
            self._rcon_service.disconnect()
            logger.info("RCON 连接已清理")

        if self._player_monitor and self._player_monitor.is_running():
            asyncio.create_task(self._player_monitor.stop_monitor())
            logger.info("玩家监控已清理")
