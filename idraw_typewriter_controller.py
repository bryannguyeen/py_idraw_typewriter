from collections import deque
import curses
from curses import wrapper
from idraw_writing_service import Service
import threading
import logging
from idraw_letter_drawer import Drawer
from hershey_font import HersheyFont
from py_idraw import IDraw
import serial.tools.list_ports

IDRAW_VID = 0x1A86
IDRAW_PID = 0x8040

IGNORABLES = ["Ȣ"]

SPECIAL_ASCIIS = [8, 10, 13, 24]

screen_mutex = threading.Lock()

process_row = 1
process_column = 0

typing_row = 1
typing_column = 0

scroll_count = 0

line_lengths = [0]

logging.basicConfig(filename="debug.log", level=logging.DEBUG) # in case of logging

def find_device():
    for port in serial.tools.list_ports.comports():
        if port.vid == IDRAW_VID and port.pid == IDRAW_PID:
            return port.device
    return None

def mark_text_to_in_progress(stdscr, overwrite):
    global process_row
    global process_column
    global typing_row
    global typing_column

    curses.init_pair(3, curses.COLOR_BLUE, curses.COLOR_BLACK)
    PROCESSING_COLOR = curses.color_pair(3)

    # code to overwrite char to the colour yellow (signalling it's now in progress)
    # don't increment the process cursor, because increment_process_progression
    # will take of that
    if process_row >= scroll_count:
        with screen_mutex:
            stdscr.addstr(process_row - scroll_count, process_column, overwrite, PROCESSING_COLOR)

            stdscr.move(typing_row - scroll_count, typing_column)
            stdscr.refresh()

# recolour next red letter to green, signifying it has been processed
def increment_process_progression(stdscr, overwrite):
    global process_row
    global process_column
    global typing_row
    global typing_column

    height, width = stdscr.getmaxyx()

    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    PROCESSED_COLOR = curses.color_pair(2)

    # code to overwrite char to the colour green (signalling it's now processed)
    # and then increments the process cursor
    if overwrite == "\n":
        process_row += 1
        process_column = 0
    else:
        if process_row >= scroll_count: #render only text to overwrite is NOT offscreen
            with screen_mutex:
                stdscr.addstr(process_row - scroll_count, process_column, overwrite, PROCESSED_COLOR)
                stdscr.move(typing_row - scroll_count, typing_column)
                stdscr.refresh()
        if process_column < width - 1:
            process_column += 1
        else :
            process_row += 1
            process_column = 0

def main(stdscr):
    global IGNORABLES
    global process_row
    global process_column
    global typing_row
    global typing_column
    global line_lengths
    global scroll_count

    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    UNPROCESSED_COLOR = curses.color_pair(1)

    port = find_device()
    if port == None:
        raise RuntimeError("Could not find a compatable IDraw device.")
    idraw = IDraw(port, 4)

    drawer = Drawer(idraw, HersheyFont("D:\\Downloads\\EMSReadability.svg", 5))
    writing_service = Service(drawer, lambda letter: mark_text_to_in_progress(stdscr, letter), lambda letter: increment_process_progression(stdscr, letter))

    stdscr.scrollok(True);

    stdscr.clear()
    stdscr.addstr("Start typing :) ctrl-x to exit\n", curses.A_REVERSE)
    stdscr.refresh()

    while True:
        height, width = stdscr.getmaxyx()

        ascii = stdscr.getch()

        if ascii not in SPECIAL_ASCIIS and (ascii < 32 or ascii > 126):
            continue

        if ascii == 24: # ctrl-x
            stdscr.addstr(min(typing_row + 1 - scroll_count, height - 1), 0, "Exiting...", curses.A_REVERSE)
            stdscr.refresh()
            writing_service.stop_gracefully()
            break

        char = chr(ascii)
        write = ""

        if char in ['\x7f', '\x08']: # Backspace
            if writing_service.remove_last(): # remove most recently queued item (cancellation)

                with screen_mutex:
                    # trying to move cursor to previous position
                    if typing_column > 0: # try to go to the left
                        typing_column -= 1
                    else: # if cursor is at the beginning of the line, try to go to rightmost side of previous line
                        if typing_row > 1:
                            typing_row -= 1
                            typing_column = line_lengths[typing_row]
                        else: # if it's at the top left, do nothing
                            continue

                    stdscr.move(typing_row - scroll_count, typing_column)
                    stdscr.delch()
            continue
        elif char not in IGNORABLES:
            writing_service.enqueue(char)
            write = char
        else:
            continue

        with screen_mutex:
            if write != "\n":
                if (typing_row >= scroll_count):
                    stdscr.insstr(typing_row - scroll_count, typing_column, write, UNPROCESSED_COLOR)
                typing_column += 1
            if write == "\n" or typing_column >= width: # new line, simply move the cursor to the next position, force a new line if cursor is reaching the right end
                # new line, record the final length of this current line before moving to next line
                line_lengths.insert(typing_row, min(typing_column, width - 1))
                typing_row += 1
                typing_column = 0
                
                if typing_row - scroll_count >= height: # if cursor is at the bottom, scroll
                    stdscr.scroll(1)
                    scroll_count += 1
            stdscr.move(typing_row - scroll_count, typing_column)
            stdscr.refresh()

wrapper(main)