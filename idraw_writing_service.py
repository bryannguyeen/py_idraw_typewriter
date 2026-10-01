from collections import deque
import threading
from idraw_letter_drawer import Drawer

class Service:
    thread: threading.Thread
    drawer: Drawer

    def __init__(self, drawer, on_started_processing, on_finished_processing):
        self.letter_queue = deque()
        self.thread_condition = threading.Condition()

        self.on_started_processing = on_started_processing
        self.on_finished_processing = on_finished_processing

        self.stop_event = threading.Event()
        self.thread = threading.Thread(target = self.run_letter_processor)
        self.thread.start()

        self.drawer = drawer

    def pop_next_letter(self):
        try:
            return self.letter_queue.popleft()
        except IndexError:
            return None

    # returns true if queue was nonempty, false otherwise
    def remove_last(self):
        try:
            self.letter_queue.pop()
            return True
        except IndexError:
            return False

    def process_next_letter(self, char: str):
        self.drawer.draw(char)

    def run_letter_processor(self):
        while True:
            with self.thread_condition:
                self.thread_condition.wait_for(lambda: len(self.letter_queue) > 0 or self.stop_event.is_set())
                if self.stop_event.is_set():
                    return

                next = self.pop_next_letter()
 
            if next == None:
                continue

            # call passed in lambda to notify a letter was popped
            self.on_started_processing(next)
            self.process_next_letter(next)
            self.on_finished_processing(next)

    def enqueue(self, letter: str):
        assert len(letter) == 1

        with self.thread_condition:
            self.letter_queue.append(letter)
            self.thread_condition.notify()

    def stop_gracefully(self):
        with self.thread_condition:
            self.stop_event.set()
            self.thread_condition.notify()

        self.thread.join()



