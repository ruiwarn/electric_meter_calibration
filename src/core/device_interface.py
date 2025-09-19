#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备抽象层 - M4阶段
为未来台体控源等设备扩展提供统一接口
确保良好的可维护性和扩展性
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum
import logging
import time


class DeviceType(Enum):
    """设备类型"""
    ELECTRIC_METER = "electric_meter"      # 电表设备
    POWER_SOURCE = "power_source"          # 台体控源设备
    MULTIMETER = "multimeter"              # 万用表设备
    UNKNOWN = "unknown"                    # 未知设备


class DeviceStatus(Enum):
    """设备状态"""
    DISCONNECTED = "disconnected"          # 未连接
    CONNECTING = "connecting"              # 连接中
    CONNECTED = "connected"                # 已连接
    BUSY = "busy"                          # 忙碌中
    ERROR = "error"                        # 错误状态
    TIMEOUT = "timeout"                    # 超时


@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str                         # 设备ID
    device_type: DeviceType               # 设备类型
    name: str                             # 设备名称
    manufacturer: str = "Unknown"          # 制造商
    model: str = "Unknown"                 # 型号
    version: str = "Unknown"               # 版本
    capabilities: List[str] = None         # 设备能力

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


@dataclass
class ConnectionConfig:
    """连接配置基类"""
    device_type: DeviceType
    timeout: float = 3.0
    max_retries: int = 3
    retry_delay: float = 0.5


@dataclass
class SerialConnectionConfig(ConnectionConfig):
    """串口连接配置"""
    port: str = "COM1"
    baudrate: int = 9600
    databits: int = 8
    parity: str = "E"
    stopbits: int = 1


@dataclass
class TCPConnectionConfig(ConnectionConfig):
    """TCP连接配置"""
    host: str = "localhost"
    port: int = 502


@dataclass
class DeviceCommand:
    """设备命令"""
    command_id: str                        # 命令ID
    command_type: str                      # 命令类型
    parameters: Dict[str, Any]             # 命令参数
    timeout: Optional[float] = None        # 超时时间
    priority: int = 1                      # 优先级 (1-10)


@dataclass
class DeviceResponse:
    """设备响应"""
    command_id: str                        # 对应命令ID
    success: bool                          # 是否成功
    data: Optional[bytes] = None           # 响应数据
    parsed_data: Optional[Dict] = None     # 解析后数据
    error_message: Optional[str] = None    # 错误信息
    response_time: float = 0.0             # 响应时间


class DeviceInterface(ABC):
    """设备接口抽象基类

    为所有设备类型提供统一的接口规范
    """

    def __init__(self, device_info: DeviceInfo):
        """初始化设备接口

        Args:
            device_info: 设备信息
        """
        self.device_info = device_info
        self.status = DeviceStatus.DISCONNECTED
        self.connection_config: Optional[ConnectionConfig] = None
        self.logger = logging.getLogger(f"Device.{device_info.device_id}")

        # 统计信息
        self.total_commands = 0
        self.successful_commands = 0
        self.failed_commands = 0
        self.total_response_time = 0.0

    @abstractmethod
    def connect(self, config: ConnectionConfig) -> bool:
        """连接设备

        Args:
            config: 连接配置

        Returns:
            是否连接成功
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """断开设备连接

        Returns:
            是否断开成功
        """
        pass

    @abstractmethod
    def send_command(self, command: DeviceCommand) -> DeviceResponse:
        """发送设备命令

        Args:
            command: 设备命令

        Returns:
            设备响应
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查设备是否已连接

        Returns:
            是否已连接
        """
        pass

    def get_device_info(self) -> DeviceInfo:
        """获取设备信息

        Returns:
            设备信息
        """
        return self.device_info

    def get_status(self) -> DeviceStatus:
        """获取设备状态

        Returns:
            设备状态
        """
        return self.status

    def get_statistics(self) -> Dict[str, Any]:
        """获取设备统计信息

        Returns:
            统计信息字典
        """
        avg_response_time = (self.total_response_time / self.total_commands
                           if self.total_commands > 0 else 0.0)

        success_rate = (self.successful_commands / self.total_commands * 100
                       if self.total_commands > 0 else 0.0)

        return {
            'total_commands': self.total_commands,
            'successful_commands': self.successful_commands,
            'failed_commands': self.failed_commands,
            'success_rate_percent': round(success_rate, 2),
            'average_response_time': round(avg_response_time, 3),
            'current_status': self.status.value
        }

    def reset_statistics(self):
        """重置统计信息"""
        self.total_commands = 0
        self.successful_commands = 0
        self.failed_commands = 0
        self.total_response_time = 0.0

    def _update_statistics(self, response: DeviceResponse):
        """更新统计信息

        Args:
            response: 设备响应
        """
        self.total_commands += 1
        self.total_response_time += response.response_time

        if response.success:
            self.successful_commands += 1
        else:
            self.failed_commands += 1


class ElectricMeterDevice(DeviceInterface):
    """电表设备实现

    实现电表的DL/T645协议通信
    """

    def __init__(self, device_id: str = "electric_meter_1"):
        device_info = DeviceInfo(
            device_id=device_id,
            device_type=DeviceType.ELECTRIC_METER,
            name="RN8213/RN8211B电表",
            manufacturer="Unknown",
            model="RN8213/RN8211B",
            capabilities=["calibration", "dl_t645"]
        )
        super().__init__(device_info)

        self.serial_port = None

    def connect(self, config: ConnectionConfig) -> bool:
        """连接电表设备"""
        if not isinstance(config, SerialConnectionConfig):
            self.logger.error("电表设备需要串口连接配置")
            return False

        try:
            self.status = DeviceStatus.CONNECTING
            self.connection_config = config

            # 导入串口模块
            from .serial_port import SerialPort

            # 创建串口连接
            self.serial_port = SerialPort()
            config_str = f"{config.port} {config.baudrate} {config.databits}{config.parity}{config.stopbits}"

            if self.serial_port.open_port(config_str):
                self.status = DeviceStatus.CONNECTED
                self.logger.info(f"电表设备连接成功: {config.port}")
                return True
            else:
                self.status = DeviceStatus.ERROR
                self.logger.error(f"电表设备连接失败: {config.port}")
                return False

        except Exception as e:
            self.status = DeviceStatus.ERROR
            self.logger.error(f"电表设备连接异常: {e}")
            return False

    def disconnect(self) -> bool:
        """断开电表设备连接"""
        try:
            if self.serial_port:
                self.serial_port.close_port()
                self.serial_port = None

            self.status = DeviceStatus.DISCONNECTED
            self.logger.info("电表设备已断开连接")
            return True

        except Exception as e:
            self.logger.error(f"电表设备断开连接异常: {e}")
            return False

    def send_command(self, command: DeviceCommand) -> DeviceResponse:
        """发送电表命令"""
        start_time = time.time()
        response = DeviceResponse(
            command_id=command.command_id,
            success=False
        )

        try:
            if not self.is_connected():
                response.error_message = "设备未连接"
                return response

            self.status = DeviceStatus.BUSY

            # 处理校表命令
            if command.command_type == "calibration":
                response = self._handle_calibration_command(command)
            else:
                response.error_message = f"不支持的命令类型: {command.command_type}"

        except Exception as e:
            response.error_message = f"命令执行异常: {str(e)}"
            self.logger.error(response.error_message)

        finally:
            response.response_time = time.time() - start_time
            self.status = DeviceStatus.CONNECTED
            self._update_statistics(response)

        return response

    def _handle_calibration_command(self, command: DeviceCommand) -> DeviceResponse:
        """处理校表命令"""
        from .frame_builder import ExcelEquivalentFrameBuilder

        response = DeviceResponse(
            command_id=command.command_id,
            success=False
        )

        try:
            # 获取命令参数
            di_code = command.parameters.get('di_code')
            parameter_data = command.parameters.get('parameter_data', b'')

            if not di_code:
                response.error_message = "缺少DI码参数"
                return response

            # 构建DL/T645帧
            builder = ExcelEquivalentFrameBuilder()
            frame = builder.build_frame_excel_equivalent(di_code, parameter_data)

            # 发送帧
            if self.serial_port.send_frame(frame):
                # 等待响应
                timeout = command.timeout or self.connection_config.timeout
                response_frame = self.serial_port.receive_frame(timeout)

                if response_frame:
                    response.success = True
                    response.data = response_frame
                    response.parsed_data = {
                        'frame_hex': response_frame.hex().upper(),
                        'frame_length': len(response_frame)
                    }
                else:
                    response.error_message = "设备无响应"
            else:
                response.error_message = "帧发送失败"

        except Exception as e:
            response.error_message = f"校表命令处理异常: {str(e)}"

        return response

    def is_connected(self) -> bool:
        """检查电表是否已连接"""
        return (self.serial_port is not None and
                self.serial_port.is_open() and
                self.status in [DeviceStatus.CONNECTED, DeviceStatus.BUSY])


class PowerSourceDevice(DeviceInterface):
    """台体控源设备实现 (预留接口)

    为未来台体控源设备扩展预留的接口
    """

    def __init__(self, device_id: str = "power_source_1"):
        device_info = DeviceInfo(
            device_id=device_id,
            device_type=DeviceType.POWER_SOURCE,
            name="台体控源设备",
            manufacturer="Unknown",
            model="Unknown",
            capabilities=["power_control", "voltage_output", "current_output"]
        )
        super().__init__(device_info)

    def connect(self, config: ConnectionConfig) -> bool:
        """连接台体控源设备 (待实现)"""
        self.logger.info("台体控源设备连接 - 待实现")
        # TODO: 实现台体控源连接逻辑
        return False

    def disconnect(self) -> bool:
        """断开台体控源连接 (待实现)"""
        self.logger.info("台体控源设备断开连接 - 待实现")
        # TODO: 实现台体控源断开逻辑
        return False

    def send_command(self, command: DeviceCommand) -> DeviceResponse:
        """发送台体控源命令 (待实现)"""
        response = DeviceResponse(
            command_id=command.command_id,
            success=False,
            error_message="台体控源设备 - 待实现"
        )
        return response

    def is_connected(self) -> bool:
        """检查台体控源是否已连接 (待实现)"""
        return False

    def set_voltage_output(self, voltage: float) -> bool:
        """设置电压输出 (待实现)"""
        self.logger.info(f"设置电压输出: {voltage}V - 待实现")
        return False

    def set_current_output(self, current: float) -> bool:
        """设置电流输出 (待实现)"""
        self.logger.info(f"设置电流输出: {current}A - 待实现")
        return False


class DeviceManager:
    """设备管理器

    管理多个设备的连接和操作
    """

    def __init__(self):
        self.devices: Dict[str, DeviceInterface] = {}
        self.logger = logging.getLogger("DeviceManager")

    def register_device(self, device: DeviceInterface):
        """注册设备

        Args:
            device: 设备接口实例
        """
        device_id = device.device_info.device_id
        self.devices[device_id] = device
        self.logger.info(f"设备已注册: {device_id} ({device.device_info.device_type.value})")

    def unregister_device(self, device_id: str):
        """注销设备

        Args:
            device_id: 设备ID
        """
        if device_id in self.devices:
            device = self.devices[device_id]
            if device.is_connected():
                device.disconnect()
            del self.devices[device_id]
            self.logger.info(f"设备已注销: {device_id}")

    def get_device(self, device_id: str) -> Optional[DeviceInterface]:
        """获取设备

        Args:
            device_id: 设备ID

        Returns:
            设备接口实例或None
        """
        return self.devices.get(device_id)

    def get_devices_by_type(self, device_type: DeviceType) -> List[DeviceInterface]:
        """按类型获取设备列表

        Args:
            device_type: 设备类型

        Returns:
            设备列表
        """
        return [device for device in self.devices.values()
                if device.device_info.device_type == device_type]

    def get_connected_devices(self) -> List[DeviceInterface]:
        """获取已连接的设备列表

        Returns:
            已连接设备列表
        """
        return [device for device in self.devices.values() if device.is_connected()]

    def disconnect_all_devices(self):
        """断开所有设备连接"""
        for device in self.devices.values():
            if device.is_connected():
                device.disconnect()

    def get_device_summary(self) -> Dict[str, Any]:
        """获取设备摘要信息

        Returns:
            设备摘要信息
        """
        summary = {
            'total_devices': len(self.devices),
            'connected_devices': len(self.get_connected_devices()),
            'device_types': {},
            'devices': []
        }

        # 统计设备类型
        for device in self.devices.values():
            device_type = device.device_info.device_type.value
            summary['device_types'][device_type] = summary['device_types'].get(device_type, 0) + 1

            # 设备详细信息
            summary['devices'].append({
                'device_id': device.device_info.device_id,
                'device_type': device_type,
                'name': device.device_info.name,
                'status': device.status.value,
                'statistics': device.get_statistics()
            })

        return summary


if __name__ == "__main__":
    # 测试设备抽象层
    print("=== 设备抽象层测试 ===\n")

    # 创建设备管理器
    device_manager = DeviceManager()

    # 创建电表设备
    electric_meter = ElectricMeterDevice("meter_1")
    device_manager.register_device(electric_meter)

    # 创建台体控源设备 (预留)
    power_source = PowerSourceDevice("source_1")
    device_manager.register_device(power_source)

    # 显示设备摘要
    summary = device_manager.get_device_summary()
    print("设备摘要:")
    print(f"  总设备数: {summary['total_devices']}")
    print(f"  已连接设备数: {summary['connected_devices']}")
    print(f"  设备类型: {summary['device_types']}")

    # 显示设备列表
    print("\n设备列表:")
    for device_info in summary['devices']:
        print(f"  - {device_info['device_id']}: {device_info['name']} ({device_info['status']})")

    # 测试电表设备 (需要实际串口才能完全测试)
    print("\n电表设备测试:")
    meter_info = electric_meter.get_device_info()
    print(f"  设备信息: {meter_info.name} - {meter_info.model}")
    print(f"  设备能力: {meter_info.capabilities}")
    print(f"  当前状态: {electric_meter.get_status().value}")

    print("\n=== 设备抽象层测试完成 ===")
    print("✓ 为台体控源扩展预留了完整的接口架构")