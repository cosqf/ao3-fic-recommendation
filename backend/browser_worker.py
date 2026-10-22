import threading
import queue
from camoufox.sync_api import Camoufox

class PlaywrightWorker(threading.Thread):
    def __init__(self, headless = True):
        super().__init__(daemon=True)
        self.headless = headless
        self._queue = queue.Queue()
        self._ready = threading.Event()
        self._camoufox = None
        self.context = None
        self.page = None
        self.startup_error = None
        self.start()
        self._ready.wait(timeout=15)

        if self.startup_error is not None:
            raise RuntimeError(f"browser failed to start: {self.startup_error}")

    def run(self):
        try:
            self._camoufox = Camoufox(headless=self.headless)
            browser = self._camoufox.start()
            self.context = browser.new_context()
            self.page = self.context.new_page()
        except Exception as e:
            print(f"Failed to start browser: {e}")
            self.startup_error = e
            self._ready.set()
            self._cleanup()
            return
        self._ready.set()

        try:
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
        finally:
            self._cleanup()

    def _cleanup(self):
        if self.context is not None:
            try:
                self.context.close()
            except Exception as e:
                print(f"Error closing browser context: {e}")
        if self._camoufox is not None:
            try:
                self._camoufox.__exit__(None, None, None)
            except Exception as e:
                print(f"Error closing browser: {e}")

# queue fn(page) without blocking
# returns (holder, done)
    def submit(self, fn):
        if not self.is_alive():
            raise RuntimeError(f"browser worker is not running (startup error: {self.startup_error})")
        holder = {}
        done = threading.Event()
        self._queue.put((fn, holder, done))
        return holder, done

# submit but blocking
    def execute(self, fn):
        holder, done = self.submit(fn)
        done.wait()
        if holder["error"]:
            raise holder["error"]
        return holder["result"]

    def stop(self):
        self._queue.put(None)