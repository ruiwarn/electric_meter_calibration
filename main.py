#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RN8213/RN8211B 电表校准工具 v2.0 - PyQt5单页版
程序入口文件

基于需求文档和Excel模板，实现电表校准的自动化工具
技术栈：PyQt5 + pyserial + openpyxl
"""

import sys
import os
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def check_dependencies():
    """检查必要依赖是否安装"""
    missing_deps = []

    try:
        import PyQt5
    except ImportError:
        missing_deps.append("PyQt5")

    try:
        import serial
    except ImportError:
        missing_deps.append("pyserial")

    try:
        import openpyxl
    except ImportError:
        missing_deps.append("openpyxl")

    if missing_deps:
        print(f"缺少依赖包: {', '.join(missing_deps)}")
        print("请运行: pip install -r requirements.txt")
        return False

    return True

def main():
    """主函数"""
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    # 设置高DPI属性（必须在创建QApplication之前）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("电表校准工具")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("RN8213/RN8211B")

    try:
        # 导入并显示主窗口
        from ui.main_window import MainWindow

        window = MainWindow()
        window.show()

        # 显示启动消息
        window.add_log("=== 电表校准工具 v2.0 启动成功 ===")
        window.add_log(">>> 框架已就绪，等待配置串口和标准值...")

        return app.exec_()

    except Exception as e:
        QMessageBox.critical(None, "启动错误", f"程序启动失败:\n{str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)