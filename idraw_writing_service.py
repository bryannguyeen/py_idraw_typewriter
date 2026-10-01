from collections import deque
import threading
from idraw_letter_drawer import Drawer

class Service:
    thread: threading.Thread
    drawer: Drawer

    def __init__(self, drawer):
        self.drawer = drawer

        self.letter_queue = deque()
        self.thread_condition = threading.Condition()

        self.stop_event = threading.Event()
        self.thread = threading.Thread(target = self.run_letter_processor)
        self.thread.start()

    def pop_next_task(self):
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

    def queue_has_tasks(self):
        return len(self.letter_queue) > 0

    def run_letter_processor(self):
        while True:
            with self.thread_condition:
                self.thread_condition.wait_for(lambda: self.queue_has_tasks() or self.stop_event.is_set())
                if self.stop_event.is_set():
                    return

                nextChar, callback_on_start, callback_on_finished = self.pop_next_task()
 
            if nextChar == None:
                continue

            # call passed in lambda to notify a letter was popped
            callback_on_start()
            self.process_next_letter(nextChar)
            callback_on_finished()

            if not self.queue_has_tasks():
                self.drawer.wait_position()

    def enqueue(self, letter: str, callback_on_start, callback_on_finished):
        assert len(letter) == 1

        with self.thread_condition:
            self.letter_queue.append((letter, callback_on_start, callback_on_finished))
            self.thread_condition.notify()

    def stop_gracefully(self):
        with self.thread_condition:
            self.stop_event.set()
            self.thread_condition.notify()

        self.drawer.exit()

        self.thread.join()



