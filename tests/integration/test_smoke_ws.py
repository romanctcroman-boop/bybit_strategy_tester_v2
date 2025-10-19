import asyncio
import os
import time
import subprocess
import requests
import websockets
import pytest

DOCKER_COMPOSE = os.path.join(os.getcwd(), 'deploy', 'docker-compose.yml')
BACKEND_URL = 'http://127.0.0.1:8000/api/v1/live/health'
WS_URL = 'ws://127.0.0.1:8000/api/v1/live/ws/candles/BTCUSDT/1'


def docker_compose_up():
    subprocess.check_call(['docker', 'compose', '-f', DOCKER_COMPOSE, 'up', '--build', '-d'])


def docker_compose_down():
    subprocess.check_call(['docker', 'compose', '-f', DOCKER_COMPOSE, 'down'])


def wait_for_backend(timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(BACKEND_URL, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


@pytest.mark.integration
@pytest.mark.timeout(120)
def test_smoke_websocket_connect_and_receive():
    # Start docker compose
    docker_compose_up()

    try:
        assert wait_for_backend(60), 'Backend did not become healthy in time'

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

    finally:
        docker_compose_down()
