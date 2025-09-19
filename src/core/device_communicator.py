#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设备通信管理器 - M3阶段
处理与电表设备的通信，包括超时重试、响应验证、错误处理
确保通信的可靠性和稳定性
"""

from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import time
import logging
from serial import Serial, SerialException

from .frame_builder import ExcelEquivalentFrameBuilder
from .frame_parser import DLT645FrameParser, ParsedFrame, FrameParseResult
from .serial_port import SerialPort


class CommunicationError(Exception):
    """通信异常基类"""
    pass


class TimeoutError(CommunicationError):
    """超时异常"""
    pass


class ResponseValidationError(CommunicationError):
    """响应验证异常"""
    pass


class DeviceError(CommunicationError):
    """设备错误异常"""
    pass


class CommunicationStatus(Enum):
    """通信状态"""
    IDLE = "idle"           # 空闲
    BUSY = "busy"           # 忙碌
    ERROR = "error"         # 错误
    TIMEOUT = "timeout"     # 超时


@dataclass
class CommunicationConfig:
    """通信配置"""
    timeout_ms: int = 3000           # 超时时间(毫秒)
    max_retries: int = 3             # 最大重试次数
    retry_delay_ms: int = 500        # 重试间隔(毫秒)
    frame_wait_ms: int = 100         # 帧间等待时间(毫秒)
    validate_response: bool = True    # 是否验证响应

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timeout_ms': self.timeout_ms,
            'max_retries': self.max_retries,
            'retry_delay_ms': self.retry_delay_ms,
            'frame_wait_ms': self.frame_wait_ms,
            'validate_response': self.validate_response
        }


@dataclass
class CommunicationResult:
    """通信结果"""
    success: bool
    response_frame: Optional[bytes] = None
    parsed_response: Optional[ParsedFrame] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    total_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'response_frame': self.response_frame.hex().upper() if self.response_frame else None,
            'parsed_response': self.parsed_response.to_dict() if self.parsed_response else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'total_time_ms': self.total_time_ms
        }


class DeviceCommunicator:
    """设备通信管理器

    负责与电表设备的DL/T645协议通信
    特性:
    - 超时重试机制
    - 响应帧验证
    - 错误分类处理
    - 通信状态跟踪
    """

    def __init__(self, serial_port: SerialPort, config: Optional[CommunicationConfig] = None):
        """初始化通信管理器

        Args:
            serial_port: 串口对象
            config: 通信配置
        """
        self.serial_port = serial_port
        self.config = config or CommunicationConfig()
        self.frame_builder = ExcelEquivalentFrameBuilder()
        self.frame_parser = DLT645FrameParser()

        self.status = CommunicationStatus.IDLE
        self.logger = logging.getLogger("DeviceCommunicator")

        # 统计信息
        self.total_commands_sent = 0
        self.successful_commands = 0
        self.failed_commands = 0
        self.total_retry_count = 0

    def send_calibration_command(self, di_code: str, parameter_data: bytes) -> bytes:
        """发送校表命令

        Args:
            di_code: DI标识码
            parameter_data: 参数数据

        Returns:
            响应帧数据

        Raises:
            CommunicationError: 通信失败
        """
        self.logger.info(f"发送校表命令 - DI: {di_code}, 参数: {parameter_data.hex().upper()}")

        # 检查串口状态
        if not self.serial_port or not self.serial_port.is_open():
            raise CommunicationError("串口未打开")

        self.status = CommunicationStatus.BUSY
        start_time = time.time()

        try:
            # 构建请求帧
            request_frame = self.frame_builder.build_frame_excel_equivalent(
                di_code=di_code,
                parameter_data=parameter_data
            )

            # 执行带重试的通信
            result = self._send_with_retry(request_frame)

            # 更新统计
            self.total_commands_sent += 1
            if result.success:
                self.successful_commands += 1
                self.status = CommunicationStatus.IDLE
            else:
                self.failed_commands += 1
                self.status = CommunicationStatus.ERROR

            self.total_retry_count += result.retry_count

            if result.success and result.response_frame:
                return result.response_frame
            else:
                raise CommunicationError(result.error_message or "通信失败")

        except Exception as e:
            self.status = CommunicationStatus.ERROR
            self.failed_commands += 1
            raise CommunicationError(f"通信异常: {str(e)}")

        finally:
            total_time = int((time.time() - start_time) * 1000)
            self.logger.info(f"通信完成 - 耗时: {total_time}ms, 状态: {self.status.value}")

    def _send_with_retry(self, request_frame: bytes) -> CommunicationResult:
        """执行带重试的发送

        Args:
            request_frame: 请求帧

        Returns:
            通信结果
        """
        start_time = time.time()
        last_error = None

        for attempt in range(self.config.max_retries + 1):  # +1 for initial attempt
            try:
                self.logger.info(f"通信尝试 {attempt + 1}/{self.config.max_retries + 1}")

                # 显示发送的帧
                frame_hex = ''.join(f'{b:02X}' for b in request_frame)
                self.logger.info(f"Tx> {frame_hex} ({len(request_frame)}字节)")

                # 发送帧
                send_success = self.serial_port.send_frame(request_frame)
                if not send_success:
                    raise CommunicationError("帧发送失败")

                # 等待响应
                response_frame = self._wait_for_response()

                if response_frame:
                    # 显示接收的帧
                    response_hex = ''.join(f'{b:02X}' for b in response_frame)
                    self.logger.info(f"Rx> {response_hex} ({len(response_frame)}字节)")
                    # 验证响应
                    if self.config.validate_response:
                        self._validate_response(request_frame, response_frame)

                    # 解析响应
                    parsed_response = self.frame_parser.parse_response_frame(response_frame)

                    total_time = int((time.time() - start_time) * 1000)
                    return CommunicationResult(
                        success=True,
                        response_frame=response_frame,
                        parsed_response=parsed_response,
                        retry_count=attempt,
                        total_time_ms=total_time
                    )

            except TimeoutError as e:
                last_error = e
                self.logger.warning(f"通信超时 (尝试 {attempt + 1}): {e}")

            except (ResponseValidationError, DeviceError) as e:
                last_error = e
                self.logger.warning(f"通信错误 (尝试 {attempt + 1}): {e}")

            except Exception as e:
                last_error = e
                self.logger.error(f"通信异常 (尝试 {attempt + 1}): {e}")

            # 重试前等待
            if attempt < self.config.max_retries:
                time.sleep(self.config.retry_delay_ms / 1000.0)

        # 所有尝试均失败
        total_time = int((time.time() - start_time) * 1000)
        return CommunicationResult(
            success=False,
            error_message=str(last_error) if last_error else "通信失败",
            retry_count=self.config.max_retries,
            total_time_ms=total_time
        )

    def _wait_for_response(self) -> Optional[bytes]:
        """等待设备响应

        Returns:
            响应帧数据或None

        Raises:
            TimeoutError: 响应超时
        """
        start_time = time.time()
        timeout_s = self.config.timeout_ms / 1000.0
        received_data = bytearray()

        while time.time() - start_time < timeout_s:
            # 读取可用数据
            available = self.serial_port.serial.in_waiting
            if available > 0:
                chunk = self.serial_port.serial.read(available)
                received_data.extend(chunk)

                # 检查是否收到完整帧
                if self._is_complete_frame(received_data):
                    return bytes(received_data)

            time.sleep(0.01)  # 短暂等待

        if received_data:
            self.logger.warning(f"接收到不完整数据: {received_data.hex().upper()}")
            raise ResponseValidationError(f"接收到不完整响应: {len(received_data)}字节")
        else:
            raise TimeoutError(f"响应超时: {self.config.timeout_ms}ms")

    def _is_complete_frame(self, data: bytearray) -> bool:
        """检查是否为完整的DL/T645帧

        Args:
            data: 接收到的数据

        Returns:
            是否为完整帧
        """
        if len(data) < 12:  # 最小DL/T645帧长度
            return False

        # 检查起始符和结束符
        if data[0] != 0x68 or data[7] != 0x68:
            return False

        # 检查数据长度
        if len(data) >= 10:
            data_len = data[9]
            expected_frame_len = 10 + data_len + 1 + 1  # 头部+数据+校验和+结束符
            if len(data) >= expected_frame_len and data[-1] == 0x16:
                return True

        return False

    def _validate_response(self, request_frame: bytes, response_frame: bytes):
        """验证响应帧

        Args:
            request_frame: 请求帧
            response_frame: 响应帧

        Raises:
            ResponseValidationError: 验证失败
        """
        # 解析请求和响应帧
        parsed_request = self.frame_parser.parse_frame(request_frame)
        parsed_response = self.frame_parser.parse_frame(response_frame)

        # 检查解析是否成功
        if parsed_response.parse_result != FrameParseResult.SUCCESS:
            raise ResponseValidationError(f"响应帧解析失败: {parsed_response.error_message}")

        # 检查地址匹配
        if parsed_request.address != parsed_response.address:
            raise ResponseValidationError("响应帧地址不匹配")

        # 检查是否为响应帧 (控制码+0x80)
        if parsed_request.control_code and parsed_response.control_code:
            expected_response_control = (parsed_request.control_code | 0x80) & 0xFF
            if parsed_response.control_code != expected_response_control:
                raise ResponseValidationError(
                    f"响应控制码不匹配: 期望0x{expected_response_control:02X}, "
                    f"实际0x{parsed_response.control_code:02X}"
                )

        # 检查校验和
        if not parsed_response.checksum_valid:
            raise ResponseValidationError("响应帧校验和错误")

    def test_communication(self) -> Dict[str, Any]:
        """测试通信连接

        Returns:
            测试结果
        """
        self.logger.info("开始通信测试")

        try:
            # 发送简单的读取命令进行测试
            test_di = "00F81500"
            test_params = b""

            result = self._send_with_retry(
                self.frame_builder.build_frame_excel_equivalent(test_di, test_params)
            )

            test_result = {
                'success': result.success,
                'response_received': result.response_frame is not None,
                'response_valid': False,
                'error_message': result.error_message,
                'retry_count': result.retry_count,
                'response_time_ms': result.total_time_ms
            }

            if result.parsed_response:
                test_result['response_valid'] = (
                    result.parsed_response.parse_result == FrameParseResult.SUCCESS
                )

            return test_result

        except Exception as e:
            return {
                'success': False,
                'error_message': str(e),
                'response_received': False,
                'response_valid': False
            }

    def get_statistics(self) -> Dict[str, Any]:
        """获取通信统计信息

        Returns:
            统计信息字典
        """
        success_rate = (self.successful_commands / self.total_commands_sent * 100
                       if self.total_commands_sent > 0 else 0)

        return {
            'total_commands': self.total_commands_sent,
            'successful_commands': self.successful_commands,
            'failed_commands': self.failed_commands,
            'success_rate_percent': round(success_rate, 2),
            'total_retries': self.total_retry_count,
            'average_retries': (self.total_retry_count / self.total_commands_sent
                              if self.total_commands_sent > 0 else 0),
            'current_status': self.status.value,
            'config': self.config.to_dict()
        }

    def reset_statistics(self):
        """重置统计信息"""
        self.total_commands_sent = 0
        self.successful_commands = 0
        self.failed_commands = 0
        self.total_retry_count = 0
        self.logger.info("通信统计已重置")


if __name__ == "__main__":
    # 测试设备通信管理器
    print("=== 设备通信管理器测试 ===\n")

    # 创建模拟串口 (需要实际串口进行完整测试)
    try:
        from .serial_port import SerialPort

        # 注意：需要实际串口设备进行测试
        # 这里仅演示API使用方式
        serial_port = SerialPort()

        # 创建通信配置
        config = CommunicationConfig(
            timeout_ms=2000,
            max_retries=2,
            retry_delay_ms=300
        )

        # 创建通信管理器
        communicator = DeviceCommunicator(serial_port, config)

        print("通信管理器已创建")
        print(f"配置: {config.to_dict()}")
        print(f"初始统计: {communicator.get_statistics()}")

        print("\n注意: 需要连接实际设备进行完整通信测试")

    except Exception as e:
        print(f"测试初始化失败: {e}")

    print("\n=== 设备通信管理器测试完成 ===")