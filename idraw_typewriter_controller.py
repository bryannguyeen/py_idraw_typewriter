from collections import deque
import curses
from curses import wrapper
from idraw_writing_service import Service, WriteTask, SetFontSizeTask
import threading
import logging
from idraw_letter_drawer import Drawer
from hershey_font import HersheyFont
from py_idraw import IDraw
import serial.tools.list_ports

IDRAW_VID = 0x1A86
IDRAW_PID = 0x8040

IGNORABLES = ["Ȣ"]

SPECIAL_ASCIIS = [8, 10, 13, 24, 127, curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT]

logging.basicConfig(filename="debug.log", level=logging.DEBUG) # in case of logging

def find_device():
    for port in serial.tools.list_ports.comports():
        if port.vid == IDRAW_VID and port.pid == IDRAW_PID:
            return port.device
    return None

class Status:
    font: HersheyFont
    font_size: float

    def __init__(self, font, font_size):
        self.font = font
        self.font_size = font_size

    def to_string(self):
        return f"font: {self.font.name}    font size: {self.font_size} pt"

class CursesCanvas():
    def __init__(self, stdscr, welcome_message: str):
        self.stdscr = stdscr
        self.typing_row = 1
        self.typing_column = 0
        self.scroll_count = 0
        self.line_lengths = [0]

        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)

        self.UNPROCESSED_COLOR = curses.color_pair(1)
        self.PROCESSING_COLOR = curses.color_pair(3)
        self.PROCESSED_COLOR = curses.color_pair(2)

        self.canvas_lock = threading.Lock() # this is for read/writes of typing_row, typing_column, scroll_count, and/or line_lengths

        self.stdscr.scrollok(True)
        height, width = self.stdscr.getmaxyx()
        stdscr.setscrreg(0, height - 2) # to set every row except the bottom row scrollable

        self.stdscr.keypad(True)

        with self.canvas_lock:
            self.stdscr.clear()
            self.stdscr.addstr(f"{welcome_message}\n", curses.A_REVERSE)
            self.stdscr.refresh()

    def row_after_scroll(self, row: int):
        return row - self.scroll_count

    # code to overwrite char at row/column position with the given colour
    def write_char_with_colour(self, row: int, column: int, char: str, color):
        assert len(char) == 1

        if row < self.scroll_count:
            return

        with self.canvas_lock:
            self.stdscr.addstr(self.row_after_scroll(row), column, char, color)

            # move cursor back to current typing position
            self.stdscr.move(self.typing_row - self.scroll_count, self.typing_column)
            self.stdscr.refresh()

    # recolour letter to green, signifying it has been processed
    def mark_text_to_in_progress(self, row: int, column: int, char: str):
        self.write_char_with_colour(row, column, char, self.PROCESSING_COLOR)

    # recolour letter to green, signifying it has been processed
    def mark_text_to_processed(self, row: int, column: int, char: str):
        self.write_char_with_colour(row, column, char, self.PROCESSED_COLOR)

    # writes the given char at the cursor and updates cursor position
    # returns lambdas to call when updating status to in-progress, and processed
    def type_char_at_cursor(self, char: str):
        assert len(char) == 1

        height, width = self.stdscr.getmaxyx()
        with self.canvas_lock:
            # insert the string, and calculate the next position for the typing cursor
            if char != "\n":
                row_written_to = self.typing_row
                column_written_to = self.typing_column
                if (self.typing_row >= self.scroll_count):
                    self.stdscr.insstr(self.typing_row - self.scroll_count, self.typing_column, char, self.UNPROCESSED_COLOR)
                self.typing_column += 1
            if char == "\n" or self.typing_column >= width: # new line, simply move the cursor down and to the left. Force a new line if cursor has reached the end of the line.
                # record the final length of this current line before moving to next line
                self.line_lengths.insert(self.typing_row, min(self.typing_column, width - 1))

                self.typing_row += 1
                self.typing_column = 0

                # if cursor is at the bottom, increment the scroll
                if self.row_after_scroll(self.typing_row) >= height - 1:
                    scroll_amount = self.row_after_scroll(self.typing_row) - height + 2
                    self.stdscr.scroll(scroll_amount)
                    self.scroll_count += scroll_amount
            self.stdscr.move(self.row_after_scroll(self.typing_row), self.typing_column)
            self.stdscr.refresh()

        if char.isspace(): # return lambdas that do nothing
            return (None, None)

        # otherwise, return lambdas that will update the colouring of the character
        return (lambda: self.mark_text_to_in_progress(row_written_to, column_written_to, char), lambda: self.mark_text_to_processed(row_written_to, column_written_to, char))

    # moves the cursor back one position and deletes the preceeding character
    def backspace_from_cursor(self):
        height, width = self.stdscr.getmaxyx()
        with self.canvas_lock:
            # find the previous cursor position
            if self.typing_column > 0: # try to go to the left
                self.typing_column -= 1
            else: # if cursor is at the beginning of the line, try to go to rightmost side of previous line
                if self.typing_row > 1:
                    self.typing_row -= 1
                    self.typing_column = min(self.line_lengths[self.typing_row], width - 1)
                else: # if it's at the top left, do nothing
                    return

            # move to the previous position and delete character at position
            self.stdscr.move(self.row_after_scroll(self.typing_row), self.typing_column)
            self.stdscr.delch()
            self.stdscr.refresh()

    # this is a BLOCKING call because it waits for keyboard input
    def get_char_in_ascii(self):
        self.stdscr.keypad(True)
        return self.stdscr.getch()

    # redraw status
    def update_status_bar(self, status: str):
        with self.canvas_lock:
            height, width = self.stdscr.getmaxyx()

            row_to_write_at = height - 1

            # clear text in row
            self.stdscr.move(row_to_write_at, 0)
            self.stdscr.clrtoeol()

            self.stdscr.addstr(status, curses.A_REVERSE)

            # move cursor back to current typing position
            self.stdscr.move(self.typing_row - self.scroll_count, self.typing_column)
            self.stdscr.refresh()

    def print_exit_message(self):
        height, width = self.stdscr.getmaxyx()

        row_to_write_at = min(self.row_after_scroll(self.typing_row) + 1, height - 1)

        # clear text in row
        self.stdscr.move(row_to_write_at, 0)
        self.stdscr.clrtoeol()

        self.stdscr.addstr("Exiting...", curses.A_REVERSE)
        self.stdscr.refresh()

def main(stdscr):
    global IGNORABLES

    status = Status(font = HersheyFont("D:\\Downloads\\EMSReadability.svg"), font_size = 16.0)

    port = find_device()
    if port == None:
        raise RuntimeError("Could not find a compatable IDraw device.")
    idraw = IDraw(port, 4, 2000)
    drawer = Drawer(idraw, status.font, status.font_size)
    writing_service = Service(drawer)

    canvas = CursesCanvas(stdscr, "Start typing :) ctrl-x to exit")
    canvas.update_status_bar(status.to_string())

    while True:
        ascii = canvas.get_char_in_ascii()

        # ignore input outside of normal typing range
        if ascii not in SPECIAL_ASCIIS and (ascii < 32 or ascii > 126):
            continue

        if ascii == 24: # ctrl-x
            canvas.print_exit_message()
            writing_service.stop_gracefully()
            break

        if ascii in [8, 127]: # Backspace
            if writing_service.remove_last(): # remove most recently queued item (cancellation)
                canvas.backspace_from_cursor()
            continue

        if ascii == curses.KEY_UP:
            status.font_size += 1.0
            callback_on_started, callback_on_finished = canvas.type_char_at_cursor("↑")
            writing_service.enqueue(SetFontSizeTask(status.font_size, callback_on_started, callback_on_finished))
            canvas.update_status_bar(status.to_string())
            continue

        if ascii == curses.KEY_DOWN:
            if status.font_size >= 9.0:
                status.font_size -= 1.0
                callback_on_started, callback_on_finished = canvas.type_char_at_cursor("↓")
                writing_service.enqueue(SetFontSizeTask(status.font_size, callback_on_started, callback_on_finished))
                canvas.update_status_bar(status.to_string())
            continue

        char = chr(ascii)
        if char in IGNORABLES:
            continue

        callback_on_started, callback_on_finished = canvas.type_char_at_cursor(char)
        writing_service.enqueue(WriteTask(char, callback_on_started, callback_on_finished))

wrapper(main)