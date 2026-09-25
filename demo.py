from py_idraw import IDraw, Unit, CoordinateMode
import serial.tools.list_ports

IDRAW_VID = 0x1A86
IDRAW_PID = 0x8040

def find_device():
    for port in serial.tools.list_ports.comports():
        if port.vid == IDRAW_VID and port.pid == IDRAW_PID:
            print(f"Port:         {port.device}")
            print(f"Description:  {port.description}")
            print(f"Manufacturer: {port.manufacturer}")
            print(f"VID:          {port.vid}")
            print(f"PID:          {port.pid}")
            print()
            return port.device
    return None

def run_demo():
    try:
        idraw = IDraw(find_device(), 4, 1000)

        # draw a square
        idraw.lower_pen()
        idraw.move(0, 10)
        idraw.move(10, 10)
        idraw.move(10, 0)
        idraw.move(0, 0)
        idraw.raise_pen()

    except Exception as e:
        print(f"Error: {e}")

run_demo()