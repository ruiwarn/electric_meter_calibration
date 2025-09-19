#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量级配置管理器 - M4阶段
基于JSON文件的配置持久化，无数据库依赖
支持版本管理、默认配置和导入导出功能
"""

import json
import os
import shutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from pathlib import Path


@dataclass
class AppConfig:
    """应用配置数据结构"""
    # 版本信息
    config_version: str = "1.0.0"
    last_updated: str = ""

    # 串口配置
    serial_port: str = "COM1"
    serial_baudrate: int = 9600
    serial_databits: int = 8
    serial_parity: str = "E"  # E/O/N
    serial_stopbits: int = 1
    serial_timeout: float = 3.0

    # 标准值配置
    standard_voltage: float = 220.0
    standard_current: float = 1.0
    standard_frequency: float = 50.0
    standard_power_factor: float = 1.0
    standard_phase_angle: float = 0.0

    # 校表参数
    no_load_threshold: float = 0.001
    small_current_threshold: float = 0.05

    # 用户界面偏好
    window_geometry: str = ""  # 主窗口几何信息
    splitter_sizes: List[int] = None
    selected_steps: List[int] = None  # 默认选中的步骤
    log_level: str = "INFO"
    auto_save_session: bool = True

    # 通信设置
    communication_timeout: int = 3000
    max_retries: int = 3
    retry_delay: int = 500

    def __post_init__(self):
        if self.splitter_sizes is None:
            self.splitter_sizes = [400, 600]
        if self.selected_steps is None:
            self.selected_steps = [1, 2, 3, 4, 5]  # 默认全选
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


class ConfigManager:
    """轻量级配置管理器

    特性:
    - JSON文件存储，人可读
    - 版本管理和兼容性检查
    - 默认配置和恢复机制
    - 配置备份和导入导出
    """

    def __init__(self, config_dir: str = "config"):
        """初始化配置管理器

        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "app_config.json"
        self.backup_dir = self.config_dir / "backups"

        self.logger = logging.getLogger("ConfigManager")

        # 确保配置目录存在
        self.config_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)

        # 当前配置
        self.current_config = AppConfig()

        # 加载配置
        self.load_config()

    def load_config(self) -> AppConfig:
        """加载配置文件

        Returns:
            应用配置对象
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_dict = json.load(f)

                # 检查配置版本
                config_version = config_dict.get('config_version', '1.0.0')
                if self._is_compatible_version(config_version):
                    # 兼容版本，直接加载
                    self.current_config = AppConfig(**config_dict)
                    self.logger.info(f"配置加载成功: {self.config_file}")
                else:
                    # 版本不兼容，需要迁移
                    self.logger.warning(f"配置版本不兼容: {config_version} -> {AppConfig().config_version}")
                    migrated_config = self._migrate_config(config_dict, config_version)
                    self.current_config = AppConfig(**migrated_config)
                    # 立即保存迁移后的配置
                    self.save_config()
            else:
                # 配置文件不存在，创建默认配置
                self.logger.info("配置文件不存在，创建默认配置")
                self.current_config = AppConfig()
                self.save_config()

        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            # 加载失败时使用默认配置
            self.current_config = AppConfig()
            # 尝试创建备份
            self._create_error_backup()

        return self.current_config

    def save_config(self) -> bool:
        """保存配置文件

        Returns:
            是否保存成功
        """
        try:
            # 更新时间戳
            self.current_config.last_updated = datetime.now().isoformat()

            # 创建备份 (如果配置文件已存在)
            if self.config_file.exists():
                self._create_backup()

            # 保存配置
            config_dict = asdict(self.current_config)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)

            self.logger.info(f"配置保存成功: {self.config_file}")
            return True

        except Exception as e:
            self.logger.error(f"配置保存失败: {e}")
            return False

    def get_serial_config(self) -> Dict[str, Any]:
        """获取串口配置

        Returns:
            串口配置字典
        """
        return {
            'port': self.current_config.serial_port,
            'baudrate': self.current_config.serial_baudrate,
            'databits': self.current_config.serial_databits,
            'parity': self.current_config.serial_parity,
            'stopbits': self.current_config.serial_stopbits,
            'timeout': self.current_config.serial_timeout
        }

    def save_serial_config(self, config: Dict[str, Any]) -> bool:
        """保存串口配置

        Args:
            config: 串口配置字典

        Returns:
            是否保存成功
        """
        try:
            self.current_config.serial_port = config.get('port', 'COM1')
            self.current_config.serial_baudrate = config.get('baudrate', 9600)
            self.current_config.serial_databits = config.get('databits', 8)
            self.current_config.serial_parity = config.get('parity', 'E')
            self.current_config.serial_stopbits = config.get('stopbits', 1)
            self.current_config.serial_timeout = config.get('timeout', 3.0)

            return self.save_config()
        except Exception as e:
            self.logger.error(f"串口配置保存失败: {e}")
            return False

    def get_standard_values(self) -> Dict[str, Any]:
        """获取标准值配置

        Returns:
            标准值配置字典
        """
        return {
            'standard_voltage': self.current_config.standard_voltage,
            'standard_current': self.current_config.standard_current,
            'standard_frequency': self.current_config.standard_frequency,
            'standard_power_factor': self.current_config.standard_power_factor,
            'standard_phase_angle': self.current_config.standard_phase_angle,
            'no_load_threshold': self.current_config.no_load_threshold,
            'small_current_threshold': self.current_config.small_current_threshold
        }

    def save_standard_values(self, values: Dict[str, Any]) -> bool:
        """保存标准值配置

        Args:
            values: 标准值配置字典

        Returns:
            是否保存成功
        """
        try:
            self.current_config.standard_voltage = values.get('standard_voltage', 220.0)
            self.current_config.standard_current = values.get('standard_current', 1.0)
            self.current_config.standard_frequency = values.get('standard_frequency', 50.0)
            self.current_config.standard_power_factor = values.get('standard_power_factor', 1.0)
            self.current_config.standard_phase_angle = values.get('standard_phase_angle', 0.0)
            self.current_config.no_load_threshold = values.get('no_load_threshold', 0.001)
            self.current_config.small_current_threshold = values.get('small_current_threshold', 0.05)

            return self.save_config()
        except Exception as e:
            self.logger.error(f"标准值配置保存失败: {e}")
            return False

    def get_ui_preferences(self) -> Dict[str, Any]:
        """获取用户界面偏好

        Returns:
            UI偏好配置字典
        """
        return {
            'window_geometry': self.current_config.window_geometry,
            'splitter_sizes': self.current_config.splitter_sizes,
            'selected_steps': self.current_config.selected_steps,
            'log_level': self.current_config.log_level,
            'auto_save_session': self.current_config.auto_save_session
        }

    def save_ui_preferences(self, preferences: Dict[str, Any]) -> bool:
        """保存用户界面偏好

        Args:
            preferences: UI偏好配置字典

        Returns:
            是否保存成功
        """
        try:
            if 'window_geometry' in preferences:
                self.current_config.window_geometry = preferences['window_geometry']
            if 'splitter_sizes' in preferences:
                self.current_config.splitter_sizes = preferences['splitter_sizes']
            if 'selected_steps' in preferences:
                self.current_config.selected_steps = preferences['selected_steps']
            if 'log_level' in preferences:
                self.current_config.log_level = preferences['log_level']
            if 'auto_save_session' in preferences:
                self.current_config.auto_save_session = preferences['auto_save_session']

            return self.save_config()
        except Exception as e:
            self.logger.error(f"UI偏好保存失败: {e}")
            return False

    def get_communication_config(self) -> Dict[str, Any]:
        """获取通信配置

        Returns:
            通信配置字典
        """
        return {
            'timeout': self.current_config.communication_timeout,
            'max_retries': self.current_config.max_retries,
            'retry_delay': self.current_config.retry_delay
        }

    def save_communication_config(self, config: Dict[str, Any]) -> bool:
        """保存通信配置

        Args:
            config: 通信配置字典

        Returns:
            是否保存成功
        """
        try:
            self.current_config.communication_timeout = config.get('timeout', 3000)
            self.current_config.max_retries = config.get('max_retries', 3)
            self.current_config.retry_delay = config.get('retry_delay', 500)

            return self.save_config()
        except Exception as e:
            self.logger.error(f"通信配置保存失败: {e}")
            return False

    def export_config(self, export_path: str) -> bool:
        """导出配置文件

        Args:
            export_path: 导出文件路径

        Returns:
            是否导出成功
        """
        try:
            shutil.copy2(self.config_file, export_path)
            self.logger.info(f"配置导出成功: {export_path}")
            return True
        except Exception as e:
            self.logger.error(f"配置导出失败: {e}")
            return False

    def import_config(self, import_path: str) -> bool:
        """导入配置文件

        Args:
            import_path: 导入文件路径

        Returns:
            是否导入成功
        """
        try:
            # 验证导入文件
            with open(import_path, 'r', encoding='utf-8') as f:
                import_dict = json.load(f)

            # 检查版本兼容性
            import_version = import_dict.get('config_version', '1.0.0')
            if not self._is_compatible_version(import_version):
                self.logger.warning(f"导入配置版本不兼容: {import_version}")
                return False

            # 创建备份
            self._create_backup()

            # 导入配置
            shutil.copy2(import_path, self.config_file)

            # 重新加载
            self.load_config()

            self.logger.info(f"配置导入成功: {import_path}")
            return True

        except Exception as e:
            self.logger.error(f"配置导入失败: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """重置为默认配置

        Returns:
            是否重置成功
        """
        try:
            # 创建备份
            self._create_backup()

            # 重置配置
            self.current_config = AppConfig()

            return self.save_config()
        except Exception as e:
            self.logger.error(f"配置重置失败: {e}")
            return False

    def get_backup_list(self) -> List[Dict[str, str]]:
        """获取备份文件列表

        Returns:
            备份文件信息列表
        """
        backups = []
        try:
            for backup_file in self.backup_dir.glob("app_config_*.json"):
                file_stat = backup_file.stat()
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'created_time': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    'size': file_stat.st_size
                })

            # 按创建时间排序 (最新的在前)
            backups.sort(key=lambda x: x['created_time'], reverse=True)

        except Exception as e:
            self.logger.error(f"获取备份列表失败: {e}")

        return backups

    def restore_from_backup(self, backup_filename: str) -> bool:
        """从备份恢复配置

        Args:
            backup_filename: 备份文件名

        Returns:
            是否恢复成功
        """
        try:
            backup_path = self.backup_dir / backup_filename
            if not backup_path.exists():
                self.logger.error(f"备份文件不存在: {backup_path}")
                return False

            return self.import_config(str(backup_path))

        except Exception as e:
            self.logger.error(f"备份恢复失败: {e}")
            return False

    def _create_backup(self):
        """创建配置备份"""
        try:
            if self.config_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"app_config_{timestamp}.json"
                backup_path = self.backup_dir / backup_filename

                shutil.copy2(self.config_file, backup_path)
                self.logger.debug(f"配置备份创建: {backup_path}")

                # 清理旧备份 (保留最近10个)
                self._cleanup_old_backups(keep_count=10)

        except Exception as e:
            self.logger.warning(f"配置备份创建失败: {e}")

    def _create_error_backup(self):
        """创建错误配置备份"""
        try:
            if self.config_file.exists():
                error_backup_path = self.backup_dir / "app_config_error.json"
                shutil.copy2(self.config_file, error_backup_path)
                self.logger.info(f"错误配置已备份: {error_backup_path}")
        except Exception as e:
            self.logger.warning(f"错误配置备份失败: {e}")

    def _cleanup_old_backups(self, keep_count: int = 10):
        """清理旧备份文件"""
        try:
            backup_files = list(self.backup_dir.glob("app_config_*.json"))
            if len(backup_files) > keep_count:
                # 按修改时间排序
                backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

                # 删除多余的备份
                for old_backup in backup_files[keep_count:]:
                    old_backup.unlink()
                    self.logger.debug(f"删除旧备份: {old_backup}")

        except Exception as e:
            self.logger.warning(f"清理备份文件失败: {e}")

    def _is_compatible_version(self, version: str) -> bool:
        """检查版本兼容性"""
        # 简单的版本兼容性检查
        try:
            major, minor, patch = version.split('.')
            current_major, current_minor, current_patch = AppConfig().config_version.split('.')

            # 主版本号必须相同
            return major == current_major

        except Exception:
            return False

    def _migrate_config(self, config_dict: Dict[str, Any], from_version: str) -> Dict[str, Any]:
        """配置迁移"""
        self.logger.info(f"开始配置迁移: {from_version} -> {AppConfig().config_version}")

        # 这里可以添加版本特定的迁移逻辑
        migrated_dict = config_dict.copy()

        # 更新版本号
        migrated_dict['config_version'] = AppConfig().config_version
        migrated_dict['last_updated'] = datetime.now().isoformat()

        # 添加缺失的字段 (使用默认值)
        default_config = asdict(AppConfig())
        for key, default_value in default_config.items():
            if key not in migrated_dict:
                migrated_dict[key] = default_value
                self.logger.debug(f"添加缺失字段: {key} = {default_value}")

        return migrated_dict


if __name__ == "__main__":
    # 测试配置管理器
    print("=== 配置管理器测试 ===\n")

    # 设置日志
    logging.basicConfig(level=logging.INFO)

    # 创建配置管理器
    config_manager = ConfigManager("test_config")

    # 测试配置加载和保存
    print("1. 测试基本功能:")
    serial_config = config_manager.get_serial_config()
    print(f"   当前串口配置: {serial_config}")

    standard_values = config_manager.get_standard_values()
    print(f"   当前标准值: {standard_values}")

    # 测试配置修改
    print("\n2. 测试配置修改:")
    config_manager.save_serial_config({'port': 'COM3', 'baudrate': 115200})
    new_serial_config = config_manager.get_serial_config()
    print(f"   修改后串口配置: {new_serial_config}")

    # 测试备份功能
    print("\n3. 测试备份功能:")
    backup_list = config_manager.get_backup_list()
    print(f"   备份文件数量: {len(backup_list)}")
    for backup in backup_list[:3]:  # 显示最近3个备份
        print(f"     - {backup['filename']} ({backup['created_time']})")

    # 测试导出功能
    print("\n4. 测试导出功能:")
    export_success = config_manager.export_config("test_export_config.json")
    print(f"   导出结果: {'成功' if export_success else '失败'}")

    print("\n=== 配置管理器测试完成 ===")