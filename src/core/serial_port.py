#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RN8213/RN8211B 电表校准工具 v2.0 - 串口通信模块
基于pyserial实现串口状态管理和DL/T645协议通信
"""

import serial
import serial.tools.list_ports
import threading
import time
from typing import List, Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal
from enum import Enum


class SerialState(Enum):
    """串口状态枚举"""
    CLOSED = "closed"       # 关闭
    OPENED = "opened"       # 已打开
    BUSY = "busy"          # 忙碌（正在通信）
    ERROR = "error"        # 错误状态


class SerialConfig:
    """串口配置类"""
    def __init__(self):
        self.port = ""                    # 端口名
        self.baudrate = 9600             # 波特率（常用9600）
        self.bytesize = 8                # 数据位
        self.parity = 'E'                # 校验位（Even）
        self.stopbits = 1                # 停止位
        self.timeout = 1.5               # 读超时（秒）
        self.write_timeout = 0.5         # 写超时（秒）
        self.retry_count = 2             # 重试次数
        self.frame_interval = 0.2        # 帧间隔（秒）

    def to_dict(self):
        """转换为字典"""
        return {
            'port': self.port,
            'baudrate': self.baudrate,
            'bytesize': self.bytesize,
            'parity': self.parity,
            'stopbits': self.stopbits,
            'timeout': self.timeout,
            'write_timeout': self.write_timeout,
            'retry_count': self.retry_count,
            'frame_interval': self.frame_interval
        }

    def from_dict(self, data):
        """从字典加载"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def __str__(self):
        """字符串表示"""
        parity_map = {'N': 'None', 'E': 'Even', 'O': 'Odd'}
        parity_str = parity_map.get(self.parity, self.parity)
        return f"{self.port}, {self.baudrate}, {self.bytesize}{parity_str[0]}{self.stopbits}"


class SerialPort(QObject):
    """串口通信类"""

    # 信号定义
    state_changed = pyqtSignal(str)      # 状态变化信号
    data_received = pyqtSignal(bytes)    # 数据接收信号
    error_occurred = pyqtSignal(str)     # 错误信号
    frame_sent = pyqtSignal(bytes)       # 帧发送信号
    frame_received = pyqtSignal(bytes)   # 帧接收信号

    def __init__(self):
        super().__init__()
        self.config = SerialConfig()
        self.serial_conn: Optional[serial.Serial] = None
        self.state = SerialState.CLOSED
        self._lock = threading.Lock()
        self.is_reading = False
        self.read_thread: Optional[threading.Thread] = None

    def get_available_ports(self) -> List[str]:
        """获取可用串口列表"""
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception as e:
            self.error_occurred.emit(f"获取串口列表失败: {str(e)}")
            return []

    def open_port(self, config: SerialConfig = None) -> bool:
        """打开串口"""
        if config:
            self.config = config

        if self.state != SerialState.CLOSED:
            self.error_occurred.emit("串口已打开或处于错误状态")
            return False

        try:
            # 创建串口连接
            self.serial_conn = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                bytesize=self.config.bytesize,
                parity=self.config.parity,
                stopbits=self.config.stopbits,
                timeout=self.config.timeout,
                write_timeout=self.config.write_timeout
            )

            # 清空缓冲区
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()

            # 更新状态
            self._set_state(SerialState.OPENED)

            # 启动读取线程
            self._start_read_thread()

            return True

        except Exception as e:
            self.error_occurred.emit(f"打开串口失败: {str(e)}")
            self._set_state(SerialState.ERROR)
            return False

    def close_port(self) -> bool:
        """关闭串口"""
        try:
            # 停止读取线程
            self._stop_read_thread()

            # 关闭串口
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()

            self.serial_conn = None
            self._set_state(SerialState.CLOSED)
            return True

        except Exception as e:
            self.error_occurred.emit(f"关闭串口失败: {str(e)}")
            return False

    def send_frame(self, frame_data: bytes) -> bool:
        """发送帧数据"""
        if self.state != SerialState.OPENED:
            self.error_occurred.emit("串口未打开")
            return False

        try:
            with self._lock:
                self._set_state(SerialState.BUSY)

                # 发送数据
                self.serial_conn.write(frame_data)
                self.serial_conn.flush()

                # 发送信号
                self.frame_sent.emit(frame_data)

                # 等待帧间隔
                time.sleep(self.config.frame_interval)

                self._set_state(SerialState.OPENED)
                return True

        except Exception as e:
            self.error_occurred.emit(f"发送帧失败: {str(e)}")
            self._set_state(SerialState.ERROR)
            return False

    def receive_frame(self, timeout: float = None) -> Optional[bytes]:
        """接收一个完整的DL/T645帧

        Args:
            timeout: 超时时间（秒），None使用配置的timeout

        Returns:
            接收到的完整帧数据，失败返回None
        """
        if self.state not in [SerialState.OPENED, SerialState.BUSY]:
            return None

        if timeout is None:
            timeout = self.config.timeout

        try:
            # 查找帧起始符 0x68
            start_time = time.time()
            while time.time() - start_time < timeout:
                byte_data = self.serial_conn.read(1)
                if not byte_data:
                    continue

                if byte_data == b'\\x68':
                    # 找到起始符，读取完整帧
                    frame = self._read_complete_frame(byte_data, timeout - (time.time() - start_time))
                    if frame:
                        self.frame_received.emit(frame)
                        return frame

            return None

        except Exception as e:
            self.error_occurred.emit(f"接收帧失败: {str(e)}")
            return None

    def _read_complete_frame(self, start_byte: bytes, remaining_timeout: float) -> Optional[bytes]:
        """读取完整的DL/T645帧

        帧格式: 68 A5..A0 68 C L DATA CS 16
        """
        try:
            frame = start_byte  # 0x68

            # 读取地址（6字节）+ 第二个68 + 控制码 + 长度（共9字节）
            header = self.serial_conn.read(9)
            if len(header) != 9:
                return None

            frame += header

            # 验证第二个起始符
            if header[6] != 0x68:
                return None

            # 获取数据长度
            data_length = header[8]

            # 读取数据域 + 校验和 + 结束符
            remaining = self.serial_conn.read(data_length + 2)
            if len(remaining) != data_length + 2:
                return None

            frame += remaining

            # 验证结束符
            if remaining[-1] != 0x16:
                return None

            return frame

        except Exception:
            return None

    def _start_read_thread(self):
        """启动读取线程"""
        if self.read_thread is not None:
            return

        self.is_reading = True
        self.read_thread = threading.Thread(target=self._read_worker, daemon=True)
        self.read_thread.start()

    def _stop_read_thread(self):
        """停止读取线程"""
        self.is_reading = False
        if self.read_thread:
            self.read_thread.join(timeout=1.0)
            self.read_thread = None

    def _read_worker(self):
        """读取工作线程"""
        while self.is_reading and self.serial_conn and self.serial_conn.is_open:
            try:
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    if data:
                        self.data_received.emit(data)

                time.sleep(0.01)  # 小延时避免过度占用CPU

            except Exception as e:
                if self.is_reading:  # 只有在读取标志为True时才报告错误
                    self.error_occurred.emit(f"读取数据出错: {str(e)}")
                break

    def _set_state(self, new_state: SerialState):
        """设置串口状态"""
        if self.state != new_state:
            self.state = new_state
            self.state_changed.emit(new_state.value)

    def get_state(self) -> SerialState:
        """获取当前状态"""
        return self.state

    def is_open(self) -> bool:
        """检查串口是否打开"""
        return self.state in [SerialState.OPENED, SerialState.BUSY]

    def get_config_summary(self) -> str:
        """获取配置摘要"""
        if self.state == SerialState.CLOSED:
            return "未连接"
        else:
            return str(self.config)


def hex_string_to_bytes(hex_str: str) -> bytes:
    """将十六进制字符串转换为字节数组

    Args:
        hex_str: 十六进制字符串，如 "68 11 11 11 11 11 11 68 14"

    Returns:
        对应的字节数组
    """
    # 移除空格和其他分隔符
    hex_str = hex_str.replace(' ', '').replace('-', '').replace(':', '')

    # 确保长度为偶数
    if len(hex_str) % 2 != 0:
        hex_str = '0' + hex_str

    # 转换为字节
    return bytes.fromhex(hex_str)


def bytes_to_hex_string(data: bytes, separator: str = ' ') -> str:
    """将字节数组转换为十六进制字符串

    Args:
        data: 字节数组
        separator: 分隔符，默认为空格

    Returns:
        十六进制字符串
    """
    return separator.join(f'{b:02X}' for b in data)


def calculate_checksum(frame_data: bytes) -> int:
    """计算DL/T645校验和

    Args:
        frame_data: 从第二个0x68到数据域末尾的字节数据

    Returns:
        校验和字节值
    """
    return sum(frame_data) & 0xFF


def build_dlt645_frame(address: str = "111111111111",
                      control_code: int = 0x14,
                      data_field: bytes = b"",
                      password: str = "33333333",
                      operator: str = "34333333") -> bytes:
    """构建DL/T645通信帧

    Args:
        address: 表地址(12位十六进制)，默认"111111111111"
        control_code: 控制码，默认0x14(写数据)
        data_field: 数据域，包含数据标识和数据
        password: 密码域(8位十六进制)，默认"33333333"
        operator: 操作者代码(8位十六进制)，默认"34333333"

    Returns:
        完整的DL/T645帧字节数组
    """
    # 起始符
    frame = bytearray([0x68])

    # 地址域(6字节，低位在前)
    addr_bytes = bytes.fromhex(address)
    if len(addr_bytes) == 6:
        # 逆序：低位在前
        frame.extend(addr_bytes[::-1])
    else:
        # 默认地址
        frame.extend([0x11, 0x11, 0x11, 0x11, 0x11, 0x11])

    # 第二个起始符
    frame.append(0x68)

    # 控制码
    frame.append(control_code)

    # 如果有数据域，添加数据
    if data_field:
        # 数据长度
        frame.append(len(data_field))

        # 数据域
        frame.extend(data_field)
    else:
        # 无数据
        frame.append(0x00)

    # 计算校验和(从第二个0x68开始)
    checksum_data = frame[7:]  # 从索引7(第二个0x68)开始
    checksum = calculate_checksum(checksum_data)
    frame.append(checksum)

    # 结束符
    frame.append(0x16)

    return bytes(frame)


def build_calibration_frame(step_id: int, standard_voltage: float = 220.0,
                           standard_current: float = 10.0) -> bytes:
    """构建校表步骤专用帧

    Args:
        step_id: 步骤ID (1-5)
        standard_voltage: 标准电压值
        standard_current: 标准电流值

    Returns:
        对应步骤的DL/T645帧
    """
    # 根据步骤ID构建不同的数据标识
    step_data_ids = {
        1: "00F81500",  # 电流有效值offset校正
        2: "00F81600",  # 电压电流增益校正
        3: "00F81700",  # 功率增益校正
        4: "00F81800",  # 相位补偿校正
        5: "00F81900"   # 小电流偏置校正
    }

    # 获取数据标识
    data_id = step_data_ids.get(step_id, "00F81500")

    # 构建数据域：数据标识 + 参数值(模拟)
    data_field = bytearray()

    # 数据标识(4字节，需要+0x33偏置)
    di_bytes = bytes.fromhex(data_id)
    for b in di_bytes:
        data_field.append((b + 0x33) & 0xFF)

    # 添加4字节参数数据(模拟标准值编码)
    voltage_encoded = int(standard_voltage * 100) & 0xFFFF
    current_encoded = int(standard_current * 100) & 0xFFFF

    data_field.append(((voltage_encoded & 0xFF) + 0x33) & 0xFF)
    data_field.append(((voltage_encoded >> 8) + 0x33) & 0xFF)
    data_field.append(((current_encoded & 0xFF) + 0x33) & 0xFF)
    data_field.append(((current_encoded >> 8) + 0x33) & 0xFF)

    return build_dlt645_frame(data_field=bytes(data_field))




# 测试代码
if __name__ == "__main__":
    # 测试十六进制转换
    test_hex = "68 11 11 11 11 11 11 68 14"
    test_bytes = hex_string_to_bytes(test_hex)
    print(f"原始: {test_hex}")
    print(f"字节: {test_bytes}")
    print(f"还原: {bytes_to_hex_string(test_bytes)}")

    # 测试串口枚举
    sp = SerialPort()
    ports = sp.get_available_ports()
    print(f"可用串口: {ports}")

    # 测试配置
    config = SerialConfig()
    print(f"默认配置: {config}")