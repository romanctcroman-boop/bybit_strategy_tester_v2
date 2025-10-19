import time
import requests
import asyncio
import websockets
import pytest
from testcontainers.compose import DockerCompose
import os

DOCKER_COMPOSE_PATH = os.path.join(os.getcwd(), 'deploy')
BACKEND_HEALTH = 'http://127.0.0.1:8000/api/v1/live/health'
WS_URL = 'ws://127.0.0.1:8000/api/v1/live/ws/candles/BTCUSDT/1'


@pytest.mark.integration
@pytest.mark.timeout(180)
def test_smoke_with_testcontainers():
    # Start docker-compose via testcontainers; it will look for docker-compose.yml in folder
    with DockerCompose(DOCKER_COMPOSE_PATH, pull=False) as compose:
        # Wait for backend health
        start = time.time()
        healthy = False
        while time.time() - start < 60:
            try:
                r = requests.get(BACKEND_HEALTH, timeout=2)
                if r.status_code == 200:
                    healthy = True
                    break
            except Exception:
                pass
            time.sleep(1)

        assert healthy, 'Backend did not become healthy in time'

        async def collect():
            async with websockets.connect(WS_URL) as ws:
                # read confirmation
                await ws.recv()
                count = 0
                start = time.time()
                while time.time() - start < 20:
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=5)
                        count += 1
                    except asyncio.TimeoutError:
                        pass
                return count

        count = asyncio.run(collect())
        assert count > 0, 'No messages received from fake publisher'
