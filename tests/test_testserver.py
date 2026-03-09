"""Some extra tests for the test server.

Like 90% of the test server and handlers are used during pyads tests. After all, that
is largely why the test server exists. However, a few features are not covered by tests
(for example because they were not needed during a test from the pyads perspective).
Since the test server has become a user feature in itself, these tests supplement the
regular pyads tests to increase the coverage of the test server itself.
"""

import time
import unittest
import os
import pyads
from pyads.testserver import AdsTestServer, BasicHandler
from pyads.pyads_ex import adsGetNetIdForPLC
import pytest

# These are pretty arbitrary
TEST_SERVER_AMS_NET_ID = "127.0.0.1.1.1"
TEST_SERVER_IP_ADDRESS = "127.0.0.1"
TEST_SERVER_AMS_PORT = pyads.PORT_TC3PLC1


def _is_real_target() -> bool:
    return os.getenv("PYADS_TEST_TARGET", "fake").lower() == "real"


def _resolve_real_ams_net_id(plc_ip: str) -> str:
    configured = os.getenv("PYADS_REAL_PLC_AMS_NET_ID", "").strip()
    if configured:
        return configured
    return adsGetNetIdForPLC(plc_ip)


def _resolve_real_ams_port() -> int:
    configured = os.getenv("PYADS_REAL_PLC_AMS_PORT", "").strip()
    if configured:
        return int(configured)
    return pyads.PORT_TC3PLC1


@pytest.mark.ads_fake
@unittest.skipIf(_is_real_target(), "Fake ADS test-server behavior is skipped in real target mode.")
class TestServerTestCase(unittest.TestCase):
    """Some rudimentary tests for the test server.

    The majority of test server code is tested as part of regular pyads tests. This
    case is only for a few items that were left uncovered.
    """

    def test_start_stop(self):
        handler = BasicHandler()
        test_server = AdsTestServer(handler=handler, logging=False)
        test_server.start()
        time.sleep(0.1)  # Give server a moment to spin up
        test_server.stop()
        time.sleep(0.1)  # Give server a moment to spin up

    def test_context(self):
        handler = BasicHandler()
        test_server = AdsTestServer(handler=handler, logging=False)

        with test_server:

            time.sleep(0.1)  # Give server a moment to spin up

            plc = pyads.Connection(TEST_SERVER_AMS_NET_ID, TEST_SERVER_AMS_PORT)
            with plc:
                byte = plc.read(12345, 1000, pyads.PLCTYPE_BYTE)
                self.assertEqual(byte, 0)

        time.sleep(0.1)  # Give server a moment to spin down

    def test_server_disconnect_then_del_device_notification(self):
        """Test no error thown, when ADS symbol with device_notification is cleaned up after the server went offline.

        Tests fix of issue [#303](https://github.com/stlehmann/pyads/issues/303), original pull request: [#304](https://github.com/stlehmann/pyads/pull/304)
        """
        # 1. spin up the server
        handler = BasicHandler()
        test_server = AdsTestServer(handler=handler, logging=False)
        test_server.start()
        time.sleep(0.1)  # Give server a moment to spin up

        # 2. open a plc connection to the test server:
        plc = pyads.Connection(TEST_SERVER_AMS_NET_ID, TEST_SERVER_AMS_PORT)
        plc.open()

        # 3. add a variable, register a device notification with auto_update=True
        test_int = pyads.AdsSymbol(plc, "TestSymbol", symbol_type=pyads.PLCTYPE_INT)
        test_int.plc_type = pyads.PLCTYPE_INT
        test_int.auto_update = True
        time.sleep(0.1)  # Give server a moment

        # 4. stop the test server
        test_server.stop()
        time.sleep(0.1)  # Give server a moment

        try:
            # some code, where test_int is cleared by the Garbage collector after the server was stopped
            # (e.g. the machine with ADS Server disconnected)
            # this raised an ADSError up to commit [a7af674](https://github.com/stlehmann/pyads/tree/a7af674b49b1c91966f2bac1f00f86273cbd9af8)
            #  `clear_device_notifications()` failed, if not wrapped in try-catch as the server is no longer present.
            del test_int  # Trigger destructor
        except pyads.ADSError as e:
            self.fail(f"Closing server connection raised: {e}")


@pytest.mark.ads_real
@unittest.skipUnless(_is_real_target(), "Real ADS tests are enabled with --ads-target=real.")
class RealRuntimeTestCase(unittest.TestCase):
    """Local integration checks against a running Beckhoff ADS runtime."""

    def test_context_real(self):
        plc_ip = os.getenv("PYADS_REAL_PLC_IP", "127.0.0.1")
        ams_net_id = _resolve_real_ams_net_id(plc_ip)
        ams_port = _resolve_real_ams_port()

        plc = pyads.Connection(ams_net_id, ams_port, plc_ip)
        with plc:
            state = plc.read_state()
            self.assertIsNotNone(state)
            self.assertEqual(len(state), 2)

    def test_start_stop_real(self):
        plc_ip = os.getenv("PYADS_REAL_PLC_IP", "127.0.0.1")
        ams_net_id = _resolve_real_ams_net_id(plc_ip)
        ams_port = _resolve_real_ams_port()

        plc = pyads.Connection(ams_net_id, ams_port, plc_ip)
        plc.open()
        time.sleep(0.1)
        plc.close()

    def test_disconnect_then_del_device_notification_real(self):
        symbol_name = os.getenv("PYADS_REAL_TEST_SYMBOL", "").strip()
        if not symbol_name:
            self.skipTest("Set PYADS_REAL_TEST_SYMBOL to run real notification cleanup test.")

        plc_ip = os.getenv("PYADS_REAL_PLC_IP", "127.0.0.1")
        ams_net_id = _resolve_real_ams_net_id(plc_ip)
        ams_port = _resolve_real_ams_port()

        plc = pyads.Connection(ams_net_id, ams_port, plc_ip)
        plc.open()

        # Requires a valid PLC symbol configured via PYADS_REAL_TEST_SYMBOL.
        symbol = pyads.AdsSymbol(plc, symbol_name, symbol_type=pyads.PLCTYPE_INT)
        symbol.plc_type = pyads.PLCTYPE_INT
        symbol.auto_update = True
        time.sleep(0.1)

        plc.close()
        time.sleep(0.1)

        try:
            del symbol
        except pyads.ADSError as e:
            self.fail(f"Deleting symbol after disconnect raised: {e}")


if __name__ == "__main__":
    unittest.main()
