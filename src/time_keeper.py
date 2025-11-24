import time
import threading
import requests

class TimeKeeper:
    def __init__(self, base_url="http://localhost:5001"):
        self.base_url = base_url
        self.local_t = 0
        self.running = False
        self.offset = 0  # For simulating drift
        self._thread = None

    def sync(self):
        """Fetches the authoritative time from the server."""
        try:
            resp = requests.get(f"{self.base_url}/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.local_t = data['current_t']
                print(f"[TimeKeeper] Synced. Local time is now: {self.local_t}")
            else:
                print(f"[TimeKeeper] Sync failed: {resp.status_code}")
        except Exception as e:
            print(f"[TimeKeeper] Sync error: {e}")

    def start(self):
        """Starts the local ticker."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()
        print("[TimeKeeper] Ticker started.")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join()

    def _tick_loop(self):
        """Accurate ticker loop."""
        next_tick = time.time() + 1
        while self.running:
            now = time.time()
            sleep_time = next_tick - now
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            next_tick += 1
            self.local_t += 1
            # print(f"[TimeKeeper] Tick: {self.get_time()}")

    def get_time(self):
        """Returns the local time + any simulated drift."""
        return self.local_t + self.offset

    def simulate_drift(self, delta):
        """Adds 'delta' seconds to the local clock (can be negative)."""
        self.offset += delta
        print(f"[TimeKeeper] Simulating drift of {delta}s. Effective time: {self.get_time()}")
