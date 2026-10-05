from enum import Enum
import serial

BAUD_RATE = 115200  # Common rates: 115200 or 250000

class Unit(Enum):
    MILLIMETER = 0
    INCHES = 1

class CoordinateMode(Enum):
    ABSOLUTE = 0
    RELATIVE = 1

class IDraw:

    def __init__(self, port, pen_down_height: float = 2, default_speed: float = 1000, unit: Unit = Unit.MILLIMETER):
        assert pen_down_height >= 1

        self.ser = serial.Serial(port, BAUD_RATE, timeout=2)
        self.current_speed = default_speed
        self.default_speed = default_speed
        self.pen_down_height = pen_down_height

        self.set_speed(default_speed)
        self.set_coordinate_mode(CoordinateMode.ABSOLUTE)
        self.set_unit(unit)
        self.set_current_position_as_x0y0()

    def send_gcode(self, gcode: str):
        formatted = gcode
        if not formatted.endswith('\n') and not formatted.endswith('\r'):
            formatted = formatted + '\n'
        self.ser.write(formatted.encode('utf-8'))
        self.ser.flush()

        while True:
            resp = self.ser.readline().decode('utf-8').strip().lower()
            if resp == 'ok':
                return
            if resp.startswith('error'):
                print(resp)
                return
            if resp.startswith('busy'):
                print(resp)
                return

    def go_home(self):
        self.send_gcode("$H\r")

    def wait_for_idle(self):
        return

    def set_unit(self, unit: Unit):
        """
        Sets the scale of the plotter to either MILLIMETER or INCHES
        """
        if unit == Unit.MILLIMETER:
            self.send_gcode("G21")
        elif unit == Unit.INCHES:
            self.send_gcode("G20")

    def set_coordinate_mode(self, mode: CoordinateMode):
        """
        Sets the coordinate mode to ABSOLUTE or RELATIVE
        """
        if mode == CoordinateMode.ABSOLUTE:
            self.send_gcode("G90")
            self.coordiate_mode = mode
        elif mode == CoordinateMode.RELATIVE:
            self.send_gcode("G91")
            self.coordiate_mode = mode

    def set_speed(self, speed: float):
        assert speed >= 50
        assert speed <= 5000

        self.send_gcode(f"F{speed}")

    def move(self, x: float, y: float):
        self.send_gcode(f"G01 X{x} Y{y}")

    def quick_move(self, x: float, y: float):
        self.send_gcode(f"G00 X{x} Y{y}")

    def move_x(self, x: float):
        self.send_gcode(f"G01 X{x}")

    def move_y(self, y: float):
        self.send_gcode(f"G01 Y{y}")

    def set_height(self, height: float):
        assert height >= 0
        assert height <= 10

        if self.coordiate_mode == CoordinateMode.ABSOLUTE:
            self.send_gcode(f"G00 Z{height}")
        else:
            temp = self.coordiate_mode
            self.set_coordinate_mode(CoordinateMode.ABSOLUTE)
            self.send_gcode(f"G00 Z{height}")
            self.set_coordinate_mode(temp)

    def arc_cw(self, x: float, y: float, i: float, j: float):
        self.send_gcode(f"G02 X{x} Y{y} I{i} J{j}")

    def arc_ccw(self, x: float, y: float, i: float, j: float):
        self.send_gcode(f"G03 X{x} Y{y} I{i} J{j}")

    def lower_pen(self):
        self.set_height(self.pen_down_height)

    def raise_pen(self):
        self.set_height(0)

    def set_current_position_as_x0y0(self):
        self.send_gcode("G92 X0Y0")
