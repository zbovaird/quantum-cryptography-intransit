import time
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.server import Server

def run_ticker():
    print("Initializing Ticker Service...")
    
    # Initialize server (loads state from DB)
    server = Server()
    print(f"Ticker started at T={server.current_t}")
    
    next_tick_time = time.time() + 1
    
    while True:
        now = time.time()
        sleep_time = next_tick_time - now
        if sleep_time > 0:
            time.sleep(sleep_time)
        
        next_tick_time += 1
        
        try:
            # Advance the server state by 1 tick
            target = server.current_t + 1
            server.advance_private_state_to(target)
            # print(f"Ticked to {target}")
        except Exception as e:
            print(f"Ticker error: {e}")

if __name__ == "__main__":
    # Ensure we have the master key
    if not os.environ.get('SERVER_MASTER_KEY'):
        print("ERROR: SERVER_MASTER_KEY env var is required.")
        sys.exit(1)
        
    run_ticker()
