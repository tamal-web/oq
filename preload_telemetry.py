import threading
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from telemetry_monaco import SUPPORTED_YEARS, load_monaco_session

def preload_all():
    print("Starting background preload of telemetry data for Monaco...")
    for year in sorted(SUPPORTED_YEARS):
        print(f"Preloading Monaco {year}...")
        try:
            # load_monaco_session already saves to cache if it isn't there
            load_monaco_session(year)
        except Exception as e:
            print(f"Failed to preload {year}: {e}")
    print("Preloading complete.")

if __name__ == '__main__':
    preload_all()
