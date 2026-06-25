"""
智能联网时钟系统 - PC上位机主程序
实现与S800板的串口通信、数字孪生镜像、扩展功能等
"""

import sys
import time
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
from PyQt5.QtCore import QTimer
from datetime import datetime
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
        
        # 数字孪生面板
        self.twin_panel = DigitalTwinPanel()
        self.window.twin_panel_container.layout().addWidget(self.twin_panel)
        
        # 连接信号和槽
        self.connect_signals()
        
        # 定时器：延迟显示刷新（不自动发送PING，仅手动点击PING按钮时更新）
        self.heartbeat_timer = QTimer()
        self.heartbeat_timer.timeout.connect(self.update_uptime_display)
        
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
            
        else:
            self.window.append_log(f"未知响应: {data}", 'error')
    
    def handle_event(self, event_str: str):
        """处理事件报文"""
        self.window.append_log(event_str, 'event')
        
        event_type, event_data = ProtocolParser.parse_event(event_str)
        
        if event_type == 'KEY':
            # 按键事件
            key_name = event_data
            self.window.append_log(f"按键按下: {key_name}", 'event')
            
            # 特殊处理USER1 - 自动触发NTP对时
            if key_name == 'USER1':
                self.on_ntp_sync()
            
        elif event_type == 'DISP':
            # 显示变化事件
            disp_str, dp_hex = ProtocolParser.parse_disp_event(event_data)
            
            # 根据FORMAT处理
            if self.current_format == 'RIGHT':
                disp_str, dp_hex = ProtocolParser.reverse_display(disp_str, dp_hex)
            
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
            
            # 使用worldtimeapi获取时间
            response = requests.get('http://worldtimeapi.org/api/timezone/Asia/Shanghai', timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                dt_str = data['datetime']
                
                # 解析ISO格式时间
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                
                # 发送时间到S800板
                date_cmd = CommandBuilder.set_date(dt.year, dt.month, dt.day)
                time_cmd = CommandBuilder.set_time(dt.hour, dt.minute, dt.second)
                
                self.send_command(date_cmd)
                time.sleep(0.1)
                self.send_command(time_cmd)
                
                self.window.ntp_status.setText(f"状态: 对时成功 {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                self.window.ntp_status.setStyleSheet("color: green;")
                self.window.append_log(f"NTP对时成功: {dt.strftime('%Y-%m-%d %H:%M:%S')}", 'info')
                
                QMessageBox.information(self.window, "成功", f"NTP对时成功\n{dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                raise Exception("NTP服务器响应错误")
                
        except Exception as e:
            self.window.ntp_status.setText(f"状态: 对时失败")
            self.window.ntp_status.setStyleSheet("color: red;")
            self.window.append_log(f"NTP对时失败: {str(e)}", 'error')
            QMessageBox.warning(self.window, "错误", f"NTP对时失败: {str(e)}")
    
    def on_get_weather(self):
        """获取天气 (E2)"""
        try:
            self.window.append_log("正在获取天气信息...", 'info')
            
            # 使用wttr.in获取天气（简单的文本API）
            response = requests.get('http://wttr.in/Shanghai?format=%t+%C', timeout=5)
            
            if response.status_code == 200:
                weather_text = response.text.strip()
                
                # 发送天气消息到S800板
                msg_cmd = CommandBuilder.set_message(f"Weather: {weather_text}")
                self.send_command(msg_cmd)
                
                self.window.weather_status.setText(f"状态: {weather_text}")
                self.window.weather_status.setStyleSheet("color: green;")
                self.window.append_log(f"天气获取成功: {weather_text}", 'info')
                
                QMessageBox.information(self.window, "成功", f"天气: {weather_text}")
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
