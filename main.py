import sys
import time
import serial
import serial.tools.list_ports
import queue
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QTimer, QThread, pyqtSignal

from UI import Ui_MainWindow

try:
    from MoveControl import MoveControl
    from get_angle import GetAngle
    from orbitron_module import get_orbitron_data
    from zenith_tracker import ZenithTracker
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保以下模块在同一目录下:")
    print("1. MoveControl.py")
    print("2. get_angle.py")
    print("3. orbitron_module.py")
    print("4. zenith_tracker.py")
    sys.exit(1)


class SerialWorker(QThread):
    command_sent = pyqtSignal(bytes, str)  # 命令已发送
    angle_data = pyqtSignal(dict)  # 角度数据
    error_occurred = pyqtSignal(str)  # 错误信息

    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.move_controller = None
        self.angle_querier = None
        self.command_queue = queue.Queue()
        self.running = True
        self.is_connected = False
        self.last_query_time = 0
        self.query_interval = 0.38  # 380ms查询间隔

    def connect_serial(self, port_name, baudrate, address):
        try:
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                timeout=0.5
            )

            self.move_controller = MoveControl(address=address)
            self.angle_querier = GetAngle()
            self.angle_querier.set_serial_port(self.serial_port)
            self.angle_querier.set_device_address(address)
            self.angle_querier.set_vertical_angle_mode('auto')

            self.is_connected = True
            return True, f"已连接到串口: {port_name} @ {baudrate}bps"

        except Exception as e:
            return False, f"串口连接失败: {e}"

    def disconnect_serial(self):
        self.is_connected = False
        if self.serial_port:
            try:
                if self.move_controller:
                    stop_cmd = self.move_controller.stop()
                    self.serial_port.write(stop_cmd)
                    time.sleep(0.1)

                self.serial_port.close()
                self.serial_port = None
            except Exception as e:
                self.error_occurred.emit(f"关闭串口时出错: {e}")

        self.move_controller = None
        self.angle_querier = None

    def send_command(self, command_bytes, description=""):
        if self.is_connected:
            self.command_queue.put((command_bytes, description))

    def set_query_interval(self, interval_ms):
        self.query_interval = interval_ms / 1000.0  # 转换为秒

    def run(self):
        while self.running:
            try:
                current_time = time.time()

                try:
                    if not self.command_queue.empty():
                        command_bytes, description = self.command_queue.get_nowait()
                        if self.serial_port and self.is_connected:
                            self.serial_port.write(command_bytes)
                            self.command_sent.emit(command_bytes, description)
                except queue.Empty:
                    pass

                if (self.is_connected and self.angle_querier and
                        current_time - self.last_query_time >= self.query_interval):

                    try:
                        result = self.angle_querier.query_angles()
                        if result:
                            self.angle_data.emit(result)
                        self.last_query_time = current_time
                    except Exception as e:
                        self.error_occurred.emit(f"角度查询失败: {e}")

                time.sleep(0.01)

            except Exception as e:
                self.error_occurred.emit(f"串口工作线程错误: {e}")
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.wait()


class OrbitronWorker(QThread):
    data_received = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = True
        self.query_interval = 1.0  # 1秒查询间隔

    def set_query_interval(self, interval_ms):
        self.query_interval = interval_ms / 1000.0  # 转换为秒

    def run(self):
        while self.running:
            try:
                data = get_orbitron_data()
                if data:
                    self.data_received.emit(data)
            except Exception as e:
                print(f"Orbitron查询错误: {e}")

            time.sleep(self.query_interval)

    def stop(self):
        self.running = False
        self.wait()


class MainApp(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.serial_worker = None
        self.orbitron_worker = None
        self.tracker = None
        self.is_tracking = False
        self.is_connected = False

        self.is_moving = False
        self.current_move_direction = None

        self.last_satellite_azimuth = None
        self.last_satellite_elevation = None

        self.command_lock = False
        self.command_lock_timer = QTimer()
        self.command_lock_timer.timeout.connect(self.release_command_lock)

        self.ui_update_timer = QTimer()
        self.ui_update_timer.timeout.connect(self.update_ui_status)
        self.ui_update_timer.start(100)

        self.setup_fonts()

        self.init_ui()

        self.init_zenith_tracker()

        self.init_new_controls()

        self.start_workers()

        self.connect_signals()

        self.update_connection_status(False)
        self.update_tracking_status("未跟踪")

    def setup_fonts(self):
        font = QtGui.QFont("幼圆")

        input_widgets = [
            self.h_in, self.d_in, self.address,
            self.h_delta, self.d_delta, self.angle_cycle,
            self.task_cycle, self.angle_resolution
        ]
        for widget in input_widgets:
            widget.setFont(font)

        combo_widgets = [
            self.ser_list, self.band_rate, self.angle_if
        ]
        for widget in combo_widgets:
            widget.setFont(font)

    def init_ui(self):
        self.refresh_serial_ports()

        baud_rates = ["2400", "4800", "9600", "19200", "38400", "57600", "115200"]
        self.band_rate.clear()
        self.band_rate.addItems(baud_rates)
        self.band_rate.setCurrentText("9600")
        self.address.setText("01")
        self.H.setText("N/A")
        self.D.setText("N/A")
        self.TX.setText("N/A")
        self.RX.setText("N/A")
        self.track_name.setText("N/A")
        self.track_h.setText("N/A")
        self.track_d.setText("N/A")
        self.status_text.setText("未跟踪")
        self.status_color.setStyleSheet("border-radius: 50%; background-color: rgb(128, 128, 128);")

        self.set_control_enabled(False)

    def init_new_controls(self):
        self.h_delta.setText("0")
        self.d_delta.setText("0")
        self.angle_cycle.setText("380")  # 默认380ms
        self.task_cycle.setText("1000")  # 默认1000ms
        self.angle_resolution.setText("0.1")  # 默认0.1°

        self.angle_if.clear()
        self.angle_if.addItems(["是", "否"])
        self.angle_if.setCurrentText("是")  # 默认启用

        self.angle_cycle.editingFinished.connect(self.update_angle_query_interval)
        self.task_cycle.editingFinished.connect(self.update_task_cycle)
        self.angle_if.currentTextChanged.connect(self.toggle_angle_query)

    def update_angle_query_interval(self):
        try:
            interval = int(self.angle_cycle.text())
            if interval < 50:  # 最小50ms
                interval = 50
                self.angle_cycle.setText("50")
            elif interval > 5000:  # 最大5000ms
                interval = 5000
                self.angle_cycle.setText("5000")

            if self.serial_worker:
                self.serial_worker.set_query_interval(interval)

            print(f"角度查询周期已更新: {interval}ms")

        except ValueError:
            self.angle_cycle.setText("380")  # 重置为默认值
            if self.serial_worker:
                self.serial_worker.set_query_interval(380)

    def update_task_cycle(self):
        try:
            interval = int(self.task_cycle.text())
            if interval < 100:  # 最小100ms
                interval = 100
                self.task_cycle.setText("100")
            elif interval > 10000:  # 最大10000ms
                interval = 10000
                self.task_cycle.setText("10000")

            if self.orbitron_worker:
                self.orbitron_worker.set_query_interval(interval)

            print(f"跟踪角度更新周期已更新: {interval}ms")

        except ValueError:
            self.task_cycle.setText("1000")  # 重置为默认值
            if self.orbitron_worker:
                self.orbitron_worker.set_query_interval(1000)

    def toggle_angle_query(self, enabled_text):
        enabled = enabled_text == "是"

        if enabled:
            print("角度查询已启用")
        else:
            self.H.setText("N/A")
            self.D.setText("N/A")
            self.TX.setText("N/A")
            self.RX.setText("N/A")
            print("角度查询已禁用")

    def init_zenith_tracker(self):
        try:
            self.tracker = ZenithTracker(self.star_plot)
            self.tracker.set_satellite_position(0, 45)
            self.tracker.set_tracker_angle(0, 45)
        except Exception as e:
            print(f"初始化天顶图失败: {e}")

    def start_workers(self):
        self.serial_worker = SerialWorker()
        self.serial_worker.command_sent.connect(self.handle_command_sent)
        self.serial_worker.angle_data.connect(self.handle_angle_data)
        self.serial_worker.error_occurred.connect(self.handle_serial_error)
        self.serial_worker.start()

        self.orbitron_worker = OrbitronWorker()
        self.orbitron_worker.data_received.connect(self.handle_orbitron_data)
        self.orbitron_worker.start()

        print("工作线程已启动")

    def connect_signals(self):
        self.ser_con.clicked.connect(self.toggle_serial_connection)

        self.up.pressed.connect(lambda: self.start_move('up'))
        self.up.released.connect(self.stop_move)
        self.down.pressed.connect(lambda: self.start_move('down'))
        self.down.released.connect(self.stop_move)
        self.left.pressed.connect(lambda: self.start_move('left'))
        self.left.released.connect(self.stop_move)
        self.right.pressed.connect(lambda: self.start_move('right'))
        self.right.released.connect(self.stop_move)
        self.stop.clicked.connect(lambda: self.stop_move())

        self.run_set.clicked.connect(self.set_angles)

        self.track_c.clicked.connect(self.toggle_tracking)

    def refresh_serial_ports(self):
        self.ser_list.clear()
        ports = serial.tools.list_ports.comports()

        for port in ports:
            description = port.description if port.description else port.name
            display_text = f"{port.name} - {description}"
            self.ser_list.addItem(display_text, port.name)

        if len(ports) == 0:
            self.ser_list.addItem("未发现串口", "")

    def toggle_serial_connection(self):
        if self.is_connected:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        if self.ser_list.currentData() is None:
            QtWidgets.QMessageBox.warning(self, "警告", "请选择串口")
            return

        port_name = self.ser_list.currentData()
        baudrate = int(self.band_rate.currentText())
        address = int(self.address.text(), 16) if self.address.text() else 0x01

        success, message = self.serial_worker.connect_serial(port_name, baudrate, address)

        if success:
            self.is_connected = True
            self.update_connection_status(True)
            self.set_control_enabled(True)

            self.ser_list.setEnabled(False)
            self.band_rate.setEnabled(False)
            self.address.setEnabled(False)

            print(message)
        else:
            QtWidgets.QMessageBox.critical(self, "连接失败", f"无法连接串口:\n{message}")

    def disconnect_serial(self):
        if self.is_tracking:
            self.stop_tracking()

        if self.is_moving:
            self.stop_move()

        self.serial_worker.disconnect_serial()
        self.is_connected = False
        self.update_connection_status(False)
        self.set_control_enabled(False)

        self.ser_list.setEnabled(True)
        self.band_rate.setEnabled(True)
        self.address.setEnabled(True)

        print("已断开串口连接")

    def update_connection_status(self, connected):
        self.is_connected = connected
        if connected:
            self.ser_con.setText("关闭串口")
        else:
            self.ser_con.setText("打开串口")
            self.status_text.setText("未连接")
            self.status_color.setStyleSheet("border-radius: 50%; background-color: rgb(128, 128, 128);")

    def set_control_enabled(self, enabled):
        self.up.setEnabled(enabled and not self.is_tracking)
        self.down.setEnabled(enabled and not self.is_tracking)
        self.left.setEnabled(enabled and not self.is_tracking)
        self.right.setEnabled(enabled and not self.is_tracking)
        self.stop.setEnabled(enabled)

        self.h_in.setEnabled(enabled and not self.is_tracking)
        self.d_in.setEnabled(enabled and not self.is_tracking)
        self.run_set.setEnabled(enabled and not self.is_tracking)

        self.track_c.setEnabled(enabled)

    def acquire_command_lock(self):
        if self.command_lock:
            return False

        self.command_lock = True
        self.command_lock_timer.start(200)
        return True

    def release_command_lock(self):
        self.command_lock = False
        self.command_lock_timer.stop()

    def send_command(self, command_bytes, description=""):
        if self.serial_worker:
            self.serial_worker.send_command(command_bytes, description)

    def start_move(self, direction):
        if not self.is_connected or self.is_tracking:
            return

        self.current_move_direction = direction

        if self.serial_worker.move_controller:
            commands = {
                'up': self.serial_worker.move_controller.move_up,
                'down': self.serial_worker.move_controller.move_down,
                'left': self.serial_worker.move_controller.move_left,
                'right': self.serial_worker.move_controller.move_right
            }

            if direction in commands:
                command_func = commands[direction]
                command_bytes = command_func()
                self.send_command(command_bytes, f"移动-{direction}")
                self.is_moving = True

    def stop_move(self):
        if not self.is_connected:
            return

        if self.serial_worker.move_controller:
            stop_cmd = self.serial_worker.move_controller.stop()
            self.send_command(stop_cmd, "停止移动")
            self.is_moving = False
            self.current_move_direction = None

    def set_angles(self):
        if not self.is_connected or self.is_tracking:
            return

        try:
            h_angle_text = self.h_in.text().strip()
            d_angle_text = self.d_in.text().strip()

            if not h_angle_text or not d_angle_text:
                QtWidgets.QMessageBox.warning(self, "警告", "请同时输入水平和垂直角度值")
                return

            h_angle = float(h_angle_text)
            d_angle = float(d_angle_text)

            if not (0 <= h_angle <= 360):
                QtWidgets.QMessageBox.warning(self, "警告", "水平角度必须在0-360度之间")
                return

            if not (-90 <= d_angle <= 90):
                QtWidgets.QMessageBox.warning(self, "警告", "垂直角度必须在-90到90度之间")
                return

            if self.serial_worker.move_controller:
                stop_cmd = self.serial_worker.move_controller.stop()
                self.send_command(stop_cmd, "停止移动")

            h_cmd = self.serial_worker.move_controller.set_horizontal_angle(h_angle)
            self.send_command(h_cmd, f"设置水平角 {h_angle}°")

            d_cmd = self.serial_worker.move_controller.set_vertical_angle(d_angle)
            self.send_command(d_cmd, f"设置垂直角 {d_angle}°")

            self.h_in.clear()
            self.d_in.clear()

            print(f"已设置角度: 水平{h_angle}°, 垂直{d_angle}°")

        except ValueError:
            QtWidgets.QMessageBox.warning(self, "警告", "请输入有效的数字")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"设置角度失败:\n{str(e)}")

    def toggle_tracking(self):
        if not self.is_connected:
            QtWidgets.QMessageBox.warning(self, "警告", "请先连接串口")
            return

        if self.is_tracking:
            self.stop_tracking()
        else:
            self.start_tracking()

    def start_tracking(self):
        self.is_tracking = True
        self.track_c.setText("停止跟踪")

        self.last_satellite_azimuth = None
        self.last_satellite_elevation = None

        self.set_control_enabled(True)

        print("开始卫星跟踪，手动控制已禁用")

    def stop_tracking(self):
        self.is_tracking = False
        self.track_c.setText("开始跟踪")

        self.set_control_enabled(True)

        if self.serial_worker and self.serial_worker.move_controller:
            stop_cmd = self.serial_worker.move_controller.stop()
            self.send_command(stop_cmd, "停止跟踪")

        print("停止卫星跟踪，手动控制已启用")

    def update_tracking_status(self, status):
        status_map = {
            "跟踪中": ("rgb(0, 255, 0)", "跟踪中"),
            "已落下": ("rgb(255, 0, 0)", "已落下"),
            "未跟踪": ("rgb(128, 128, 128)", "未跟踪")
        }

        if status in status_map:
            color, text = status_map[status]
            self.status_color.setStyleSheet(f"border-radius: 50%; background-color: {color};")
            self.status_text.setText(text)

    def apply_angle_delta(self, azimuth, elevation):
        try:
            h_delta_val = float(self.h_delta.text())
            d_delta_val = float(self.d_delta.text())

            azimuth_with_delta = azimuth - h_delta_val
            elevation_with_delta = elevation - d_delta_val

            azimuth_with_delta = azimuth_with_delta % 360
            if elevation_with_delta > 90:
                elevation_with_delta = 90
            elif elevation_with_delta < -90:
                elevation_with_delta = -90

            return azimuth_with_delta, elevation_with_delta

        except ValueError:
            print(f"角度差输入无效，使用默认值0")
            return azimuth, elevation

    def handle_command_sent(self, command_bytes, description):
        tx_hex = ' '.join([f'{b:02X}' for b in command_bytes])
        self.TX.setText(tx_hex)

    def handle_angle_data(self, result):
        if self.angle_if.currentText() != "是":
            return

        if result and result.get('success'):
            h_angle = result.get('horizontal_angle', 0)
            d_angle = result.get('vertical_angle', 0)

            self.H.setText(f"{h_angle:.1f}")
            self.D.setText(f"{d_angle:.1f}")

            if 'tx_horizontal' in result and result['tx_horizontal']:
                tx_hex = ' '.join([f'{b:02X}' for b in result['tx_horizontal']])
                self.TX.setText(tx_hex)

            if 'rx_horizontal' in result and result['rx_horizontal']:
                rx_hex = ' '.join([f'{b:02X}' for b in result['rx_horizontal']])
                self.RX.setText(rx_hex)

            if self.tracker:
                self.tracker.set_tracker_angle(h_angle, d_angle)

    def handle_orbitron_data(self, data):
        if data and data.get('status') == 'tracking':
            satellite = data.get('satellite', 'N/A')
            azimuth = data.get('azimuth', 0)
            elevation = data.get('elevation', 0)

            self.track_name.setText(satellite)
            self.track_h.setText(f"{azimuth:.1f}")
            self.track_d.setText(f"{elevation:.1f}")

            azimuth_with_delta, elevation_with_delta = self.apply_angle_delta(azimuth, elevation)

            if self.tracker:
                self.tracker.set_satellite_position(azimuth, elevation)

            if elevation < 0:
                status = "已落下"
                if self.is_tracking:
                    self.stop_tracking()
            else:
                status = "跟踪中" if self.is_tracking else "未跟踪"

            self.update_tracking_status(status)

            if self.is_tracking and elevation >= 0 and self.serial_worker and self.serial_worker.move_controller:
                self.send_tracking_commands(azimuth, elevation)

        else:
            self.track_name.setText("N/A")
            self.track_h.setText("N/A")
            self.track_d.setText("N/A")
            self.update_tracking_status("未跟踪")

    def send_tracking_commands(self, azimuth, elevation):
        if not self.is_connected or not self.serial_worker.move_controller:
            return

        azimuth_with_delta, elevation_with_delta = self.apply_angle_delta(azimuth, elevation)

        position_changed = False

        if (self.last_satellite_azimuth is None or
                self.last_satellite_elevation is None):
            position_changed = True
        else:
            az_diff = abs(azimuth_with_delta - self.last_satellite_azimuth)
            el_diff = abs(elevation_with_delta - self.last_satellite_elevation)

            try:
                threshold = float(self.angle_resolution.text())
                if threshold <= 0:
                    threshold = 0.1
            except ValueError:
                threshold = 0.1

            if (az_diff > threshold or el_diff > threshold):
                position_changed = True

        if position_changed:
            self.last_satellite_azimuth = azimuth_with_delta
            self.last_satellite_elevation = elevation_with_delta

            if self.acquire_command_lock():

                stop_cmd = self.serial_worker.move_controller.stop()
                self.send_command(stop_cmd, "停止移动")

                h_cmd = self.serial_worker.move_controller.set_horizontal_angle(azimuth_with_delta)
                self.send_command(h_cmd, f"跟踪水平角 {azimuth}°->{azimuth_with_delta:.1f}°")

                d_cmd = self.serial_worker.move_controller.set_vertical_angle(elevation_with_delta)
                self.send_command(d_cmd, f"跟踪垂直角 {elevation}°->{elevation_with_delta:.1f}°")

                print(f"发送跟踪命令: 方位{azimuth}°->{azimuth_with_delta:.1f}°, "
                      f"仰角{elevation}°->{elevation_with_delta:.1f}°")

    def handle_serial_error(self, error_msg):
        print(f"串口错误: {error_msg}")

    def update_ui_status(self):
        pass

    def closeEvent(self, event):
        if self.is_tracking:
            self.stop_tracking()

        if self.serial_worker:
            self.serial_worker.stop()

        if self.orbitron_worker:
            self.orbitron_worker.stop()

        self.ui_update_timer.stop()
        self.command_lock_timer.stop()

        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)

    font = QtGui.QFont("幼圆", 9)
    app.setFont(font)

    window = MainApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()