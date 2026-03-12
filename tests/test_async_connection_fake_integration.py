"""Fake-backend integration tests for AsyncConnection."""

import asyncio
import time

import pyads
import pytest
from pyads.testserver import AdsTestServer


pytestmark = pytest.mark.ads_fake

TEST_SERVER_AMS_NET_ID = "127.0.0.1.1.1"
TEST_SERVER_IP_ADDRESS = "127.0.0.1"
TEST_SERVER_AMS_PORT = pyads.PORT_TC3PLC1


@pytest.fixture(scope="module")
def fake_ads_server():
    try:
        server = AdsTestServer(logging=False)
    except PermissionError as exc:
        pytest.skip(f"Cannot start fake ADS test server in this environment: {exc}")
    server.start()
    time.sleep(0.2)
    try:
        yield server
    finally:
        server.stop()
        time.sleep(0.2)


def test_async_sum_read_with_fake_server(fake_ads_server) -> None:
    async def _scenario() -> None:
        conn = pyads.AsyncConnection(
            TEST_SERVER_AMS_NET_ID,
            TEST_SERVER_AMS_PORT,
            TEST_SERVER_IP_ADDRESS,
        )
        try:
            await conn.open()
            values = await conn.sum_read(["i1", "i2", "i3", "str_test"])
            assert values["i1"] == 1
            assert values["i2"] == 2
            assert values["i3"] == 3
            assert values["str_test"] == "test"
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_async_sum_write_with_fake_server(fake_ads_server) -> None:
    async def _scenario() -> None:
        conn = pyads.AsyncConnection(
            TEST_SERVER_AMS_NET_ID,
            TEST_SERVER_AMS_PORT,
            TEST_SERVER_IP_ADDRESS,
        )
        try:
            await conn.open()
            fut = conn.submit_sum_write(
                {
                    "i1": 1,
                    "i2": 2,
                    "i3": 3,
                    "str_test": "test",
                }
            )
            result = await fut
            assert result == {
                "i1": "no error",
                "i2": "no error",
                "i3": "no error",
                "str_test": "no error",
            }
        finally:
            await conn.aclose()

    asyncio.run(_scenario())
