"""
串口协议解析模块
处理PC与S800板之间的通信协议
"""

import re
from typing import Tuple, Optional, Dict, List


class ProtocolParser:
    """协议解析器，处理命令的编码和解码"""
    
    # 命令缩写映射表
    COMMAND_ABBR = {
        'MIN': 'MINUTE',
        'MINU': 'MINUTE',
        'MINUT': 'MINUTE',
        'MINUTE': 'MINUTE',
        'SEC': 'SECOND',
        'SECO': 'SECOND',
        'SECON': 'SECOND',
        'SECOND': 'SECOND',
        'DISP': 'DISPLAY',
        'DISPL': 'DISPLAY',
        'DISPLA': 'DISPLAY',
        'DISPLAY': 'DISPLAY',
    }
    
    @staticmethod
    def normalize_command(cmd: str) -> str:
        """
        规范化命令，处理大小写和缩写
        
        Args:
            cmd: 原始命令字符串
            
        Returns:
            规范化后的命令字符串
        """
        # 转大写
        cmd = cmd.upper().strip()
        
        # 处理空格
        cmd = re.sub(r'\s+', ' ', cmd)
        
        # 处理缩写
        parts = cmd.split()
        normalized_parts = []
        
        for part in parts:
            if part in ProtocolParser.COMMAND_ABBR:
                normalized_parts.append(ProtocolParser.COMMAND_ABBR[part])
            else:
                normalized_parts.append(part)
        
        return ' '.join(normalized_parts)
    
    @staticmethod
    def build_set_command(subcmd: str, params: Dict[str, str]) -> str:
        """
        构建SET命令
        
        Args:
            subcmd: 子命令 (DATE/TIME/ALARM等)
            params: 参数字典
            
        Returns:
            完整的命令字符串
        """
        cmd = f"*SET:{subcmd}"
        
        if params:
            param_str = ' '.join(f"{k} {v}" for k, v in params.items())
            cmd += f" {param_str}"
        
        return cmd + "\r\n"
    
    @staticmethod
    def build_get_command(subcmd: str, params: Optional[List[str]] = None) -> str:
        """
        构建GET命令
        
        Args:
            subcmd: 子命令
            params: 参数列表（可选）
            
        Returns:
            完整的命令字符串
        """
        cmd = f"*GET:{subcmd}"
        
        if params:
            cmd += " " + " ".join(params)
        
        return cmd + "\r\n"
    
    @staticmethod
    def parse_response(response: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        解析S800板的响应
        
        Args:
            response: 响应字符串
            
        Returns:
            (类型, 数据, 原因) 元组
            类型: 'OK', 'ERROR', 'EVENT', 'PONG', 'UNKNOWN'
        """
        response = response.strip()
        
        if not response:
            return 'UNKNOWN', None, None
        
        # OK响应
        if response.startswith('OK'):
            data = response[2:].strip() if len(response) > 2 else None
            return 'OK', data, None
        
        # ERROR响应
        if response.startswith('ERROR'):
            reason = response[5:].strip() if len(response) > 5 else 'UNKNOWN'
            return 'ERROR', None, reason
        
        # 事件报文
        if response.startswith('*EVT:'):
            return 'EVENT', response, None
        
        # PONG响应
        if response.startswith('*PONG'):
            uptime = response[5:].strip() if len(response) > 5 else None
            return 'PONG', uptime, None
        
        return 'UNKNOWN', response, None
    
    @staticmethod
    def parse_event(event_str: str) -> Tuple[str, Optional[str]]:
        """
        解析事件报文
        
        Args:
            event_str: 事件字符串，如 "*EVT:KEY FUNC"
            
        Returns:
            (事件类型, 事件数据) 元组
        """
        if not event_str.startswith('*EVT:'):
            return 'UNKNOWN', None
        
        content = event_str[5:].strip()
        parts = content.split(None, 1)
        
        if len(parts) == 1:
            return parts[0], None
        else:
            return parts[0], parts[1]
    
    @staticmethod
    def parse_disp_event(data: str) -> Tuple[str, int]:
        """
        解析DISP事件
        
        Args:
            data: DISP数据，如 "12.30.45 03"
            
        Returns:
            (显示字符串, 小数点hex) 元组
        """
        parts = data.strip().split()
        
        if len(parts) >= 2:
            disp_str = parts[0]
            dp_hex = int(parts[1], 16) if len(parts[1]) <= 2 else 0
            return disp_str, dp_hex
        elif len(parts) == 1:
            return parts[0], 0
        else:
            return '', 0
    
    @staticmethod
    def parse_led_event(data: str) -> int:
        """
        解析LED事件
        
        Args:
            data: LED数据，如 "A5"
            
        Returns:
            LED状态字节
        """
        try:
            return int(data.strip(), 16)
        except:
            return 0
    
    @staticmethod
    def reverse_display(text: str, dp_hex: int) -> Tuple[str, int]:
        """
        反转显示内容（FORMAT RIGHT模式）
        
        Args:
            text: 显示文本
            dp_hex: 小数点hex值
            
        Returns:
            (反转后的文本, 反转后的dp_hex) 元组
        """
        # 反转文本
        reversed_text = text[::-1]
        
        # 反转小数点位
        reversed_dp = 0
        for i in range(8):
            if dp_hex & (1 << i):
                reversed_dp |= (1 << (7 - i))
        
        return reversed_text, reversed_dp


class CommandBuilder:
    """命令构建器，提供便捷的命令构建方法"""
    
    @staticmethod
    def rst() -> str:
        """复位命令"""
        return "*RST\r\n"
    
    @staticmethod
    def ping() -> str:
        """心跳命令"""
        return "*PING\r\n"
    
    @staticmethod
    def set_date(year: Optional[int] = None, month: Optional[int] = None, 
                 date: Optional[int] = None) -> str:
        """设置日期 - 格式: *SET:DATE YEAR MONTH DATE 2026 06 01"""
        param_names = []
        param_values = []
        
        if year is not None:
            param_names.append('YEAR')
            param_values.append(str(year))
        if month is not None:
            param_names.append('MONTH')
            param_values.append(str(month))
        if date is not None:
            param_names.append('DATE')
            param_values.append(str(date))
        
        if param_names:
            cmd = f"*SET:DATE {' '.join(param_names)} {' '.join(param_values)}\r\n"
        else:
            cmd = "*SET:DATE\r\n"
        return cmd
    
    @staticmethod
    def set_time(hour: Optional[int] = None, minute: Optional[int] = None,
                 second: Optional[int] = None) -> str:
        """设置时间 - 格式: *SET:TIME HOUR MINUTE SECOND 12 30 45"""
        param_names = []
        param_values = []
        
        if hour is not None:
            param_names.append('HOUR')
            param_values.append(str(hour))
        if minute is not None:
            param_names.append('MINUTE')
            param_values.append(str(minute))
        if second is not None:
            param_names.append('SECOND')
            param_values.append(str(second))
        
        if param_names:
            cmd = f"*SET:TIME {' '.join(param_names)} {' '.join(param_values)}\r\n"
        else:
            cmd = "*SET:TIME\r\n"
        return cmd
    
    @staticmethod
    def set_alarm(hour: Optional[int] = None, minute: Optional[int] = None,
                  second: Optional[int] = None, off: bool = False) -> str:
        """设置闹钟 - 格式: *SET:ALARM HOUR MINUTE SECOND 07 00 00"""
        if off:
            return "*SET:ALARM OFF\r\n"
        
        param_names = []
        param_values = []
        
        if hour is not None:
            param_names.append('HOUR')
            param_values.append(str(hour))
        if minute is not None:
            param_names.append('MINUTE')
            param_values.append(str(minute))
        if second is not None:
            param_names.append('SECOND')
            param_values.append(str(second))
        
        if param_names:
            cmd = f"*SET:ALARM {' '.join(param_names)} {' '.join(param_values)}\r\n"
        else:
            cmd = "*SET:ALARM\r\n"
        return cmd
    
    @staticmethod
    def set_display(on: bool) -> str:
        """设置显示开关"""
        params = {'ON' if on else 'OFF': ''}
        return ProtocolParser.build_set_command('DISPLAY', params)
    
    @staticmethod
    def set_format(left: bool) -> str:
        """设置显示方向"""
        params = {'LEFT' if left else 'RIGHT': ''}
        return ProtocolParser.build_set_command('FORMAT', params)
    
    @staticmethod
    def set_message(text: str) -> str:
        """设置滚动消息"""
        params = {'': text}  # MSG参数直接跟文本
        cmd = f"*SET:MSG {text}\r\n"
        return cmd
    
    @staticmethod
    def set_beep(duration_ms: int) -> str:
        """设置蜂鸣器"""
        params = {'': str(duration_ms)}
        cmd = f"*SET:BEEP {duration_ms}\r\n"
        return cmd
    
    @staticmethod
    def set_led(value: int) -> str:
        """设置LED"""
        params = {'': f"{value:02X}"}
        cmd = f"*SET:LED {value:02X}\r\n"
        return cmd
    
    @staticmethod
    def set_key(key_name: str) -> str:
        """模拟按键"""
        cmd = f"*SET:KEY {key_name}\r\n"
        return cmd
    
    @staticmethod
    def set_mode(day: bool) -> str:
        """设置昼夜模式"""
        params = {'DAY' if day else 'NIGHT': ''}
        return ProtocolParser.build_set_command('MODE', params)
    
    @staticmethod
    def get_date(params: Optional[List[str]] = None) -> str:
        """查询日期"""
        return ProtocolParser.build_get_command('DATE', params)
    
    @staticmethod
    def get_time(params: Optional[List[str]] = None) -> str:
        """查询时间"""
        return ProtocolParser.build_get_command('TIME', params)
    
    @staticmethod
    def get_alarm(params: Optional[List[str]] = None) -> str:
        """查询闹钟"""
        return ProtocolParser.build_get_command('ALARM', params)
    
    @staticmethod
    def get_display() -> str:
        """查询显示状态"""
        return ProtocolParser.build_get_command('DISPLAY')
    
    @staticmethod
    def get_format() -> str:
        """查询显示方向"""
        return ProtocolParser.build_get_command('FORMAT')
