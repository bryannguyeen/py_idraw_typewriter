from collections import deque
import threading
from idraw_letter_drawer import Drawer
from enum import Enum, auto
from collections.abc import Callable
import time
from hershey_font import HersheyFont

class TaskType(Enum):
    WRITE_CHAR = auto()
    SET_FONT_SIZE = auto()
    SET_FONT = auto()

class Task:
    task_type: TaskType
    callback_on_start: Callable[[], None]
    callback_on_finished: Callable[[], None]

    def __init__(self, task_type: TaskType, callback_on_start: Callable[[], None], callback_on_finished: Callable[[], None]):
        self.task_type = task_type
        self.callback_on_start = callback_on_start
        self.callback_on_finished = callback_on_finished

class WriteTask(Task):
    message: str

    def __init__(self, char: str, callback_on_start: Callable[[], None], callback_on_finished: Callable[[], None]):
        assert len(char) == 1

        super().__init__(task_type = TaskType.WRITE_CHAR, callback_on_start = callback_on_start, callback_on_finished = callback_on_finished)
        self.message = char

class SetFontSizeTask(Task):
    message: float

    def __init__(self, size: float, callback_on_start: Callable[[], None], callback_on_finished: Callable[[], None]):
        assert size > 0

        super().__init__(task_type = TaskType.SET_FONT_SIZE, callback_on_start = callback_on_start, callback_on_finished = callback_on_finished)
        self.message = size

class SetFontTask(Task):
    message: HersheyFont

    def __init__(self, font: HersheyFont, callback_on_start: Callable[[], None], callback_on_finished: Callable[[], None]):
        assert font != None

        super().__init__(task_type = TaskType.SET_FONT, callback_on_start = callback_on_start, callback_on_finished = callback_on_finished)
        self.message = font

class Service:
    thread: threading.Thread
    drawer: Drawer
    thread_idle: bool

    def __init__(self, drawer):
        self.drawer = drawer

        self.task_queue = deque()
        self.thread_condition = threading.Condition()

        self.stop_event = threading.Event()
        self.thread_idle = False
        self.thread = threading.Thread(target = self.run_letter_processor)
        self.thread.start()

    def is_idle(self):
        return self.thread_idle

    def pop_next_task(self):
        try:
            return self.task_queue.popleft()
        except IndexError:
            return None

    # returns true if queue had an item and removed it, false otherwise
    def remove_last(self):
        try:
            self.task_queue.pop()
            return True
        except IndexError:
            return False

    def queue_has_tasks(self):
        return len(self.task_queue) > 0

    def process_next_letter(self, char: str):
        self.drawer.draw(char)

    def update_font_size(self, size: float):
        self.drawer.set_font_size(size)

    def update_font(self, font: HersheyFont):
        self.drawer.set_font(font)

    def process_task(self, task: Task):
        match task.task_type:
            case TaskType.WRITE_CHAR:
                self.process_next_letter(task.message)
                return
            case TaskType.SET_FONT_SIZE:
                self.update_font_size(task.message)
                return
            case TaskType.SET_FONT:
                self.update_font(task.message)
                return

    def run_letter_processor(self):
        while True:
            if not self.queue_has_tasks():
                self.thread_idle = True
                self.drawer.wait_position()

            with self.thread_condition:
                self.thread_condition.wait_for(lambda: self.queue_has_tasks() or self.stop_event.is_set())
                if self.stop_event.is_set():
                    return
                self.thread_idle = False
                task = self.pop_next_task()
 
            if task == None:
                continue

            # call passed in lambda to notify a letter was popped
            if (task.callback_on_start != None):
                task.callback_on_start()
            self.process_task(task)
            if (task.callback_on_finished != None):
                task.callback_on_finished()

    def enqueue(self, task: Task):
        with self.thread_condition:
            self.task_queue.append(task)
            self.thread_condition.notify()

    def stop_gracefully(self):
        with self.thread_condition:
            self.stop_event.set()
            self.thread_condition.notify()
        self.thread.join()
        time.sleep(0.3) # give some buffer time for plotter to finish current task

        self.drawer.exit()



