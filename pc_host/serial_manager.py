"""
串口管理模块
负责串口连接、收发、心跳等功能
"""

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker
import time
from typing import Optional, List


class SerialThread(QThread):
    """串口接收线程"""
    
    # 信号定义
    data_received = pyqtSignal(str)  # 接收到数据
    connection_lost = pyqtSignal()   # 连接丢失
    
    def __init__(self, serial_port: serial.Serial):
        super().__init__()
        self.serial_port = serial_port
        self.running = True
        self.buffer = ""
        
    def run(self):
        """线程运行函数"""
        while self.running:
            try:
                if self.serial_port and self.serial_port.is_open:
                    if self.serial_port.in_waiting > 0:
                        # 读取数据
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        try:
                            text = data.decode('ascii', errors='ignore')
                            self.buffer += text
                            
                            # 处理完整的行
                            while '\n' in self.buffer or '\r' in self.buffer:
                                # 查找行结束符
                                idx_n = self.buffer.find('\n')
                                idx_r = self.buffer.find('\r')
                                
                                if idx_n == -1:
                                    idx = idx_r
                                elif idx_r == -1:
                                    idx = idx_n
                                else:
                                    idx = min(idx_n, idx_r)
                                
                                # 提取一行
                                line = self.buffer[:idx].strip()
                                
                                # 移除已处理的部分（包括\r\n）
                                if idx < len(self.buffer) - 1:
                                    next_char = self.buffer[idx + 1]
                                    if (self.buffer[idx] == '\r' and next_char == '\n') or \
                                       (self.buffer[idx] == '\n' and next_char == '\r'):
                                        self.buffer = self.buffer[idx + 2:]
                                    else:
                                        self.buffer = self.buffer[idx + 1:]
                                else:
                                    self.buffer = self.buffer[idx + 1:]
                                
                                # 发送数据
                                if line:
                                    self.data_received.emit(line)
                        except Exception as e:
                            print(f"解码错误: {e}")
                    
                    time.sleep(0.01)  # 10ms轮询
                else:
                    break
            except Exception as e:
                print(f"串口读取错误: {e}")
                self.connection_lost.emit()
                break
    
    def stop(self):
        """停止线程"""
        self.running = False


class SerialManager:
    """串口管理器"""
    
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.serial_thread: Optional[SerialThread] = None
        self.mutex = QMutex()
        self.connected = False
        
        # 统计信息
        self.tx_count = 0
        self.rx_count = 0
        self.last_ping_time = 0
        self.last_pong_time = 0
        self.uptime = 0
        
    @staticmethod
    def list_ports() -> List[str]:
        """
        列出所有可用串口
        
        Returns:
            串口列表
        """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """
        连接串口
        
        Args:
            port: 串口名称
            baudrate: 波特率
            
        Returns:
            是否连接成功
        """
        try:
            # 如果已连接，先断开
            if self.connected:
                self.disconnect()
            
            # 打开串口
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            
            # 启动接收线程
            self.serial_thread = SerialThread(self.serial_port)
            self.serial_thread.start()
            
            self.connected = True
            self.tx_count = 0
            self.rx_count = 0
            
            return True
            
        except Exception as e:
            print(f"串口连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开串口连接"""
        try:
            self.connected = False
            
            # 停止接收线程
            if self.serial_thread:
                self.serial_thread.stop()
                self.serial_thread.wait(1000)  # 等待最多1秒
                if self.serial_thread.isRunning():
                    self.serial_thread.terminate()
                self.serial_thread = None
            
            # 关闭串口
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
                self.serial_port = None
                
        except Exception as e:
            print(f"串口断开失败: {e}")
    
    def send(self, data: str) -> bool:
        """
        发送数据
        
        Args:
            data: 要发送的字符串
            
        Returns:
            是否发送成功
        """
        with QMutexLocker(self.mutex):
            try:
                if self.serial_port and self.serial_port.is_open:
                    # 确保数据以\r\n结尾
                    if not data.endswith('\r\n') and not data.endswith('\n'):
                        data += '\r\n'
                    
                    self.serial_port.write(data.encode('ascii'))
                    self.serial_port.flush()
                    self.tx_count += 1
                    return True
                else:
                    return False
            except Exception as e:
                print(f"发送数据失败: {e}")
                return False
    
    def is_connected(self) -> bool:
        """
        检查是否已连接
        
        Returns:
            是否已连接
        """
        return self.connected and self.serial_port is not None and self.serial_port.is_open
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'connected': self.connected,
            'tx_count': self.tx_count,
            'rx_count': self.rx_count,
            'uptime': self.uptime,
            'latency': int((time.time() - self.last_ping_time) * 1000) if self.last_ping_time > 0 else 0
        }
    
    def update_ping_time(self):
        """更新PING时间"""
        self.last_ping_time = time.time()
    
    def update_pong_time(self, uptime: int):
        """更新PONG时间和运行时间"""
        self.last_pong_time = time.time()
        self.uptime = uptime
    
    def increment_rx(self):
        """增加接收计数"""
        self.rx_count += 1
