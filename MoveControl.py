class MoveControl:
    PELCOD_HEAD = 0xFF
    HEAD_GO_LEFT = 0x04
    HEAD_GO_RIGHT = 0x02
    HEAD_GO_UP = 0x10
    HEAD_GO_DOWN = 0x08
    HEAD_STOP = 0x00

    CMD_HORIZONTAL_ABS = 0x4B
    CMD_VERTICAL_ABS = 0x4D

    def __init__(self, address: int = 0x01):
        if not 0x01 <= address <= 0xFF:
            raise ValueError(f"设备地址必须在0x01到0xFF之间")

        self.address = address
        self._speed = 0x20

    def set_address(self, address: int) -> bool:
        if not 0x01 <= address <= 0xFF:
            return False

        self.address = address
        return True

    def _calculate_checksum(self, data_bytes: list) -> int:
        return sum(data_bytes) & 0xFF

    def _create_command_frame(self, cmd1: int, cmd2: int, data1: int = 0, data2: int = 0) -> bytes:
        frame = [
            self.PELCOD_HEAD,
            self.address,
            cmd1,
            cmd2,
            data1,
            data2
        ]

        checksum = self._calculate_checksum(frame[1:])
        frame.append(checksum)

        return bytes(frame)


    def move_up(self) -> bytes:
        return self._create_command_frame(0x00, self.HEAD_GO_UP, 0x00, self._speed)

    def move_down(self) -> bytes:
        return self._create_command_frame(0x00, self.HEAD_GO_DOWN, 0x00, self._speed)

    def move_left(self) -> bytes:
        return self._create_command_frame(0x00, self.HEAD_GO_LEFT, self._speed, 0x00)

    def move_right(self) -> bytes:
        return self._create_command_frame(0x00, self.HEAD_GO_RIGHT, self._speed, 0x00)

    def stop(self) -> bytes:
        return self._create_command_frame(0x00, self.HEAD_STOP, 0x00, 0x00)


    def set_horizontal_angle(self, angle: float) -> bytes:
        if angle < 0 or angle > 360:
            raise ValueError(f"水平角度必须在0-360度之间")

        encoded = int(angle * 100)

        data1 = (encoded >> 8) & 0xFF
        data2 = encoded & 0xFF

        return self._create_command_frame(0x00, self.CMD_HORIZONTAL_ABS, data1, data2)

    def set_vertical_angle(self, angle: float) -> bytes:
        if angle < -90 or angle > 90:
            raise ValueError(f"垂直角度必须在-90到+90度之间")

        if angle >= 0:
            encoded = int(angle * 100)
        else:
            encoded = 36000 - int(-angle * 100)

        encoded = max(0, min(encoded, 36000))

        data1 = (encoded >> 8) & 0xFF
        data2 = encoded & 0xFF

        return self._create_command_frame(0x00, self.CMD_VERTICAL_ABS, data1, data2)

    def get_version(self) -> str:
        return "PELCO-D MoveControl v1.2 (修正垂直角度方向)"