#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标准值输入对话框
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QDoubleSpinBox, QCheckBox, QPushButton,
    QGroupBox, QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class StandardValuesConfig:
    """标准值配置类"""
    def __init__(self):
        self.standard_voltage = 220.0      # 标准电压(V)
        self.standard_current = 64.0       # 标准电流(A)
        self.power_error = 0.0            # 功率误差(%)
        self.error_mode_enabled = False    # 误差校准模式

    def is_valid(self):
        """验证配置有效性"""
        errors = []

        if not (90 <= self.standard_voltage <= 300):
            errors.append("标准电压必须在90-300V范围内")

        if not (0 <= self.standard_current <= 200):
            errors.append("标准电流必须在0-200A范围内")

        if not (-10 <= self.power_error <= 10):
            errors.append("功率误差必须在±10%范围内")

        return len(errors) == 0, errors

    def to_dict(self):
        """转换为字典"""
        return {
            'standard_voltage': self.standard_voltage,
            'standard_current': self.standard_current,
            'power_error': self.power_error,
            'error_mode_enabled': self.error_mode_enabled
        }

    def from_dict(self, data):
        """从字典加载"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def get_summary(self):
        """获取摘要字符串"""
        if self.error_mode_enabled:
            return f"U={self.standard_voltage}V, I={self.standard_current}A, 误差={self.power_error}%"
        else:
            return f"U={self.standard_voltage}V, I={self.standard_current}A"


class StandardValuesDialog(QDialog):
    """标准值输入对话框"""

    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.config = current_config or StandardValuesConfig()
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("标准值输入")
        self.setModal(True)
        self.resize(400, 250)

        layout = QVBoxLayout(self)

        # 标准值输入组
        values_group = QGroupBox("标准值设置")
        values_layout = QGridLayout(values_group)

        # 标准电压
        values_layout.addWidget(QLabel("标准电压:"), 0, 0)
        self.voltage_spin = QDoubleSpinBox()
        self.voltage_spin.setRange(90.0, 300.0)
        self.voltage_spin.setDecimals(1)
        self.voltage_spin.setSuffix(" V")
        self.voltage_spin.valueChanged.connect(self.validate_values)
        values_layout.addWidget(self.voltage_spin, 0, 1)

        voltage_note = QLabel("(范围: 90-300V)")
        voltage_note.setStyleSheet("color: gray; font-size: 10px;")
        values_layout.addWidget(voltage_note, 0, 2)

        # 标准电流
        values_layout.addWidget(QLabel("标准电流:"), 1, 0)
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0.0, 200.0)
        self.current_spin.setDecimals(1)
        self.current_spin.setSuffix(" A")
        self.current_spin.valueChanged.connect(self.validate_values)
        values_layout.addWidget(self.current_spin, 1, 1)

        current_note = QLabel("(范围: 0-200A)")
        current_note.setStyleSheet("color: gray; font-size: 10px;")
        values_layout.addWidget(current_note, 1, 2)

        layout.addWidget(values_group)

        # 误差校准模式组
        error_group = QGroupBox("误差校准模式")
        error_layout = QVBoxLayout(error_group)

        self.error_mode_check = QCheckBox("启用误差校准模式")
        self.error_mode_check.toggled.connect(self.on_error_mode_toggled)
        error_layout.addWidget(self.error_mode_check)

        # 功率误差输入
        error_input_layout = QHBoxLayout()
        error_input_layout.addWidget(QLabel("功率误差:"))

        self.power_error_spin = QDoubleSpinBox()
        self.power_error_spin.setRange(-10.0, 10.0)
        self.power_error_spin.setDecimals(2)
        self.power_error_spin.setSuffix(" %")
        self.power_error_spin.valueChanged.connect(self.validate_values)
        error_input_layout.addWidget(self.power_error_spin)

        error_note = QLabel("(范围: ±10%)")
        error_note.setStyleSheet("color: gray; font-size: 10px;")
        error_input_layout.addWidget(error_note)

        error_input_layout.addStretch()
        error_layout.addLayout(error_input_layout)

        layout.addWidget(error_group)

        # 验证提示标签
        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: red; font-weight: bold;")
        self.validation_label.hide()
        layout.addWidget(self.validation_label)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 初始状态
        self.on_error_mode_toggled(False)

    def on_error_mode_toggled(self, enabled):
        """误差模式切换"""
        self.power_error_spin.setEnabled(enabled)
        if not enabled:
            self.power_error_spin.setValue(0.0)

    def validate_values(self):
        """验证输入值"""
        temp_config = StandardValuesConfig()
        temp_config.standard_voltage = self.voltage_spin.value()
        temp_config.standard_current = self.current_spin.value()
        temp_config.power_error = self.power_error_spin.value()
        temp_config.error_mode_enabled = self.error_mode_check.isChecked()

        is_valid, errors = temp_config.is_valid()

        if is_valid:
            self.validation_label.hide()
            self.ok_button.setEnabled(True)
        else:
            self.validation_label.setText("\\n".join(errors))
            self.validation_label.show()
            self.ok_button.setEnabled(False)

    def load_config(self):
        """加载配置到界面"""
        self.voltage_spin.setValue(self.config.standard_voltage)
        self.current_spin.setValue(self.config.standard_current)
        self.power_error_spin.setValue(self.config.power_error)
        self.error_mode_check.setChecked(self.config.error_mode_enabled)

        self.validate_values()

    def get_config(self):
        """获取配置"""
        config = StandardValuesConfig()
        config.standard_voltage = self.voltage_spin.value()
        config.standard_current = self.current_spin.value()
        config.power_error = self.power_error_spin.value()
        config.error_mode_enabled = self.error_mode_check.isChecked()

        return config

    def accept(self):
        """确认按钮处理"""
        config = self.get_config()
        is_valid, errors = config.is_valid()

        if not is_valid:
            QMessageBox.warning(self, "输入错误", "\\n".join(errors))
            return

        super().accept()