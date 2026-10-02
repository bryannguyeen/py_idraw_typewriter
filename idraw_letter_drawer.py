from hershey_font import HersheyFont
from py_idraw import IDraw
import time
import logging

logging.basicConfig(filename="debug.log", level=logging.DEBUG)

class Drawer:
    font_size: float

    def __init__(self, idraw: IDraw, font: HersheyFont, font_size = 32):
        self.font = font
        self.idraw = idraw
        self.font_size = font_size

        self.current_pos = complex(0, 0)

    def font_size_in_mm(self):
        return self.font_size / 72.0 * 25.4 # convert pt to inches, then mm

    # return the deltax deltay for the next position
    def draw_internal(self, char: str, offset: complex = 0):
        assert len(char) == 1

        scale = self.font_size_in_mm() / self.font.body_height

        # newline sets to position to lower line, leftmost
        if char == "\n":
            return complex(-offset.real, -self.font.body_height * scale * 1.1)

        start_time = time.monotonic()

        glyph = self.font.get_or_default(char)
        for subpath in glyph.path.continuous_subpaths():
            if (len(subpath) == 0):
                continue

            # go to starting position and lower pen
            transformed_subpath = subpath.scaled(scale).translated(offset)
            starting_pos = transformed_subpath[0].start
            self.idraw.quick_move(starting_pos.real, starting_pos.imag)
            self.idraw.lower_pen()

            # a subpath is continuous, so the end of each previous segment is the start of the next segment
            # i.e. no need to lift the pen for continuous lines
            for segment in transformed_subpath:
                segment_type = type(segment).__name__

                match segment_type:
                    case "Line": # is a straight line
                        dest_pos = segment.end
                        self.idraw.move(dest_pos.real, dest_pos.imag)
                        next
                    case _: # is a curve, need to sample points
                        samples = 4
                        for t in range(1, samples + 1):
                            dest_pos = segment.point(float(t) / float(samples))
                            self.idraw.mov(dest_pos.real, dest_pos.imag)
                        next
            
            # raise the pen to go to the next subpath
            self.idraw.raise_pen()
        elapsed_time =  time.monotonic() - start_time

        length = float(glyph.path.length()) * scale
        if length != None and length > 1:

            # subtract the estimated drawing time with time it took to calculate translated coordinates and send gcode
            # to get the remaining estimated time
            estimated_drawing_time = (length / self.idraw.current_speed) * 60.0 - elapsed_time
            if (estimated_drawing_time > 0):
                time.sleep(estimated_drawing_time)


        # return x and y advancement
        return complex(glyph.width * scale, 0)

    def draw(self, char: str):
        assert len(char) == 1
        self.current_pos += self.draw_internal(char, self.current_pos)

    def exit(self):
        self.idraw.quick_move(0.0, 0.0)

    def wait_position(self):
        self.idraw.quick_move(self.current_pos.real, self.current_pos.imag)