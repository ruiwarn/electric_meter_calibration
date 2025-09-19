#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
串口配置对话框
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QSpinBox, QPushButton,
    QGroupBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt
from core.serial_port import SerialConfig, SerialPort


class SerialConfigDialog(QDialog):
    """串口配置对话框"""

    def __init__(self, parent=None, current_config=None):
        super().__init__(parent)
        self.config = current_config or SerialConfig()
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("串口配置")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # 基本参数组
        basic_group = QGroupBox("基本参数")
        basic_layout = QGridLayout(basic_group)

        # 端口选择
        basic_layout.addWidget(QLabel("端口:"), 0, 0)
        self.port_combo = QComboBox()
        self.refresh_ports()
        basic_layout.addWidget(self.port_combo, 0, 1)

        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_ports)
        basic_layout.addWidget(refresh_btn, 0, 2)

        # 波特率
        basic_layout.addWidget(QLabel("波特率:"), 1, 0)
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["2400", "4800", "9600", "19200", "38400"])
        self.baudrate_combo.setEditable(True)
        basic_layout.addWidget(self.baudrate_combo, 1, 1)

        # 数据位
        basic_layout.addWidget(QLabel("数据位:"), 2, 0)
        self.bytesize_combo = QComboBox()
        self.bytesize_combo.addItems(["7", "8"])
        basic_layout.addWidget(self.bytesize_combo, 2, 1)

        # 校验位
        basic_layout.addWidget(QLabel("校验位:"), 3, 0)
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd"])
        basic_layout.addWidget(self.parity_combo, 3, 1)

        # 停止位
        basic_layout.addWidget(QLabel("停止位:"), 4, 0)
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "2"])
        basic_layout.addWidget(self.stopbits_combo, 4, 1)

        layout.addWidget(basic_group)

        # 高级参数组
        advanced_group = QGroupBox("高级参数")
        advanced_layout = QGridLayout(advanced_group)

        # 读超时
        advanced_layout.addWidget(QLabel("读超时(ms):"), 0, 0)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(100, 10000)
        self.timeout_spin.setSuffix(" ms")
        advanced_layout.addWidget(self.timeout_spin, 0, 1)

        # 写超时
        advanced_layout.addWidget(QLabel("写超时(ms):"), 1, 0)
        self.write_timeout_spin = QSpinBox()
        self.write_timeout_spin.setRange(100, 5000)
        self.write_timeout_spin.setSuffix(" ms")
        advanced_layout.addWidget(self.write_timeout_spin, 1, 1)

        # 重试次数
        advanced_layout.addWidget(QLabel("重试次数:"), 2, 0)
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        advanced_layout.addWidget(self.retry_spin, 2, 1)

        # 帧间隔
        advanced_layout.addWidget(QLabel("帧间隔(ms):"), 3, 0)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(0, 2000)
        self.interval_spin.setSuffix(" ms")
        advanced_layout.addWidget(self.interval_spin, 3, 1)

        layout.addWidget(advanced_group)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def refresh_ports(self):
        """刷新端口列表"""
        sp = SerialPort()
        ports = sp.get_available_ports()

        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(ports)

        # 恢复之前选择的端口
        if current_port in ports:
            self.port_combo.setCurrentText(current_port)

    def load_config(self):
        """加载配置到界面"""
        self.port_combo.setCurrentText(self.config.port)
        self.baudrate_combo.setCurrentText(str(self.config.baudrate))
        self.bytesize_combo.setCurrentText(str(self.config.bytesize))

        parity_map = {'N': 'None', 'E': 'Even', 'O': 'Odd'}
        self.parity_combo.setCurrentText(parity_map.get(self.config.parity, 'None'))

        self.stopbits_combo.setCurrentText(str(self.config.stopbits))
        self.timeout_spin.setValue(int(self.config.timeout * 1000))
        self.write_timeout_spin.setValue(int(self.config.write_timeout * 1000))
        self.retry_spin.setValue(self.config.retry_count)
        self.interval_spin.setValue(int(self.config.frame_interval * 1000))

    def get_config(self):
        """获取配置"""
        config = SerialConfig()
        config.port = self.port_combo.currentText()
        config.baudrate = int(self.baudrate_combo.currentText())
        config.bytesize = int(self.bytesize_combo.currentText())

        parity_map = {'None': 'N', 'Even': 'E', 'Odd': 'O'}
        config.parity = parity_map.get(self.parity_combo.currentText(), 'N')

        config.stopbits = int(self.stopbits_combo.currentText())
        config.timeout = self.timeout_spin.value() / 1000.0
        config.write_timeout = self.write_timeout_spin.value() / 1000.0
        config.retry_count = self.retry_spin.value()
        config.frame_interval = self.interval_spin.value() / 1000.0

        return config