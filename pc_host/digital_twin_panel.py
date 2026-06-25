"""
数字孪生面板 - 镜像显示S800板的状态
实现8位7段数码管、8位LED、8位按键、USER1/USER2按钮的可视化
"""

from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPainter, QColor, QPen, QFont


class SevenSegmentDisplay(QWidget):
    """七段数码管显示组件"""
    
    # 七段编码映射 (0-9, A-Z, 空格, 减号, 下划线等)
    SEGMENT_MAP = {
        '0': 0b00111111, '1': 0b00000110, '2': 0b01011011, '3': 0b01001111,
        '4': 0b01100110, '5': 0b01101101, '6': 0b01111101, '7': 0b00000111,
        '8': 0b01111111, '9': 0b01101111,
        'A': 0b01110111, 'B': 0b01111100, 'C': 0b00111001, 'D': 0b01011110,
        'E': 0b01111001, 'F': 0b01110001, 'G': 0b00111101, 'H': 0b01110110,
        'I': 0b00000110, 'J': 0b00011110, 'K': 0b01110110, 'L': 0b00111000,
        'M': 0b00010101, 'N': 0b01010100, 'O': 0b00111111, 'P': 0b01110011,
        'Q': 0b01100111, 'R': 0b01010000, 'S': 0b01101101, 'T': 0b01111000,
        'U': 0b00111110, 'V': 0b00111110, 'W': 0b00101010, 'X': 0b01110110,
        'Y': 0b01101110, 'Z': 0b01011011,
        ' ': 0b00000000, '-': 0b01000000, '_': 0b00001000, '=': 0b01001000,
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments = 0b00000000  # 7段状态
        self.dp = False  # 小数点状态
        self.is_on = True  # 是否点亮
        self.setMinimumSize(40, 60)
        
    def set_char(self, char: str, dp: bool = False):
        """
        设置显示字符
        
        Args:
            char: 要显示的字符
            dp: 是否显示小数点
        """
        char = char.upper()
        if char in self.SEGMENT_MAP:
            self.segments = self.SEGMENT_MAP[char]
        else:
            self.segments = 0b00000000
        self.dp = dp
        self.update()
    
    def set_segments(self, segments: int, dp: bool = False):
        """
        直接设置段码
        
        Args:
            segments: 段码值
            dp: 是否显示小数点
        """
        self.segments = segments
        self.dp = dp
        self.update()
    
    def set_on(self, on: bool):
        """设置开关状态"""
        self.is_on = on
        self.update()
    
    def paintEvent(self, event):
        """绘制七段数码管"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # 背景
        painter.fillRect(0, 0, w, h, QColor(20, 20, 20))
        
        if not self.is_on:
            return
        
        # 段的颜色
        on_color = QColor(255, 0, 0)
        off_color = QColor(40, 0, 0)
        
        # 定义各段的坐标 (相对于宽高的比例)
        # 段序号: 0=A(顶), 1=B(右上), 2=C(右下), 3=D(底), 4=E(左下), 5=F(左上), 6=G(中)
        seg_a = [(0.2, 0.1), (0.8, 0.1), (0.75, 0.15), (0.25, 0.15)]
        seg_b = [(0.8, 0.15), (0.75, 0.2), (0.7, 0.45), (0.75, 0.5)]
        seg_c = [(0.75, 0.5), (0.7, 0.55), (0.7, 0.8), (0.8, 0.85)]
        seg_d = [(0.25, 0.85), (0.75, 0.85), (0.7, 0.8), (0.3, 0.8)]
        seg_e = [(0.2, 0.5), (0.25, 0.55), (0.3, 0.8), (0.2, 0.85)]
        seg_f = [(0.25, 0.15), (0.3, 0.2), (0.25, 0.45), (0.2, 0.5)]
        seg_g = [(0.25, 0.48), (0.3, 0.45), (0.7, 0.45), (0.75, 0.48), 
                 (0.7, 0.52), (0.3, 0.52)]
        
        segments_coords = [seg_a, seg_b, seg_c, seg_d, seg_e, seg_f, seg_g]
        
        # 绘制各段
        for i, coords in enumerate(segments_coords):
            color = on_color if (self.segments & (1 << i)) else off_color
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            
            # 转换为实际坐标
            points = [painter.transform().map(int(x * w), int(y * h)) 
                     for x, y in coords]
            from PyQt5.QtGui import QPolygon
            from PyQt5.QtCore import QPoint
            polygon = QPolygon([QPoint(int(x * w), int(y * h)) for x, y in coords])
            painter.drawPolygon(polygon)
        
        # 绘制小数点
        if self.dp:
            painter.setBrush(on_color)
            painter.drawEllipse(int(w * 0.85), int(h * 0.85), int(w * 0.1), int(h * 0.1))


class LEDIndicator(QWidget):
    """LED指示灯组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_on = False
        self.setMinimumSize(20, 20)
        self.setMaximumSize(20, 20)
    
    def set_on(self, on: bool):
        """设置LED状态"""
        self.is_on = on
        self.update()
    
    def paintEvent(self, event):
        """绘制LED"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.is_on:
            color = QColor(0, 255, 0)
            glow_color = QColor(0, 200, 0, 100)
        else:
            color = QColor(40, 40, 40)
            glow_color = QColor(40, 40, 40)
        
        # 绘制光晕
        painter.setBrush(glow_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 16, 16)
        
        # 绘制LED
        painter.setBrush(color)
        painter.drawEllipse(4, 4, 12, 12)


class DigitalTwinPanel(QWidget):
    """数字孪生面板 - 完整镜像S800板"""
    
    # 信号：按键被点击
    key_clicked = pyqtSignal(str)  # 按键名称
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 状态
        self.night_mode = False
        self.display_on = True
        
        # 初始化UI
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        
        # 标题
        title = QLabel("数字孪生面板 (Digital Twin)")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2196F3;")
        main_layout.addWidget(title)
        
        # 8位数码管
        seg_layout = QHBoxLayout()
        seg_layout.setSpacing(5)
        self.segments = []
        for i in range(8):
            seg = SevenSegmentDisplay()
            self.segments.append(seg)
            seg_layout.addWidget(seg)
        
        seg_widget = QWidget()
        seg_widget.setLayout(seg_layout)
        main_layout.addWidget(seg_widget)
        
        # 8位LED
        led_layout = QHBoxLayout()
        led_layout.setSpacing(10)
        self.leds = []
        led_labels = []
        for i in range(8):
            led_container = QVBoxLayout()
            led_container.setSpacing(2)
            
            led = LEDIndicator()
            self.leds.append(led)
            led_container.addWidget(led, alignment=Qt.AlignCenter)
            
            label = QLabel(f"LED{i}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 10px;")
            led_labels.append(label)
            led_container.addWidget(label)
            
            led_widget = QWidget()
            led_widget.setLayout(led_container)
            led_layout.addWidget(led_widget)
        
        led_widget = QWidget()
        led_widget.setLayout(led_layout)
        main_layout.addWidget(led_widget)
        
        # 8位按键 (K1-K8)
        key_layout = QGridLayout()
        key_layout.setSpacing(10)
        self.keys = {}
        
        key_names = ['FUNC', 'SHIFT', 'ADD', 'SAVE', 'DISP', 'SPEED', 'FORMAT', 'EXT']
        for i, name in enumerate(key_names):
            btn = QPushButton(f"K{i+1}\n{name}")
            btn.setMinimumSize(80, 50)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #455A64;
                    color: white;
                    border: 2px solid #607D8B;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:pressed {
                    background-color: #2196F3;
                }
            """)
            btn.clicked.connect(lambda checked, n=name: self.on_key_clicked(n))
            self.keys[name] = btn
            key_layout.addWidget(btn, i // 4, i % 4)
        
        key_widget = QWidget()
        key_widget.setLayout(key_layout)
        main_layout.addWidget(key_widget)
        
        # USER1和USER2按钮
        user_layout = QHBoxLayout()
        user_layout.setSpacing(20)
        
        self.user1_btn = QPushButton("USER1\n(请求对时)")
        self.user1_btn.setMinimumSize(120, 50)
        self.user1_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: 2px solid #F57C00;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #F57C00;
            }
        """)
        self.user1_btn.clicked.connect(lambda: self.on_key_clicked('USER1'))
        user_layout.addWidget(self.user1_btn)
        
        self.user2_btn = QPushButton("USER2\n(显示天气)")
        self.user2_btn.setMinimumSize(120, 50)
        self.user2_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: 2px solid #388E3C;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
        """)
        self.user2_btn.clicked.connect(lambda: self.on_key_clicked('USER2'))
        user_layout.addWidget(self.user2_btn)
        
        user_widget = QWidget()
        user_widget.setLayout(user_layout)
        main_layout.addWidget(user_widget)
        
        self.setLayout(main_layout)
        
        # 设置整体样式
        self.setStyleSheet("""
            QWidget {
                background-color: #263238;
                color: white;
            }
        """)
    
    def on_key_clicked(self, key_name: str):
        """按键点击处理"""
        self.key_clicked.emit(key_name)
    
    def update_display(self, text: str, dp_hex: int):
        """
        更新数码管显示
        
        Args:
            text: 8字符显示文本
            dp_hex: 小数点hex值
        """
        # 确保文本长度为8
        text = text.ljust(8, ' ')[:8]
        
        for i in range(8):
            char = text[i]
            dp = bool(dp_hex & (1 << i))
            
            # 昼夜模式：NIGHT时只显示前4位（时分）
            if self.night_mode and i >= 4:
                self.segments[i].set_char(' ', False)
                self.segments[i].set_on(False)
            else:
                self.segments[i].set_char(char, dp)
                self.segments[i].set_on(self.display_on)
    
    def update_leds(self, led_byte: int):
        """
        更新LED显示
        
        Args:
            led_byte: LED状态字节
        """
        for i in range(8):
            is_on = bool(led_byte & (1 << i))
            
            # 昼夜模式：NIGHT时只保留心跳LED（假设LED0是心跳）
            if self.night_mode and i > 0:
                self.leds[i].set_on(False)
            else:
                self.leds[i].set_on(is_on)
    
    def set_night_mode(self, night: bool):
        """设置昼夜模式"""
        self.night_mode = night
        # 强制刷新显示
        self.update()
    
    def set_display_on(self, on: bool):
        """设置显示开关"""
        self.display_on = on
        for seg in self.segments:
            seg.set_on(on)
