from collections import deque
import threading
import time
from idraw_letter_drawer import Drawer

class Service:
    thread: threading.Thread

    def __init__(self, on_started_processing, on_finished_processing):
        self.letter_queue = deque()
        self.queue_mutex = threading.Lock()
        self.queue_running_bool_mutex = threading.Lock()

        self.on_started_processing = on_started_processing
        self.on_finished_processing = on_finished_processing
        self.thread_running = False
        self.stop_event = threading.Event()
        self.thread = None

        self.drawer = Drawer()

    def pop_next_letter(self):
        with self.queue_mutex:
            if len(self.letter_queue) == 0:
                return None
            return self.letter_queue.popleft()

    # returns true if queue was nonempty, false otherwise
    def remove_last(self):
        with self.queue_mutex:
            if len(self.letter_queue) > 0:
                self.letter_queue.pop()
                return True
            return False

    def process_next_letter(self, char: str):
        self.drawer.draw(char)

    def run_letter_processor(self):
        while not self.stop_event.is_set():
            next = None
            with self.queue_running_bool_mutex:
                next = self.pop_next_letter()
                if next == None:
                    self.thread_running = False
                    return

            # call passed in lambda to notify a letter was popped
            self.on_started_processing(next)
            self.process_next_letter(next)
            self.on_finished_processing(next)

    def enqueue(self, letter: str):
        assert len(letter) == 1

        with self.queue_running_bool_mutex:
            with self.queue_mutex:
                self.letter_queue.append(letter)

            if not self.thread_running and not self.stop_event.is_set():
                self.thread_running = True
                self.thread = threading.Thread(target = self.run_letter_processor)
                self.thread.start()

    def stop_gracefully(self):
        if self.thread != None and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()



