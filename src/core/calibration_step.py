#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校表步骤引擎 - M3阶段
定义校表步骤基类和五个具体校表步骤实现
确保高可维护性和模块化设计
"""

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import time
import logging

class StepStatus(Enum):
    """步骤执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class CalibrationParameters:
    """校表参数数据结构"""
    standard_voltage: float = 220.0  # 标准电压(V)
    standard_current: float = 1.0    # 标准电流(A)
    frequency: float = 50.0          # 频率(Hz)
    power_factor: float = 1.0        # 功率因数
    phase_angle: float = 0.0         # 相位角(度)

    # 扩展参数
    no_load_threshold: float = 0.001 # 空载电流阈值(A)
    small_current_threshold: float = 0.05 # 小电流阈值(A)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'standard_voltage': self.standard_voltage,
            'standard_current': self.standard_current,
            'frequency': self.frequency,
            'power_factor': self.power_factor,
            'phase_angle': self.phase_angle,
            'no_load_threshold': self.no_load_threshold,
            'small_current_threshold': self.small_current_threshold
        }

@dataclass
class StepResult:
    """步骤执行结果"""
    status: StepStatus
    correction_value: Optional[float] = None  # 校正值
    raw_response: Optional[bytes] = None      # 原始响应
    error_message: Optional[str] = None       # 错误信息
    execution_time: Optional[float] = None    # 执行时间(秒)
    additional_data: Optional[Dict] = None    # 附加数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'status': self.status.value,
            'correction_value': self.correction_value,
            'raw_response': self.raw_response.hex().upper() if self.raw_response else None,
            'error_message': self.error_message,
            'execution_time': self.execution_time,
            'additional_data': self.additional_data or {}
        }

class CalibrationStep(ABC):
    """校表步骤基类

    每个具体的校表步骤需要继承此基类并实现抽象方法
    设计原则：单一职责、可测试、高内聚低耦合
    """

    def __init__(self, step_id: str, name: str, description: str):
        """初始化校表步骤

        Args:
            step_id: 步骤ID (如 "step1")
            name: 步骤名称 (如 "电流有效值offset校正")
            description: 步骤描述
        """
        self.step_id = step_id
        self.name = name
        self.description = description
        self.status = StepStatus.PENDING
        self.result: Optional[StepResult] = None
        self.logger = logging.getLogger(f"CalibrationStep.{step_id}")

    @abstractmethod
    def get_di_code(self) -> str:
        """获取DI码

        Returns:
            8位十六进制DI码
        """
        pass

    @abstractmethod
    def prepare_parameters(self, calibration_params: CalibrationParameters) -> bytes:
        """准备参数数据

        Args:
            calibration_params: 校表参数

        Returns:
            编码后的参数数据
        """
        pass

    @abstractmethod
    def process_response(self, response_frame: bytes) -> float:
        """处理设备响应并计算校正值

        Args:
            response_frame: 设备响应帧

        Returns:
            校正值
        """
        pass

    def execute(self, communicator, calibration_params: CalibrationParameters) -> StepResult:
        """执行校表步骤

        Args:
            communicator: 设备通信器
            calibration_params: 校表参数

        Returns:
            执行结果
        """
        self.logger.info(f"开始执行步骤: {self.name}")
        start_time = time.time()

        try:
            self.status = StepStatus.RUNNING

            # 1. 准备参数
            parameter_data = self.prepare_parameters(calibration_params)

            # 2. 发送校表命令
            response_frame = communicator.send_calibration_command(
                self.get_di_code(),
                parameter_data
            )

            # 3. 处理响应
            correction_value = self.process_response(response_frame)

            # 4. 创建成功结果
            execution_time = time.time() - start_time
            self.result = StepResult(
                status=StepStatus.SUCCESS,
                correction_value=correction_value,
                raw_response=response_frame,
                execution_time=execution_time
            )
            self.status = StepStatus.SUCCESS

            self.logger.info(f"步骤执行成功: {self.name}, 校正值: {correction_value}")
            return self.result

        except Exception as e:
            # 处理异常
            execution_time = time.time() - start_time
            error_msg = f"步骤执行失败: {str(e)}"

            self.result = StepResult(
                status=StepStatus.FAILED,
                error_message=error_msg,
                execution_time=execution_time
            )
            self.status = StepStatus.FAILED

            self.logger.error(error_msg)
            return self.result

    def skip(self, reason: str = "用户跳过") -> StepResult:
        """跳过步骤

        Args:
            reason: 跳过原因

        Returns:
            跳过结果
        """
        self.result = StepResult(
            status=StepStatus.SKIPPED,
            error_message=reason
        )
        self.status = StepStatus.SKIPPED

        self.logger.info(f"步骤跳过: {self.name}, 原因: {reason}")
        return self.result

    def reset(self):
        """重置步骤状态"""
        self.status = StepStatus.PENDING
        self.result = None
        self.logger.debug(f"步骤状态已重置: {self.name}")

    def get_summary(self) -> Dict[str, Any]:
        """获取步骤摘要信息"""
        return {
            'step_id': self.step_id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'di_code': self.get_di_code(),
            'result': self.result.to_dict() if self.result else None
        }


class CurrentOffsetCalibrationStep(CalibrationStep):
    """步骤1: 电流有效值offset校正 (空载校正)"""

    def __init__(self):
        super().__init__(
            step_id="step1",
            name="电流有效值offset校正",
            description="空载状态下的电流偏置校正，消除零点漂移"
        )

    def get_di_code(self) -> str:
        return "00F81500"

    def prepare_parameters(self, calibration_params: CalibrationParameters) -> bytes:
        """准备空载校正参数"""
        # 空载状态标识，通常为0
        no_load_flag = 0x00
        return bytes([no_load_flag])

    def process_response(self, response_frame: bytes) -> float:
        """处理空载校正响应"""
        # 从响应帧中提取校正值
        # 简化实现：返回基于响应数据的校正值
        if len(response_frame) >= 12:
            # 提取数据域并计算校正值
            data_start = 10
            data_len = response_frame[9]
            if len(response_frame) >= data_start + data_len:
                data_field = response_frame[data_start:data_start + data_len]
                # 计算校正值 (示例算法)
                correction_value = sum(data_field) / len(data_field) if data_field else 0.0
                return correction_value
        return 0.0


class VoltageCurrentGainCalibrationStep(CalibrationStep):
    """步骤2: 电压电流增益校正 (1.0L标准)"""

    def __init__(self):
        super().__init__(
            step_id="step2",
            name="电压电流增益校正",
            description="1.0L标准负载下的电压电流增益校正"
        )

    def get_di_code(self) -> str:
        return "00F81600"

    def prepare_parameters(self, calibration_params: CalibrationParameters) -> bytes:
        """准备增益校正参数"""
        # 编码标准电压和电流值
        voltage_encoded = int(calibration_params.standard_voltage * 100)  # 放大100倍
        current_encoded = int(calibration_params.standard_current * 1000) # 放大1000倍

        # 打包为字节流 (小端序)
        voltage_bytes = voltage_encoded.to_bytes(2, byteorder='little')
        current_bytes = current_encoded.to_bytes(2, byteorder='little')

        return voltage_bytes + current_bytes

    def process_response(self, response_frame: bytes) -> float:
        """处理增益校正响应"""
        if len(response_frame) >= 12:
            data_start = 10
            data_len = response_frame[9]
            if len(response_frame) >= data_start + data_len and data_len >= 4:
                data_field = response_frame[data_start:data_start + data_len]
                # 提取增益校正值 (前4字节)
                gain_value = int.from_bytes(data_field[:4], byteorder='little')
                return gain_value / 10000.0  # 归一化
        return 1.0


class PowerGainCalibrationStep(CalibrationStep):
    """步骤3: 功率增益校正"""

    def __init__(self):
        super().__init__(
            step_id="step3",
            name="功率增益校正",
            description="有功功率测量的增益校正"
        )

    def get_di_code(self) -> str:
        return "00F81700"

    def prepare_parameters(self, calibration_params: CalibrationParameters) -> bytes:
        """准备功率校正参数"""
        # 计算标准功率值
        standard_power = (calibration_params.standard_voltage *
                         calibration_params.standard_current *
                         calibration_params.power_factor)

        # 编码功率值
        power_encoded = int(standard_power * 100)  # 放大100倍
        power_bytes = power_encoded.to_bytes(4, byteorder='little')

        return power_bytes

    def process_response(self, response_frame: bytes) -> float:
        """处理功率校正响应"""
        if len(response_frame) >= 12:
            data_start = 10
            data_len = response_frame[9]
            if len(response_frame) >= data_start + data_len and data_len >= 4:
                data_field = response_frame[data_start:data_start + data_len]
                # 提取功率校正值
                power_correction = int.from_bytes(data_field[:4], byteorder='little')
                return power_correction / 10000.0  # 归一化
        return 1.0


class PhaseCompensationCalibrationStep(CalibrationStep):
    """步骤4: 相位补偿校正"""

    def __init__(self):
        super().__init__(
            step_id="step4",
            name="相位补偿校正",
            description="功率测量中的相位角度补偿校正"
        )

    def get_di_code(self) -> str:
        return "00F81800"

    def prepare_parameters(self, calibration_params: CalibrationParameters) -> bytes:
        """准备相位补偿参数"""
        # 编码相位角度 (度数转换为0.01度单位)
        phase_encoded = int(calibration_params.phase_angle * 100)
        phase_bytes = phase_encoded.to_bytes(2, byteorder='little', signed=True)

        return phase_bytes

    def process_response(self, response_frame: bytes) -> float:
        """处理相位补偿响应"""
        if len(response_frame) >= 12:
            data_start = 10
            data_len = response_frame[9]
            if len(response_frame) >= data_start + data_len and data_len >= 2:
                data_field = response_frame[data_start:data_start + data_len]
                # 提取相位补偿值
                phase_compensation = int.from_bytes(data_field[:2], byteorder='little', signed=True)
                return phase_compensation / 100.0  # 转换为度数
        return 0.0


class SmallCurrentBiasCalibrationStep(CalibrationStep):
    """步骤5: 小电流偏置校正"""

    def __init__(self):
        super().__init__(
            step_id="step5",
            name="小电流偏置校正",
            description="小电流条件下的测量偏置校正"
        )

    def get_di_code(self) -> str:
        return "00F81900"

    def prepare_parameters(self, calibration_params: CalibrationParameters) -> bytes:
        """准备小电流校正参数"""
        # 编码小电流阈值
        threshold_encoded = int(calibration_params.small_current_threshold * 10000)  # 放大10000倍
        threshold_bytes = threshold_encoded.to_bytes(4, byteorder='little')

        return threshold_bytes

    def process_response(self, response_frame: bytes) -> float:
        """处理小电流校正响应"""
        if len(response_frame) >= 12:
            data_start = 10
            data_len = response_frame[9]
            if len(response_frame) >= data_start + data_len and data_len >= 4:
                data_field = response_frame[data_start:data_start + data_len]
                # 提取偏置校正值
                bias_correction = int.from_bytes(data_field[:4], byteorder='little')
                return bias_correction / 10000.0  # 归一化
        return 0.0


# 工厂函数：创建所有校表步骤
def create_all_calibration_steps() -> List[CalibrationStep]:
    """创建所有校表步骤实例

    Returns:
        校表步骤列表
    """
    return [
        CurrentOffsetCalibrationStep(),
        VoltageCurrentGainCalibrationStep(),
        PowerGainCalibrationStep(),
        PhaseCompensationCalibrationStep(),
        SmallCurrentBiasCalibrationStep()
    ]


if __name__ == "__main__":
    # 测试校表步骤
    print("=== 校表步骤引擎测试 ===\n")

    # 创建校表参数
    params = CalibrationParameters(
        standard_voltage=220.0,
        standard_current=1.0,
        phase_angle=0.0
    )

    # 创建所有校表步骤
    steps = create_all_calibration_steps()

    # 测试每个步骤的基本功能
    for step in steps:
        print(f"步骤: {step.name}")
        print(f"  ID: {step.step_id}")
        print(f"  描述: {step.description}")
        print(f"  DI码: {step.get_di_code()}")

        # 测试参数准备
        try:
            param_data = step.prepare_parameters(params)
            print(f"  参数数据: {param_data.hex().upper() if param_data else '无'}")
        except Exception as e:
            print(f"  参数准备错误: {e}")

        print(f"  状态: {step.status.value}")
        print()

    print("=== 校表步骤引擎测试完成 ===")