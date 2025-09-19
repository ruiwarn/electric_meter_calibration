#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M2阶段：精确分析Excel逻辑
逐字节分析Excel生成的帧，确保算法100%等价
"""

def analyze_excel_frame():
    """精确分析Excel生成的帧"""
    excel_frame = "6811111111111168140D33482B33333333333433333333FC16"
    print("=== Excel帧精确分析 ===\n")

    print(f"Excel完整帧: {excel_frame}")
    print(f"帧长度: {len(excel_frame) // 2} 字节\n")

    # 逐部分分析
    pos = 0

    # 起始符
    start1 = excel_frame[pos:pos+2]
    pos += 2
    print(f"起始符1: {start1}")

    # 地址域 (6字节)
    address = excel_frame[pos:pos+12]
    pos += 12
    print(f"地址域: {address} (6字节)")

    # 起始符2
    start2 = excel_frame[pos:pos+2]
    pos += 2
    print(f"起始符2: {start2}")

    # 控制码
    control = excel_frame[pos:pos+2]
    pos += 2
    print(f"控制码: {control}")

    # 数据长度
    data_len_hex = excel_frame[pos:pos+2]
    data_len = int(data_len_hex, 16)
    pos += 2
    print(f"数据长度: {data_len_hex} ({data_len} 字节)")

    # 数据域
    data_field = excel_frame[pos:pos + data_len * 2]
    pos += data_len * 2
    print(f"数据域: {data_field} ({data_len} 字节)")

    # 分析数据域内容
    print("\n数据域详细分析:")
    data_bytes = [data_field[i:i+2] for i in range(0, len(data_field), 2)]
    for i, byte_hex in enumerate(data_bytes):
        byte_val = int(byte_hex, 16)
        original = (byte_val - 0x33) & 0xFF
        print(f"  字节{i}: {byte_hex} (原始: {original:02X})")

    # 校验和
    checksum = excel_frame[pos:pos+2]
    pos += 2
    print(f"\n校验和: {checksum}")

    # 结束符
    end_marker = excel_frame[pos:pos+2]
    print(f"结束符: {end_marker}")

    # 验证校验和
    print(f"\n校验和验证:")
    checksum_data = excel_frame[14:-4]  # 从第二个68到数据域末尾
    checksum_bytes = [checksum_data[i:i+2] for i in range(0, len(checksum_data), 2)]
    total = sum(int(b, 16) for b in checksum_bytes)
    calculated = total & 0xFF
    print(f"校验和范围: {checksum_data}")
    print(f"计算结果: {total:04X} & 0xFF = {calculated:02X}")
    print(f"Excel结果: {checksum}")
    print(f"校验和{'正确' if f'{calculated:02X}' == checksum else '错误'}")

def decode_data_field():
    """解码数据域"""
    print("\n=== 数据域解码 ===")

    # Excel中的数据域: 33482B33333333333433333333
    data_field = "33482B33333333333433333333"
    data_bytes = [data_field[i:i+2] for i in range(0, len(data_field), 2)]

    print(f"数据域: {data_field}")
    print(f"数据字节: {data_bytes}")

    # 尝试解码 (减去0x33偏置)
    decoded = []
    for byte_hex in data_bytes:
        byte_val = int(byte_hex, 16)
        original = (byte_val - 0x33) & 0xFF
        decoded.append(f"{original:02X}")

    print(f"解码后: {decoded}")

    # 分析解码结果
    print("\n解码分析:")
    print(f"DI部分: {decoded[0:4]} (应该是 00 15 F8 00)")
    print(f"密码部分: {decoded[4:8]} (应该是 00 00 00 00)")
    print(f"操作者部分: {decoded[8:12]} (应该是 01 00 00 00)")
    print(f"额外数据: {decoded[12:]} (如果有)")

def understand_excel_logic():
    """理解Excel的精确逻辑"""
    print("\n=== Excel逻辑理解 ===")

    # 从分析来看，Excel的逻辑应该是：
    # 1. DI翻转: 00F81500 -> 00 15 F8 00
    # 2. 密码域: 33333333 -> 00 00 00 00 (这里没有+0x33!)
    # 3. 操作者码: 34333333 -> 01 00 00 00 (这里也没有+0x33!)
    # 4. 然后整体+0x33偏置

    print("发现的关键逻辑:")
    print("1. DI码确实需要字节序翻转")
    print("2. 密码域和操作者码需要特殊处理，不是直接的十六进制")
    print("3. B34的值(33)是额外添加的数据")
    print("4. 最后对整个数据域统一+0x33偏置")

    # 重新分析密码域
    print("\n密码域分析:")
    password_excel = "33333333"
    print(f"Excel中密码域: {password_excel}")
    print("这可能不是十六进制，而是字符串'3333' = [51, 51, 51, 51] = [0x33, 0x33, 0x33, 0x33]")
    print("减去0x33偏置后: [0x00, 0x00, 0x00, 0x00]")

    # 重新分析操作者码
    print("\n操作者码分析:")
    operator_excel = "34333333"
    print(f"Excel中操作者码: {operator_excel}")
    print("字符'4' = 52 = 0x34, 字符'3' = 51 = 0x33")
    print("所以是: [0x34, 0x33, 0x33, 0x33]")
    print("减去0x33偏置后: [0x01, 0x00, 0x00, 0x00]")

if __name__ == "__main__":
    analyze_excel_frame()
    decode_data_field()
    understand_excel_logic()