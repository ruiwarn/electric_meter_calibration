#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帧解析引擎 - M2阶段
DL/T645响应帧解析，与Excel算法逆向等价
"""

from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from enum import Enum

class FrameParseResult(Enum):
    """帧解析结果类型"""
    SUCCESS = "success"
    INVALID_FORMAT = "invalid_format"
    CHECKSUM_ERROR = "checksum_error"
    LENGTH_ERROR = "length_error"
    UNKNOWN_ERROR = "unknown_error"

@dataclass
class ParsedFrame:
    """解析后的帧数据结构"""
    # 基本帧信息
    raw_frame: bytes
    frame_hex: str
    parse_result: FrameParseResult
    error_message: Optional[str] = None

    # 帧结构字段
    start_marker1: Optional[int] = None
    address: Optional[bytes] = None
    start_marker2: Optional[int] = None
    control_code: Optional[int] = None
    data_length: Optional[int] = None
    data_field: Optional[bytes] = None
    checksum: Optional[int] = None
    end_marker: Optional[int] = None

    # 解析后的数据域
    di_code: Optional[str] = None
    di_original: Optional[str] = None
    parameter_data: Optional[bytes] = None
    password_field: Optional[bytes] = None
    operator_field: Optional[bytes] = None

    # 校验信息
    calculated_checksum: Optional[int] = None
    checksum_valid: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'parse_result': self.parse_result.value,
            'error_message': self.error_message,
            'frame_hex': self.frame_hex,
            'frame_info': {
                'start_marker1': f"0x{self.start_marker1:02X}" if self.start_marker1 else None,
                'address': self.address.hex().upper() if self.address else None,
                'start_marker2': f"0x{self.start_marker2:02X}" if self.start_marker2 else None,
                'control_code': f"0x{self.control_code:02X}" if self.control_code else None,
                'data_length': self.data_length,
                'checksum': f"0x{self.checksum:02X}" if self.checksum else None,
                'checksum_valid': self.checksum_valid,
                'end_marker': f"0x{self.end_marker:02X}" if self.end_marker else None,
            },
            'data_info': {
                'di_code': self.di_code,
                'di_original': self.di_original,
                'parameter_data': self.parameter_data.hex().upper() if self.parameter_data else None,
                'password_field': self.password_field.hex().upper() if self.password_field else None,
                'operator_field': self.operator_field.hex().upper() if self.operator_field else None,
            }
        }

class DLT645FrameParser:
    """DL/T645帧解析器

    与FrameBuilder对应，能够解析由FrameBuilder生成的帧
    以及真实设备返回的响应帧
    """

    def __init__(self):
        self.DATA_OFFSET = 0x33  # 0x33偏置

    def parse_frame(self, frame_data: Union[bytes, str]) -> ParsedFrame:
        """解析DL/T645帧

        Args:
            frame_data: 帧数据，可以是bytes或十六进制字符串

        Returns:
            ParsedFrame对象
        """
        # 统一转换为bytes
        if isinstance(frame_data, str):
            try:
                frame_bytes = bytes.fromhex(frame_data.replace(' ', ''))
                frame_hex = frame_data.replace(' ', '').upper()
            except ValueError:
                return ParsedFrame(
                    raw_frame=b'',
                    frame_hex=frame_data,
                    parse_result=FrameParseResult.INVALID_FORMAT,
                    error_message="无效的十六进制字符串"
                )
        else:
            frame_bytes = frame_data
            frame_hex = frame_data.hex().upper()

        # 创建基本ParsedFrame对象
        parsed = ParsedFrame(
            raw_frame=frame_bytes,
            frame_hex=frame_hex,
            parse_result=FrameParseResult.SUCCESS
        )

        try:
            # 基本长度检查
            if len(frame_bytes) < 12:  # 最小DL/T645帧长度
                parsed.parse_result = FrameParseResult.LENGTH_ERROR
                parsed.error_message = f"帧长度过短: {len(frame_bytes)}字节，最少需要12字节"
                return parsed

            # 解析帧结构
            self._parse_frame_structure(frame_bytes, parsed)

            # 验证校验和
            self._verify_checksum(frame_bytes, parsed)

            # 解析数据域
            if parsed.data_field:
                self._parse_data_field(parsed.data_field, parsed)

        except Exception as e:
            parsed.parse_result = FrameParseResult.UNKNOWN_ERROR
            parsed.error_message = f"解析异常: {str(e)}"

        return parsed

    def _parse_frame_structure(self, frame_bytes: bytes, parsed: ParsedFrame):
        """解析帧基本结构"""
        # 起始符1
        parsed.start_marker1 = frame_bytes[0]
        if parsed.start_marker1 != 0x68:
            parsed.parse_result = FrameParseResult.INVALID_FORMAT
            parsed.error_message = f"无效的起始符1: 0x{parsed.start_marker1:02X}, 期望0x68"
            return

        # 地址域 (6字节)
        parsed.address = frame_bytes[1:7]

        # 起始符2
        parsed.start_marker2 = frame_bytes[7]
        if parsed.start_marker2 != 0x68:
            parsed.parse_result = FrameParseResult.INVALID_FORMAT
            parsed.error_message = f"无效的起始符2: 0x{parsed.start_marker2:02X}, 期望0x68"
            return

        # 控制码
        parsed.control_code = frame_bytes[8]

        # 数据长度
        parsed.data_length = frame_bytes[9]

        # 验证帧长度是否与数据长度匹配
        expected_frame_len = 10 + parsed.data_length + 1 + 1  # 头部+数据+校验和+结束符
        if len(frame_bytes) != expected_frame_len:
            parsed.parse_result = FrameParseResult.LENGTH_ERROR
            parsed.error_message = f"帧长度不匹配: 实际{len(frame_bytes)}字节, 期望{expected_frame_len}字节"
            return

        # 数据域
        if parsed.data_length > 0:
            parsed.data_field = frame_bytes[10:10 + parsed.data_length]

        # 校验和
        parsed.checksum = frame_bytes[10 + parsed.data_length]

        # 结束符
        parsed.end_marker = frame_bytes[10 + parsed.data_length + 1]
        if parsed.end_marker != 0x16:
            parsed.parse_result = FrameParseResult.INVALID_FORMAT
            parsed.error_message = f"无效的结束符: 0x{parsed.end_marker:02X}, 期望0x16"
            return

    def _verify_checksum(self, frame_bytes: bytes, parsed: ParsedFrame):
        """验证校验和"""
        if parsed.data_length is None or parsed.checksum is None:
            return

        # 计算校验和 (整个帧除了校验和和结束符)
        checksum_data = frame_bytes[:-2]
        calculated = sum(checksum_data) & 0xFF

        parsed.calculated_checksum = calculated
        parsed.checksum_valid = (calculated == parsed.checksum)

        if not parsed.checksum_valid:
            parsed.parse_result = FrameParseResult.CHECKSUM_ERROR
            parsed.error_message = f"校验和错误: 计算0x{calculated:02X}, 帧中0x{parsed.checksum:02X}"

    def _parse_data_field(self, data_field: bytes, parsed: ParsedFrame):
        """解析数据域"""
        if len(data_field) < 4:
            # 数据域太短，无法包含完整DI
            return

        try:
            # 移除0x33偏置
            deoffset_data = [(b - self.DATA_OFFSET) & 0xFF for b in data_field]

            # 解析DI码 (前4字节)
            di_bytes = deoffset_data[:4]

            # DI字节序还原 (逆向操作)
            # 原始顺序: 00 15 F8 00 -> 翻转为: 00 F8 15 00
            di_restored = f"{di_bytes[3]:02X}{di_bytes[2]:02X}{di_bytes[1]:02X}{di_bytes[0]:02X}"
            parsed.di_original = di_restored
            parsed.di_code = ' '.join(f"{b:02X}" for b in di_bytes)

            # 解析其余数据
            remaining_data = deoffset_data[4:]

            # 尝试识别密码域和操作者码
            if len(remaining_data) >= 8:
                parsed.password_field = bytes(remaining_data[:4])
                parsed.operator_field = bytes(remaining_data[4:8])

                if len(remaining_data) > 8:
                    parsed.parameter_data = bytes(remaining_data[8:])
            elif len(remaining_data) > 0:
                parsed.parameter_data = bytes(remaining_data)

        except Exception as e:
            # 数据域解析失败，不影响基本帧解析
            pass

    def parse_response_frame(self, frame_data: Union[bytes, str]) -> ParsedFrame:
        """解析响应帧

        响应帧通常控制码+0x80，数据域包含确认信息或错误码

        Args:
            frame_data: 响应帧数据

        Returns:
            ParsedFrame对象
        """
        parsed = self.parse_frame(frame_data)

        if parsed.parse_result == FrameParseResult.SUCCESS:
            # 添加响应帧特定分析
            if parsed.control_code and parsed.control_code & 0x80:
                # 这是一个响应帧
                original_control = parsed.control_code & 0x7F
                parsed.error_message = f"响应帧 (原始控制码: 0x{original_control:02X})"
            else:
                parsed.error_message = "可能不是响应帧"

        return parsed

    def compare_with_sent_frame(self, response_frame: Union[bytes, str],
                               sent_frame: Union[bytes, str]) -> Dict[str, Any]:
        """比较响应帧与发送帧

        Args:
            response_frame: 响应帧
            sent_frame: 发送帧

        Returns:
            比较结果字典
        """
        sent_parsed = self.parse_frame(sent_frame)
        response_parsed = self.parse_response_frame(response_frame)

        comparison = {
            'sent_frame': sent_parsed.to_dict(),
            'response_frame': response_parsed.to_dict(),
            'comparison': {
                'address_match': sent_parsed.address == response_parsed.address,
                'is_response': False,
                'control_relationship': None
            }
        }

        if sent_parsed.control_code and response_parsed.control_code:
            expected_response_control = (sent_parsed.control_code | 0x80) & 0xFF
            comparison['comparison']['is_response'] = (
                response_parsed.control_code == expected_response_control
            )
            comparison['comparison']['control_relationship'] = (
                f"发送: 0x{sent_parsed.control_code:02X} -> "
                f"期望响应: 0x{expected_response_control:02X} -> "
                f"实际响应: 0x{response_parsed.control_code:02X}"
            )

        return comparison


def parse_dlt645_frame(frame_data: Union[bytes, str]) -> ParsedFrame:
    """便捷函数：解析DL/T645帧"""
    parser = DLT645FrameParser()
    return parser.parse_frame(frame_data)


if __name__ == "__main__":
    # 测试帧解析
    print("=== 帧解析引擎测试 ===\n")

    parser = DLT645FrameParser()

    # 测试1: 解析Excel生成的标准帧
    excel_frame = "6811111111111168140D33482B33333333333433333333FC16"
    print("1. 解析Excel标准帧:")
    parsed = parser.parse_frame(excel_frame)
    print(f"解析结果: {parsed.parse_result.value}")
    print(f"校验和验证: {'通过' if parsed.checksum_valid else '失败'}")
    print(f"DI原码: {parsed.di_original}")
    print(f"DI翻转: {parsed.di_code}")

    # 测试2: 解析响应帧
    print("\n2. 解析模拟响应帧:")
    response_frame = "6811111111111168940433333333C116"  # 修正：补充缺失的字节
    response_parsed = parser.parse_response_frame(response_frame)
    print(f"解析结果: {response_parsed.parse_result.value}")
    if response_parsed.control_code:
        print(f"控制码: 0x{response_parsed.control_code:02X} (响应帧)")
    else:
        print(f"控制码解析失败: {response_parsed.error_message}")

    # 测试3: 对比分析
    print("\n3. 请求/响应对比:")
    comparison = parser.compare_with_sent_frame(response_frame, excel_frame)
    print(f"地址匹配: {comparison['comparison']['address_match']}")
    print(f"控制关系: {comparison['comparison']['control_relationship']}")

    # 测试4: 错误帧处理
    print("\n4. 错误帧测试:")
    invalid_frames = [
        "68",  # 太短
        "6811111111111168140D33482B33333333333433333333FB16",  # 错误校验和
        "6911111111111168140D33482B33333333333433333333FC16",  # 错误起始符
    ]

    for i, frame in enumerate(invalid_frames):
        parsed = parser.parse_frame(frame)
        print(f"  错误帧{i+1}: {parsed.parse_result.value} - {parsed.error_message}")

    print("\n=== 帧解析引擎测试完成 ===")