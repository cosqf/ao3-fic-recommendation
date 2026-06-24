import threading
import queue
import atexit
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

class PlaywrightWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._queue = queue.Queue()
        self._ready = threading.Event()
        self.context = None
        self.page = None
        self.start()
        self._ready.wait(timeout=15)

    def run(self):
        with Stealth().use_sync(sync_playwright()) as pw:
            self.context = pw.chromium.launch(headless=True).new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36")
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