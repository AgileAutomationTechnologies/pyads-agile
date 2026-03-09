"""Real Beckhoff ADS integration tests.

These tests are opt-in and intended for local/lab environments with a running
TwinCAT ADS runtime.
"""

import os
import time
from typing import Generator
from collections import OrderedDict

import pyads
import pytest
from pyads.pyads_ex import adsGetNetIdForPLC


pytestmark = pytest.mark.ads_real


def _plc_ip() -> str:
    return os.getenv("PYADS_REAL_PLC_IP", "127.0.0.1")


def _plc_ams_net_id() -> str:
    configured = os.getenv("PYADS_REAL_PLC_AMS_NET_ID", "").strip()
    if configured:
        return configured
    return adsGetNetIdForPLC(_plc_ip())


def _plc_ams_port() -> int:
    configured = os.getenv("PYADS_REAL_PLC_AMS_PORT", "").strip()
    if configured:
        return int(configured)
    return pyads.PORT_TC3PLC1


def _required_symbol_int() -> str:
    symbol = os.getenv("PYADS_REAL_TEST_SYMBOL_INT", "").strip()
    if not symbol:
        pytest.skip("Set PYADS_REAL_TEST_SYMBOL_INT to run real read/write and notification tests.")
    return symbol


def _required_symbol_str() -> str:
    symbol = os.getenv("PYADS_REAL_TEST_SYMBOL_STR", "").strip()
    if not symbol:
        pytest.skip("Set PYADS_REAL_TEST_SYMBOL_STR to run real STRING symbol tests.")
    return symbol


def _required_symbol_struct() -> str:
    symbol = os.getenv("PYADS_REAL_TEST_SYMBOL_STRUCT", "").strip()
    if not symbol:
        pytest.skip("Set PYADS_REAL_TEST_SYMBOL_STRUCT to run real structure symbol tests.")
    return symbol


def _required_symbol_struct_array() -> str:
    symbol = os.getenv("PYADS_REAL_TEST_SYMBOL_STRUCT_ARRAY", "").strip()
    if not symbol:
        pytest.skip("Set PYADS_REAL_TEST_SYMBOL_STRUCT_ARRAY to run real structure-array symbol tests.")
    return symbol


def _struct_strlen() -> int:
    value = os.getenv("PYADS_REAL_TEST_STRUCT_STRLEN", "").strip()
    return int(value) if value else 80


def _struct_array_size() -> int:
    value = os.getenv("PYADS_REAL_TEST_STRUCT_ARRAY_SIZE", "").strip()
    return int(value) if value else 2


def _struct_def():
    return (
        ("i", pyads.PLCTYPE_INT, 1),
        ("s", pyads.PLCTYPE_STRING, 1, _struct_strlen()),
    )


@pytest.fixture
def plc() -> Generator[pyads.Connection, None, None]:
    conn = pyads.Connection(_plc_ams_net_id(), _plc_ams_port(), _plc_ip())
    conn.open()
    try:
        yield conn
    finally:
        conn.close()


def test_get_ams_real_runtime() -> None:
    expected = os.getenv("PYADS_REAL_PLC_AMS_NET_ID", "").strip()
    actual = adsGetNetIdForPLC(_plc_ip())
    if expected:
        assert actual == expected
    else:
        parts = actual.split(".")
        assert len(parts) == 6
        assert all(0 <= int(p) <= 255 for p in parts)


def test_context_real() -> None:
    plc = pyads.Connection(_plc_ams_net_id(), _plc_ams_port(), _plc_ip())
    with plc:
        state = plc.read_state()
        assert state is not None
        assert len(state) == 2


def test_start_stop_real() -> None:
    plc = pyads.Connection(_plc_ams_net_id(), _plc_ams_port(), _plc_ip())
    plc.open()
    time.sleep(0.05)
    plc.close()


def test_disconnect_then_del_device_notification_real() -> None:
    symbol_name = _required_symbol_int()

    plc = pyads.Connection(_plc_ams_net_id(), _plc_ams_port(), _plc_ip())
    plc.open()
    symbol = pyads.AdsSymbol(plc, symbol_name, symbol_type=pyads.PLCTYPE_INT)
    symbol.plc_type = pyads.PLCTYPE_INT
    symbol.auto_update = True
    time.sleep(0.05)
    plc.close()

    # Should not raise even if connection is already gone.
    del symbol


def test_read_state_real(plc: pyads.Connection) -> None:
    state = plc.read_state()
    assert state is not None
    assert len(state) == 2


def test_read_device_info_real(plc: pyads.Connection) -> None:
    info = plc.read_device_info()
    assert info is not None
    name, version = info
    assert isinstance(name, str)
    assert hasattr(version, "version")
    assert hasattr(version, "revision")
    assert hasattr(version, "build")


def test_open_twice_real() -> None:
    plc = pyads.Connection(_plc_ams_net_id(), _plc_ams_port(), _plc_ip())
    plc.open()
    plc.open()
    plc.close()


def test_get_local_address_real(plc: pyads.Connection) -> None:
    addr = plc.get_local_address()
    assert addr is not None
    assert isinstance(addr.netid, str)


def test_read_by_name_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_int()
    value = plc.read_by_name(symbol_name, pyads.PLCTYPE_INT)
    assert isinstance(value, int)


def test_write_by_name_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_int()
    old_value = plc.read_by_name(symbol_name, pyads.PLCTYPE_INT)
    new_value = old_value + 1 if old_value < 32767 else old_value - 1
    try:
        plc.write_by_name(symbol_name, new_value, pyads.PLCTYPE_INT)
        check_value = plc.read_by_name(symbol_name, pyads.PLCTYPE_INT)
        assert check_value == new_value
    finally:
        plc.write_by_name(symbol_name, old_value, pyads.PLCTYPE_INT)


def test_add_notification_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_int()

    callbacks = []

    def _cb(notification, name) -> None:
        callbacks.append((notification, name))

    symbol = pyads.AdsSymbol(plc, symbol_name, symbol_type=pyads.PLCTYPE_INT)
    symbol.plc_type = pyads.PLCTYPE_INT
    handles = symbol.add_device_notification(_cb)
    assert handles is not None
    symbol.del_device_notification(handles)


def test_write_control_real(plc: pyads.Connection) -> None:
    ads_state, device_state = plc.read_state()
    # Keep current state values to avoid changing runtime mode.
    plc.write_control(ads_state, device_state, 0, pyads.PLCTYPE_INT)


def test_symbol_read_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_int()
    symbol = pyads.AdsSymbol(plc, symbol_name, symbol_type=pyads.PLCTYPE_INT)
    symbol.plc_type = pyads.PLCTYPE_INT
    value = symbol.read()
    assert isinstance(value, int)


def test_symbol_write_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_int()
    symbol = pyads.AdsSymbol(plc, symbol_name, symbol_type=pyads.PLCTYPE_INT)
    symbol.plc_type = pyads.PLCTYPE_INT
    old_value = symbol.read()
    new_value = old_value + 1 if old_value < 32767 else old_value - 1
    try:
        symbol.write(new_value)
        assert symbol.read() == new_value
    finally:
        symbol.write(old_value)


def test_symbol_string_read_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_str()
    symbol = pyads.AdsSymbol(plc, symbol_name, symbol_type=pyads.PLCTYPE_STRING)
    symbol.plc_type = pyads.PLCTYPE_STRING
    value = symbol.read()
    assert isinstance(value, str)


def test_symbol_string_write_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_str()
    symbol = pyads.AdsSymbol(plc, symbol_name, symbol_type=pyads.PLCTYPE_STRING)
    symbol.plc_type = pyads.PLCTYPE_STRING
    old_value = symbol.read()
    new_value = "pyads-agile-it"
    try:
        symbol.write(new_value)
        assert symbol.read().startswith(new_value)
    finally:
        symbol.write(old_value)


def test_symbol_structure_read_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_struct()
    symbol = plc.get_symbol(symbol_name, structure_def=_struct_def())
    value = symbol.read()
    assert isinstance(value, (dict, OrderedDict))
    assert "i" in value
    assert "s" in value


def test_symbol_structure_write_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_struct()
    symbol = plc.get_symbol(symbol_name, structure_def=_struct_def())
    old_value = symbol.read()
    new_value = {"i": 42, "s": "pyads-agile-struct"}
    try:
        symbol.write(new_value)
        read_back = symbol.read()
        assert int(read_back["i"]) == 42
        assert str(read_back["s"]).startswith("pyads-agile-struct")
    finally:
        symbol.write(old_value)


def test_symbol_structure_array_read_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_struct_array()
    symbol = plc.get_symbol(
        symbol_name,
        structure_def=_struct_def(),
        array_size=_struct_array_size(),
    )
    value = symbol.read()
    assert isinstance(value, list)
    assert len(value) == _struct_array_size()
    assert all("i" in item and "s" in item for item in value)


def test_symbol_structure_array_write_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_struct_array()
    n = _struct_array_size()
    symbol = plc.get_symbol(symbol_name, structure_def=_struct_def(), array_size=n)
    old_value = symbol.read()
    new_value = [{"i": i + 100, "s": f"pyads-arr-{i}"} for i in range(n)]
    try:
        symbol.write(new_value)
        read_back = symbol.read()
        assert len(read_back) == n
        for i in range(n):
            assert int(read_back[i]["i"]) == i + 100
            assert str(read_back[i]["s"]).startswith(f"pyads-arr-{i}")
    finally:
        symbol.write(old_value)
