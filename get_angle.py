import time
from typing import Optional, Tuple, Dict, Any


class GetAngle:

    def __init__(self):
        self.serial_port = None

        self.device_address = 0x01  # 设备地址，默认1
        self.timeout_ms = 350  # 查询超时时间(ms)
        self.retry_count = 3  # 重试次数
        self.query_interval = 0.05  # 查询间隔(s)

        self.last_horizontal_angle = None
        self.last_vertical_angle = None

        self.vertical_angle_mode = 'auto'

    def set_serial_port(self, serial_port):
        self.serial_port = serial_port

    def set_device_address(self, address: int):
        if 1 <= address <= 255:
            self.device_address = address
            return True
        else:
            return False

    def set_vertical_angle_mode(self, mode: str):
        if mode in ['auto', 'direct', 'negative']:
            self.vertical_angle_mode = mode
            return True
        else:
            return False

    def _calculate_checksum(self, data: list) -> int:
        return sum(data) & 0xFF

    def _build_query_command(self, command_byte: int) -> bytes:
        # 构建数据部分（不包括0xFF）
        data = [
            self.device_address,  # 地址默认为1 (0x01)
            0x00,  # 固定为0
            command_byte,  # 命令字节
            0x00,  # 数据1固定为0
            0x00  # 数据2固定为0
        ]

        checksum = self._calculate_checksum(data)

        cmd = [0xFF] + data + [checksum]

        return bytes(cmd)

    def _convert_vertical_angle(self, angle_raw: int) -> float:
        if angle_raw is None:
            return None

        angle_deg = angle_raw / 100.0

        if self.vertical_angle_mode == 'direct':
            return angle_deg

        elif self.vertical_angle_mode == 'negative':
            if angle_deg > 180.0:
                return angle_deg - 360.0
            else:
                return angle_deg

        else:
            if angle_deg <= 90.0 or angle_deg >= 270.0:
                if angle_deg > 180.0:
                    return angle_deg - 360.0
                else:
                    return angle_deg

            elif angle_deg > 180.0:
                return angle_deg - 360.0

            else:
                return angle_deg

    def _parse_response(self, response: bytes, expected_cmd: int,
                        is_vertical: bool = False) -> Optional[float]:
        if len(response) < 7:
            return None

        if response[0] != 0xFF:
            return None

        if response[1] != self.device_address:
            return None

        if response[3] != expected_cmd:
            return None

        calc_csum = self._calculate_checksum(response[1:6])
        if calc_csum != response[6]:
            return None

        angle_raw = (response[4] << 8) | response[5]

        if is_vertical:
            angle_deg = self._convert_vertical_angle(angle_raw)
        else:
            angle_deg = angle_raw / 100.0 if angle_raw is not None else None

        return angle_deg

    def _query_single_angle(self, is_horizontal: bool) -> Tuple[Optional[float], bytes, bytes]:
        if not self.serial_port:
            return None, b'', b''

        query_cmd = 0x51 if is_horizontal else 0x53
        cmd_bytes = self._build_query_command(query_cmd)

        try:
            self.serial_port.write(cmd_bytes)
        except Exception as e:
            print(f"发送命令失败: {e}")
            return None, cmd_bytes, b''

        try:
            self.serial_port.reset_input_buffer()

            start_time = time.time()
            response = b''

            while time.time() - start_time < (self.timeout_ms / 1000.0):
                if self.serial_port.in_waiting > 0:
                    response += self.serial_port.read(self.serial_port.in_waiting)
                    if len(response) >= 7:
                        break
                time.sleep(0.001)

            response = response[:7]

        except Exception as e:
            print(f"接收响应失败: {e}")
            return None, cmd_bytes, b''

        expected_resp = query_cmd + 0x08
        angle_deg = self._parse_response(response, expected_resp, not is_horizontal)

        return angle_deg, cmd_bytes, response

    def query_angles(self) -> Dict[str, Any]:
        if not self.serial_port:
            return {
                'success': False,
                'horizontal_angle': None,
                'vertical_angle': None,
                'horizontal_raw': None,
                'vertical_raw': None,
                'tx_horizontal': b'',
                'rx_horizontal': b'',
                'tx_vertical': b'',
                'rx_vertical': b'',
                'device_address': self.device_address,
                'error_message': '未连接串口',
                'vertical_mode': self.vertical_angle_mode
            }

        result = {
            'success': False,
            'horizontal_angle': None,
            'vertical_angle': None,
            'horizontal_raw': None,
            'vertical_raw': None,
            'tx_horizontal': b'',
            'rx_horizontal': b'',
            'tx_vertical': b'',
            'rx_vertical': b'',
            'device_address': self.device_address,
            'error_message': '',
            'vertical_mode': self.vertical_angle_mode
        }

        for retry in range(self.retry_count):
            h_angle, tx_h, rx_h = self._query_single_angle(True)

            result['tx_horizontal'] = tx_h
            result['rx_horizontal'] = rx_h

            if h_angle is not None:
                result['horizontal_angle'] = h_angle
                if rx_h and len(rx_h) >= 7:
                    result['horizontal_raw'] = (rx_h[4] << 8) | rx_h[5]
                self.last_horizontal_angle = h_angle
                break
            elif retry < self.retry_count - 1:
                time.sleep(0.05)

        time.sleep(self.query_interval)

        for retry in range(self.retry_count):
            v_angle, tx_v, rx_v = self._query_single_angle(False)

            result['tx_vertical'] = tx_v
            result['rx_vertical'] = rx_v

            if v_angle is not None:
                result['vertical_angle'] = v_angle
                if rx_v and len(rx_v) >= 7:
                    result['vertical_raw'] = (rx_v[4] << 8) | rx_v[5]
                self.last_vertical_angle = v_angle
                break
            elif retry < self.retry_count - 1:
                time.sleep(0.05)

        if result['horizontal_angle'] is not None and result['vertical_angle'] is not None:
            result['success'] = True
        else:
            result['error_message'] = '角度查询失败'

        return result

    def format_result(self, result: Dict[str, Any]) -> str:
        if not result['success']:
            return f"查询失败: {result['error_message']}"

        def format_bytes(data):
            return ' '.join([f'{b:02X}' for b in data]) if data else '无数据'

        lines = [
            f"查询成功 - 设备地址: 0x{result['device_address']:02X}",
            f"垂直角度模式: {result['vertical_mode']}",
            f"水平角度: {result['horizontal_angle']:.2f}°",
            f"垂直角度: {result['vertical_angle']:.2f}°",
        ]

        if result['horizontal_raw'] is not None:
            lines.append(f"水平原始值: {result['horizontal_raw']} (0x{result['horizontal_raw']:04X})")
        if result['vertical_raw'] is not None:
            lines.append(f"垂直原始值: {result['vertical_raw']} (0x{result['vertical_raw']:04X})")

        lines.extend([
            f"{format_bytes(result['tx_horizontal'])}",
            f"          {format_bytes(result['rx_horizontal'])}",
            f"{format_bytes(result['tx_vertical'])}",
            f"          {format_bytes(result['rx_vertical'])}",
        ])

        return '\n'.join(lines)

    def get_last_angles(self) -> Tuple[Optional[float], Optional[float]]:
        return self.last_horizontal_angle, self.last_vertical_angle

    def get_angle_representation(self, raw_value: int, is_vertical: bool = False) -> Dict[str, Any]:
        if raw_value is None:
            return {}

        direct_angle = raw_value / 100.0

        result = {
            'raw_value': raw_value,
            'raw_hex': f"0x{raw_value:04X}",
            'direct_angle': direct_angle,
        }

        if is_vertical:
            negative_angle = direct_angle - 360.0 if direct_angle > 180.0 else direct_angle
            if 0 <= raw_value <= 9000:  # 0-90度
                angle_type = "正角度 (0-90°)"
            elif 27000 <= raw_value <= 35999:  # 270-360度
                angle_type = "负角度 (-90°到0°)"
                negative_angle = direct_angle - 360.0
            elif 18000 <= raw_value < 27000:  # 180-270度
                angle_type = "负角度 (-180°到-90°)"
                negative_angle = direct_angle - 360.0
            elif 9000 < raw_value < 18000:  # 90-180度
                angle_type = "正角度 (90-180°)"
            else:
                angle_type = "未知范围"

            result.update({
                'negative_representation': negative_angle,
                'angle_type': angle_type,
                'suggested_angle': negative_angle if direct_angle > 180.0 else direct_angle
            })

        return result