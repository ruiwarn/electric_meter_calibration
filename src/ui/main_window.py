#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RN8213/RN8211B 电表校准工具 v2.0 - 主窗口
基于需求文档实现单页GUI布局
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QGroupBox, QCheckBox, QPushButton, QLabel,
    QTextEdit, QToolBar, QMenuBar, QStatusBar, QAction,
    QFrame, QGridLayout, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

# M3校表执行引擎
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.calibration_step import CalibrationParameters, StepStatus
from core.calibration_executor import CalibrationExecutor, ExecutionConfig, ExecutionMode
from core.device_communicator import DeviceCommunicator, CommunicationConfig
from core.parameter_calculator import ParameterCalculator


class StatusIndicator(QLabel):
    """状态指示灯控件"""
    def __init__(self, size=16):
        super().__init__()
        self.size = size
        self.setFixedSize(size, size)
        self.set_status("gray")  # 默认灰色

    def set_status(self, color):
        """设置状态颜色: green/gray/yellow/red"""
        pixmap = QPixmap(self.size, self.size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        color_map = {
            "green": QColor(0, 255, 0),
            "gray": QColor(128, 128, 128),
            "yellow": QColor(255, 255, 0),
            "red": QColor(255, 0, 0)
        }

        painter.setBrush(color_map.get(color, QColor(128, 128, 128)))
        painter.drawEllipse(2, 2, self.size-4, self.size-4)
        painter.end()

        self.setPixmap(pixmap)


class CalibrationStepWidget(QWidget):
    """校表步骤控件"""
    step_triggered = pyqtSignal(int)  # 步骤执行信号

    def __init__(self, step_id, step_name, step_description):
        super().__init__()
        self.step_id = step_id
        self.step_name = step_name
        self.step_description = step_description
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 第一行：复选框 + 步骤名称 + 执行按钮
        top_layout = QHBoxLayout()

        self.checkbox = QCheckBox(self.step_name)
        self.checkbox.setChecked(True)  # 默认勾选
        top_layout.addWidget(self.checkbox)

        top_layout.addStretch()

        self.exec_button = QPushButton("执行此步")
        self.exec_button.clicked.connect(lambda: self.step_triggered.emit(self.step_id))
        top_layout.addWidget(self.exec_button)

        layout.addLayout(top_layout)

        # 第二行：结果显示区域
        self.result_label = QLabel("等待执行...")
        self.result_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addWidget(self.result_label)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

    def set_result(self, status, message, elapsed_time=None):
        """设置步骤结果"""
        if status == "success":
            icon = "✓"
            color = "green"
        elif status == "error":
            icon = "✗"
            color = "red"
        elif status == "running":
            icon = "⟳"
            color = "blue"
        else:
            icon = "●"
            color = "gray"

        time_str = f" ({elapsed_time}ms)" if elapsed_time else ""
        self.result_label.setText(f"{icon} {message}{time_str}")
        self.result_label.setStyleSheet(f"color: {color}; font-size: 12px;")


class MainWindow(QMainWindow):
    """主窗口类"""

    def __init__(self):
        super().__init__()

        # 基本配置
        from core.serial_port import SerialConfig
        self.serial_config = SerialConfig()  # 默认串口配置
        self.serial_config.port = "COM1"  # 设置默认端口
        self.standard_values = None  # 标准值配置
        self.serial_port = None  # 串口对象

        # M3校表执行引擎组件
        self.calibration_executor = None
        self.device_communicator = None
        self.parameter_calculator = ParameterCalculator()
        self.calibration_params = CalibrationParameters()  # 默认校表参数

        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        self.connect_signals()

    def setup_ui(self):
        """设置UI布局"""
        self.setWindowTitle("RN8213/RN8211B 电表校准工具 v2.0")
        self.setMinimumSize(1000, 700)

        # 中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 创建水平分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # 左侧：步骤清单区域
        self.setup_steps_panel(splitter)

        # 右侧：过程日志区域
        self.setup_log_panel(splitter)

        # 设置分割比例 (40% : 60%)
        splitter.setSizes([400, 600])

    def setup_steps_panel(self, parent):
        """设置左侧步骤面板"""
        steps_group = QGroupBox("校表步骤")
        steps_layout = QVBoxLayout(steps_group)

        # 五大校表步骤
        steps_info = [
            (1, "电流有效值offset校正", "电流有效值offset校正 (空载)"),
            (2, "电压电流增益校正", "1.0L标准电压电流校正"),
            (3, "功率增益校正", "功率增益校正"),
            (4, "相位补偿校正", "相位补偿校正"),
            (5, "小电流偏置校正", "小电流有功偏置校正")
        ]

        self.step_widgets = {}
        for step_id, step_name, step_desc in steps_info:
            step_widget = CalibrationStepWidget(step_id, step_name, step_desc)
            step_widget.step_triggered.connect(self.on_step_execute)
            self.step_widgets[step_id] = step_widget
            steps_layout.addWidget(step_widget)

        steps_layout.addStretch()
        parent.addWidget(steps_group)

    def setup_log_panel(self, parent):
        """设置右侧日志面板"""
        log_group = QGroupBox("通信日志")
        log_layout = QVBoxLayout(log_group)

        # 日志文本区域
        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Consolas", 9))  # 等宽字体
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("通信日志将在此显示...\n格式: Tx> / Rx> + 十六进制帧数据")
        log_layout.addWidget(self.log_text)

        parent.addWidget(log_group)

    def setup_menus(self):
        """设置菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        load_template_action = QAction("载入模板", self)
        load_template_action.triggered.connect(self.on_load_template)
        file_menu.addAction(load_template_action)

        export_records_action = QAction("导出记录", self)
        export_records_action.triggered.connect(self.on_export_records)
        file_menu.addAction(export_records_action)

        file_menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 通讯菜单
        comm_menu = menubar.addMenu("通讯")

        serial_config_action = QAction("串口配置", self)
        serial_config_action.triggered.connect(self.on_serial_config)
        comm_menu.addAction(serial_config_action)

        port_detect_action = QAction("端口探测", self)
        port_detect_action.triggered.connect(self.on_port_detect)
        comm_menu.addAction(port_detect_action)

        # 参数菜单
        params_menu = menubar.addMenu("参数")

        standard_values_action = QAction("标准值输入", self)
        standard_values_action.triggered.connect(self.on_standard_values)
        params_menu.addAction(standard_values_action)

        engineer_params_action = QAction("工程师参数", self)
        engineer_params_action.triggered.connect(self.on_engineer_params)
        params_menu.addAction(engineer_params_action)

        # 自动化菜单
        auto_menu = menubar.addMenu("自动化")

        step_template_action = QAction("步骤模板管理", self)
        step_template_action.triggered.connect(self.on_step_template)
        auto_menu.addAction(step_template_action)

        exec_strategy_action = QAction("执行策略", self)
        exec_strategy_action.triggered.connect(self.on_exec_strategy)
        auto_menu.addAction(exec_strategy_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")

        usage_action = QAction("使用说明", self)
        usage_action.triggered.connect(self.on_usage_help)
        help_menu.addAction(usage_action)

        about_action = QAction("关于", self)
        about_action.triggered.connect(self.on_about)
        help_menu.addAction(about_action)

    def setup_toolbar(self):
        """设置工具栏"""
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)

        # 一键校表按钮
        self.one_click_button = QPushButton("一键校表")
        self.one_click_button.setMinimumHeight(35)
        self.one_click_button.clicked.connect(self.on_one_click_calibration)
        toolbar.addWidget(self.one_click_button)

        toolbar.addSeparator()

        # 串口控制按钮
        self.serial_toggle_button = QPushButton("开始串口")
        self.serial_toggle_button.setMinimumHeight(35)
        self.serial_toggle_button.clicked.connect(self.on_serial_toggle)
        toolbar.addWidget(self.serial_toggle_button)

        # 刷新端口按钮
        refresh_button = QPushButton("刷新端口")
        refresh_button.setMinimumHeight(35)
        refresh_button.clicked.connect(self.on_refresh_ports)
        toolbar.addWidget(refresh_button)

        toolbar.addSeparator()

        # 状态指示灯
        toolbar.addWidget(QLabel("串口状态:"))
        self.status_indicator = StatusIndicator()
        toolbar.addWidget(self.status_indicator)

    def setup_statusbar(self):
        """设置状态栏"""
        self.status_bar = self.statusBar()

        # 串口参数摘要
        self.serial_status_label = QLabel("串口: 未连接")
        self.status_bar.addWidget(self.serial_status_label)

        self.status_bar.addPermanentWidget(QLabel(" | "))

        # 标准值摘要
        self.standard_values_label = QLabel("标准值: 未设置")
        self.status_bar.addPermanentWidget(self.standard_values_label)

    def connect_signals(self):
        """连接信号槽"""
        # 这里将在后续实现具体的信号连接
        pass

    # ================ 槽函数 ================

    def on_step_execute(self, step_id):
        """执行单个步骤"""
        step_name = self.step_widgets[step_id].step_name
        self.add_log(f">>> 开始执行 {step_name}")

        # 检查校表执行引擎是否可用
        if not self.calibration_executor:
            step_widget = self.step_widgets[step_id]
            step_widget.set_result("error", "校表引擎未初始化", 0)
            self.add_log(f"!!! {step_name} 执行失败: 校表引擎未初始化")
            return

        # 检查串口连接状态
        if not self.serial_port or not self.serial_port.is_open():
            step_widget = self.step_widgets[step_id]
            step_widget.set_result("error", "串口未连接", 0)
            self.add_log(f"!!! {step_name} 执行失败: 串口未连接")
            return

        try:
            # 更新校表参数
            self._update_calibration_params_from_standard_values()

            # 数字ID转换为步骤字符串ID
            step_string_id = f"step{step_id}"

            # 使用M3校表执行引擎执行步骤
            step_result = self.calibration_executor.execute_single_step(
                step_string_id,
                self.calibration_params
            )

            # 结果已通过进度回调处理，这里不需要额外操作

        except Exception as e:
            step_widget = self.step_widgets[step_id]
            step_widget.set_result("error", f"执行异常: {str(e)}", 0)
            self.add_log(f"!!! {step_name} 执行异常: {str(e)}")



    def on_one_click_calibration(self):
        """一键校表"""
        # 检查校表执行引擎是否可用
        if not self.calibration_executor:
            self.add_log("!!! 一键校表失败: 校表引擎未初始化")
            return

        # 检查串口连接状态
        if not self.serial_port or not self.serial_port.is_open():
            self.add_log("!!! 一键校表失败: 串口未连接")
            return

        # 检查选中的步骤
        checked_steps = [
            step_id for step_id, widget in self.step_widgets.items()
            if widget.checkbox.isChecked()
        ]

        if not checked_steps:
            self.add_log("!!! 未选择任何步骤")
            return

        try:
            # 更新校表参数
            self._update_calibration_params_from_standard_values()

            # 转换为步骤字符串ID列表
            step_string_ids = [f"step{step_id}" for step_id in sorted(checked_steps)]

            self.add_log(f">>> 开始一键校表，步骤: {step_string_ids}")

            # 使用M3校表执行引擎执行选择的步骤
            execution_result = self.calibration_executor.execute_selected_steps(
                step_string_ids,
                self.calibration_params
            )

            # 显示执行结果摘要
            if execution_result.status.value == "completed":
                success_count = len(execution_result.successful_steps)
                total_count = len(execution_result.executed_steps)
                self.add_log(f">>> 一键校表完成: {success_count}/{total_count} 步骤成功")
            else:
                self.add_log(f"!!! 一键校表异常: {execution_result.error_message}")

        except Exception as e:
            self.add_log(f"!!! 一键校表异常: {str(e)}")

    def on_serial_toggle(self):
        """串口开关"""
        if self.serial_toggle_button.text() == "开始串口":
            # 检查是否有串口配置，如果没有则自动打开配置对话框
            config_is_default = (not hasattr(self, 'serial_config') or
                                not self.serial_config or
                                not hasattr(self.serial_config, 'port') or
                                not self.serial_config.port or
                                self.serial_config.port == "COM1")  # 默认端口

            if config_is_default:
                self.add_log(">>> 首次使用，请配置串口参数...")

                # 自动打开串口配置对话框
                from .dialogs.serial_config_dialog import SerialConfigDialog
                from core.serial_port import SerialConfig

                # 创建带默认值的配置
                default_config = SerialConfig()
                # 尝试设置第一个可用端口作为默认值
                from core.serial_port import SerialPort
                sp = SerialPort()
                ports = sp.get_available_ports()
                if ports:
                    default_config.port = ports[0]

                dialog = SerialConfigDialog(self, default_config)
                if dialog.exec_() == SerialConfigDialog.Accepted:
                    self.serial_config = dialog.get_config()
                    self.add_log(f">>> 串口配置完成: {self.serial_config}")
                    self.serial_status_label.setText(f"串口: {self.serial_config} (未连接)")
                    # 配置完成后继续执行串口打开流程
                else:
                    self.add_log(">>> 串口配置取消，无法打开串口")
                    return

            # 尝试真实打开串口
            self.add_log(f">>> 正在打开串口: {self.serial_config}")

            try:
                from core.serial_port import SerialPort
                self.serial_port = SerialPort()

                if self.serial_port.open_port(self.serial_config):
                    # 成功打开
                    self.serial_toggle_button.setText("关闭串口")
                    self.status_indicator.set_status("green")
                    self.serial_status_label.setText(f"串口: {self.serial_config}")
                    self.add_log(f">>> 串口打开成功: {self.serial_config}")

                    # 初始化M3校表执行引擎
                    self._initialize_calibration_engine()

                else:
                    # 打开失败
                    self.add_log(f"!!! 串口打开失败: {self.serial_config}")
                    self.status_indicator.set_status("red")
                    self.serial_port = None

            except Exception as e:
                self.add_log(f"!!! 串口打开异常: {str(e)}")
                self.status_indicator.set_status("red")
                self.serial_port = None
        else:
            # 关闭串口
            self.add_log(">>> 正在关闭串口...")

            if self.serial_port:
                try:
                    self.serial_port.close_port()
                    self.add_log(">>> 串口关闭成功")
                except Exception as e:
                    self.add_log(f"!!! 串口关闭异常: {str(e)}")
                finally:
                    self.serial_port = None
                    # 清理M3引擎组件
                    self._cleanup_calibration_engine()

            self.serial_toggle_button.setText("开始串口")
            self.status_indicator.set_status("gray")
            self.serial_status_label.setText("串口: 未连接")

    def on_refresh_ports(self):
        """刷新端口"""
        self.add_log(">>> 正在刷新串口列表...")

    def on_load_template(self):
        """载入模板"""
        self.add_log(">>> 载入Excel模板")

    def on_export_records(self):
        """导出记录"""
        self.add_log(">>> 导出校表记录")

    def on_serial_config(self):
        """串口配置"""
        from .dialogs.serial_config_dialog import SerialConfigDialog

        # 获取当前串口配置（如果有的话）
        current_config = getattr(self, 'serial_config', None)

        dialog = SerialConfigDialog(self, current_config)
        if dialog.exec_() == SerialConfigDialog.Accepted:
            self.serial_config = dialog.get_config()
            self.add_log(f">>> 串口配置已更新: {self.serial_config}")

            # 更新状态栏显示 - 配置完成但未连接
            self.serial_status_label.setText(f"串口: {self.serial_config} (未连接)")
        else:
            self.add_log(">>> 串口配置取消")

    def on_port_detect(self):
        """端口探测"""
        from core.serial_port import SerialPort

        sp = SerialPort()
        ports = sp.get_available_ports()

        if ports:
            ports_str = ", ".join(ports)
            self.add_log(f">>> 发现串口: {ports_str}")
        else:
            self.add_log(">>> 未发现可用串口")

    def on_standard_values(self):
        """标准值输入"""
        from .dialogs.standard_values_dialog import StandardValuesDialog

        # 获取当前标准值配置（如果有的话）
        current_config = getattr(self, 'standard_values_config', None)

        dialog = StandardValuesDialog(self, current_config)
        if dialog.exec_() == StandardValuesDialog.Accepted:
            self.standard_values_config = dialog.get_config()
            self.add_log(f">>> 标准值已更新: {self.standard_values_config.get_summary()}")

            # 更新状态栏显示
            self.standard_values_label.setText(f"标准值: {self.standard_values_config.get_summary()}")
        else:
            self.add_log(">>> 标准值输入取消")

    def on_engineer_params(self):
        """工程师参数"""
        self.add_log(">>> 打开工程师参数对话框")

    def on_step_template(self):
        """步骤模板管理"""
        self.add_log(">>> 步骤模板管理")

    def on_exec_strategy(self):
        """执行策略"""
        self.add_log(">>> 执行策略配置")

    def on_usage_help(self):
        """使用说明"""
        self.add_log(">>> 显示使用说明")

    def on_about(self):
        """关于"""
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.about(self, "关于",
                         "RN8213/RN8211B 电表校准工具 v2.0\\n\\n"
                         "基于PyQt5的单页版校准工具\\n"
                         "支持DL/T645协议和一键校表")

    def add_log(self, message):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.append(f"[{timestamp}] {message}")

        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


    def _initialize_calibration_engine(self):
        """初始化M3校表执行引擎"""
        try:
            self.add_log(">>> 正在初始化校表执行引擎...")

            # 创建通信配置
            comm_config = CommunicationConfig(
                timeout_ms=3000,
                max_retries=3,
                retry_delay_ms=500
            )

            # 创建设备通信器
            self.device_communicator = DeviceCommunicator(self.serial_port, comm_config)

            # 设置通信器日志转发到主窗口
            self._setup_communicator_logging()

            # 创建执行配置
            exec_config = ExecutionConfig(
                mode=ExecutionMode.SINGLE_STEP,
                stop_on_error=False,
                auto_retry_failed=True,
                max_step_retries=2,
                progress_callback=self._on_step_progress
            )

            # 创建校表执行器
            self.calibration_executor = CalibrationExecutor(self.device_communicator, exec_config)

            # 测试通信连接
            test_result = self.device_communicator.test_communication()
            if test_result['success']:
                self.add_log(">>> 校表执行引擎初始化成功，通信测试通过")
            else:
                self.add_log(f">>> 校表执行引擎初始化成功，但通信测试失败: {test_result.get('error_message', '')}")

        except Exception as e:
            self.add_log(f"!!! 校表执行引擎初始化失败: {str(e)}")
            self.calibration_executor = None
            self.device_communicator = None

    def _cleanup_calibration_engine(self):
        """清理M3校表执行引擎"""
        if self.calibration_executor:
            self.calibration_executor.cancel_execution()
            self.calibration_executor = None

        if self.device_communicator:
            self.device_communicator = None

        self.add_log(">>> 校表执行引擎已清理")

    def _on_step_progress(self, step_id: str, status: StepStatus, result):
        """步骤进度回调"""
        step_name = self._get_step_name_from_id(step_id)

        # 转换字符串步骤ID为数字ID (step1 -> 1)
        numeric_step_id = int(step_id.replace("step", "")) if step_id.startswith("step") else None

        if status == StepStatus.RUNNING:
            self.add_log(f">>> 正在执行步骤: {step_name}")
            if numeric_step_id and numeric_step_id in self.step_widgets:
                self.step_widgets[numeric_step_id].set_result("running", "正在执行...")

        elif status == StepStatus.SUCCESS:
            correction_value = result.correction_value if result else 0.0
            self.add_log(f">>> 步骤执行成功: {step_name}, 校正值: {correction_value:+.2f}")
            if numeric_step_id and numeric_step_id in self.step_widgets:
                execution_time = int(result.execution_time * 1000) if result and result.execution_time else 0
                self.step_widgets[numeric_step_id].set_result("success", f"校正成功 ({correction_value:+.2f}%)", execution_time)

        elif status == StepStatus.FAILED:
            error_msg = result.error_message if result else "执行失败"
            self.add_log(f"!!! 步骤执行失败: {step_name}, 错误: {error_msg}")
            if numeric_step_id and numeric_step_id in self.step_widgets:
                self.step_widgets[numeric_step_id].set_result("error", f"执行失败: {error_msg}", 0)

    def _get_step_name_from_id(self, step_id: str) -> str:
        """根据步骤ID获取步骤名称"""
        step_names = {
            "step1": "电流有效值offset校正",
            "step2": "电压电流增益校正",
            "step3": "功率增益校正",
            "step4": "相位补偿校正",
            "step5": "小电流偏置校正"
        }
        return step_names.get(step_id, f"步骤{step_id}")

    def _update_calibration_params_from_standard_values(self):
        """从标准值配置更新校表参数"""
        if hasattr(self, 'standard_values_config') and self.standard_values_config:
            self.calibration_params.standard_voltage = self.standard_values_config.standard_voltage
            self.calibration_params.standard_current = self.standard_values_config.standard_current
            if hasattr(self.standard_values_config, 'frequency'):
                self.calibration_params.frequency = self.standard_values_config.frequency
            if hasattr(self.standard_values_config, 'phase_angle'):
                self.calibration_params.phase_angle = self.standard_values_config.phase_angle

    def _setup_communicator_logging(self):
        """设置通信器日志转发到主窗口"""
        import logging

        class MainWindowLogHandler(logging.Handler):
            def __init__(self, main_window):
                super().__init__()
                self.main_window = main_window

            def emit(self, record):
                try:
                    message = self.format(record)
                    # 在主线程中添加日志
                    if hasattr(self.main_window, 'add_log'):
                        self.main_window.add_log(message)
                except Exception:
                    pass

        # 为设备通信器和相关组件添加日志处理器
        handler = MainWindowLogHandler(self)
        handler.setLevel(logging.INFO)

        # 添加到相关日志器
        communicator_logger = logging.getLogger("DeviceCommunicator")
        communicator_logger.addHandler(handler)
        communicator_logger.setLevel(logging.INFO)


def main():
    """测试主窗口"""
    app = QApplication([])

    window = MainWindow()
    window.show()

    app.exec_()

if __name__ == "__main__":
    main()