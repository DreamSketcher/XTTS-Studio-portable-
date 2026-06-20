# engine/task_queue.py
import queue


class TaskQueue:
    def __init__(self):
        self.q = queue.Queue()

    def add(self, task):
        self.q.put(task)

    def get(self):
        return self.q.get()

    def empty(self):
        return self.q.empty()