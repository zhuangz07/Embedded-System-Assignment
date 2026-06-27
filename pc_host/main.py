"""
智能联网时钟系统 - PC上位机主程序
实现与S800板的串口通信、数字孪生镜像、扩展功能等
"""

import re
import sys
import time
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt5.QtCore import QTimer
from datetime import datetime, timezone, timedelta
import ntplib
import requests

from ui_mainwindow import MainWindow
from serial_manager import SerialManager
from protocol_parser import ProtocolParser, CommandBuilder
from digital_twin_panel import DigitalTwinPanel


class ClockSystemApp:
    """时钟系统主应用"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.window = MainWindow()
        self.serial_mgr = SerialManager()
        
        # 状态变量
        self.current_format = 'LEFT'
        self.current_mode = 'DAY'
        self.alarm_enabled = False
        self.display_on = True
        
        # 自动昼夜模式状态
        self.auto_mode_enabled = False
        self._sunrise_time = None  # datetime.time 对象，本地时间
        self._sunset_time = None   # datetime.time 对象，本地时间
        self._sun_info_date = None  # 上次查询日出日落的日期
        
        # 数字孪生面板
        self.twin_panel = DigitalTwinPanel()
        self.window.twin_panel_container.layout().addWidget(self.twin_panel)
        
        # 连接信号和槽
        self.connect_signals()
        
        # 定时器：延迟显示刷新（不自动发送PING，仅手动点击PING按钮时更新）
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.update_uptime_display)
        
        # 定时器：自动昼夜模式检查（每60秒检查一次）
        self.auto_mode_timer = QTimer()
        self.auto_mode_timer.timeout.connect(self.check_auto_mode)
        
        # 初始化
        self.refresh_ports()
        
    def connect_signals(self):
        """连接所有信号和槽"""
        # 串口连接
        self.window.refresh_btn.clicked.connect(self.refresh_ports)
        self.window.connect_btn.clicked.connect(self.toggle_connection)
        
        # 基础控制
        self.window.set_date_btn.clicked.connect(self.on_set_date)
        self.window.set_time_btn.clicked.connect(self.on_set_time)
        self.window.set_alarm_btn.clicked.connect(self.on_set_alarm)
        self.window.alarm_off_btn.clicked.connect(self.on_alarm_off)
        self.window.set_timer_btn.clicked.connect(self.on_set_timer)
        self.window.timer_off_btn.clicked.connect(self.on_timer_off)
        
        self.window.display_on_btn.clicked.connect(lambda: self.on_set_display(True))
        self.window.display_off_btn.clicked.connect(lambda: self.on_set_display(False))
        self.window.format_left_btn.clicked.connect(lambda: self.on_set_format(True))
        self.window.format_right_btn.clicked.connect(lambda: self.on_set_format(False))
        
        self.window.send_msg_btn.clicked.connect(self.on_send_message)
        self.window.beep_btn.clicked.connect(self.on_beep)
        self.window.set_led_btn.clicked.connect(self.on_set_led)
        
        self.window.ping_btn.clicked.connect(self.on_ping)
        self.window.rst_btn.clicked.connect(self.on_reset)
        
        # 高级功能
        self.window.ntp_btn.clicked.connect(self.on_ntp_sync)
        self.window.weather_btn.clicked.connect(self.on_get_weather)
        self.window.mode_day_btn.clicked.connect(lambda: self.on_set_mode(True))
        self.window.mode_night_btn.clicked.connect(lambda: self.on_set_mode(False))
        self.window.auto_mode_btn.clicked.connect(self.on_toggle_auto_mode)
        
        self.window.combo_send_btn.clicked.connect(self.on_send_combo)
        self.window.abbr_min_btn.clicked.connect(lambda: self.send_command("*SET:TIME MIN 30"))
        self.window.abbr_sec_btn.clicked.connect(lambda: self.send_command("*SET:TIME SEC 45"))
        self.window.abbr_disp_btn.clicked.connect(lambda: self.send_command("*SET:DISP ON"))
        
        self.window.case_mixed_btn.clicked.connect(lambda: self.send_command("*SeT:TiMe HoUr 12"))
        self.window.case_lower_btn.clicked.connect(lambda: self.send_command("*set:time hour 12"))
        
        # 查询
        self.window.get_date_btn.clicked.connect(lambda: self.send_command(CommandBuilder.get_date()))
        self.window.get_time_btn.clicked.connect(lambda: self.send_command(CommandBuilder.get_time()))
        self.window.get_alarm_btn.clicked.connect(lambda: self.send_command(CommandBuilder.get_alarm()))
        self.window.get_display_btn.clicked.connect(lambda: self.send_command(CommandBuilder.get_display()))
        self.window.get_format_btn.clicked.connect(lambda: self.send_command(CommandBuilder.get_format()))
        
        self.window.custom_send_btn.clicked.connect(self.on_send_custom)
        self.window.custom_cmd_edit.returnPressed.connect(self.on_send_custom)
        
        # 日志
        self.window.clear_log_btn.clicked.connect(self.window.log_text.clear)
        self.window.export_log_btn.clicked.connect(self.on_export_log)
        
        # 数字孪生面板 - 按键点击
        self.twin_panel.key_clicked.connect(self.on_virtual_key_clicked)
        
    def refresh_ports(self):
        """刷新串口列表"""
        ports = SerialManager.list_ports()
        self.window.port_combo.clear()
        self.window.port_combo.addItems(ports)
        
        if ports:
            self.window.append_log(f"发现 {len(ports)} 个串口", 'info')
        else:
            self.window.append_log("未发现可用串口", 'error')
    
    def toggle_connection(self):
        """切换连接状态"""
        if self.serial_mgr.is_connected():
            self.disconnect()
        else:
            self.connect()
    
    def connect(self):
        """连接串口"""
        port = self.window.port_combo.currentText()
        if not port:
            QMessageBox.warning(self.window, "错误", "请选择串口")
            return
        
        baudrate = int(self.window.baudrate_combo.currentText())
        
        if self.serial_mgr.connect(port, baudrate):
            self.window.append_log(f"连接成功: {port} @ {baudrate}", 'info')
            self.window.update_connection_status(True)
            
            # 连接串口接收信号
            self.serial_mgr.serial_thread.data_received.connect(self.on_data_received)
            self.serial_mgr.serial_thread.connection_lost.connect(self.on_connection_lost)
            
            # 启动心跳
            self.heartbeat_timer.start(1000)  # 1秒心跳
            
        else:
            QMessageBox.critical(self.window, "错误", f"连接失败: {port}")
            self.window.append_log(f"连接失败: {port}", 'error')
    
    def disconnect(self):
        """断开串口"""
        self.heartbeat_timer.stop()
        self.serial_mgr.disconnect()
        self.window.update_connection_status(False)
        self.window.append_log("已断开连接", 'info')
    
    def send_command(self, cmd: str) -> bool:
        """
        发送命令
        
        Args:
            cmd: 命令字符串
            
        Returns:
            是否发送成功
        """
        if not self.serial_mgr.is_connected():
            QMessageBox.warning(self.window, "错误", "请先连接串口")
            return False
        
        # 确保命令格式正确
        if not cmd.endswith('\r\n'):
            cmd = cmd.strip() + '\r\n'
        
        if self.serial_mgr.send(cmd):
            self.window.append_log(cmd.strip(), 'send')
            return True
        else:
            self.window.append_log("发送失败", 'error')
            return False
    
    def on_data_received(self, data: str):
        """处理接收到的数据"""
        self.serial_mgr.increment_rx()
        
        # 解析响应
        resp_type, resp_data, reason = ProtocolParser.parse_response(data)
        
        if resp_type == 'OK':
            self.window.append_log(f"OK {resp_data if resp_data else ''}", 'recv')
            
        elif resp_type == 'ERROR':
            self.window.append_log(f"ERROR {reason}", 'error')
            QMessageBox.warning(self.window, "设备错误", f"S800板返回错误: {reason}")
            
        elif resp_type == 'EVENT':
            self.handle_event(resp_data)
            
        elif resp_type == 'PONG':
            uptime = int(resp_data) if resp_data else 0
            self.serial_mgr.update_pong_time(uptime)
            self.window.append_log(f"PONG {uptime}s", 'recv')
            
            # 更新状态栏
            stats = self.serial_mgr.get_stats()
            self.window.update_status_bar(
                latency=stats['latency'],
                uptime=stats['uptime']
            )
        
        elif resp_type == 'REQ':
            if resp_data == 'SYNC':
                self.on_ntp_sync()
            elif resp_data == 'WEA':
                self.on_get_weather()
            else:
                self.window.append_log(f"ERROR {resp_data}", 'error')
                QMessageBox.warning(self.window, "请求错误", f"S800板请求错误: {resp_data}")
            
        else:
            self.window.append_log(f"未知响应: {data}", 'error')
    
    def handle_event(self, event_str: str):
        """处理事件报文"""
        self.window.append_log(event_str, 'event')
        
        event_type, event_data = ProtocolParser.parse_event(event_str)
        
        if event_type == 'INIT':
            # 设备初始化事件：重置所有状态为初始值
            self._reset_all_states()
            self.window.append_log("设备初始化，所有状态已重置", 'info')
            
        elif event_type == 'KEY':
            # 按键事件
            key_name = event_data
            self.window.append_log(f"按键按下: {key_name}", 'event')
        elif event_type == 'DISP':
            # 显示变化事件
            disp_str, dp_hex = ProtocolParser.parse_disp_event(event_data)
            
            # 更新数字孪生面板
            self.twin_panel.update_display(disp_str, dp_hex)
            
        elif event_type == 'LED':
            # LED变化事件
            led_byte = ProtocolParser.parse_led_event(event_data)
            self.twin_panel.update_leds(led_byte)
        elif event_type == 'ALARM':
            # 闹钟响铃
            self.alarm_enabled = True
            self.window.update_status_bar(alarm_val='响铃中')
            
        elif event_type == 'ALARM_OFF':
            # 闹钟停止
            self.window.update_status_bar(alarm_val='已停止')
        elif event_type == 'EDIT':
            # 本地编辑事件
            self.window.append_log(f"本地编辑: {event_data}", 'event')
            
        elif event_type == 'MODE':
            # 模式切换
            self.current_mode = event_data
            self.window.update_status_bar(mode_val=event_data)
            self.twin_panel.set_night_mode(event_data == 'NIGHT')
    
    def _reset_all_states(self):
        """重置所有状态为初始值"""
        # 显示方向
        self.current_format = 'LEFT'
        self.window.update_status_bar(format_val='LEFT')

        # 显示模式
        self.current_mode = 'DAY'
        self.window.update_status_bar(mode_val='DAY')
        self.twin_panel.set_night_mode(False)

        # 显示开关
        self.display_on = True
        self.twin_panel.set_display_on(True)

        # 闹钟状态
        self.alarm_enabled = False
        self.window.update_status_bar(alarm_val='未知')

        # 自动昼夜模式
        self.auto_mode_enabled = False
        self.auto_mode_timer.stop()
        self.window.auto_mode_btn.setChecked(False)
        self.window.auto_mode_btn.setStyleSheet("background-color: #9C27B0;")
        self.window.auto_mode_status.setText("状态: 未启用")
        self.window.auto_mode_status.setStyleSheet("color: gray;")

        # 日出日落缓存
        self._sunrise_time = None
        self._sunset_time = None
        self._sun_info_date = None

        # NTP对时状态
        self.window.ntp_status.setText("状态: 未对时")
        self.window.ntp_status.setStyleSheet("color: gray;")

        # 天气状态
        self.window.weather_status.setText("状态: 未获取")
        self.window.weather_status.setStyleSheet("color: gray;")

        # 延迟和运行时间
        self.window.latency_label.setText("-- ms")
        self.window.uptime_label.setText("-- s")
        
    def on_connection_lost(self):
        """连接丢失处理"""
        self.disconnect()
        QMessageBox.warning(self.window, "连接丢失", "串口连接已断开")
    
    def update_uptime_display(self):
        """定时刷新运行时间显示（不主动发送PING）"""
        if self.serial_mgr.is_connected():
            stats = self.serial_mgr.get_stats()
            self.window.update_status_bar(uptime=stats['uptime'])
    
    # === 基础控制功能 ===
    
    def on_set_date(self):
        """设置日期"""
        year = self.window.year_spin.value()
        month = self.window.month_spin.value()
        date = self.window.date_spin.value()
        cmd = CommandBuilder.set_date(year, month, date)
        self.send_command(cmd)
    
    def on_set_time(self):
        """设置时间"""
        hour = self.window.hour_spin.value()
        minute = self.window.minute_spin.value()
        second = self.window.second_spin.value()
        cmd = CommandBuilder.set_time(hour, minute, second)
        self.send_command(cmd)
    
    def on_set_alarm(self):
        """设置闹钟"""
        hour = self.window.alarm_hour_spin.value()
        minute = self.window.alarm_minute_spin.value()
        second = self.window.alarm_second_spin.value()
        cmd = CommandBuilder.set_alarm(hour, minute, second)
        self.send_command(cmd)
        self.alarm_enabled = True
        self.window.update_status_bar(alarm_val='已启用')
    
    def on_alarm_off(self):
        """关闭闹钟"""
        cmd = CommandBuilder.set_alarm(off=True)
        self.send_command(cmd)
        self.alarm_enabled = False
        self.window.update_status_bar(alarm_val='已关闭')

    def on_set_timer(self):
        """设置倒计时"""
        hour = self.window.timer_hour_spin.value()
        minute = self.window.timer_minute_spin.value()
        second = self.window.timer_second_spin.value()
        cmd = CommandBuilder.set_timer(hour, minute, second)
        self.send_command(cmd)

    def on_timer_off(self):
        """关闭倒计时"""
        cmd = CommandBuilder.set_timer(off=True)
        self.send_command(cmd)
    
    def on_set_display(self, on: bool):
        """设置显示开关"""
        cmd = CommandBuilder.set_display(on)
        self.send_command(cmd)
        self.display_on = on
        self.twin_panel.set_display_on(on)
    
    def on_set_format(self, left: bool):
        """设置显示方向"""
        cmd = CommandBuilder.set_format(left)
        self.send_command(cmd)
        self.current_format = 'LEFT' if left else 'RIGHT'
        self.window.update_status_bar(format_val=self.current_format)
    
    def on_send_message(self):
        """发送滚动消息"""
        msg = self.window.msg_edit.text()
        if not msg:
            QMessageBox.warning(self.window, "警告", "请输入消息内容")
            return
        
        if len(msg.encode('ascii', errors='ignore')) > 32:
            QMessageBox.warning(self.window, "警告", "消息长度超过32字节")
            return
        
        cmd = CommandBuilder.set_message(msg)
        self.send_command(cmd)
    
    def on_beep(self):
        """蜂鸣"""
        duration = self.window.beep_spin.value()
        cmd = CommandBuilder.set_beep(duration)
        self.send_command(cmd)
    
    def on_set_led(self):
        """设置LED"""
        led_str = self.window.led_edit.text().strip()
        try:
            led_val = int(led_str, 16)
            if led_val < 0 or led_val > 0xFF:
                raise ValueError
            cmd = CommandBuilder.set_led(led_val)
            self.send_command(cmd)
        except:
            QMessageBox.warning(self.window, "错误", "请输入有效的HEX值 (00-FF)")
    
    def on_ping(self):
        """PING命令"""
        self.send_command(CommandBuilder.ping())
    
    def on_reset(self):
        """复位命令"""
        reply = QMessageBox.question(
            self.window, '确认', '确定要复位设备吗？',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.send_command(CommandBuilder.rst())
    
    # === 扩展功能 ===
    
    def on_ntp_sync(self):
        """NTP网络对时 (E1)"""
        try:
            self.window.append_log("正在从NTP服务器获取时间...", 'info')
            
            dt = None
            errors = []
            
            # 主源：ntplib 直接走 NTP UDP 协议，访问阿里云 NTP
            try:
                c = ntplib.NTPClient()
                ntp_resp = c.request('ntp.aliyun.com', version=3)
                dt = datetime.fromtimestamp(ntp_resp.tx_time)
                self.window.append_log("NTP源: ntp.aliyun.com", 'info')
            except Exception as e:
                errors.append(f"ntplib: {e}")
            
            # 备用：本机系统时间
            if dt is None:
                dt = datetime.now()
                self.window.append_log(
                    f"警告：网络时源不可用（{'; '.join(errors)}），使用本机系统时间", 'error'
                )
            
            # 发送时间到 S800 板
            date_cmd = CommandBuilder.set_date(dt.year, dt.month, dt.day)
            time_cmd = CommandBuilder.set_time(dt.hour, dt.minute, dt.second)
            
            self.send_command(date_cmd)
            time.sleep(0.1)
            self.send_command(time_cmd)
            
            self.window.ntp_status.setText(f"状态: 对时成功 {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            self.window.ntp_status.setStyleSheet("color: green;")
            self.window.append_log(f"NTP对时成功: {dt.strftime('%Y-%m-%d %H:%M:%S')}", 'info')
            
            QMessageBox.information(self.window, "成功", f"NTP对时成功\n{dt.strftime('%Y-%m-%d %H:%M:%S')}")
                
        except Exception as e:
            self.window.ntp_status.setText("状态: 对时失败")
            self.window.ntp_status.setStyleSheet("color: red;")
            self.window.append_log(f"NTP对时失败: {str(e)}", 'error')
            QMessageBox.warning(self.window, "错误", f"NTP对时失败: {str(e)}")
    
    @staticmethod
    def _parse_weather(raw: str):
        """解析 wttr.in 天气字符串，返回 (temp: int, cond_code: str)"""
        m = re.search(r'([+-]?\d+)\s*°?C', raw)
        temp = int(m.group(1)) if m else 0
        desc = re.sub(r'[+-]?\d+\s*°?C', '', raw).strip().lower()
        _MAP = [
            ('SNO', ['snow', 'sleet', 'blizzard', 'hail']),
            ('RAI', ['rain', 'drizzle', 'shower', 'thunder', 'storm']),
            ('FOG', ['fog', 'mist', 'haze', 'smoke', 'smoky', 'smog', 'dust', 'sand', 'ash']),
            ('OVC', ['overcast']),
            ('CLD', ['cloud', 'partly', 'mostly', 'broken', 'scattered']),
            ('SUN', ['sun', 'clear', 'fair', 'bright']),
        ]
        for code, words in _MAP:
            if any(w in desc for w in words):
                return temp, code
        return temp, 'OTH'

    def on_get_weather(self):
        """获取天气 (E2)"""
        try:
            self.window.append_log("正在获取天气信息...", 'info')
            
            response = requests.get('http://wttr.in/Shanghai?format=%t+%C', timeout=5)
            
            if response.status_code == 200:
                weather_text = response.text.strip()
                temp, cond = self._parse_weather(weather_text)
                
                wea_cmd = f"*SET:WEA {temp:02d} {cond}"
                self.send_command(wea_cmd)
                
                self.window.weather_status.setText(f"状态: {weather_text} → {cond}")
                self.window.weather_status.setStyleSheet("color: green;")
                self.window.append_log(f"天气获取成功: {weather_text} → T={temp:02d} COND={cond}", 'info')
                
                QMessageBox.information(self.window, "成功", f"天气: {weather_text}\n发送: {wea_cmd}")
            else:
                raise Exception("天气服务响应错误")
                
        except Exception as e:
            self.window.weather_status.setText(f"状态: 获取失败")
            self.window.weather_status.setStyleSheet("color: red;")
            self.window.append_log(f"天气获取失败: {str(e)}", 'error')
            QMessageBox.warning(self.window, "错误", f"天气获取失败: {str(e)}")
    
    def on_set_mode(self, day: bool):
        """设置昼夜模式 (E3)"""
        cmd = CommandBuilder.set_mode(day)
        self.send_command(cmd)
        self.current_mode = 'DAY' if day else 'NIGHT'
        self.window.update_status_bar(mode_val=self.current_mode)
        self.twin_panel.set_night_mode(not day)

    # === 自动昼夜模式 (E4) ===

    def _fetch_sun_times(self) -> bool:
        """
        查询固定坐标的日出日落时间。
        固定使用 31°01'36.27"N 121°26'14.61"E（上海交通大学闵行校区）。
        结果缓存到 self._sunrise_time / self._sunset_time。
        返回是否查询成功。
        """
        today = datetime.now().date()
        # 同一天内直接使用缓存
        if self._sun_info_date == today and self._sunrise_time and self._sunset_time:
            return True

        try:
            # 固定坐标：31°01'36.27"N 121°26'14.61"E
            lat, lon = 31.026742, 121.437392

            # 查询日出日落时间（UTC）
            sun_resp = requests.get(
                'https://api.sunrise-sunset.org/json',
                params={'lat': lat, 'lng': lon, 'formatted': 0},
                timeout=5
            )
            sun_resp.raise_for_status()
            sun_data = sun_resp.json()

            if sun_data.get('status') != 'OK':
                raise ValueError(f"sunrise-sunset API 返回异常: {sun_data.get('status')}")

            results = sun_data['results']
            # API 返回 ISO8601 UTC 时间字符串，如 "2025-06-01T22:13:00+00:00"
            sunrise_utc = datetime.fromisoformat(results['sunrise'])
            sunset_utc = datetime.fromisoformat(results['sunset'])

            # 转换为本地时间
            sunrise_local = sunrise_utc.astimezone().replace(tzinfo=None)
            sunset_local = sunset_utc.astimezone().replace(tzinfo=None)

            self._sunrise_time = sunrise_local.time()
            self._sunset_time = sunset_local.time()
            self._sun_info_date = today

            self.window.append_log(
                f"日出: {self._sunrise_time.strftime('%H:%M:%S')}  "
                f"日落: {self._sunset_time.strftime('%H:%M:%S')}（本地时间）",
                'info'
            )
            return True

        except Exception as e:
            self.window.append_log(f"日出日落查询失败: {e}", 'error')
            return False

    def _is_daytime(self) -> bool:
        """判断当前本地时间是否处于白天（日出到日落之间）"""
        now_t = datetime.now().time()
        return self._sunrise_time <= now_t < self._sunset_time

    def check_auto_mode(self):
        """定时检查并自动下发昼夜模式指令"""
        if not self.auto_mode_enabled:
            return
        if not self.serial_mgr.is_connected():
            return

        # 如果缓存过期（新的一天）则重新获取日出日落
        today = datetime.now().date()
        if self._sun_info_date != today:
            if not self._fetch_sun_times():
                self.window.auto_mode_status.setText("状态: 日出日落查询失败")
                self.window.auto_mode_status.setStyleSheet("color: red;")
                return

        day = self._is_daytime()
        new_mode = 'DAY' if day else 'NIGHT'

        # 仅在模式发生变化时下发指令，避免重复发送
        if new_mode != self.current_mode:
            self.window.append_log(
                f"自动昼夜: {self.current_mode} → {new_mode}", 'info'
            )
            self.on_set_mode(day)

        # 刷新状态标签
        sr = self._sunrise_time.strftime('%H:%M') if self._sunrise_time else '--:--'
        ss = self._sunset_time.strftime('%H:%M') if self._sunset_time else '--:--'
        self.window.auto_mode_status.setText(
            f"状态: {'白天' if day else '夜晚'}  日出{sr} 日落{ss}"
        )
        self.window.auto_mode_status.setStyleSheet(
            "color: #FF9800;" if day else "color: #5C6BC0;"
        )

    def on_toggle_auto_mode(self):
        """切换自动昼夜模式开关"""
        self.auto_mode_enabled = self.window.auto_mode_btn.isChecked()

        if self.auto_mode_enabled:
            self.window.auto_mode_btn.setStyleSheet(
                "background-color: #6A1B9A; border: 2px solid #CE93D8;"
            )
            self.window.append_log("自动昼夜模式已启用", 'info')

            # 立即查询日出日落并执行一次检查
            self.window.auto_mode_status.setText("状态: 正在查询日出日落...")
            self.window.auto_mode_status.setStyleSheet("color: gray;")

            if self._fetch_sun_times():
                self.check_auto_mode()
            else:
                self.window.auto_mode_status.setText("状态: 查询失败，将在下次重试")
                self.window.auto_mode_status.setStyleSheet("color: red;")

            self.auto_mode_timer.start(60_000)  # 每60秒检查一次
        else:
            self.auto_mode_timer.stop()
            self.window.auto_mode_btn.setStyleSheet("background-color: #9C27B0;")
            self.window.auto_mode_status.setText("状态: 未启用")
            self.window.auto_mode_status.setStyleSheet("color: gray;")
            self.window.append_log("自动昼夜模式已关闭", 'info')
    
    # === 其他功能 ===
    
    def on_send_combo(self):
        """发送参数组合命令"""
        cmd = self.window.combo_selector.currentText()
        self.send_command(cmd)
    
    def on_send_custom(self):
        """发送自定义命令"""
        cmd = self.window.custom_cmd_edit.text().strip()
        if cmd:
            self.send_command(cmd)
            self.window.custom_cmd_edit.clear()
    
    def on_virtual_key_clicked(self, key_name: str):
        """虚拟按键点击"""
        cmd = CommandBuilder.set_key(key_name)
        self.send_command(cmd)
        self.window.append_log(f"虚拟按键: {key_name}", 'send')
        if key_name == 'USER1':
            self.on_ntp_sync()
        elif key_name == 'USER2':
            self.on_get_weather()
    
    def on_export_log(self):
        """导出日志"""
        filename, _ = QFileDialog.getSaveFileName(
            self.window, "导出日志", f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.window.log_text.toPlainText())
                QMessageBox.information(self.window, "成功", f"日志已导出到:\n{filename}")
            except Exception as e:
                QMessageBox.warning(self.window, "错误", f"导出失败: {str(e)}")
    
    def run(self):
        """运行应用"""
        self.window.show()
        return self.app.exec_()


def main():
    """主函数"""
    app = ClockSystemApp()
    sys.exit(app.run())


if __name__ == '__main__':
    main()
