#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RN8213/RN8211B 电表校准工具 v2.0 - 日志系统
实现通信日志记录和格式化显示
"""

import time
from datetime import datetime
from typing import List, Optional
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    COMM = "COMM"     # 通信日志


class LogEntry:
    """日志条目类"""
    def __init__(self, level: LogLevel, message: str, timestamp: datetime = None):
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now()

    def to_string(self, show_timestamp: bool = True) -> str:
        """转换为字符串"""
        if show_timestamp:
            time_str = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
            return f"[{time_str}] {self.level.value}: {self.message}"
        else:
            return f"{self.level.value}: {self.message}"


class FrameLogEntry:
    """帧日志条目类"""
    def __init__(self, direction: str, frame_data: bytes, result: str = "", elapsed_time: float = 0):
        self.timestamp = datetime.now()
        self.direction = direction  # "Tx" 或 "Rx"
        self.frame_data = frame_data
        self.result = result        # "CS OK", "CS BAD", "TIMEOUT" 等
        self.elapsed_time = elapsed_time  # 毫秒

    def to_hex_string(self, separator: str = " ") -> str:
        """转换为十六进制字符串"""
        return separator.join(f'{b:02X}' for b in self.frame_data)

    def to_display_string(self) -> str:
        """转换为显示字符串"""
        time_str = self.timestamp.strftime("%H:%M:%S.%f")[:-3]
        hex_str = self.to_hex_string()

        # 构建显示字符串
        result_str = f" [{self.result}]" if self.result else ""
        time_str_suffix = f" ({self.elapsed_time:.0f}ms)" if self.elapsed_time > 0 else ""

        return f"[{time_str}] {self.direction}> {hex_str}{result_str}{time_str_suffix}"


class CalibrationLogger(QObject):
    """校准日志记录器"""

    # 信号定义
    log_added = pyqtSignal(str)        # 新日志添加信号
    frame_logged = pyqtSignal(str)     # 帧日志添加信号

    def __init__(self, max_entries: int = 1000):
        super().__init__()
        self.max_entries = max_entries
        self.log_entries: List[LogEntry] = []
        self.frame_entries: List[FrameLogEntry] = []
        self._last_tx_time: Optional[float] = None

    def log(self, level: LogLevel, message: str):
        """记录普通日志"""
        entry = LogEntry(level, message)
        self.log_entries.append(entry)

        # 限制日志数量
        if len(self.log_entries) > self.max_entries:
            self.log_entries.pop(0)

        # 发送信号
        self.log_added.emit(entry.to_string())

    def debug(self, message: str):
        """记录调试日志"""
        self.log(LogLevel.DEBUG, message)

    def info(self, message: str):
        """记录信息日志"""
        self.log(LogLevel.INFO, message)

    def warning(self, message: str):
        """记录警告日志"""
        self.log(LogLevel.WARNING, message)

    def error(self, message: str):
        """记录错误日志"""
        self.log(LogLevel.ERROR, message)

    def log_frame_tx(self, frame_data: bytes):
        """记录发送帧"""
        self._last_tx_time = time.time()
        entry = FrameLogEntry("Tx", frame_data)
        self.frame_entries.append(entry)

        # 限制帧日志数量
        if len(self.frame_entries) > self.max_entries:
            self.frame_entries.pop(0)

        # 发送信号
        self.frame_logged.emit(entry.to_display_string())

    def log_frame_rx(self, frame_data: bytes, result: str = ""):
        """记录接收帧"""
        elapsed_time = 0
        if self._last_tx_time:
            elapsed_time = (time.time() - self._last_tx_time) * 1000  # 转换为毫秒

        entry = FrameLogEntry("Rx", frame_data, result, elapsed_time)
        self.frame_entries.append(entry)

        # 限制帧日志数量
        if len(self.frame_entries) > self.max_entries:
            self.frame_entries.pop(0)

        # 发送信号
        self.frame_logged.emit(entry.to_display_string())

        # 重置发送时间
        self._last_tx_time = None

    def log_comm_event(self, message: str):
        """记录通信事件"""
        self.log(LogLevel.COMM, message)

    def get_recent_logs(self, count: int = 50) -> List[str]:
        """获取最近的日志"""
        recent_entries = self.log_entries[-count:] if count < len(self.log_entries) else self.log_entries
        return [entry.to_string() for entry in recent_entries]

    def get_recent_frames(self, count: int = 50) -> List[str]:
        """获取最近的帧日志"""
        recent_entries = self.frame_entries[-count:] if count < len(self.frame_entries) else self.frame_entries
        return [entry.to_display_string() for entry in recent_entries]

    def clear_logs(self):
        """清空日志"""
        self.log_entries.clear()
        self.frame_entries.clear()

    def export_logs_to_dict(self) -> dict:
        """导出日志到字典（用于Excel存储）"""
        return {
            'general_logs': [
                {
                    'timestamp': entry.timestamp.isoformat(),
                    'level': entry.level.value,
                    'message': entry.message
                }
                for entry in self.log_entries
            ],
            'frame_logs': [
                {
                    'timestamp': entry.timestamp.isoformat(),
                    'direction': entry.direction,
                    'frame_hex': entry.to_hex_string(),
                    'result': entry.result,
                    'elapsed_time': entry.elapsed_time
                }
                for entry in self.frame_entries
            ]
        }


class DLT645FrameAnalyzer:
    """DL/T645帧分析器"""

    @staticmethod
    def analyze_frame(frame_data: bytes) -> dict:
        """分析DL/T645帧结构

        Returns:
            包含帧分析结果的字典
        """
        if len(frame_data) < 12:  # 最小帧长度
            return {'valid': False, 'error': '帧长度不足'}

        try:
            # 基本结构检查
            if frame_data[0] != 0x68:
                return {'valid': False, 'error': '起始符错误'}

            if frame_data[7] != 0x68:
                return {'valid': False, 'error': '第二起始符错误'}

            if frame_data[-1] != 0x16:
                return {'valid': False, 'error': '结束符错误'}

            # 提取字段
            address = frame_data[1:7]
            control_code = frame_data[8]
            data_length = frame_data[9]
            data_field = frame_data[10:10+data_length]
            checksum = frame_data[10+data_length]

            # 校验和验证
            calc_checksum = sum(frame_data[7:10+data_length]) & 0xFF
            cs_valid = (calc_checksum == checksum)

            return {
                'valid': True,
                'address': address.hex().upper(),
                'control_code': f'0x{control_code:02X}',
                'data_length': data_length,
                'data_field': data_field.hex().upper(),
                'checksum': f'0x{checksum:02X}',
                'checksum_calc': f'0x{calc_checksum:02X}',
                'checksum_valid': cs_valid,
                'frame_type': DLT645FrameAnalyzer._get_frame_type(control_code)
            }

        except Exception as e:
            return {'valid': False, 'error': f'解析异常: {str(e)}'}

    @staticmethod
    def _get_frame_type(control_code: int) -> str:
        """获取帧类型描述"""
        frame_types = {
            0x01: '读数据',
            0x02: '读后续数据',
            0x04: '写数据',
            0x11: '读数据应答',
            0x12: '读后续数据应答',
            0x14: '写数据应答',
            0x81: '读数据异常应答',
            0x82: '读后续数据异常应答',
            0x84: '写数据异常应答'
        }
        return frame_types.get(control_code, f'未知类型(0x{control_code:02X})')

    @staticmethod
    def format_frame_analysis(analysis: dict) -> str:
        """格式化帧分析结果"""
        if not analysis['valid']:
            return f"❌ 帧分析失败: {analysis['error']}"

        cs_status = "✅" if analysis['checksum_valid'] else "❌"
        return (
            f"📋 {analysis['frame_type']} | "
            f"地址:{analysis['address']} | "
            f"控制码:{analysis['control_code']} | "
            f"数据长度:{analysis['data_length']} | "
            f"校验和:{cs_status}"
        )


# 全局日志实例
calibration_logger = CalibrationLogger()


# 测试代码
if __name__ == "__main__":
    # 测试日志记录
    logger = CalibrationLogger()

    logger.info("系统启动")
    logger.debug("调试信息")
    logger.warning("警告信息")
    logger.error("错误信息")

    # 测试帧日志
    test_frame = bytes.fromhex("68111111111111681400F81500333333343333334C16")
    logger.log_frame_tx(test_frame)

    time.sleep(0.1)
    response_frame = bytes.fromhex("681111111111116814053333333AC16")
    logger.log_frame_rx(response_frame, "CS OK")

    # 测试帧分析
    analyzer = DLT645FrameAnalyzer()
    analysis = analyzer.analyze_frame(test_frame)
    print("帧分析结果:", analysis)
    print("格式化结果:", analyzer.format_frame_analysis(analysis))

    # 输出日志
    print("\\n最近日志:")
    for log in logger.get_recent_logs():
        print(log)

    print("\\n最近帧日志:")
    for frame_log in logger.get_recent_frames():
        print(frame_log)