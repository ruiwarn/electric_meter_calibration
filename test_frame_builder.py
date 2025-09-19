#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M2阶段：FrameBuilder单元测试
验证FrameBuilder算法与Excel模板的100%等价性
"""

import unittest
import sys
import os

# 添加src路径到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.frame_builder import ExcelEquivalentFrameBuilder, create_excel_equivalent_frame

class TestFrameBuilderEquivalence(unittest.TestCase):
    """FrameBuilder Excel等价性测试"""

    def setUp(self):
        """测试初始化"""
        self.builder = ExcelEquivalentFrameBuilder()
        # Excel中B32的实际结果
        self.excel_frame = "6811111111111168140D33482B33333333333433333333FC16"

    def test_di_reverse_function(self):
        """测试DI字节序翻转功能"""
        print("\n=== 测试DI字节序翻转 ===")

        test_cases = [
            ("00F81500", "00 15 F8 00"),  # Excel中的示例
            ("12345678", "78 56 34 12"),  # 一般情况
            ("ABCDEF01", "01 EF CD AB"),  # 十六进制字母
            ("00000000", "00 00 00 00"),  # 全零
            ("FFFFFFFF", "FF FF FF FF"),  # 全F
        ]

        for original, expected in test_cases:
            with self.subTest(original=original):
                result = self.builder.reverse_di_bytes(original)
                self.assertEqual(result, expected,
                    f"DI翻转失败: {original} -> {result}, 期望: {expected}")
                print(f"✓ {original} -> {result}")

    def test_data_offset_function(self):
        """测试0x33偏置功能"""
        print("\n=== 测试0x33偏置 ===")

        test_cases = [
            ([0x00, 0x15, 0xF8, 0x00], [0x33, 0x48, 0x2B, 0x33]),  # Excel示例
            ([0x00, 0x00, 0x00, 0x00], [0x33, 0x33, 0x33, 0x33]),  # 全零
            ([0x01, 0x00, 0x00, 0x00], [0x34, 0x33, 0x33, 0x33]),  # 操作者码
            ([0xFF], [0x32]),  # 溢出测试: 0xFF + 0x33 = 0x132 & 0xFF = 0x32
            ([0xCC], [0xFF]),  # 边界测试: 0xCC + 0x33 = 0xFF
        ]

        for original, expected in test_cases:
            with self.subTest(original=original):
                result = self.builder.apply_data_offset(original)
                self.assertEqual(result, expected,
                    f"偏置计算失败: {original} -> {result}, 期望: {expected}")
                print(f"✓ {[f'{b:02X}' for b in original]} -> {[f'{b:02X}' for b in result]}")

    def test_excel_field_conversion(self):
        """测试Excel字段转换"""
        print("\n=== 测试Excel字段转换 ===")

        test_cases = [
            ("33333333", [0x00, 0x00, 0x00, 0x00]),  # 密码域
            ("34333333", [0x01, 0x00, 0x00, 0x00]),  # 操作者码
            ("3433", [0x01, 0x00, 0x00, 0x00]),      # 操作者码(前4位)
        ]

        for field_str, expected in test_cases:
            with self.subTest(field=field_str):
                result = self.builder.convert_excel_field_to_bytes(field_str)
                self.assertEqual(result, expected,
                    f"字段转换失败: {field_str} -> {result}, 期望: {expected}")
                print(f"✓ '{field_str}' -> {[f'{b:02X}' for b in result]}")

    def test_checksum_calculation(self):
        """测试校验和计算"""
        print("\n=== 测试校验和计算 ===")

        # 使用Excel帧测试校验和
        excel_frame_bytes = bytes.fromhex(self.excel_frame.replace(' ', ''))
        frame_without_checksum = excel_frame_bytes[:-2]  # 去掉校验和和结束符

        calculated_checksum = self.builder.calculate_checksum(frame_without_checksum, start_pos=0)
        expected_checksum = 0xFC

        self.assertEqual(calculated_checksum, expected_checksum,
            f"校验和计算失败: 计算得{calculated_checksum:02X}, 期望{expected_checksum:02X}")
        print(f"✓ 校验和计算正确: {calculated_checksum:02X}")

    def test_complete_frame_generation(self):
        """测试完整帧生成"""
        print("\n=== 测试完整帧生成 ===")

        # 使用Excel中的默认参数生成帧
        generated_frame = self.builder.build_frame_excel_equivalent()
        generated_hex = ''.join(f'{b:02X}' for b in generated_frame)

        self.assertEqual(generated_hex, self.excel_frame,
            f"完整帧生成失败:\n生成: {generated_hex}\nExcel: {self.excel_frame}")
        print(f"✓ 完整帧生成正确: {len(generated_frame)}字节")

    def test_frame_validation_function(self):
        """测试帧验证功能"""
        print("\n=== 测试帧验证功能 ===")

        # 正确的帧
        correct_frame = self.builder.build_frame_excel_equivalent()
        validation_result = self.builder.validate_against_excel(correct_frame, self.excel_frame)

        self.assertTrue(validation_result['is_match'], "正确帧验证失败")
        self.assertEqual(validation_result['generated_len'], validation_result['expected_len'])
        print(f"✓ 正确帧验证通过")

        # 错误的帧（修改一个字节）
        wrong_frame = bytearray(correct_frame)
        wrong_frame[0] = 0x69  # 修改起始符
        validation_result = self.builder.validate_against_excel(bytes(wrong_frame), self.excel_frame)

        self.assertFalse(validation_result['is_match'], "错误帧应该验证失败")
        self.assertGreater(len(validation_result['differences']), 0, "应该有差异记录")
        print(f"✓ 错误帧验证正确失败，发现{len(validation_result['differences'])}个差异")

    def test_different_di_codes(self):
        """测试不同DI码的帧生成"""
        print("\n=== 测试不同DI码 ===")

        test_di_codes = [
            "00F81600",  # 不同的DI码
            "00F81700",
            "00F81800",
            "00F81900",
        ]

        for di_code in test_di_codes:
            with self.subTest(di_code=di_code):
                frame = self.builder.build_frame_excel_equivalent(di_code=di_code)
                frame_hex = ''.join(f'{b:02X}' for b in frame)

                # 验证帧结构正确性
                self.assertEqual(frame[0], 0x68, "起始符错误")
                self.assertEqual(frame[7], 0x68, "第二个起始符错误")
                self.assertEqual(frame[8], 0x14, "控制码错误")
                self.assertEqual(frame[-1], 0x16, "结束符错误")

                print(f"✓ DI {di_code}: {len(frame)}字节帧")

    def test_parameter_data_handling(self):
        """测试参数数据处理"""
        print("\n=== 测试参数数据处理 ===")

        test_cases = [
            (b"", "无参数数据"),
            (b"\x01\x02", "2字节参数"),
            (b"\x01\x02\x03\x04", "4字节参数"),
        ]

        for param_data, description in test_cases:
            with self.subTest(description=description):
                frame = self.builder.build_frame_excel_equivalent(parameter_data=param_data)

                # 验证帧结构
                self.assertEqual(frame[0], 0x68, "起始符错误")
                self.assertEqual(frame[-1], 0x16, "结束符错误")

                # 验证数据长度字段
                expected_data_len = 4 + len(param_data) + 4 + 4 + 1  # DI + 参数 + 密码 + 操作者 + B34
                actual_data_len = frame[9]
                self.assertEqual(actual_data_len, expected_data_len,
                    f"数据长度错误: 期望{expected_data_len}, 实际{actual_data_len}")

                print(f"✓ {description}: 数据长度{actual_data_len}")

    def test_convenience_function(self):
        """测试便捷函数"""
        print("\n=== 测试便捷函数 ===")

        # 测试工厂函数
        frame1 = create_excel_equivalent_frame()
        frame2 = self.builder.build_frame_excel_equivalent()

        self.assertEqual(frame1, frame2, "便捷函数与类方法结果不一致")
        print(f"✓ 便捷函数工作正常")


class TestFrameBuilderEdgeCases(unittest.TestCase):
    """FrameBuilder边界条件测试"""

    def setUp(self):
        self.builder = ExcelEquivalentFrameBuilder()

    def test_invalid_di_code(self):
        """测试无效DI码"""
        print("\n=== 测试无效DI码 ===")

        invalid_di_codes = [
            "12345",      # 长度不对
            "1234567890", # 长度不对
            "GHIJ5678",   # 非十六进制字符
        ]

        for di_code in invalid_di_codes:
            with self.subTest(di_code=di_code):
                with self.assertRaises(ValueError, msg=f"应该抛出ValueError: {di_code}"):
                    self.builder.reverse_di_bytes(di_code)
                print(f"✓ 正确拒绝无效DI: {di_code}")

    def test_large_parameter_data(self):
        """测试大量参数数据"""
        print("\n=== 测试大参数数据 ===")

        large_data = b"\x00" * 100  # 100字节数据
        frame = self.builder.build_frame_excel_equivalent(parameter_data=large_data)

        # 验证帧结构完整性
        self.assertEqual(frame[0], 0x68, "起始符错误")
        self.assertEqual(frame[-1], 0x16, "结束符错误")

        # 验证数据长度
        expected_len = 4 + 100 + 4 + 4 + 1  # DI + 参数 + 密码 + 操作者 + B34
        actual_len = frame[9]
        self.assertEqual(actual_len, expected_len, "大数据长度计算错误")

        print(f"✓ 大参数数据处理正常: {len(large_data)}字节 -> {len(frame)}字节帧")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("M2阶段：FrameBuilder算法等价性验证测试")
    print("=" * 60)

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestFrameBuilderEquivalence))
    suite.addTests(loader.loadTestsFromTestCase(TestFrameBuilderEdgeCases))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出总结
    print("\n" + "=" * 60)
    print("测试总结:")
    print(f"总测试数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split()[-1] if traceback else 'Unknown'}")

    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split()[-1] if traceback else 'Unknown'}")

    success_rate = (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100
    print(f"\n成功率: {success_rate:.1f}%")

    if success_rate == 100.0:
        print("🎉 所有测试通过！FrameBuilder算法与Excel完全等价！")
    else:
        print("⚠️  存在测试失败，需要进一步调试")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)