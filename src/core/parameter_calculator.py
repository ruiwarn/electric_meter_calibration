#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参数计算引擎 - M3阶段
处理物理量与DL/T645协议数据格式的转换
包括标准值验证、精度控制、单位转换、误差分析
"""

from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import math
import logging
from enum import Enum


class ParameterType(Enum):
    """参数类型"""
    VOLTAGE = "voltage"
    CURRENT = "current"
    POWER = "power"
    FREQUENCY = "frequency"
    PHASE = "phase"
    ENERGY = "energy"


class ValidationResult(Enum):
    """验证结果"""
    VALID = "valid"
    OUT_OF_RANGE = "out_of_range"
    INVALID_FORMAT = "invalid_format"
    PRECISION_ERROR = "precision_error"


@dataclass
class ParameterRange:
    """参数范围定义"""
    min_value: float
    max_value: float
    precision_digits: int = 3
    unit: str = ""

    def validate(self, value: float) -> ValidationResult:
        """验证参数值是否在范围内"""
        if not isinstance(value, (int, float)):
            return ValidationResult.INVALID_FORMAT

        if not (self.min_value <= value <= self.max_value):
            return ValidationResult.OUT_OF_RANGE

        # 检查精度
        rounded_value = round(value, self.precision_digits)
        if abs(value - rounded_value) > (10 ** (-self.precision_digits - 1)):
            return ValidationResult.PRECISION_ERROR

        return ValidationResult.VALID


@dataclass
class CalculationResult:
    """计算结果"""
    encoded_value: bytes
    original_value: float
    validation_result: ValidationResult
    error_message: Optional[str] = None
    encoding_info: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'encoded_value': self.encoded_value.hex().upper(),
            'original_value': self.original_value,
            'validation_result': self.validation_result.value,
            'error_message': self.error_message,
            'encoding_info': self.encoding_info or {}
        }


class ParameterCalculator:
    """参数计算引擎

    负责处理校表过程中的参数计算和格式转换:
    - 标准值范围验证
    - 物理量到DL/T645格式编码
    - DL/T645格式到物理量解码
    - 精度控制和误差分析
    """

    def __init__(self):
        self.logger = logging.getLogger("ParameterCalculator")

        # 定义各类参数的标准范围
        self.parameter_ranges = {
            ParameterType.VOLTAGE: ParameterRange(50.0, 500.0, 2, "V"),
            ParameterType.CURRENT: ParameterRange(0.001, 200.0, 3, "A"),
            ParameterType.POWER: ParameterRange(0.01, 100000.0, 2, "W"),
            ParameterType.FREQUENCY: ParameterRange(45.0, 65.0, 2, "Hz"),
            ParameterType.PHASE: ParameterRange(-180.0, 180.0, 2, "度"),
            ParameterType.ENERGY: ParameterRange(0.0, 999999.999, 3, "kWh")
        }

        # DL/T645编码配置
        self.encoding_configs = {
            ParameterType.VOLTAGE: {'scale': 100, 'bytes': 2, 'signed': False},
            ParameterType.CURRENT: {'scale': 1000, 'bytes': 4, 'signed': False},
            ParameterType.POWER: {'scale': 100, 'bytes': 4, 'signed': False},
            ParameterType.FREQUENCY: {'scale': 100, 'bytes': 2, 'signed': False},
            ParameterType.PHASE: {'scale': 100, 'bytes': 2, 'signed': True},
            ParameterType.ENERGY: {'scale': 1000, 'bytes': 4, 'signed': False}
        }

    def calculate_voltage_params(self, standard_voltage: float) -> CalculationResult:
        """计算电压参数

        Args:
            standard_voltage: 标准电压值(V)

        Returns:
            计算结果
        """
        return self._calculate_parameter(
            value=standard_voltage,
            param_type=ParameterType.VOLTAGE,
            description="标准电压"
        )

    def calculate_current_params(self, standard_current: float) -> CalculationResult:
        """计算电流参数

        Args:
            standard_current: 标准电流值(A)

        Returns:
            计算结果
        """
        return self._calculate_parameter(
            value=standard_current,
            param_type=ParameterType.CURRENT,
            description="标准电流"
        )

    def calculate_power_params(self, voltage: float, current: float,
                              power_factor: float = 1.0) -> CalculationResult:
        """计算功率参数

        Args:
            voltage: 电压值(V)
            current: 电流值(A)
            power_factor: 功率因数

        Returns:
            计算结果
        """
        # 计算有功功率
        power_value = voltage * current * power_factor

        result = self._calculate_parameter(
            value=power_value,
            param_type=ParameterType.POWER,
            description="计算功率"
        )

        # 添加计算信息
        if result.encoding_info:
            result.encoding_info.update({
                'voltage': voltage,
                'current': current,
                'power_factor': power_factor,
                'calculated_power': power_value
            })

        return result

    def calculate_frequency_params(self, frequency: float) -> CalculationResult:
        """计算频率参数

        Args:
            frequency: 频率值(Hz)

        Returns:
            计算结果
        """
        return self._calculate_parameter(
            value=frequency,
            param_type=ParameterType.FREQUENCY,
            description="频率"
        )

    def calculate_phase_params(self, phase_angle: float) -> CalculationResult:
        """计算相位参数

        Args:
            phase_angle: 相位角度(度)

        Returns:
            计算结果
        """
        return self._calculate_parameter(
            value=phase_angle,
            param_type=ParameterType.PHASE,
            description="相位角"
        )

    def _calculate_parameter(self, value: float, param_type: ParameterType,
                           description: str) -> CalculationResult:
        """通用参数计算方法

        Args:
            value: 参数值
            param_type: 参数类型
            description: 参数描述

        Returns:
            计算结果
        """
        self.logger.debug(f"计算{description}: {value}")

        try:
            # 1. 验证参数范围
            param_range = self.parameter_ranges.get(param_type)
            if not param_range:
                return CalculationResult(
                    encoded_value=b'',
                    original_value=value,
                    validation_result=ValidationResult.INVALID_FORMAT,
                    error_message=f"不支持的参数类型: {param_type}"
                )

            validation_result = param_range.validate(value)
            if validation_result != ValidationResult.VALID:
                error_msg = self._get_validation_error_message(validation_result, param_range, value)
                return CalculationResult(
                    encoded_value=b'',
                    original_value=value,
                    validation_result=validation_result,
                    error_message=error_msg
                )

            # 2. 编码为DL/T645格式
            encoded_value = self.encode_to_dl645_format(value, param_type)

            # 3. 创建编码信息
            encoding_config = self.encoding_configs[param_type]
            encoding_info = {
                'parameter_type': param_type.value,
                'scale_factor': encoding_config['scale'],
                'byte_count': encoding_config['bytes'],
                'signed': encoding_config['signed'],
                'unit': param_range.unit,
                'scaled_value': int(value * encoding_config['scale'])
            }

            return CalculationResult(
                encoded_value=encoded_value,
                original_value=value,
                validation_result=ValidationResult.VALID,
                encoding_info=encoding_info
            )

        except Exception as e:
            self.logger.error(f"参数计算异常: {e}")
            return CalculationResult(
                encoded_value=b'',
                original_value=value,
                validation_result=ValidationResult.INVALID_FORMAT,
                error_message=f"计算异常: {str(e)}"
            )

    def encode_to_dl645_format(self, physical_value: float, param_type: ParameterType) -> bytes:
        """将物理值编码为DL/T645格式

        Args:
            physical_value: 物理量值
            param_type: 参数类型

        Returns:
            编码后的字节数据
        """
        encoding_config = self.encoding_configs.get(param_type)
        if not encoding_config:
            raise ValueError(f"不支持的参数类型: {param_type}")

        # 缩放处理
        scaled_value = int(round(physical_value * encoding_config['scale']))

        # 范围检查
        if encoding_config['signed']:
            max_value = 2 ** (encoding_config['bytes'] * 8 - 1) - 1
            min_value = -2 ** (encoding_config['bytes'] * 8 - 1)
        else:
            max_value = 2 ** (encoding_config['bytes'] * 8) - 1
            min_value = 0

        if not (min_value <= scaled_value <= max_value):
            raise ValueError(f"编码值超出范围: {scaled_value} not in [{min_value}, {max_value}]")

        # 编码为字节
        return scaled_value.to_bytes(
            encoding_config['bytes'],
            byteorder='little',
            signed=encoding_config['signed']
        )

    def decode_from_dl645_format(self, dl645_data: bytes, param_type: ParameterType) -> float:
        """从DL/T645格式解码为物理值

        Args:
            dl645_data: DL/T645编码数据
            param_type: 参数类型

        Returns:
            物理量值
        """
        encoding_config = self.encoding_configs.get(param_type)
        if not encoding_config:
            raise ValueError(f"不支持的参数类型: {param_type}")

        if len(dl645_data) != encoding_config['bytes']:
            raise ValueError(f"数据长度不匹配: 期望{encoding_config['bytes']}字节, 实际{len(dl645_data)}字节")

        # 解码为整数
        scaled_value = int.from_bytes(
            dl645_data,
            byteorder='little',
            signed=encoding_config['signed']
        )

        # 还原为物理值
        return scaled_value / encoding_config['scale']

    def calculate_error_percentage(self, measured_value: float, standard_value: float) -> float:
        """计算误差百分比

        Args:
            measured_value: 测量值
            standard_value: 标准值

        Returns:
            误差百分比
        """
        if standard_value == 0:
            return 0.0 if measured_value == 0 else float('inf')

        error_percentage = ((measured_value - standard_value) / standard_value) * 100
        return round(error_percentage, 3)

    def validate_calibration_parameters(self, voltage: float, current: float,
                                      frequency: float = 50.0,
                                      phase: float = 0.0) -> Dict[str, Any]:
        """验证校表参数组合

        Args:
            voltage: 电压值
            current: 电流值
            frequency: 频率值
            phase: 相位角

        Returns:
            验证结果字典
        """
        results = {}
        all_valid = True

        # 验证各个参数
        params_to_validate = [
            (voltage, ParameterType.VOLTAGE, "电压"),
            (current, ParameterType.CURRENT, "电流"),
            (frequency, ParameterType.FREQUENCY, "频率"),
            (phase, ParameterType.PHASE, "相位角")
        ]

        for value, param_type, name in params_to_validate:
            param_range = self.parameter_ranges[param_type]
            validation = param_range.validate(value)

            results[name] = {
                'value': value,
                'validation': validation.value,
                'range': f"{param_range.min_value}~{param_range.max_value}{param_range.unit}",
                'valid': validation == ValidationResult.VALID
            }

            if validation != ValidationResult.VALID:
                all_valid = False
                results[name]['error'] = self._get_validation_error_message(
                    validation, param_range, value
                )

        # 计算功率并验证
        power = voltage * current
        power_range = self.parameter_ranges[ParameterType.POWER]
        power_validation = power_range.validate(power)

        results['计算功率'] = {
            'value': power,
            'validation': power_validation.value,
            'range': f"{power_range.min_value}~{power_range.max_value}{power_range.unit}",
            'valid': power_validation == ValidationResult.VALID
        }

        if power_validation != ValidationResult.VALID:
            all_valid = False

        return {
            'all_valid': all_valid,
            'parameter_results': results,
            'summary': f"{'✓ 所有参数有效' if all_valid else '✗ 存在无效参数'}"
        }

    def _get_validation_error_message(self, validation_result: ValidationResult,
                                    param_range: ParameterRange, value: float) -> str:
        """获取验证错误消息"""
        if validation_result == ValidationResult.OUT_OF_RANGE:
            return f"值{value}超出范围[{param_range.min_value}, {param_range.max_value}]{param_range.unit}"
        elif validation_result == ValidationResult.PRECISION_ERROR:
            return f"精度超出限制，最多{param_range.precision_digits}位小数"
        elif validation_result == ValidationResult.INVALID_FORMAT:
            return "无效的数值格式"
        else:
            return "未知验证错误"

    def get_parameter_info(self, param_type: ParameterType) -> Dict[str, Any]:
        """获取参数类型信息

        Args:
            param_type: 参数类型

        Returns:
            参数信息字典
        """
        param_range = self.parameter_ranges.get(param_type)
        encoding_config = self.encoding_configs.get(param_type)

        if not param_range or not encoding_config:
            return {}

        return {
            'type': param_type.value,
            'range': {
                'min': param_range.min_value,
                'max': param_range.max_value,
                'precision': param_range.precision_digits,
                'unit': param_range.unit
            },
            'encoding': {
                'scale_factor': encoding_config['scale'],
                'byte_count': encoding_config['bytes'],
                'signed': encoding_config['signed']
            }
        }


if __name__ == "__main__":
    # 测试参数计算引擎
    print("=== 参数计算引擎测试 ===\n")

    calculator = ParameterCalculator()

    # 测试1: 标准参数计算
    print("1. 标准参数计算:")
    voltage_result = calculator.calculate_voltage_params(220.0)
    current_result = calculator.calculate_current_params(1.0)
    power_result = calculator.calculate_power_params(220.0, 1.0, 1.0)

    print(f"电压编码: {voltage_result.to_dict()}")
    print(f"电流编码: {current_result.to_dict()}")
    print(f"功率编码: {power_result.to_dict()}")

    # 测试2: 参数验证
    print("\n2. 参数验证:")
    validation = calculator.validate_calibration_parameters(220.0, 1.0, 50.0, 0.0)
    print(f"验证结果: {validation['summary']}")
    for param, result in validation['parameter_results'].items():
        status = "✓" if result['valid'] else "✗"
        print(f"  {status} {param}: {result['value']}{result.get('error', '')}")

    # 测试3: 编码解码
    print("\n3. 编码解码测试:")
    test_voltage = 220.0
    encoded = calculator.encode_to_dl645_format(test_voltage, ParameterType.VOLTAGE)
    decoded = calculator.decode_from_dl645_format(encoded, ParameterType.VOLTAGE)
    print(f"原值: {test_voltage}V")
    print(f"编码: {encoded.hex().upper()}")
    print(f"解码: {decoded}V")
    print(f"误差: {calculator.calculate_error_percentage(decoded, test_voltage)}%")

    # 测试4: 参数范围
    print("\n4. 参数类型信息:")
    for param_type in ParameterType:
        info = calculator.get_parameter_info(param_type)
        if info:
            range_info = info['range']
            encoding_info = info['encoding']
            print(f"{param_type.value}: {range_info['min']}~{range_info['max']}{range_info['unit']}, "
                  f"缩放x{encoding_info['scale_factor']}, {encoding_info['byte_count']}字节")

    print("\n=== 参数计算引擎测试完成 ===")