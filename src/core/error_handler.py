#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误处理系统 - M4阶段
增强的错误处理、分类和恢复建议系统
提供用户友好的错误信息和解决方案
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import traceback
from datetime import datetime


class ErrorCategory(Enum):
    """错误类别"""
    COMMUNICATION = "communication"        # 通信错误
    DEVICE = "device"                     # 设备错误
    PARAMETER = "parameter"               # 参数错误
    CONFIGURATION = "configuration"       # 配置错误
    SYSTEM = "system"                     # 系统错误
    USER = "user"                         # 用户操作错误


class ErrorSeverity(Enum):
    """错误严重程度"""
    INFO = "info"                         # 信息
    WARNING = "warning"                   # 警告
    ERROR = "error"                       # 错误
    CRITICAL = "critical"                 # 严重错误


@dataclass
class ErrorInfo:
    """错误信息"""
    error_id: str                         # 错误ID
    category: ErrorCategory               # 错误类别
    severity: ErrorSeverity               # 严重程度
    message: str                          # 错误消息
    user_message: str                     # 用户友好消息
    suggestions: List[str]                # 解决建议
    timestamp: str = ""                   # 发生时间
    context: Optional[Dict] = None        # 上下文信息
    technical_details: Optional[str] = None  # 技术详情

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'error_id': self.error_id,
            'category': self.category.value,
            'severity': self.severity.value,
            'message': self.message,
            'user_message': self.user_message,
            'suggestions': self.suggestions,
            'timestamp': self.timestamp,
            'context': self.context or {},
            'technical_details': self.technical_details
        }


class ErrorHandler:
    """错误处理器

    提供统一的错误处理、分类和恢复建议功能
    """

    def __init__(self):
        self.logger = logging.getLogger("ErrorHandler")
        self.error_callbacks: Dict[ErrorCategory, List[Callable]] = {}
        self.error_history: List[ErrorInfo] = []

        # 初始化错误定义
        self._init_error_definitions()

    def _init_error_definitions(self):
        """初始化错误定义"""
        self.error_definitions = {
            # 通信错误
            "COMM_001": ErrorInfo(
                error_id="COMM_001",
                category=ErrorCategory.COMMUNICATION,
                severity=ErrorSeverity.ERROR,
                message="串口连接失败",
                user_message="无法连接到指定的串口设备",
                suggestions=[
                    "检查串口线缆是否正确连接",
                    "确认串口号是否正确",
                    "检查串口是否被其他程序占用",
                    "尝试重新插拔串口设备"
                ]
            ),

            "COMM_002": ErrorInfo(
                error_id="COMM_002",
                category=ErrorCategory.COMMUNICATION,
                severity=ErrorSeverity.WARNING,
                message="通信超时",
                user_message="设备响应超时，可能设备未正确连接或故障",
                suggestions=[
                    "检查设备电源是否正常",
                    "确认设备地址配置是否正确",
                    "检查通信参数（波特率、校验位等）",
                    "尝试重新发送命令"
                ]
            ),

            "COMM_003": ErrorInfo(
                error_id="COMM_003",
                category=ErrorCategory.COMMUNICATION,
                severity=ErrorSeverity.ERROR,
                message="校验和错误",
                user_message="接收到的数据校验失败，可能存在通信干扰",
                suggestions=[
                    "检查通信线路是否有干扰",
                    "确认通信距离是否过长",
                    "尝试降低通信速率",
                    "检查接地是否良好"
                ]
            ),

            # 设备错误
            "DEV_001": ErrorInfo(
                error_id="DEV_001",
                category=ErrorCategory.DEVICE,
                severity=ErrorSeverity.ERROR,
                message="设备未响应",
                user_message="设备没有响应命令，可能设备故障或未上电",
                suggestions=[
                    "检查设备电源指示灯",
                    "确认设备工作状态正常",
                    "检查设备地址是否正确",
                    "尝试重启设备"
                ]
            ),

            "DEV_002": ErrorInfo(
                error_id="DEV_002",
                category=ErrorCategory.DEVICE,
                severity=ErrorSeverity.WARNING,
                message="设备忙碌",
                user_message="设备当前正在执行其他操作，请稍后重试",
                suggestions=[
                    "等待设备完成当前操作",
                    "检查是否有其他程序在操作设备",
                    "稍后重新尝试"
                ]
            ),

            # 参数错误
            "PARAM_001": ErrorInfo(
                error_id="PARAM_001",
                category=ErrorCategory.PARAMETER,
                severity=ErrorSeverity.ERROR,
                message="参数超出范围",
                user_message="输入的参数值超出了允许的范围",
                suggestions=[
                    "检查参数值是否在有效范围内",
                    "参考设备说明书确认参数限制",
                    "重新输入正确的参数值"
                ]
            ),

            "PARAM_002": ErrorInfo(
                error_id="PARAM_002",
                category=ErrorCategory.PARAMETER,
                severity=ErrorSeverity.ERROR,
                message="参数格式错误",
                user_message="参数格式不正确，请检查输入格式",
                suggestions=[
                    "确认数值格式是否正确",
                    "检查小数位数是否符合要求",
                    "参考帮助文档的格式示例"
                ]
            ),

            # 配置错误
            "CFG_001": ErrorInfo(
                error_id="CFG_001",
                category=ErrorCategory.CONFIGURATION,
                severity=ErrorSeverity.ERROR,
                message="配置文件损坏",
                user_message="配置文件损坏或格式错误",
                suggestions=[
                    "尝试恢复默认配置",
                    "从备份文件中恢复配置",
                    "手动重新配置参数"
                ]
            ),

            # 系统错误
            "SYS_001": ErrorInfo(
                error_id="SYS_001",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.CRITICAL,
                message="系统资源不足",
                user_message="系统资源不足，程序可能无法正常运行",
                suggestions=[
                    "关闭其他不必要的程序",
                    "检查可用内存和磁盘空间",
                    "重启计算机释放资源"
                ]
            ),

            # 用户操作错误
            "USER_001": ErrorInfo(
                error_id="USER_001",
                category=ErrorCategory.USER,
                severity=ErrorSeverity.WARNING,
                message="未选择校表步骤",
                user_message="请至少选择一个校表步骤进行执行",
                suggestions=[
                    "勾选需要执行的校表步骤",
                    "确认校表流程是否正确"
                ]
            )
        }

    def handle_error(self, error: Exception, context: Optional[Dict] = None) -> ErrorInfo:
        """处理异常错误

        Args:
            error: 异常对象
            context: 错误上下文

        Returns:
            错误信息对象
        """
        error_type = type(error).__name__
        error_message = str(error)

        # 尝试识别错误类型
        error_info = self._identify_error(error_type, error_message, context)

        # 添加技术详情
        error_info.technical_details = f"{error_type}: {error_message}\n{traceback.format_exc()}"

        # 记录错误
        self._log_error(error_info)

        # 调用错误回调
        self._call_error_callbacks(error_info)

        return error_info

    def handle_communication_error(self, error_code: str, details: Optional[Dict] = None) -> ErrorInfo:
        """处理通信错误

        Args:
            error_code: 错误代码
            details: 错误详情

        Returns:
            错误信息对象
        """
        error_info = self._get_predefined_error(error_code)
        if error_info and details:
            error_info.context = details

        self._log_error(error_info)
        self._call_error_callbacks(error_info)

        return error_info

    def handle_device_error(self, error_code: str, device_info: Optional[Dict] = None) -> ErrorInfo:
        """处理设备错误

        Args:
            error_code: 错误代码
            device_info: 设备信息

        Returns:
            错误信息对象
        """
        error_info = self._get_predefined_error(error_code)
        if error_info and device_info:
            error_info.context = device_info

        self._log_error(error_info)
        self._call_error_callbacks(error_info)

        return error_info

    def handle_parameter_error(self, error_code: str, parameter_info: Optional[Dict] = None) -> ErrorInfo:
        """处理参数错误

        Args:
            error_code: 错误代码
            parameter_info: 参数信息

        Returns:
            错误信息对象
        """
        error_info = self._get_predefined_error(error_code)
        if error_info and parameter_info:
            error_info.context = parameter_info

        self._log_error(error_info)
        self._call_error_callbacks(error_info)

        return error_info

    def register_error_callback(self, category: ErrorCategory, callback: Callable):
        """注册错误回调函数

        Args:
            category: 错误类别
            callback: 回调函数
        """
        if category not in self.error_callbacks:
            self.error_callbacks[category] = []
        self.error_callbacks[category].append(callback)

    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息

        Returns:
            错误统计字典
        """
        if not self.error_history:
            return {
                'total_errors': 0,
                'by_category': {},
                'by_severity': {},
                'recent_errors': []
            }

        # 按类别统计
        by_category = {}
        for error in self.error_history:
            category = error.category.value
            by_category[category] = by_category.get(category, 0) + 1

        # 按严重程度统计
        by_severity = {}
        for error in self.error_history:
            severity = error.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # 最近错误
        recent_errors = [error.to_dict() for error in self.error_history[-10:]]

        return {
            'total_errors': len(self.error_history),
            'by_category': by_category,
            'by_severity': by_severity,
            'recent_errors': recent_errors
        }

    def generate_error_report(self, session_id: Optional[str] = None) -> str:
        """生成错误报告

        Args:
            session_id: 会话ID（可选）

        Returns:
            错误报告文本
        """
        if not self.error_history:
            return "无错误记录"

        report_lines = [
            "=" * 60,
            "错误报告",
            "=" * 60,
            ""
        ]

        if session_id:
            report_lines.append(f"会话ID: {session_id}")
            report_lines.append("")

        # 统计信息
        stats = self.get_error_statistics()
        report_lines.extend([
            "统计信息:",
            f"  总错误数: {stats['total_errors']}",
            ""
        ])

        if stats['by_category']:
            report_lines.append("按类别分布:")
            for category, count in stats['by_category'].items():
                report_lines.append(f"  {category}: {count}")
            report_lines.append("")

        if stats['by_severity']:
            report_lines.append("按严重程度分布:")
            for severity, count in stats['by_severity'].items():
                report_lines.append(f"  {severity}: {count}")
            report_lines.append("")

        # 详细错误列表
        report_lines.extend([
            "详细错误列表:",
            "-" * 40
        ])

        for i, error in enumerate(self.error_history[-20:], 1):  # 最近20个错误
            report_lines.extend([
                f"{i}. {error.error_id} - {error.message}",
                f"   时间: {error.timestamp}",
                f"   类别: {error.category.value}",
                f"   严重程度: {error.severity.value}",
                f"   用户消息: {error.user_message}",
                ""
            ])

        return "\n".join(report_lines)

    def clear_error_history(self):
        """清除错误历史记录"""
        self.error_history.clear()
        self.logger.info("错误历史记录已清除")

    def _identify_error(self, error_type: str, error_message: str, context: Optional[Dict]) -> ErrorInfo:
        """识别错误类型"""
        # 根据异常类型和消息内容识别预定义错误
        if "timeout" in error_message.lower():
            return self._get_predefined_error("COMM_002")
        elif "connection" in error_message.lower():
            return self._get_predefined_error("COMM_001")
        elif "checksum" in error_message.lower():
            return self._get_predefined_error("COMM_003")
        elif "parameter" in error_message.lower():
            return self._get_predefined_error("PARAM_001")
        else:
            # 创建通用错误信息
            return ErrorInfo(
                error_id="GEN_001",
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.ERROR,
                message=f"{error_type}: {error_message}",
                user_message="发生未知错误，请查看详细信息或联系技术支持",
                suggestions=[
                    "重新尝试操作",
                    "检查程序日志获取更多信息",
                    "如问题持续存在，请联系技术支持"
                ],
                context=context
            )

    def _get_predefined_error(self, error_code: str) -> ErrorInfo:
        """获取预定义错误信息"""
        if error_code in self.error_definitions:
            # 复制错误信息以避免修改原始定义
            original = self.error_definitions[error_code]
            return ErrorInfo(
                error_id=original.error_id,
                category=original.category,
                severity=original.severity,
                message=original.message,
                user_message=original.user_message,
                suggestions=original.suggestions.copy(),
                context=original.context
            )
        else:
            return ErrorInfo(
                error_id=error_code,
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.ERROR,
                message=f"未知错误代码: {error_code}",
                user_message="发生未知错误",
                suggestions=["请联系技术支持"]
            )

    def _log_error(self, error_info: ErrorInfo):
        """记录错误"""
        # 添加到历史记录
        self.error_history.append(error_info)

        # 限制历史记录数量
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-500:]  # 保留最近500条

        # 写入日志
        log_message = f"[{error_info.error_id}] {error_info.message}"
        if error_info.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.ERROR:
            self.logger.error(log_message)
        elif error_info.severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    def _call_error_callbacks(self, error_info: ErrorInfo):
        """调用错误回调函数"""
        callbacks = self.error_callbacks.get(error_info.category, [])
        for callback in callbacks:
            try:
                callback(error_info)
            except Exception as e:
                self.logger.error(f"错误回调函数执行失败: {e}")


# 全局错误处理器实例
error_handler = ErrorHandler()


def handle_error(error: Exception, context: Optional[Dict] = None) -> ErrorInfo:
    """全局错误处理函数"""
    return error_handler.handle_error(error, context)


if __name__ == "__main__":
    # 测试错误处理系统
    print("=== 错误处理系统测试 ===\n")

    # 创建错误处理器
    handler = ErrorHandler()

    # 测试预定义错误
    print("1. 测试预定义错误:")
    comm_error = handler.handle_communication_error("COMM_001", {"port": "COM1"})
    print(f"   错误ID: {comm_error.error_id}")
    print(f"   用户消息: {comm_error.user_message}")
    print(f"   建议数量: {len(comm_error.suggestions)}")

    # 测试异常处理
    print("\n2. 测试异常处理:")
    try:
        raise TimeoutError("连接超时")
    except Exception as e:
        error_info = handler.handle_error(e, {"operation": "device_connect"})
        print(f"   识别错误ID: {error_info.error_id}")
        print(f"   用户消息: {error_info.user_message}")

    # 测试错误统计
    print("\n3. 错误统计:")
    stats = handler.get_error_statistics()
    print(f"   总错误数: {stats['total_errors']}")
    print(f"   按类别: {stats['by_category']}")
    print(f"   按严重程度: {stats['by_severity']}")

    # 测试报告生成
    print("\n4. 错误报告:")
    report = handler.generate_error_report("test_session")
    print("   报告生成成功，长度:", len(report))

    print("\n=== 错误处理系统测试完成 ===")