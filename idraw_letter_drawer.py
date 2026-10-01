from hershey_font import HersheyFont
from py_idraw import IDraw
import time

class Drawer:
    def __init__(self, idraw: IDraw, font: HersheyFont, port = None):
        self.font = font
        self.idraw = idraw

        self.current_pos = complex(0, 0)

    # return the deltax deltay for the next position
    def draw_internal(self, char: str, offset: complex = 0):
        assert len(char) == 1

        # newline sets to position to lower line, leftmost
        if char == "\n":
            return complex(-offset.real, -self.font.height)

        glyph = self.font.get_or_default(char)
        start_time = time.monotonic()
        for subpath in glyph.path.continuous_subpaths():
            if (len(subpath) == 0):
                continue

            translated_subpath = subpath.translated(offset)
            starting_pos = translated_subpath[0].start
            self.idraw.quick_move(starting_pos.real, starting_pos.imag)
            self.idraw.lower_pen()

            # path is continuous, so the end of the previous segment is the start of the next segment
            for segment in translated_subpath:
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
            self.idraw.raise_pen()
        elapsed_time =  time.monotonic() - start_time

        length = float(glyph.path.length())
        if length != None and length > 1:
            estimated_drawing_time = (length / self.idraw.current_speed) * 60.0 - elapsed_time
            if (estimated_drawing_time > 0):
                time.sleep(estimated_drawing_time)


        # return x and y advancement
        return complex(glyph.width, 0)

    def draw(self, char: str):
        assert len(char) == 1
        self.current_pos += self.draw_internal(char, self.current_pos)
