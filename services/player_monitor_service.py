"""
玩家监控服务模块
定时查询玩家数量并在玩家变动时发送通知
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable
from astrbot.api import logger


@dataclass
class PlayerDetailInfo:
    """玩家详细信息数据类"""
    account: str = ""
    player_name: str = ""
    guild: str = ""
    level: int = 0
    total_online: float = 0.0
    birthday: str = ""
    is_online: bool = False


@dataclass
class PlayerInfo:
    """玩家信息数据类"""
    online_count: int = 0
    total_count: int = 0
    online_names: list[str] = field(default_factory=list)
    all_players: list[PlayerDetailInfo] = field(default_factory=list)


@dataclass
class PlayerChange:
    """玩家变动信息"""
    online_count: int
    total_count: int
    player_names: list[str]
    change_type: str
    previous_online: int
    current_online: int


class PlayerMonitorService:
    """玩家监控服务类"""

    def __init__(
        self,
        get_rcon_service_func: Callable[[], any],
        notify_callback: Optional[Callable[[str], Awaitable[None]]] = None
    ):
        """
        初始化玩家监控服务

        Args:
            get_rcon_service_func: 获取 RCON 服务的回调函数
            notify_callback: 通知回调函数，接收消息字符串
        """
        self._get_rcon_service = get_rcon_service_func
        self._notify_callback = notify_callback
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        self._check_interval = 60
        self._notify_group_id = "720937751"
        self._last_online_count: Optional[int] = None
        self._last_total_count: Optional[int] = None

    def set_notify_callback(self, callback: Callable[[str], Awaitable[None]]):
        """设置通知回调函数"""
        self._notify_callback = callback

    def set_check_interval(self, interval: int):
        """设置检查间隔（秒）"""
        self._check_interval = max(10, interval)

    def set_notify_group_id(self, group_id: str):
        """设置通知目标群聊 ID"""
        self._notify_group_id = group_id

    async def start_monitor(self):
        """启动监控任务"""
        if self._running:
            logger.warning("玩家监控已在运行中")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"玩家监控已启动，检查间隔: {self._check_interval}秒")

    async def stop_monitor(self):
        """停止监控任务"""
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self._monitor_task = None
        logger.info("玩家监控已停止")

    def is_running(self) -> bool:
        """检查监控是否在运行"""
        return self._running

    async def query_player_info(self) -> Optional[PlayerInfo]:
        """
        查询玩家信息（在线人数 + 总注册人数）

        Returns:
            PlayerInfo 或 None（查询失败时）
        """
        try:
            rcon = self._get_rcon_service()
            if not rcon.is_connected():
                success, _ = rcon.connect()
                if not success:
                    logger.error("玩家监控: RCON 连接失败")
                    return None

            online_result = await rcon.send_command_async("List_OnlinePlayers")
            online_info = self._parse_online_players(online_result[1] if online_result[0] else "")

            all_result = await rcon.send_command_async("List_AllPlayers")
            all_info = self._parse_all_players(all_result[1] if all_result[0] else "")

            online_info.total_count = all_info.total_count
            online_info.all_players = all_info.all_players

            online_names_set = set(online_info.online_names)
            for player in online_info.all_players:
                if player.player_name in online_names_set:
                    player.is_online = True

            online_info.all_players.sort(key=lambda p: (not p.is_online, -p.level))

            logger.info(f"查询结果: 在线={online_info.online_count}, 总计={online_info.total_count}")
            return online_info

        except Exception as e:
            logger.error(f"玩家监控: 查询异常 - {e}")
            return None

    def _parse_online_players(self, raw_data: str) -> PlayerInfo:
        """
        解析在线玩家数据

        Args:
            raw_data: List_OnlinePlayers 返回的原始数据

        Returns:
            PlayerInfo
        """
        player_info = PlayerInfo()
        if not raw_data or raw_data.strip() == "":
            return player_info

        logger.info(f"在线玩家原始数据: {repr(raw_data[:500])}")

        try:
            import json
            data = json.loads(raw_data)
            if isinstance(data, list):
                player_info.online_count = len(data)
                player_info.online_names = [
                    p.get("name", "") or p.get("playerName", "") or p.get("DisplayName", "")
                    for p in data
                    if p.get("name") or p.get("playerName") or p.get("DisplayName")
                ]
        except (json.JSONDecodeError, ValueError):
            player_info = self._parse_online_players_text(raw_data)

        return player_info

    def _parse_online_players_text(self, raw_data: str) -> PlayerInfo:
        """
        文本模式解析在线玩家数据

        Args:
            raw_data: 原始文本数据

        Returns:
            PlayerInfo
        """
        player_info = PlayerInfo()
        lines = raw_data.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('|---') or line.startswith('+---'):
                continue

            parts = [p.strip() for p in line.split('|')]
            parts = [p for p in parts if p]

            name_match = re.search(r"'([^']+)'", line)
            if name_match:
                player_info.online_names.append(name_match.group(1))
                player_info.online_count += 1

        return player_info

    def _parse_all_players(self, raw_data: str) -> PlayerInfo:
        """
        解析所有玩家账户数据

        Args:
            raw_data: List_AllPlayers 返回的原始数据

        Returns:
            PlayerInfo
        """
        player_info = PlayerInfo()
        if not raw_data or raw_data.strip() == "":
            return player_info

        logger.info(f"所有玩家原始数据长度: {len(raw_data)}")

        lines = raw_data.strip().split('\n')
        header_found = False
        header_indices = {}

        for line in lines:
            line = line.strip()
            if not line or line.startswith('|---') or line.startswith('+---'):
                continue

            parts = [p.strip() for p in line.split('|')]
            parts = [p for p in parts if p]

            if not header_found and len(parts) > 0 and parts[0] == "Account":
                header_found = True
                for i, col in enumerate(parts):
                    col_lower = col.lower()
                    if "account" in col_lower:
                        header_indices["account"] = i
                    elif "player" in col_lower and "name" in col_lower:
                        header_indices["name"] = i
                    elif "guild" in col_lower:
                        header_indices["guild"] = i
                    elif "level" in col_lower:
                        header_indices["level"] = i
                    elif "total" in col_lower and "online" in col_lower:
                        header_indices["total_online"] = i
                    elif "birthday" in col_lower or "date" in col_lower:
                        header_indices["birthday"] = i
                continue

            if header_found and len(parts) >= 2:
                first_part = parts[0].strip()
                if first_part.isdigit() and len(first_part) > 10:
                    detail = PlayerDetailInfo()
                    detail.account = first_part

                    if "name" in header_indices and header_indices["name"] < len(parts):
                        name_val = parts[header_indices["name"]].strip("'\"")
                        detail.player_name = name_val

                    if "guild" in header_indices and header_indices["guild"] < len(parts):
                        detail.guild = parts[header_indices["guild"]].strip("'\"")

                    if "level" in header_indices and header_indices["level"] < len(parts):
                        try:
                            detail.level = int(parts[header_indices["level"]])
                        except ValueError:
                            detail.level = 0

                    if "total_online" in header_indices and header_indices["total_online"] < len(parts):
                        try:
                            detail.total_online = float(parts[header_indices["total_online"]])
                        except ValueError:
                            detail.total_online = 0.0

                    if "birthday" in header_indices and header_indices["birthday"] < len(parts):
                        detail.birthday = parts[header_indices["birthday"]]

                    player_info.all_players.append(detail)
                    player_info.total_count = len(player_info.all_players)

        logger.info(f"解析到总玩家数: {player_info.total_count}")
        return player_info

    def detect_change(self, current: PlayerInfo) -> Optional[PlayerChange]:
        """
        检测玩家数量变动

        Args:
            current: 当前的玩家信息

        Returns:
            PlayerChange 或 None（无变动时）
        """
        if self._last_online_count is None:
            self._last_online_count = current.online_count
            self._last_total_count = current.total_count
            return None

        if self._last_online_count != current.online_count:
            change_type = "increase" if current.online_count > self._last_online_count else "decrease"
            change = PlayerChange(
                online_count=current.online_count,
                total_count=current.total_count,
                player_names=current.online_names,
                change_type=change_type,
                previous_online=self._last_online_count,
                current_online=current.online_count
            )
            self._last_online_count = current.online_count
            self._last_total_count = current.total_count
            return change

        return None

    async def _monitor_loop(self):
        """监控主循环"""
        while self._running:
            try:
                player_info = await self.query_player_info()
                if player_info:
                    change = self.detect_change(player_info)
                    if change and self._notify_callback:
                        message = self._build_change_message(change)
                        await self._notify_callback(message)
                        logger.info(
                            f"玩家变动: {change.previous_online} -> {change.current_online}"
                        )

            except Exception as e:
                logger.error(f"玩家监控循环异常: {e}")

            await asyncio.sleep(self._check_interval)

    def _build_change_message(self, change: PlayerChange) -> str:
        """
        构建变动通知消息

        Args:
            change: 玩家变动信息

        Returns:
            格式化的通知消息
        """
        emoji = "🆕" if change.change_type == "increase" else "👋"

        msg = f"""🎮 玩家状态变动 {emoji}
━━━━━━━━━━━━━━━
📊 在线玩家: {change.current_online}人
━━━━━━━━━━━━━━━"""

        if change.player_names:
            names_preview = ", ".join(change.player_names[:10])
            if len(change.player_names) > 10:
                names_preview += f" ... (+{len(change.player_names) - 10}人)"
            msg += f"\n👥 {names_preview}"

        return msg

    def get_last_state(self) -> tuple[Optional[int], Optional[int]]:
        """
        获取上次状态

        Returns:
            (上次在线人数, 上次总人数)
        """
        return self._last_online_count, self._last_total_count
