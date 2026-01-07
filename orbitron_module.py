import sys
import time
import re
import threading
from typing import Dict, Any, Optional, Callable, List
import win32ui
import dde


class OrbitronParser:
    @staticmethod
    def parse_tracking_data_ex(raw_data: str) -> Dict[str, Any]:
        if not raw_data or raw_data.strip() == "":
            return {"status": "no_data", "raw": raw_data}

        result = {"status": "tracking", "raw": raw_data, "errors": []}

        try:
            pattern = r'(\w+)(?:"([^"]*)"|([^"\s]+))?'
            matches = re.findall(pattern, raw_data)

            for field, quoted_val, unquoted_val in matches:
                field = field.upper()
                value = quoted_val if quoted_val else unquoted_val

                if not value:
                    continue

                if field in ["AZ", "EL", "RA", "RR", "LO", "LA", "AL"]:
                    try:
                        result[field.lower()] = float(value)
                    except ValueError:
                        result[field.lower()] = 0.0
                        result["errors"].append(f"字段 {field} 值转换失败: {value}")
                elif field in ["DN", "UP"]:
                    try:
                        result[field.lower() + "_freq"] = int(float(value))
                    except ValueError:
                        result[field.lower() + "_freq"] = 0
                        result["errors"].append(f"字段 {field} 值转换失败: {value}")
                elif field in ["SN", "UM", "DM", "AOS"]:
                    result[field.lower()] = value
                elif field in ["TU", "TL"]:
                    result[field.lower() + "_time"] = value
                else:
                    result[field.lower()] = value

            if not result.get("sn") and "SN" in raw_data:
                sn_match = re.search(r'SN"([^"]+)"', raw_data)
                if sn_match:
                    result["sn"] = sn_match.group(1)

            if "az" not in result:
                az_match = re.search(r'AZ([-\d.]+)', raw_data)
                if az_match:
                    try:
                        result["az"] = float(az_match.group(1))
                    except:
                        pass

            if "el" not in result:
                el_match = re.search(r'EL([-\d.]+)', raw_data)
                if el_match:
                    try:
                        result["el"] = float(el_match.group(1))
                    except:
                        pass

        except Exception as e:
            result["status"] = "parse_error"
            result["errors"].append(f"解析异常: {str(e)}")

        return result

    @staticmethod
    def parse_tracking_data(raw_data: str) -> Dict[str, Any]:
        if not raw_data or raw_data.strip() == "":
            return {"status": "no_data", "raw": raw_data}

        result = {"status": "tracking", "raw": raw_data}

        try:
            parts = raw_data.split()
            for part in parts:
                if part.startswith("SN"):
                    result["sn"] = part[2:]
                elif part.startswith("AZ"):
                    result["az"] = float(part[2:])
                elif part.startswith("EL"):
                    result["el"] = float(part[2:])
                elif part.startswith("DN"):
                    result["dn_freq"] = int(float(part[2:]))
                elif part.startswith("UP"):
                    result["up_freq"] = int(float(part[2:]))
                elif part.startswith("DM"):
                    result["dm"] = part[2:]
                elif part.startswith("UM"):
                    result["um"] = part[2:]
        except Exception as e:
            result["status"] = "parse_error"
            result["error"] = str(e)

        return result


class OrbitronDDE:
    def __init__(self, service: str = "Orbitron", topic: str = "Tracking"):
        self.service = service
        self.topic = topic
        self.conversation = None
        self.server = None
        self.parser = OrbitronParser()
        self.is_connected = False

        self.current_data = {
            "tracking_data_ex": None,
            "tracking_data": None,
            "timestamp": None
        }

        self.data_callbacks = []

        self._monitor_thread = None
        self._stop_monitor = threading.Event()

    def connect(self) -> bool:
        try:
            if self.is_connected:
                self.disconnect()

            self.server = dde.CreateServer()
            server_name = f"OrbitronDataModule_{int(time.time() * 1000)}"
            self.server.Create(server_name)

            self.conversation = dde.CreateConversation(self.server)
            self.conversation.ConnectTo(self.service, self.topic)
            self.is_connected = True
            return True
        except Exception as e:
            print(f"连接失败: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        try:
            if self.conversation:
                self.conversation.Disconnect()
            if self.server:
                try:
                    pass
                except:
                    pass
            self.is_connected = False
            self.conversation = None
            self.server = None
        except Exception as e:
            print(f"断开连接时出错: {e}")

    def read_data(self) -> Dict[str, Any]:
        if not self.is_connected:
            return {"status": "disconnected", "error": "未连接到 Orbitron"}

        result = {
            "status": "success",
            "timestamp": time.time(),
            "tracking_data_ex": None,
            "tracking_data": None
        }

        try:
            raw_data_ex = self.conversation.Request("TrackingDataEx")
            parsed_ex = self.parser.parse_tracking_data_ex(raw_data_ex)
            result["tracking_data_ex"] = parsed_ex

            raw_data = self.conversation.Request("TrackingData")
            parsed = self.parser.parse_tracking_data(raw_data)
            result["tracking_data"] = parsed

            self.current_data = result.copy()

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            result.setdefault("tracking_data_ex", None)
            result.setdefault("tracking_data", None)

        return result

    def get_satellite_info(self) -> Dict[str, Any]:
        data = self.read_data()

        if data.get("status") in ["disconnected", "error"]:
            return {"status": "error", "error": data.get("error", "连接或读取错误")}

        tracking_data_ex = data.get("tracking_data_ex")
        tracking_data = data.get("tracking_data")

        if tracking_data_ex and tracking_data_ex.get("status") == "tracking":
            parsed = tracking_data_ex
        elif tracking_data and tracking_data.get("status") == "tracking":
            parsed = tracking_data
        else:
            return {"status": "no_tracking", "timestamp": data.get("timestamp")}

        info = {
            "status": "tracking",
            "satellite": parsed.get("sn", "Unknown"),
            "azimuth": parsed.get("az", 0.0),
            "elevation": parsed.get("el", 0.0),
            "uplink_freq": parsed.get("up_freq", 0),
            "downlink_freq": parsed.get("dn_freq", 0),
            "timestamp": data.get("timestamp", time.time())
        }

        if "ra" in parsed:
            info["range"] = parsed.get("ra", 0.0)
        if "rr" in parsed:
            info["range_rate"] = parsed.get("rr", 0.0)

        return info

    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        self.data_callbacks.append(callback)

    def start_monitoring(self, interval: float = 2.0):
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self):
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)

    def _monitor_loop(self, interval: float):
        while not self._stop_monitor.is_set():
            try:
                data = self.read_data()

                for callback in self.data_callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"回调函数执行失败: {e}")

                time.sleep(interval)
            except Exception as e:
                print(f"监控循环错误: {e}")
                time.sleep(interval)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_monitoring()
        self.disconnect()


class _OrbitronManager:
    _instance = None
    _orbitron_instance = None
    _connection_count = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_orbitron(self):
        if self._orbitron_instance is None:
            self._orbitron_instance = OrbitronDDE()
            if not self._orbitron_instance.connect():
                self._orbitron_instance = None
                return None
        self._connection_count += 1
        return self._orbitron_instance

    def release_orbitron(self):
        self._connection_count -= 1
        if self._connection_count <= 0 and self._orbitron_instance:
            self._orbitron_instance.disconnect()
            self._orbitron_instance = None
            self._connection_count = 0


_orbitron_manager = _OrbitronManager()


def get_orbitron_data() -> Dict[str, Any]:
    try:
        orbitron = _orbitron_manager.get_orbitron()
        if orbitron is None:
            return {"status": "error", "error": "无法连接到 Orbitron"}

        data = orbitron.get_satellite_info()

        return data
    except Exception as e:
        return {"status": "error", "error": str(e)}


def cleanup_orbitron_connections():
    _orbitron_manager.release_orbitron()


def example_usage():
    print("=" * 70)
    print("Orbitron DDE 模块使用示例 (修复版)")
    print("=" * 70)

    try:
        print("\n1. 测试多次调用 get_orbitron_data():")
        for i in range(3):
            data = get_orbitron_data()
            status = data.get("status", "unknown")
            if status == "tracking":
                print(f"   调用 #{i + 1}: {data.get('satellite', 'Unknown')} - "
                      f"AZ:{data.get('azimuth', 0):.1f}° EL:{data.get('elevation', 0):.1f}°")
            else:
                print(f"   调用 #{i + 1}: {status} - {data.get('error', '')}")

        print("\n2. 使用 OrbitronDDE 类:")
        orbitron = OrbitronDDE()
        if orbitron.connect():
            info = orbitron.get_satellite_info()
            status = info.get("status", "unknown")
            if status == 'tracking':
                print(f"   卫星: {info.get('satellite', 'Unknown')}")
                print(f"   方位: {info.get('azimuth', 0):.1f}°, 仰角: {info.get('elevation', 0):.1f}°")
            else:
                print(f"   状态: {status}")
            orbitron.disconnect()
        else:
            print("   无法连接到 Orbitron")

        cleanup_orbitron_connections()
        print("\n 测试完成，连接已清理")

    except Exception as e:
        print(f"\n 测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        import win32ui
        import dde
        import re
    except ImportError:
        print(" 缺少必要的库")
        print("请安装: pip install pywin32")
        sys.exit(1)

    example_usage()