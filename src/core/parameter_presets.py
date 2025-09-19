#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参数预设系统 - M4阶段
提供常用参数组合的预设和快速切换功能
支持内置预设和用户自定义预设
"""

import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from datetime import datetime


@dataclass
class ParameterPreset:
    """参数预设"""
    preset_id: str                        # 预设ID
    name: str                            # 预设名称
    description: str                     # 描述
    is_builtin: bool = False             # 是否为内置预设
    created_time: str = ""               # 创建时间

    # 标准值参数
    standard_voltage: float = 220.0      # 标准电压(V)
    standard_current: float = 1.0        # 标准电流(A)
    standard_frequency: float = 50.0     # 标准频率(Hz)
    standard_power_factor: float = 1.0   # 功率因数
    standard_phase_angle: float = 0.0    # 相位角(度)

    # 校表阈值参数
    no_load_threshold: float = 0.001     # 空载电流阈值(A)
    small_current_threshold: float = 0.05 # 小电流阈值(A)

    # 通信参数
    communication_timeout: int = 3000    # 通信超时(ms)
    max_retries: int = 3                 # 最大重试次数
    retry_delay: int = 500               # 重试延时(ms)

    # 执行选项
    selected_steps: List[int] = None     # 默认选中的步骤
    auto_retry_failed: bool = True       # 失败自动重试
    step_delay: int = 500                # 步骤间延时(ms)

    def __post_init__(self):
        if self.selected_steps is None:
            self.selected_steps = [1, 2, 3, 4, 5]  # 默认全选
        if not self.created_time:
            self.created_time = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ParameterPreset':
        """从字典创建预设"""
        return cls(**data)


class ParameterPresets:
    """参数预设管理器

    特性:
    - 内置常用参数组合
    - 用户自定义预设
    - 预设验证和快速切换
    - JSON文件存储
    """

    def __init__(self, presets_dir: str = "presets"):
        """初始化参数预设管理器

        Args:
            presets_dir: 预设文件目录
        """
        self.presets_dir = Path(presets_dir)
        self.presets_dir.mkdir(exist_ok=True)

        self.presets_file = self.presets_dir / "parameter_presets.json"
        self.logger = logging.getLogger("ParameterPresets")

        # 预设存储
        self.presets: Dict[str, ParameterPreset] = {}

        # 初始化预设
        self._init_builtin_presets()
        self.load_presets()

    def _init_builtin_presets(self):
        """初始化内置预设"""
        builtin_presets = [
            ParameterPreset(
                preset_id="default_220v_1a",
                name="标准220V/1A",
                description="标准单相电表校表参数：220V/1A/50Hz",
                is_builtin=True,
                standard_voltage=220.0,
                standard_current=1.0,
                standard_frequency=50.0,
                standard_power_factor=1.0,
                selected_steps=[1, 2, 3, 4, 5]
            ),

            ParameterPreset(
                preset_id="low_current_220v",
                name="小电流220V/0.1A",
                description="小电流校表参数：220V/0.1A",
                is_builtin=True,
                standard_voltage=220.0,
                standard_current=0.1,
                standard_frequency=50.0,
                small_current_threshold=0.01,
                selected_steps=[1, 5]  # 只校正空载和小电流
            ),

            ParameterPreset(
                preset_id="high_current_220v",
                name="大电流220V/10A",
                description="大电流校表参数：220V/10A",
                is_builtin=True,
                standard_voltage=220.0,
                standard_current=10.0,
                standard_frequency=50.0,
                selected_steps=[2, 3, 4]  # 跳过空载和小电流校正
            ),

            ParameterPreset(
                preset_id="three_phase_380v",
                name="三相380V/1A",
                description="三相电表校表参数：380V/1A/50Hz",
                is_builtin=True,
                standard_voltage=380.0,
                standard_current=1.0,
                standard_frequency=50.0,
                standard_power_factor=0.8,  # 通常三相负载功率因数
                selected_steps=[1, 2, 3, 4, 5]
            ),

            ParameterPreset(
                preset_id="fast_calibration",
                name="快速校表",
                description="快速校表模式，仅校正关键项目",
                is_builtin=True,
                standard_voltage=220.0,
                standard_current=1.0,
                selected_steps=[1, 2, 3],  # 只校正基本项目
                communication_timeout=2000,  # 更短的超时时间
                step_delay=200  # 更快的步骤切换
            ),

            ParameterPreset(
                preset_id="precision_mode",
                name="精密校表模式",
                description="高精度校表，包含所有校正项目",
                is_builtin=True,
                standard_voltage=220.0,
                standard_current=1.0,
                selected_steps=[1, 2, 3, 4, 5],
                communication_timeout=5000,  # 更长的超时时间
                max_retries=5,  # 更多重试次数
                step_delay=1000  # 更多等待时间确保精度
            ),

            ParameterPreset(
                preset_id="production_line",
                name="产线校表",
                description="产线批量校表优化参数",
                is_builtin=True,
                standard_voltage=220.0,
                standard_current=1.0,
                selected_steps=[1, 2, 3],  # 关键校正项目
                communication_timeout=3000,
                step_delay=500,
                auto_retry_failed=False  # 产线模式不自动重试，提高效率
            )
        ]

        for preset in builtin_presets:
            self.presets[preset.preset_id] = preset

    def load_presets(self) -> bool:
        """加载用户自定义预设

        Returns:
            是否加载成功
        """
        try:
            if self.presets_file.exists():
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    presets_data = json.load(f)

                # 加载用户预设（不覆盖内置预设）
                for preset_id, preset_data in presets_data.items():
                    if not preset_data.get('is_builtin', False):
                        preset = ParameterPreset.from_dict(preset_data)
                        self.presets[preset_id] = preset

                self.logger.info(f"加载用户预设: {len(presets_data)}个")
                return True

        except Exception as e:
            self.logger.error(f"加载预设文件失败: {e}")

        return False

    def save_presets(self) -> bool:
        """保存用户自定义预设

        Returns:
            是否保存成功
        """
        try:
            # 只保存用户自定义预设
            user_presets = {
                preset_id: preset.to_dict()
                for preset_id, preset in self.presets.items()
                if not preset.is_builtin
            }

            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(user_presets, f, indent=2, ensure_ascii=False)

            self.logger.info(f"保存用户预设: {len(user_presets)}个")
            return True

        except Exception as e:
            self.logger.error(f"保存预设文件失败: {e}")
            return False

    def get_preset_list(self, include_builtin: bool = True) -> List[Dict[str, Any]]:
        """获取预设列表

        Args:
            include_builtin: 是否包含内置预设

        Returns:
            预设信息列表
        """
        preset_list = []

        for preset in self.presets.values():
            if not include_builtin and preset.is_builtin:
                continue

            preset_list.append({
                'preset_id': preset.preset_id,
                'name': preset.name,
                'description': preset.description,
                'is_builtin': preset.is_builtin,
                'created_time': preset.created_time,
                'standard_voltage': preset.standard_voltage,
                'standard_current': preset.standard_current,
                'selected_steps': preset.selected_steps
            })

        # 按名称排序，内置预设在前
        preset_list.sort(key=lambda x: (not x['is_builtin'], x['name']))
        return preset_list

    def get_preset(self, preset_id: str) -> Optional[ParameterPreset]:
        """获取指定预设

        Args:
            preset_id: 预设ID

        Returns:
            预设对象或None
        """
        return self.presets.get(preset_id)

    def save_preset(self, name: str, description: str, parameters: Dict[str, Any],
                   preset_id: Optional[str] = None) -> str:
        """保存参数预设

        Args:
            name: 预设名称
            description: 预设描述
            parameters: 参数字典
            preset_id: 预设ID（可选，用于更新现有预设）

        Returns:
            预设ID
        """
        if preset_id is None:
            # 生成新的预设ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            preset_id = f"user_{timestamp}"

        # 检查是否为内置预设
        existing_preset = self.presets.get(preset_id)
        if existing_preset and existing_preset.is_builtin:
            raise ValueError("不能修改内置预设")

        # 创建预设对象
        preset_data = {
            'preset_id': preset_id,
            'name': name,
            'description': description,
            'is_builtin': False,
            **parameters
        }

        preset = ParameterPreset.from_dict(preset_data)

        # 验证预设
        validation_result = self.validate_preset(preset)
        if not validation_result['is_valid']:
            raise ValueError(f"预设验证失败: {validation_result['errors']}")

        # 保存预设
        self.presets[preset_id] = preset
        self.save_presets()

        self.logger.info(f"保存预设: {name} ({preset_id})")
        return preset_id

    def delete_preset(self, preset_id: str) -> bool:
        """删除预设

        Args:
            preset_id: 预设ID

        Returns:
            是否删除成功
        """
        preset = self.presets.get(preset_id)
        if not preset:
            self.logger.warning(f"预设不存在: {preset_id}")
            return False

        if preset.is_builtin:
            self.logger.error(f"不能删除内置预设: {preset_id}")
            return False

        del self.presets[preset_id]
        self.save_presets()

        self.logger.info(f"删除预设: {preset.name} ({preset_id})")
        return True

    def apply_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """应用预设参数

        Args:
            preset_id: 预设ID

        Returns:
            参数字典或None
        """
        preset = self.presets.get(preset_id)
        if not preset:
            self.logger.error(f"预设不存在: {preset_id}")
            return None

        # 转换为参数字典
        parameters = {
            # 标准值参数
            'standard_values': {
                'standard_voltage': preset.standard_voltage,
                'standard_current': preset.standard_current,
                'standard_frequency': preset.standard_frequency,
                'standard_power_factor': preset.standard_power_factor,
                'standard_phase_angle': preset.standard_phase_angle,
                'no_load_threshold': preset.no_load_threshold,
                'small_current_threshold': preset.small_current_threshold
            },

            # 通信参数
            'communication_config': {
                'timeout': preset.communication_timeout,
                'max_retries': preset.max_retries,
                'retry_delay': preset.retry_delay
            },

            # 执行选项
            'execution_config': {
                'selected_steps': preset.selected_steps,
                'auto_retry_failed': preset.auto_retry_failed,
                'step_delay': preset.step_delay
            }
        }

        self.logger.info(f"应用预设: {preset.name} ({preset_id})")
        return parameters

    def validate_preset(self, preset: ParameterPreset) -> Dict[str, Any]:
        """验证预设参数

        Args:
            preset: 预设对象

        Returns:
            验证结果字典
        """
        errors = []

        # 验证电压范围
        if not (50.0 <= preset.standard_voltage <= 500.0):
            errors.append("标准电压超出范围(50-500V)")

        # 验证电流范围
        if not (0.001 <= preset.standard_current <= 200.0):
            errors.append("标准电流超出范围(0.001-200A)")

        # 验证频率范围
        if not (45.0 <= preset.standard_frequency <= 65.0):
            errors.append("标准频率超出范围(45-65Hz)")

        # 验证功率因数
        if not (0.0 <= preset.standard_power_factor <= 1.0):
            errors.append("功率因数超出范围(0.0-1.0)")

        # 验证相位角
        if not (-180.0 <= preset.standard_phase_angle <= 180.0):
            errors.append("相位角超出范围(-180到180度)")

        # 验证步骤选择
        if not preset.selected_steps or not all(1 <= step <= 5 for step in preset.selected_steps):
            errors.append("选中的步骤无效(必须是1-5之间的数字)")

        # 验证通信参数
        if preset.communication_timeout < 1000:
            errors.append("通信超时时间过短(最少1000ms)")

        if preset.max_retries < 0:
            errors.append("最大重试次数不能为负数")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }

    def export_preset(self, preset_id: str, export_path: str) -> bool:
        """导出预设到文件

        Args:
            preset_id: 预设ID
            export_path: 导出文件路径

        Returns:
            是否导出成功
        """
        preset = self.presets.get(preset_id)
        if not preset:
            self.logger.error(f"预设不存在: {preset_id}")
            return False

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(preset.to_dict(), f, indent=2, ensure_ascii=False)

            self.logger.info(f"预设导出成功: {export_path}")
            return True

        except Exception as e:
            self.logger.error(f"预设导出失败: {e}")
            return False

    def import_preset(self, import_path: str, new_name: Optional[str] = None) -> Optional[str]:
        """从文件导入预设

        Args:
            import_path: 导入文件路径
            new_name: 新预设名称（可选）

        Returns:
            导入的预设ID或None
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)

            # 创建预设对象
            preset = ParameterPreset.from_dict(preset_data)

            # 生成新的预设ID（避免冲突）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_preset_id = f"imported_{timestamp}"
            preset.preset_id = new_preset_id
            preset.is_builtin = False

            if new_name:
                preset.name = new_name

            # 验证预设
            validation_result = self.validate_preset(preset)
            if not validation_result['is_valid']:
                self.logger.error(f"预设验证失败: {validation_result['errors']}")
                return None

            # 保存预设
            self.presets[new_preset_id] = preset
            self.save_presets()

            self.logger.info(f"预设导入成功: {preset.name} ({new_preset_id})")
            return new_preset_id

        except Exception as e:
            self.logger.error(f"预设导入失败: {e}")
            return None

    def get_preset_summary(self) -> Dict[str, Any]:
        """获取预设摘要信息

        Returns:
            摘要信息字典
        """
        builtin_count = len([p for p in self.presets.values() if p.is_builtin])
        user_count = len([p for p in self.presets.values() if not p.is_builtin])

        return {
            'total_presets': len(self.presets),
            'builtin_presets': builtin_count,
            'user_presets': user_count,
            'preset_categories': {
                'standard': len([p for p in self.presets.values() if '220V' in p.name]),
                'low_current': len([p for p in self.presets.values() if '小电流' in p.name or '0.1A' in p.name]),
                'high_current': len([p for p in self.presets.values() if '大电流' in p.name or '10A' in p.name]),
                'three_phase': len([p for p in self.presets.values() if '三相' in p.name or '380V' in p.name])
            }
        }


if __name__ == "__main__":
    # 测试参数预设系统
    print("=== 参数预设系统测试 ===\n")

    # 创建预设管理器
    presets_manager = ParameterPresets("test_presets")

    # 获取预设列表
    preset_list = presets_manager.get_preset_list()
    print(f"1. 可用预设数量: {len(preset_list)}")
    for preset in preset_list:
        print(f"   - {preset['name']}: {preset['description']} ({'内置' if preset['is_builtin'] else '用户自定义'})")

    # 应用预设
    print(f"\n2. 应用标准预设:")
    params = presets_manager.apply_preset("default_220v_1a")
    if params:
        print(f"   标准电压: {params['standard_values']['standard_voltage']}V")
        print(f"   标准电流: {params['standard_values']['standard_current']}A")
        print(f"   选中步骤: {params['execution_config']['selected_steps']}")

    # 创建用户预设
    print(f"\n3. 创建用户预设:")
    custom_params = {
        'standard_voltage': 110.0,
        'standard_current': 0.5,
        'selected_steps': [1, 2, 3],
        'communication_timeout': 4000
    }

    try:
        custom_preset_id = presets_manager.save_preset(
            "自定义110V预设",
            "用于110V系统的校表参数",
            custom_params
        )
        print(f"   创建成功，预设ID: {custom_preset_id}")
    except Exception as e:
        print(f"   创建失败: {e}")

    # 获取预设摘要
    print(f"\n4. 预设摘要:")
    summary = presets_manager.get_preset_summary()
    print(f"   总预设数: {summary['total_presets']}")
    print(f"   内置预设: {summary['builtin_presets']}")
    print(f"   用户预设: {summary['user_presets']}")
    print(f"   分类统计: {summary['preset_categories']}")

    print("\n=== 参数预设系统测试完成 ===")