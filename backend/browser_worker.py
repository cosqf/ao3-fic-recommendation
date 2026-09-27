import threading
import queue
import atexit
from camoufox.sync_api import Camoufox

class PlaywrightWorker(threading.Thread):
    def __init__(self, headless = True):
        super().__init__(daemon=True)
        self.headless = headless
        self._queue = queue.Queue()
        self._ready = threading.Event()
        self.context = None
        self.page = None
        self.start()
        self._ready.wait(timeout=15)

    def run(self):
        self.context = Camoufox(headless=self.headless).start().new_context()
        self.page = self.context.new_page()
        self._ready.set()

        while True:
            task = self._queue.get()
            if task is None:           # shutdown signal
                break
            fn, holder, done = task
            try:
                holder["result"] = fn(self.page)
                holder["error"]  = None
            except Exception as e:
                holder["result"] = None
                holder["error"]  = e
            finally:
                done.set()

    def execute(self, fn):
        holder = {}
        done = threading.Event()
        self._queue.put((fn, holder, done))
        done.wait()
        if holder["error"]:
            raise holder["error"]
        return holder["result"]

    def stop(self):
        self._queue.put(None)