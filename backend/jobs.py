import threading
import time


class Busy(Exception):
    """A run can't start right now. The message is meant for the user."""


class Job:
    def __init__(self, key, session_id):
        self.key = key
        self.session_id = session_id
        self.cancel_event = threading.Event()   # handed to the browser worker; scrapers check it
        self.released = threading.Event()       # set once the run is fully over (browser closed)
        self.started = time.monotonic()

    def cancel(self):
        self.cancel_event.set()


class JobRegistry:
    # Who is scraping right now. State lives in this process only, which is correct as long as the
    # service runs a single instance (Cloud Run --max-instances=1). With more instances this would
    # need shared storage.

    # Rules for acquire(username, session_id):
    #   - nobody running for this username  -> accept (if there is global capacity)
    #   - same session_id is already running -> it is a restart (double click, rerun): cancel the old
    #     run, wait for it to release, then accept
    #   - another session_id is running     -> refuse, so nobody can stop someone else's run just by
    #     typing their username
    

    def __init__(self, max_jobs=2, takeover_wait=35.0):
        self.max_jobs = max_jobs
        self.takeover_wait = takeover_wait
        self._jobs = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(username):
        return " ".join(str(username).lower().split())

    def acquire(self, username, session_id=None):
        key = self._key(username)
        deadline = time.monotonic() + self.takeover_wait
        while True:
            with self._lock:
                current = self._jobs.get(key)
                if current is None:
                    if len(self._jobs) >= self.max_jobs:
                        raise Busy("The server is busy with other scrapes right now. Please try again in a few minutes.")
                    job = Job(key, session_id)
                    self._jobs[key] = job
                    return job
                if not session_id or current.session_id != session_id:
                    raise Busy("A scrape for this AO3 account is already running. Wait for it to finish, then try again.")
                current.cancel()  # same session starting over: stop the previous run
            # wait outside the lock, then loop to re-check who holds the slot
            if not current.released.wait(timeout=max(0.0, deadline - time.monotonic())):
                raise Busy("Your previous run is still stopping. Please try again in a few seconds.")

    def release(self, job):
        with self._lock:
            if self._jobs.get(job.key) is job:
                del self._jobs[job.key]
        job.released.set()

    def active(self):
        with self._lock:
            return len(self._jobs)