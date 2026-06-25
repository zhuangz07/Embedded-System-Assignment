"""
主窗口UI定义
包含串口管理、控制面板、数字孪生面板、日志等所有界面元素
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QTextEdit, QGroupBox,
                             QGridLayout, QLineEdit, QSpinBox, QTabWidget, QSplitter,
                             QMessageBox, QFileDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QTextCursor, QFont, QColor
from datetime import datetime
import json


class MainWindow(QMainWindow):
    """主窗口"""
    
    # 信号定义
    connect_requested = pyqtSignal(str)
    disconnect_requested = pyqtSignal()
    send_command = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("智能联网时钟系统 - PC上位机")
        self.setGeometry(100, 100, 1400, 900)
        
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 顶部：串口连接区域
        main_layout.addWidget(self.create_serial_group())
        
        # 状态栏区域
        main_layout.addWidget(self.create_status_bar_widget())
        
        # 中部：分割器（左：控制+日志，右：数字孪生）
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：控制面板和日志
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        
        # 控制面板（标签页）
        self.control_tabs = QTabWidget()
        self.control_tabs.addTab(self.create_basic_control_panel(), "基础控制")
        self.control_tabs.addTab(self.create_advanced_control_panel(), "高级功能")
        self.control_tabs.addTab(self.create_query_panel(), "查询命令")
        left_layout.addWidget(self.control_tabs)
        
        # 日志区域
        left_layout.addWidget(self.create_log_group())
        
        splitter.addWidget(left_widget)
        
        # 右侧：占位符（将在main.py中添加数字孪生面板）
        self.twin_panel_container = QWidget()
        twin_layout = QVBoxLayout()
        self.twin_panel_container.setLayout(twin_layout)
        splitter.addWidget(self.twin_panel_container)
        
        # 设置分割比例
        splitter.setSizes([700, 700])
        
        main_layout.addWidget(splitter)
        
        # 样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5F5F5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #BDBDBD;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
            QLineEdit, QSpinBox, QComboBox {
                padding: 5px;
                border: 1px solid #BDBDBD;
                border-radius: 3px;
            }
        """)
    
    def create_serial_group(self):
        """创建串口连接区域"""
        group = QGroupBox("串口连接")
        layout = QHBoxLayout()
        
        # 串口选择
        layout.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        layout.addWidget(self.port_combo)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setMaximumWidth(80)
        layout.addWidget(self.refresh_btn)
        
        # 波特率
        layout.addWidget(QLabel("波特率:"))
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baudrate_combo.setCurrentText('115200')
        self.baudrate_combo.setMaximumWidth(100)
        layout.addWidget(self.baudrate_combo)
        
        # 连接/断开按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setMaximumWidth(100)
        layout.addWidget(self.connect_btn)
        
        # 状态指示
        layout.addWidget(QLabel("状态:"))
        self.connection_status = QLabel("未连接")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.connection_status)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def create_status_bar_widget(self):
        """创建状态栏区域"""
        group = QGroupBox("系统状态")
        layout = QHBoxLayout()
        
        # FORMAT状态
        layout.addWidget(QLabel("方向:"))
        self.format_label = QLabel("LEFT")
        self.format_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addWidget(self.format_label)
        
        layout.addWidget(QLabel("|"))
        
        # MODE状态
        layout.addWidget(QLabel("模式:"))
        self.mode_label = QLabel("DAY")
        self.mode_label.setStyleSheet("color: #FF9800; font-weight: bold;")
        layout.addWidget(self.mode_label)
        
        layout.addWidget(QLabel("|"))
        
        # ALARM状态
        layout.addWidget(QLabel("闹钟:"))
        self.alarm_label = QLabel("未知")
        self.alarm_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.alarm_label)
        
        layout.addWidget(QLabel("|"))
        
        # 心跳延迟
        layout.addWidget(QLabel("延迟:"))
        self.latency_label = QLabel("-- ms")
        self.latency_label.setStyleSheet("color: #9C27B0; font-weight: bold;")
        layout.addWidget(self.latency_label)
        
        layout.addWidget(QLabel("|"))
        
        # 运行时间
        layout.addWidget(QLabel("运行:"))
        self.uptime_label = QLabel("-- s")
        self.uptime_label.setStyleSheet("color: #009688; font-weight: bold;")
        layout.addWidget(self.uptime_label)
        
        layout.addStretch()
        
        group.setLayout(layout)
        group.setMaximumHeight(80)
        return group
    
    def create_basic_control_panel(self):
        """创建基础控制面板"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 时间日期设置
        datetime_group = QGroupBox("时间日期设置")
        datetime_layout = QGridLayout()
        
        # 日期设置
        datetime_layout.addWidget(QLabel("年:"), 0, 0)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2099)
        self.year_spin.setValue(2026)
        datetime_layout.addWidget(self.year_spin, 0, 1)
        
        datetime_layout.addWidget(QLabel("月:"), 0, 2)
        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setValue(6)
        datetime_layout.addWidget(self.month_spin, 0, 3)
        
        datetime_layout.addWidget(QLabel("日:"), 0, 4)
        self.date_spin = QSpinBox()
        self.date_spin.setRange(1, 31)
        self.date_spin.setValue(1)
        datetime_layout.addWidget(self.date_spin, 0, 5)
        
        self.set_date_btn = QPushButton("设置日期")
        datetime_layout.addWidget(self.set_date_btn, 0, 6)
        
        # 时间设置
        datetime_layout.addWidget(QLabel("时:"), 1, 0)
        self.hour_spin = QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.hour_spin.setValue(12)
        datetime_layout.addWidget(self.hour_spin, 1, 1)
        
        datetime_layout.addWidget(QLabel("分:"), 1, 2)
        self.minute_spin = QSpinBox()
        self.minute_spin.setRange(0, 59)
        self.minute_spin.setValue(0)
        datetime_layout.addWidget(self.minute_spin, 1, 3)
        
        datetime_layout.addWidget(QLabel("秒:"), 1, 4)
        self.second_spin = QSpinBox()
        self.second_spin.setRange(0, 59)
        self.second_spin.setValue(0)
        datetime_layout.addWidget(self.second_spin, 1, 5)
        
        self.set_time_btn = QPushButton("设置时间")
        datetime_layout.addWidget(self.set_time_btn, 1, 6)
        
        datetime_group.setLayout(datetime_layout)
        layout.addWidget(datetime_group)
        
        # 闹钟设置
        alarm_group = QGroupBox("闹钟设置")
        alarm_layout = QGridLayout()
        
        alarm_layout.addWidget(QLabel("时:"), 0, 0)
        self.alarm_hour_spin = QSpinBox()
        self.alarm_hour_spin.setRange(0, 23)
        self.alarm_hour_spin.setValue(7)
        alarm_layout.addWidget(self.alarm_hour_spin, 0, 1)
        
        alarm_layout.addWidget(QLabel("分:"), 0, 2)
        self.alarm_minute_spin = QSpinBox()
        self.alarm_minute_spin.setRange(0, 59)
        self.alarm_minute_spin.setValue(0)
        alarm_layout.addWidget(self.alarm_minute_spin, 0, 3)
        
        alarm_layout.addWidget(QLabel("秒:"), 0, 4)
        self.alarm_second_spin = QSpinBox()
        self.alarm_second_spin.setRange(0, 59)
        self.alarm_second_spin.setValue(0)
        alarm_layout.addWidget(self.alarm_second_spin, 0, 5)
        
        self.set_alarm_btn = QPushButton("设置闹钟")
        alarm_layout.addWidget(self.set_alarm_btn, 0, 6)
        
        self.alarm_off_btn = QPushButton("关闭闹钟")
        alarm_layout.addWidget(self.alarm_off_btn, 0, 7)
        
        alarm_group.setLayout(alarm_layout)
        layout.addWidget(alarm_group)
        
        # 显示控制
        display_group = QGroupBox("显示控制")
        display_layout = QHBoxLayout()
        
        self.display_on_btn = QPushButton("显示开")
        display_layout.addWidget(self.display_on_btn)
        
        self.display_off_btn = QPushButton("显示关")
        display_layout.addWidget(self.display_off_btn)
        
        self.format_left_btn = QPushButton("方向LEFT")
        display_layout.addWidget(self.format_left_btn)
        
        self.format_right_btn = QPushButton("方向RIGHT")
        display_layout.addWidget(self.format_right_btn)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # 消息和蜂鸣
        misc_group = QGroupBox("消息与蜂鸣")
        misc_layout = QGridLayout()
        
        misc_layout.addWidget(QLabel("消息:"), 0, 0)
        self.msg_edit = QLineEdit()
        self.msg_edit.setPlaceholderText("输入滚动消息(≤32字节)")
        misc_layout.addWidget(self.msg_edit, 0, 1, 1, 2)
        
        self.send_msg_btn = QPushButton("发送消息")
        misc_layout.addWidget(self.send_msg_btn, 0, 3)
        
        misc_layout.addWidget(QLabel("蜂鸣(ms):"), 1, 0)
        self.beep_spin = QSpinBox()
        self.beep_spin.setRange(10, 5000)
        self.beep_spin.setValue(500)
        misc_layout.addWidget(self.beep_spin, 1, 1)
        
        self.beep_btn = QPushButton("蜂鸣")
        misc_layout.addWidget(self.beep_btn, 1, 2)
        
        misc_layout.addWidget(QLabel("LED(HEX):"), 1, 3)
        self.led_edit = QLineEdit()
        self.led_edit.setPlaceholderText("00-FF")
        self.led_edit.setMaximumWidth(80)
        misc_layout.addWidget(self.led_edit, 1, 4)
        
        self.set_led_btn = QPushButton("设置LED")
        misc_layout.addWidget(self.set_led_btn, 1, 5)
        
        misc_group.setLayout(misc_layout)
        layout.addWidget(misc_group)
        
        # 系统命令
        system_group = QGroupBox("系统命令")
        system_layout = QHBoxLayout()
        
        self.ping_btn = QPushButton("PING")
        system_layout.addWidget(self.ping_btn)
        
        self.rst_btn = QPushButton("复位")
        system_layout.addWidget(self.rst_btn)
        
        system_group.setLayout(system_layout)
        layout.addWidget(system_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_advanced_control_panel(self):
        """创建高级功能面板"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 扩展功能
        ext_group = QGroupBox("扩展功能")
        ext_layout = QGridLayout()
        
        # NTP对时
        self.ntp_btn = QPushButton("NTP网络对时 (E1)")
        self.ntp_btn.setStyleSheet("background-color: #4CAF50;")
        ext_layout.addWidget(self.ntp_btn, 0, 0)
        
        self.ntp_status = QLabel("状态: 未对时")
        ext_layout.addWidget(self.ntp_status, 0, 1)
        
        # 天气获取
        self.weather_btn = QPushButton("获取天气 (E2)")
        self.weather_btn.setStyleSheet("background-color: #FF9800;")
        ext_layout.addWidget(self.weather_btn, 1, 0)
        
        self.weather_status = QLabel("状态: 未获取")
        ext_layout.addWidget(self.weather_status, 1, 1)
        
        # 昼夜模式
        self.mode_day_btn = QPushButton("昼间模式 (E3)")
        ext_layout.addWidget(self.mode_day_btn, 2, 0)
        
        self.mode_night_btn = QPushButton("夜间模式 (E3)")
        ext_layout.addWidget(self.mode_night_btn, 2, 1)
        
        ext_group.setLayout(ext_layout)
        layout.addWidget(ext_group)
        
        # 参数组合演示
        combo_group = QGroupBox("参数组合演示")
        combo_layout = QVBoxLayout()
        
        self.combo_selector = QComboBox()
        self.combo_selector.addItems([
            "*SET:DATE YEAR MONTH DATE 2026 06 01",
            "*SET:DATE YEAR DATE 2026 01",
            "*SET:DATE MONTH DATE 06 01",
            "*SET:TIME HOUR MINUTE SECOND 12 30 45",
            "*SET:TIME HOUR SECOND 12 45",
            "*SET:TIME MINUTE SECOND 30 45",
            "*SET:ALARM HOUR MINUTE SECOND 07 00 00",
            "*GET:DATE YEAR MONTH",
            "*GET:TIME HOUR MINUTE",
        ])
        combo_layout.addWidget(self.combo_selector)
        
        self.combo_send_btn = QPushButton("发送选中命令")
        combo_layout.addWidget(self.combo_send_btn)
        
        combo_group.setLayout(combo_layout)
        layout.addWidget(combo_group)
        
        # 缩写演示
        abbr_group = QGroupBox("缩写演示")
        abbr_layout = QVBoxLayout()
        
        abbr_btns_layout = QHBoxLayout()
        self.abbr_min_btn = QPushButton("MIN演示")
        abbr_btns_layout.addWidget(self.abbr_min_btn)
        
        self.abbr_sec_btn = QPushButton("SEC演示")
        abbr_btns_layout.addWidget(self.abbr_sec_btn)
        
        self.abbr_disp_btn = QPushButton("DISP演示")
        abbr_btns_layout.addWidget(self.abbr_disp_btn)
        
        abbr_layout.addLayout(abbr_btns_layout)
        abbr_group.setLayout(abbr_layout)
        layout.addWidget(abbr_group)
        
        # 大小写混合演示
        case_group = QGroupBox("大小写混合演示")
        case_layout = QVBoxLayout()
        
        case_btns_layout = QHBoxLayout()
        self.case_mixed_btn = QPushButton("混合大小写")
        case_btns_layout.addWidget(self.case_mixed_btn)
        
        self.case_lower_btn = QPushButton("全小写")
        case_btns_layout.addWidget(self.case_lower_btn)
        
        case_layout.addLayout(case_btns_layout)
        case_group.setLayout(case_layout)
        layout.addWidget(case_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_query_panel(self):
        """创建查询面板"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        query_group = QGroupBox("查询命令")
        query_layout = QGridLayout()
        
        self.get_date_btn = QPushButton("查询日期")
        query_layout.addWidget(self.get_date_btn, 0, 0)
        
        self.get_time_btn = QPushButton("查询时间")
        query_layout.addWidget(self.get_time_btn, 0, 1)
        
        self.get_alarm_btn = QPushButton("查询闹钟")
        query_layout.addWidget(self.get_alarm_btn, 0, 2)
        
        self.get_display_btn = QPushButton("查询显示")
        query_layout.addWidget(self.get_display_btn, 1, 0)
        
        self.get_format_btn = QPushButton("查询方向")
        query_layout.addWidget(self.get_format_btn, 1, 1)
        
        query_group.setLayout(query_layout)
        layout.addWidget(query_group)
        
        # 自定义命令
        custom_group = QGroupBox("自定义命令")
        custom_layout = QVBoxLayout()
        
        self.custom_cmd_edit = QLineEdit()
        self.custom_cmd_edit.setPlaceholderText("输入自定义命令，如: *PING")
        custom_layout.addWidget(self.custom_cmd_edit)
        
        self.custom_send_btn = QPushButton("发送自定义命令")
        custom_layout.addWidget(self.custom_send_btn)
        
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_log_group(self):
        """创建日志区域"""
        group = QGroupBox("通信日志")
        layout = QVBoxLayout()
        
        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(250)
        font = QFont("Consolas", 9)
        self.log_text.setFont(font)
        layout.addWidget(self.log_text)
        
        # 日志控制按钮
        log_btns = QHBoxLayout()
        
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.setMinimumWidth(90)
        log_btns.addWidget(self.clear_log_btn)
        
        self.export_log_btn = QPushButton("导出日志")
        self.export_log_btn.setMinimumWidth(90)
        log_btns.addWidget(self.export_log_btn)
        
        log_btns.addStretch()
        layout.addLayout(log_btns)
        
        group.setLayout(layout)
        return group
    
    def append_log(self, message: str, log_type: str = 'info'):
        """
        添加日志
        
        Args:
            message: 日志消息
            log_type: 日志类型 ('send', 'recv', 'event', 'error', 'info')
        """
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        # 颜色映射
        colors = {
            'send': '#1976D2',    # 蓝色 - 发送
            'recv': '#388E3C',    # 绿色 - 接收应答
            'event': '#F57C00',   # 橙色 - 事件
            'error': '#D32F2F',   # 红色 - 错误
            'info': '#616161'     # 灰色 - 信息
        }
        
        # 方向标记
        markers = {
            'send': '>>> ',
            'recv': '<<< ',
            'event': '*** ',
            'error': '!!! ',
            'info': '--- '
        }
        
        color = colors.get(log_type, colors['info'])
        marker = markers.get(log_type, markers['info'])
        
        # 格式化日志
        log_html = f'<span style="color: #9E9E9E;">[{timestamp}]</span> '
        log_html += f'<span style="color: {color}; font-weight: bold;">{marker}</span>'
        log_html += f'<span style="color: {color};">{message}</span>'
        
        self.log_text.append(log_html)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
    
    def update_connection_status(self, connected: bool):
        """更新连接状态"""
        if connected:
            self.connection_status.setText("已连接")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            self.connect_btn.setText("断开")
        else:
            self.connection_status.setText("未连接")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.connect_btn.setText("连接")
    
    def update_status_bar(self, format_val: str = None, mode_val: str = None, 
                         alarm_val: str = None, latency: int = None, uptime: int = None):
        """更新状态栏"""
        if format_val is not None:
            self.format_label.setText(format_val)
        
        if mode_val is not None:
            self.mode_label.setText(mode_val)
        
        if alarm_val is not None:
            self.alarm_label.setText(alarm_val)
        
        if latency is not None:
            self.latency_label.setText(f"{latency} ms")
        
        if uptime is not None:
            self.uptime_label.setText(f"{uptime} s")
