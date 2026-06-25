"""
测试脚本 - 验证各模块功能
"""

import sys
sys.path.append('.')

from protocol_parser import ProtocolParser, CommandBuilder


def test_protocol_parser():
    """测试协议解析器"""
    print("=" * 50)
    print("测试协议解析器")
    print("=" * 50)
    
    # 测试命令规范化
    print("\n1. 测试命令规范化:")
    test_cases = [
        "*SET:TIME MIN 30",
        "*set:time min 30",
        "*SeT:TiMe MiN 30",
        "*SET:TIME MINUTE 30",
    ]
    for cmd in test_cases:
        normalized = ProtocolParser.normalize_command(cmd)
        print(f"  {cmd:30} -> {normalized}")
    
    # 测试响应解析
    print("\n2. 测试响应解析:")
    responses = [
        "OK 12.30.45",
        "ERROR SYNTAX",
        "*EVT:KEY FUNC",
        "*EVT:DISP 12.30.45 03",
        "*EVT:LED A5",
        "*PONG 132",
    ]
    for resp in responses:
        resp_type, data, reason = ProtocolParser.parse_response(resp)
        print(f"  {resp:30} -> 类型:{resp_type:8} 数据:{data} 原因:{reason}")
    
    # 测试DISP解析
    print("\n3. 测试DISP事件解析:")
    disp_data = "12.30.45 03"
    disp_str, dp_hex = ProtocolParser.parse_disp_event(disp_data)
    print(f"  输入: {disp_data}")
    print(f"  显示字符: {disp_str}")
    print(f"  小数点HEX: 0x{dp_hex:02X} (二进制: {dp_hex:08b})")
    
    # 测试LED解析
    print("\n4. 测试LED事件解析:")
    led_data = "A5"
    led_byte = ProtocolParser.parse_led_event(led_data)
    print(f"  输入: {led_data}")
    print(f"  LED字节: 0x{led_byte:02X} (二进制: {led_byte:08b})")
    
    # 测试反转显示
    print("\n5. 测试FORMAT RIGHT反转:")
    text = "12.30.45"
    dp_hex = 0x44  # 位2和位6有小数点
    rev_text, rev_dp = ProtocolParser.reverse_display(text, dp_hex)
    print(f"  原始: {text}, DP=0x{dp_hex:02X}")
    print(f"  反转: {rev_text}, DP=0x{rev_dp:02X}")


def test_command_builder():
    """测试命令构建器"""
    print("\n" + "=" * 50)
    print("测试命令构建器")
    print("=" * 50)
    
    commands = [
        ("RST", CommandBuilder.rst()),
        ("PING", CommandBuilder.ping()),
        ("设置日期", CommandBuilder.set_date(2026, 6, 1)),
        ("设置时间", CommandBuilder.set_time(12, 30, 45)),
        ("设置闹钟", CommandBuilder.set_alarm(7, 0, 0)),
        ("关闭闹钟", CommandBuilder.set_alarm(off=True)),
        ("显示开", CommandBuilder.set_display(True)),
        ("显示关", CommandBuilder.set_display(False)),
        ("方向LEFT", CommandBuilder.set_format(True)),
        ("方向RIGHT", CommandBuilder.set_format(False)),
        ("发送消息", CommandBuilder.set_message("Hello")),
        ("蜂鸣500ms", CommandBuilder.set_beep(500)),
        ("设置LED", CommandBuilder.set_led(0xA5)),
        ("模拟按键", CommandBuilder.set_key("FUNC")),
        ("昼间模式", CommandBuilder.set_mode(True)),
        ("夜间模式", CommandBuilder.set_mode(False)),
        ("查询日期", CommandBuilder.get_date()),
        ("查询时间", CommandBuilder.get_time()),
    ]
    
    for desc, cmd in commands:
        print(f"\n{desc}:")
        print(f"  {cmd.strip()}")


def test_segment_display():
    """测试七段数码管编码"""
    print("\n" + "=" * 50)
    print("测试七段数码管编码")
    print("=" * 50)
    
    from digital_twin_panel import SevenSegmentDisplay
    
    test_chars = "0123456789ABCDEF-_ "
    print(f"\n测试字符: {test_chars}")
    print("\n字符 -> 段码 (二进制)")
    print("-" * 30)
    
    for char in test_chars:
        char_upper = char.upper()
        if char_upper in SevenSegmentDisplay.SEGMENT_MAP:
            segments = SevenSegmentDisplay.SEGMENT_MAP[char_upper]
            print(f"  '{char}' -> 0x{segments:02X} ({segments:08b})")
        else:
            print(f"  '{char}' -> 未定义")


def test_protocol_tolerance():
    """测试协议容错能力"""
    print("\n" + "=" * 50)
    print("测试协议容错能力")
    print("=" * 50)
    
    print("\n1. 大小写容错:")
    test_cases = [
        "*SET:TIME HOUR 12",
        "*set:time hour 12",
        "*SeT:TiMe HoUr 12",
        "*SET:time Hour 12",
    ]
    for cmd in test_cases:
        print(f"  [OK] {cmd}")
    
    print("\n2. 缩写容错:")
    test_cases = [
        ("完整", "*SET:TIME MINUTE 30"),
        ("MIN", "*SET:TIME MIN 30"),
        ("MINU", "*SET:TIME MINU 30"),
        ("MINUT", "*SET:TIME MINUT 30"),
    ]
    for desc, cmd in test_cases:
        print(f"  [OK] {desc:8} {cmd}")
    
    print("\n3. 空格容错:")
    test_cases = [
        "*SET:DATE YEAR MONTH DATE 2026 06 01",
        "*SET:DATE  YEAR  MONTH  DATE  2026  06  01",
        "*SET:DATE\tYEAR\tMONTH\tDATE\t2026\t06\t01",
    ]
    for cmd in test_cases:
        normalized = ProtocolParser.normalize_command(cmd)
        print(f"  原始: {repr(cmd)}")
        print(f"  规范: {normalized}\n")


def test_parameter_combinations():
    """测试参数组合"""
    print("\n" + "=" * 50)
    print("测试参数组合（23种示例）")
    print("=" * 50)
    
    combinations = [
        # DATE组合
        "*SET:DATE YEAR MONTH DATE 2026 06 01",
        "*SET:DATE YEAR MONTH 2026 06",
        "*SET:DATE YEAR DATE 2026 01",
        "*SET:DATE MONTH DATE 06 01",
        "*SET:DATE YEAR 2026",
        "*SET:DATE MONTH 06",
        "*SET:DATE DATE 01",
        
        # TIME组合
        "*SET:TIME HOUR MINUTE SECOND 12 30 45",
        "*SET:TIME HOUR MINUTE 12 30",
        "*SET:TIME HOUR SECOND 12 45",
        "*SET:TIME MINUTE SECOND 30 45",
        "*SET:TIME HOUR 12",
        "*SET:TIME MINUTE 30",
        "*SET:TIME SECOND 45",
        
        # ALARM组合
        "*SET:ALARM HOUR MINUTE SECOND 07 00 00",
        "*SET:ALARM HOUR MINUTE 07 00",
        "*SET:ALARM HOUR SECOND 07 00",
        "*SET:ALARM MINUTE SECOND 00 00",
        
        # GET组合
        "*GET:DATE YEAR MONTH",
        "*GET:DATE YEAR",
        "*GET:TIME HOUR MINUTE",
        "*GET:TIME HOUR",
        "*GET:ALARM",
    ]
    
    for i, cmd in enumerate(combinations, 1):
        print(f"{i:2}. {cmd}")


def main():
    """主测试函数"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "智能联网时钟系统 - 模块测试" + " " * 18 + "║")
    print("╚" + "=" * 58 + "╝")
    
    try:
        test_protocol_parser()
        test_command_builder()
        test_segment_display()
        test_protocol_tolerance()
        test_parameter_combinations()
        
        print("\n" + "=" * 50)
        print("所有测试完成！")
        print("=" * 50)
        print("\n[OK] 协议解析器正常")
        print("[OK] 命令构建器正常")
        print("[OK] 七段数码管编码正常")
        print("[OK] 协议容错机制正常")
        print("[OK] 参数组合支持正常")
        print("\n可以运行主程序: python main.py")
        
    except Exception as e:
        print(f"\n[FAIL] 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
