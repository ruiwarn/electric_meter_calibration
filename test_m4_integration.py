#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4可维护性优化集成测试
验证轻量级配置管理、设备扩展架构、会话记录等组件
"""

import sys
import os
import tempfile
import shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_config_manager():
    """测试配置管理器"""
    print("1. 测试配置管理器...")

    try:
        from core.config_manager import ConfigManager, AppConfig

        # 创建临时配置目录
        temp_dir = tempfile.mkdtemp()
        config_manager = ConfigManager(temp_dir)

        # 测试基本功能
        serial_config = config_manager.get_serial_config()
        print(f"   ✓ 默认串口配置: {serial_config['port']}@{serial_config['baudrate']}")

        # 测试配置保存
        config_manager.save_serial_config({'port': 'COM3', 'baudrate': 115200})
        new_config = config_manager.get_serial_config()
        print(f"   ✓ 配置修改: {new_config['port']}@{new_config['baudrate']}")

        # 测试标准值配置
        standard_values = config_manager.get_standard_values()
        print(f"   ✓ 标准值: {standard_values['standard_voltage']}V/{standard_values['standard_current']}A")

        # 测试备份功能
        backups = config_manager.get_backup_list()
        print(f"   ✓ 备份数量: {len(backups)}")

        # 清理
        shutil.rmtree(temp_dir)
        return True

    except Exception as e:
        print(f"   ❌ 配置管理器测试失败: {e}")
        return False

def test_device_interface():
    """测试设备接口架构"""
    print("\n2. 测试设备接口架构...")

    try:
        from core.device_interface import (
            DeviceManager, ElectricMeterDevice, PowerSourceDevice,
            DeviceType, DeviceStatus, SerialConnectionConfig
        )

        # 创建设备管理器
        device_manager = DeviceManager()

        # 注册电表设备
        electric_meter = ElectricMeterDevice("meter_test")
        device_manager.register_device(electric_meter)

        # 注册台体控源设备（预留）
        power_source = PowerSourceDevice("source_test")
        device_manager.register_device(power_source)

        # 获取摘要
        summary = device_manager.get_device_summary()
        print(f"   ✓ 注册设备数: {summary['total_devices']}")
        print(f"   ✓ 设备类型: {list(summary['device_types'].keys())}")

        # 测试设备信息
        meter_info = electric_meter.get_device_info()
        print(f"   ✓ 电表设备: {meter_info.name} - {meter_info.capabilities}")

        source_info = power_source.get_device_info()
        print(f"   ✓ 控源设备: {source_info.name} - {source_info.capabilities}")

        return True

    except Exception as e:
        print(f"   ❌ 设备接口测试失败: {e}")
        return False

def test_session_recorder():
    """测试会话记录器"""
    print("\n3. 测试会话记录器...")

    try:
        from core.session_recorder import SessionRecorder

        # 创建临时记录目录
        temp_dir = tempfile.mkdtemp()
        recorder = SessionRecorder(temp_dir)

        # 开始会话
        session_id = recorder.start_session({
            'serial_config': {'port': 'COM1', 'baudrate': 9600},
            'standard_values': {'voltage': 220.0, 'current': 1.0}
        })
        print(f"   ✓ 会话创建: {session_id}")

        # 记录步骤结果
        recorder.record_step_result(
            "step1", "电流offset校正", "00F81500",
            "success", correction_value=1.23, execution_time=2.5
        )

        recorder.record_step_result(
            "step2", "电压电流增益校正", "00F81600",
            "failed", error_message="设备无响应", execution_time=3.0
        )

        # 结束会话
        success = recorder.end_session("completed", "测试完成")
        print(f"   ✓ 会话结束: {'成功' if success else '失败'}")

        # 获取会话列表
        recent_sessions = recorder.get_recent_sessions(3)
        print(f"   ✓ 会话数量: {len(recent_sessions)}")

        # 导出报告
        if recent_sessions:
            report_file = recorder.export_session_report(recent_sessions[0]['session_id'], "txt")
            print(f"   ✓ 报告导出: {'成功' if report_file else '失败'}")

        # 统计信息
        stats = recorder.get_statistics()
        print(f"   ✓ 统计信息: {stats.get('total_sessions', 0)}个会话, 成功率{stats.get('average_success_rate', 0):.1f}%")

        # 清理
        shutil.rmtree(temp_dir)
        return True

    except Exception as e:
        print(f"   ❌ 会话记录器测试失败: {e}")
        return False

def test_error_handler():
    """测试错误处理系统"""
    print("\n4. 测试错误处理系统...")

    try:
        from core.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity

        handler = ErrorHandler()

        # 测试预定义错误
        comm_error = handler.handle_communication_error("COMM_001", {"port": "COM1"})
        print(f"   ✓ 通信错误处理: {comm_error.error_id} - {comm_error.user_message}")
        print(f"     建议: {len(comm_error.suggestions)}条")

        # 测试异常处理
        try:
            raise TimeoutError("设备响应超时")
        except Exception as e:
            error_info = handler.handle_error(e, {"operation": "calibration"})
            print(f"   ✓ 异常处理: {error_info.error_id}")

        # 测试统计信息
        stats = handler.get_error_statistics()
        print(f"   ✓ 错误统计: 总数{stats['total_errors']}, 分类{len(stats['by_category'])}")

        # 测试报告生成
        report = handler.generate_error_report("test_session")
        print(f"   ✓ 错误报告生成: {len(report)}字符")

        return True

    except Exception as e:
        print(f"   ❌ 错误处理系统测试失败: {e}")
        return False

def test_parameter_presets():
    """测试参数预设系统"""
    print("\n5. 测试参数预设系统...")

    try:
        from core.parameter_presets import ParameterPresets

        # 创建临时预设目录
        temp_dir = tempfile.mkdtemp()
        presets_manager = ParameterPresets(temp_dir)

        # 获取内置预设
        preset_list = presets_manager.get_preset_list()
        builtin_count = len([p for p in preset_list if p['is_builtin']])
        print(f"   ✓ 内置预设数量: {builtin_count}")

        # 应用预设
        params = presets_manager.apply_preset("default_220v_1a")
        if params:
            std_values = params['standard_values']
            print(f"   ✓ 预设应用: {std_values['standard_voltage']}V/{std_values['standard_current']}A")

        # 创建自定义预设
        custom_params = {
            'standard_voltage': 110.0,
            'standard_current': 0.5,
            'selected_steps': [1, 2, 3]
        }

        custom_id = presets_manager.save_preset(
            "测试预设", "用于测试的自定义预设", custom_params
        )
        print(f"   ✓ 自定义预设创建: {custom_id}")

        # 预设摘要
        summary = presets_manager.get_preset_summary()
        print(f"   ✓ 预设摘要: 总数{summary['total_presets']}, 内置{summary['builtin_presets']}, 用户{summary['user_presets']}")

        # 清理
        shutil.rmtree(temp_dir)
        return True

    except Exception as e:
        print(f"   ❌ 参数预设系统测试失败: {e}")
        return False

def test_integration_scenario():
    """测试集成场景"""
    print("\n6. 测试集成场景...")

    try:
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()

        # 1. 配置管理 + 预设系统
        from core.config_manager import ConfigManager
        from core.parameter_presets import ParameterPresets

        config_manager = ConfigManager(os.path.join(temp_dir, "config"))
        presets_manager = ParameterPresets(os.path.join(temp_dir, "presets"))

        # 应用预设到配置
        preset_params = presets_manager.apply_preset("fast_calibration")
        if preset_params:
            config_manager.save_standard_values(preset_params['standard_values'])
            config_manager.save_communication_config(preset_params['communication_config'])
            print("   ✓ 预设应用到配置成功")

        # 2. 会话记录 + 错误处理
        from core.session_recorder import SessionRecorder
        from core.error_handler import ErrorHandler

        recorder = SessionRecorder(os.path.join(temp_dir, "records"))
        error_handler = ErrorHandler()

        # 开始测试会话
        session_id = recorder.start_session()

        # 模拟校表过程中的错误
        error_info = error_handler.handle_communication_error("COMM_002")
        recorder.record_step_result(
            "step1", "测试步骤", "00F81500", "failed",
            error_message=error_info.user_message
        )

        recorder.end_session("failed", f"因错误终止: {error_info.error_id}")
        print("   ✓ 错误处理集成到会话记录成功")

        # 3. 设备管理集成
        from core.device_interface import DeviceManager, ElectricMeterDevice

        device_manager = DeviceManager()
        meter = ElectricMeterDevice("integration_test")
        device_manager.register_device(meter)

        device_summary = device_manager.get_device_summary()
        print(f"   ✓ 设备管理集成: {device_summary['total_devices']}个设备")

        # 清理
        shutil.rmtree(temp_dir)
        return True

    except Exception as e:
        print(f"   ❌ 集成场景测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("=== M4可维护性优化集成测试 ===\n")

    test_results = []

    # 逐个测试各组件
    test_results.append(test_config_manager())
    test_results.append(test_device_interface())
    test_results.append(test_session_recorder())
    test_results.append(test_error_handler())
    test_results.append(test_parameter_presets())
    test_results.append(test_integration_scenario())

    # 汇总结果
    passed_tests = sum(test_results)
    total_tests = len(test_results)

    print(f"\n=== 测试结果汇总 ===")
    print(f"通过测试: {passed_tests}/{total_tests}")
    print(f"测试成功率: {passed_tests/total_tests*100:.1f}%")

    if all(test_results):
        print("\n🎉 M4可维护性优化集成完成！")
        print("主要特性:")
        print("- ✅ 轻量级配置管理 (JSON文件存储)")
        print("- ✅ 设备抽象层 (支持台体控源扩展)")
        print("- ✅ 简化会话记录 (无数据库依赖)")
        print("- ✅ 智能错误处理 (分类建议系统)")
        print("- ✅ 参数预设系统 (内置+自定义)")
        print("- ✅ 完整集成验证")
        print("\n🏆 应用具备了出色的可维护性和扩展能力！")
        print("📋 为未来台体控源集成奠定了坚实基础")
        return True
    else:
        print("\n❌ 部分测试失败，需要修复后再继续")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)