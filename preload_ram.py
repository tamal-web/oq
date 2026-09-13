import asyncio
import websockets

async def wake_up():
    for year in [2018, 2019, 2021, 2022, 2023, 2024]:
        try:
            async with websockets.connect(f'ws://localhost:8000/ws/race/{year}/VER') as ws:
                msg = await ws.recv()
                print(f"Preloaded {year} into RAM: {msg}")
        except Exception as e:
            pass

asyncio.run(wake_up())
