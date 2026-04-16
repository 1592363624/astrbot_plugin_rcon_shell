"""
RCON 服务模块
提供 RCON 协议连接和命令执行功能
"""

import asyncio
import socket
import struct
from typing import Optional, Tuple
from astrbot.api import logger


class RconService:
    """RCON 协议服务类，参考 RCONWeb 项目实现"""

    PACKET_TYPE_AUTH = 3
    PACKET_TYPE_EXECCMD = 2
    PACKET_TYPE_RESPONSE = 0
    PACKET_TYPE_AUTH_RESPONSE = 2

    def __init__(self, host: str, port: int, password: str, timeout: int = 30):
        """
        初始化 RCON 服务

        Args:
            host: RCON 服务器地址
            port: RCON 服务器端口
            password: RCON 连接密码
            timeout: 连接超时时间（秒）
        """
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._request_id = 1

    def _send_packet(self, packet_type: int, data: str) -> Optional[str]:
        """
        发送 RCON 数据包

        Args:
            packet_type: 数据包类型
            data: 要发送的数据

        Returns:
            响应体或 None
        """
        if not self._socket:
            return None

        request_id = self._request_id
        self._request_id += 1

        body = data.encode('utf-8') + b'\x00\x00'
        packet_size = 4 + 4 + len(body)

        packet = struct.pack('<i', packet_size)
        packet += struct.pack('<i', request_id)
        packet += struct.pack('<i', packet_type)
        packet += body

        try:
            self._socket.send(packet)
            return self._receive_packet()
        except Exception as e:
            logger.error(f"RCON 发送数据包异常: {e}")
            raise e

    def _receive_packet(self) -> Optional[str]:
        """
        接收 RCON 响应数据包

        Returns:
            响应体或 None
        """
        try:
            size_data = self._socket.recv(4)
            if len(size_data) < 4:
                return None

            packet_size = struct.unpack('<i', size_data)[0]

            packet_data = b''
            while len(packet_data) < packet_size:
                chunk = self._socket.recv(packet_size - len(packet_data))
                if not chunk:
                    return None
                packet_data += chunk

            if len(packet_data) >= 8:
                response_id = struct.unpack('<i', packet_data[0:4])[0]
                response_type = struct.unpack('<i', packet_data[4:8])[0]
                response_body = packet_data[8:-2].decode('utf-8', errors='ignore')

                if response_type == 2 and response_id == -1:
                    return None

                return response_body

        except Exception:
            return None
        return None

    def _authenticate(self) -> bool:
        """
        RCON 认证

        Returns:
            认证是否成功
        """
        try:
            response = self._send_packet(self.PACKET_TYPE_AUTH, self.password)
            return response is not None
        except:
            return False

    def connect(self) -> Tuple[bool, str]:
        """
        连接到 RCON 服务器

        Returns:
            (是否成功, 错误信息)
        """
        try:
            if self._connected:
                logger.info("RCON 已连接，先断开旧连接")
                self.disconnect()

            logger.info(f"正在连接 RCON 服务器: {self.host}:{self.port}")
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))

            if self._authenticate():
                self._connected = True
                logger.info(f"RCON 连接成功: {self.host}:{self.port}")
                return True, "连接成功"
            else:
                self.disconnect()
                return False, "RCON 认证失败"

        except socket.timeout:
            logger.error(f"RCON 连接超时: {self.host}:{self.port}")
            self.disconnect()
            return False, "连接超时"
        except ConnectionRefusedError:
            logger.error(f"RCON 连接被拒绝: {self.host}:{self.port}")
            self.disconnect()
            return False, "连接被拒绝，请检查服务器是否启动"
        except OSError as e:
            if e.winerror == 10061:
                logger.error(f"RCON 无法连接到服务器: {self.host}:{self.port}，服务器可能未启动或端口未开放")
                self.disconnect()
                return False, "连接错误: 由于目标计算机积极拒绝，无法连接"
            logger.error(f"RCON 连接错误: {e}")
            self.disconnect()
            return False, f"连接错误: {str(e)}"
        except Exception as e:
            logger.error(f"RCON 连接异常: {e}")
            self.disconnect()
            return False, f"连接异常: {str(e)}"

    def disconnect(self):
        """断开 RCON 连接"""
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            self._socket = None
        self._connected = False

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected

    def send_command(self, command: str) -> Tuple[bool, str]:
        """
        发送 RCON 命令

        Args:
            command: 要执行的命令

        Returns:
            (是否成功, 命令执行结果或错误信息)
        """
        if not self._connected:
            success, msg = self.connect()
            if not success:
                return False, f"连接失败: {msg}"

        try:
            response = self._send_packet(self.PACKET_TYPE_EXECCMD, command)
            if response:
                return True, response.strip()
            else:
                return False, "命令执行失败"

        except socket.timeout:
            self._connected = False
            return False, "命令执行超时"
        except OSError as e:
            self._connected = False
            if e.winerror == 10061:
                return False, "连接错误: 由于目标计算机积极拒绝，无法连接"
            return False, f"命令执行错误: {str(e)}"
        except Exception as e:
            self._connected = False
            return False, f"命令执行异常: {str(e)}"

    async def send_command_async(self, command: str) -> Tuple[bool, str]:
        """
        异步发送 RCON 命令

        Args:
            command: 要执行的命令

        Returns:
            (是否成功, 命令执行结果或错误信息)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send_command, command)


class RconConnectionPool:
    """RCON 连接池，用于管理多个 RCON 连接"""

    def __init__(self):
        self._connections: dict[str, RconService] = {}

    def get_connection(self, host: str, port: int, password: str) -> RconService:
        """
        获取或创建 RCON 连接

        Args:
            host: RCON 服务器地址
            port: RCON 服务器端口
            password: RCON 连接密码

        Returns:
            RconService 实例
        """
        key = f"{host}:{port}"
        if key not in self._connections:
            self._connections[key] = RconService(host, port, password)
        return self._connections[key]

    def close_all(self):
        """关闭所有连接"""
        for conn in self._connections.values():
            conn.disconnect()
        self._connections.clear()


_rcon_pool: Optional[RconConnectionPool] = None


def get_rcon_pool() -> RconConnectionPool:
    """获取全局 RCON 连接池"""
    global _rcon_pool
    if _rcon_pool is None:
        _rcon_pool = RconConnectionPool()
    return _rcon_pool
