import curses
from curses import wrapper
from idraw_writing_service import Service, WriteTask, SetFontSizeTask, SetFontTask
import threading
import logging
from idraw_letter_drawer import Drawer
from hershey_font import HersheyFont
from py_idraw import IDraw
import serial.tools.list_ports
import configparser
from pathlib import Path

IDRAW_VID = 0x1A86
IDRAW_PID = 0x8040

IGNORABLES = ["Ȣ"]

SPECIAL_ASCIIS = [1, 8, 10, 13, 24, 127, curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT]
CONFIG_PATH = "./config.ini"

MIN_FONT_SIZE = 8.0
MAX_FONT_SIZE = 500.0

logging.basicConfig(filename="debug.log", level=logging.DEBUG) # in case of logging

def find_device():
    for port in serial.tools.list_ports.comports():
        if port.vid == IDRAW_VID and port.pid == IDRAW_PID:
            return port.device
    return None

def truncate_string(string: str, max_length: int) -> str:
    assert max_length > 3
    if len(string) <= max_length:
        return string

    return string[:(max_length - 3)] + "..."

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

    def list_selector(self, prompt_message: str, items: list[str], previous_selection = None) -> str:
        assert len(items) > 0

        # hide cursor
        curses.curs_set(0)

        selected_index = 0
        scroll_distance = 0

        self.stdscr.touchwin()
        self.stdscr.refresh()

        height, width = self.stdscr.getmaxyx()
        list_pad = curses.newpad(max(len(items), height - 1), 1000)
        self.stdscr.refresh()

        previous_bottom_text = self.get_bottom_text_bar_as_string()
        self.update_bottom_text_bar(prompt_message)

        for index, item in enumerate(items):
            list_pad.addstr(index, 0, truncate_string(item, width))
            if previous_selection == item:
                selected_index = index
        list_pad.chgat(selected_index, 0, -1, self.PROCESSED_COLOR)
        
        list_pad.refresh(0, 0, 0, 0, height-2, width-1)

        while True:
            ascii = self.get_char_in_ascii()
            if ascii == 13 or ascii == 10: # Enter key
                break

            new_selected_index = None
            if ascii == curses.KEY_DOWN and selected_index < len(items) - 1:
                new_selected_index = selected_index + 1
                if (new_selected_index < len(items) - 1) and (new_selected_index - scroll_distance > height - 3):
                    scroll_distance += 1
            elif ascii == curses.KEY_UP and selected_index > 0:
                new_selected_index = selected_index - 1
                if (new_selected_index > 0) and (new_selected_index - scroll_distance < 1):
                    scroll_distance -= 1
            if new_selected_index != None:
                list_pad.chgat(selected_index, 0, -1, curses.A_NORMAL)
                list_pad.chgat(new_selected_index, 0, -1, self.PROCESSED_COLOR)
                selected_index = new_selected_index

                list_pad.refresh(scroll_distance, 0, 0, 0, height-2, width-1)

        # remove pad and return to before
        del list_pad
        curses.curs_set(1)
        self.stdscr.touchwin()
        self.stdscr.refresh()
        self.update_bottom_text_bar(previous_bottom_text)

        return items[selected_index]

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
    def update_bottom_text_bar(self, status: str):
        with self.canvas_lock:
            height, width = self.stdscr.getmaxyx()

            row_to_write_at = height - 1

            # clear text in row
            self.stdscr.move(row_to_write_at, 0)
            self.stdscr.clrtoeol()
            self.stdscr.chgat(row_to_write_at, 0, -1, curses.A_REVERSE)

            self.stdscr.addstr(status, curses.A_REVERSE)

            # move cursor back to current typing position
            self.stdscr.move(self.typing_row - self.scroll_count, self.typing_column)
            self.stdscr.refresh()

    def get_bottom_text_bar_as_string(self):
        height, width = self.stdscr.getmaxyx()

        status_bar_row = height - 1
        bytes = self.stdscr.instr(status_bar_row, 0)
        return bytes.decode("utf-8").rstrip()

    def print_exit_message(self):
        height, width = self.stdscr.getmaxyx()

        row_to_write_at = min(self.row_after_scroll(self.typing_row) + 1, height - 1)

        # clear text in row
        self.stdscr.move(row_to_write_at, 0)
        self.stdscr.clrtoeol()

        self.stdscr.addstr("Exiting...", curses.A_REVERSE)
        self.stdscr.refresh()

def get_hershey_font_or_return_none(file_path: str) -> HersheyFont:
    if not file_path.strip():
        return None
    try:
        return HersheyFont(file_path)
    except Exception:
        return None

class Status:
    font: HersheyFont
    font_size: float
    font_dir_name: str
    available_fonts: list[str]

    def __init__(self, font_size, config_file_name):
        self.font_size = font_size

        # load config
        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_PATH)
        self.set_available_fonts_from_config()

    def set_available_fonts_from_config(self):
            self.font_dir_name = self.config.get("settings", "font_directory", fallback = "./fonts")
            font_dir = Path(self.font_dir_name)
            self.available_fonts = list()
            for item in font_dir.iterdir():
                if item.is_file() and item.name.lower().endswith(".svg"):
                    self.available_fonts.append(item.name)
            if len(self.available_fonts) == 0:
                raise RuntimeError("No font found")

    def load_recent_font_or_prompt_user(self, canvas):
        recent_font = self.config.get("settings", "recently_used_font", fallback = "")

        self.font = get_hershey_font_or_return_none(recent_font)
        if self.font: # if recent font is loaded successfully, do nothing more
            return

        # else, prompt user to make a selection
        self.prompt_user_to_select_font(canvas)


    def prompt_user_to_select_font(self, canvas):
        font_selection = canvas.list_selector(prompt_message = "Pick a font", items = self.available_fonts,
                                              previous_selection = self.font.file_name if self.font else None)
        font_file_to_use = "/".join([self.font_dir_name, font_selection])

        # save recently used font
        if not self.config.has_section("settings"):
            self.config.add_section("settings")
        self.config.set("settings", "recently_used_font", font_file_to_use)
    
        with open(CONFIG_PATH, "w") as f:
            self.config.write(f)

        self.font = HersheyFont(font_file_to_use)

    def to_string(self):
        return f"font: {self.font.name}    font size: {self.font_size} pt"

def main(stdscr):
    canvas = CursesCanvas(stdscr, "Start typing :) ctrl-x to exit")

    status = Status(font_size = 16.0, config_file_name = CONFIG_PATH)
    status.load_recent_font_or_prompt_user(canvas)

    port = find_device()
    if port == None:
        raise RuntimeError("Could not find a compatable IDraw device.")
    idraw = IDraw(port, 4, 2000)
    drawer = Drawer(idraw, status.font, status.font_size)
    writing_service = Service(drawer)

    canvas.update_bottom_text_bar(status.to_string())

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

        if ascii == 1: # ctrl-a: switch fonts
            if writing_service.is_idle(): # only switch fonts when idle
                status.prompt_user_to_select_font(canvas)

                # update drawer's font and status bar
                writing_service.enqueue(SetFontTask(status.font, callback_on_started, callback_on_finished))
                canvas.update_bottom_text_bar(status.to_string())

            continue

        if ascii == curses.KEY_UP:
            if status.font_size < MAX_FONT_SIZE:
                status.font_size = min(status.font_size + 1.0, MAX_FONT_SIZE)
                callback_on_started, callback_on_finished = canvas.type_char_at_cursor("↑")
                writing_service.enqueue(SetFontSizeTask(status.font_size, callback_on_started, callback_on_finished))
                canvas.update_bottom_text_bar(status.to_string())
            continue

        if ascii == curses.KEY_DOWN:
            if status.font_size > MIN_FONT_SIZE:
                status.font_size = max(status.font_size - 1.0, MIN_FONT_SIZE)
                callback_on_started, callback_on_finished = canvas.type_char_at_cursor("↓")
                writing_service.enqueue(SetFontSizeTask(status.font_size, callback_on_started, callback_on_finished))
                canvas.update_bottom_text_bar(status.to_string())
            continue

        char = chr(ascii)
        if char in IGNORABLES:
            continue

        callback_on_started, callback_on_finished = canvas.type_char_at_cursor(char)
        writing_service.enqueue(WriteTask(char, callback_on_started, callback_on_finished))

wrapper(main)