import threading

from engine.gui.console import ConsoleRedirect


class FakeWidget:
    def __init__(self):
        self.callbacks = {}
        self.counter = 0
        self.inserts = []
        self.see_calls = 0

    def after(self, delay, callback):
        self.counter += 1
        token = f"after-{self.counter}"
        self.callbacks[token] = (delay, callback)
        return token

    def winfo_exists(self):
        return True

    def insert(self, where, text, tag):
        self.inserts.append((text, tag))

    def see(self, where):
        self.see_calls += 1

    def run_next(self):
        token = next(iter(self.callbacks))
        _delay, callback = self.callbacks.pop(token)
        callback()


def test_worker_writes_do_not_call_tk():
    redirect = ConsoleRedirect()
    widget = FakeWidget()
    redirect.attach(widget)
    scheduled = widget.counter

    worker = threading.Thread(target=lambda: [redirect.write(f"line {i}\n") for i in range(20)])
    worker.start()
    worker.join()

    assert widget.counter == scheduled
    assert widget.inserts == []


def test_queue_is_batched_and_consecutive_tags_are_grouped():
    redirect = ConsoleRedirect()
    widget = FakeWidget()
    redirect.attach(widget)
    redirect.write("one\n")
    redirect.write("two\n")
    redirect.write("warning\n")
    widget.run_next()

    assert widget.inserts == [("one\ntwo\n", "info"), ("warning\n", "warn")]
    assert widget.see_calls == 1


def test_pre_attach_buffer_is_delivered():
    redirect = ConsoleRedirect()
    redirect.write("before attach\n")
    widget = FakeWidget()
    redirect.attach(widget)
    widget.run_next()
    assert widget.inserts == [("before attach\n", "info")]
