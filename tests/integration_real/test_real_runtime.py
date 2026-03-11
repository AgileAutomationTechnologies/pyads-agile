"""Real Beckhoff ADS integration tests.

These tests are opt-in and intended for local/lab environments with a running
TwinCAT ADS runtime.
"""

import time
import ctypes
from pathlib import Path
from typing import Any, Generator
from collections import OrderedDict

import pyads
import pytest
from pyads.constants import ADSIGRP_SYM_VALBYHND
from pyads.pyads_ex import adsGetNetIdForPLC

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None


pytestmark = pytest.mark.ads_real


def _load_real_runtime_cfg() -> dict[str, Any]:
    cfg_path = Path(__file__).with_name("real_runtime.toml")
    if not cfg_path.exists() or not cfg_path.is_file() or tomllib is None:
        return {}
    with cfg_path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        return {}
    section = data.get("real_runtime", {})
    return section if isinstance(section, dict) else {}


_REAL_CFG = _load_real_runtime_cfg()


def _cfg_str(key: str, default: str = "") -> str:
    value = _REAL_CFG.get(key, default)
    return str(value).strip()


def _cfg_int(key: str, default: int) -> int:
    value = _REAL_CFG.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _plc_ip() -> str:
    return _cfg_str("plc_ip", "127.0.0.1")


def _plc_ams_net_id() -> str:
    configured = _cfg_str("plc_ams_net_id")
    if configured:
        return configured
    return adsGetNetIdForPLC(_plc_ip())


def _plc_ams_port() -> int:
    return _cfg_int("plc_ams_port", pyads.PORT_TC3PLC1)


def _ads_timeout_ms() -> int:
    return _cfg_int("timeout_ms", 3000)


def _required_symbol_int() -> str:
    symbol = _cfg_str("test_symbol_int")
    if not symbol:
        pytest.skip("Set real_runtime.test_symbol_int in tests/integration_real/real_runtime.toml.")
    return symbol


def _required_symbol_str() -> str:
    symbol = _cfg_str("test_symbol_str")
    if not symbol:
        pytest.skip("Set real_runtime.test_symbol_str in tests/integration_real/real_runtime.toml.")
    return symbol


def _required_symbol_struct() -> str:
    symbol = _cfg_str("test_symbol_struct")
    if not symbol:
        pytest.skip("Set real_runtime.test_symbol_struct in tests/integration_real/real_runtime.toml.")
    return symbol


def _required_symbol_struct_array() -> str:
    symbol = _cfg_str("test_symbol_struct_array")
    if not symbol:
        pytest.skip("Set real_runtime.test_symbol_struct_array in tests/integration_real/real_runtime.toml.")
    return symbol


def _struct_strlen() -> int:
    return _cfg_int("test_struct_strlen", 80)


def _struct_array_size() -> int:
    return _cfg_int("test_struct_array_size", 2)


def _required_rpc_method() -> str:
    method = _cfg_str("test_rpc_method")
    if not method:
        pytest.skip("Set real_runtime.test_rpc_method in tests/integration_real/real_runtime.toml.")
    return method


def _required_rpc_target_parts() -> tuple[str, str]:
    method = _required_rpc_method()
    if "#" not in method:
        pytest.skip("real_runtime.test_rpc_method must look like '<object>#<method>'.")
    object_name, rpc_method = method.split("#", 1)
    if not object_name or not rpc_method:
        pytest.skip("real_runtime.test_rpc_method must look like '<object>#<method>'.")
    return object_name, rpc_method


def _rpc_return_type():
    type_name = _cfg_str("test_rpc_return_type", "UDINT").upper()
    mapping = {
        "BOOL": pyads.PLCTYPE_BOOL,
        "INT": pyads.PLCTYPE_INT,
        "DINT": pyads.PLCTYPE_DINT,
        "UDINT": pyads.PLCTYPE_UDINT,
        "REAL": pyads.PLCTYPE_REAL,
        "LREAL": pyads.PLCTYPE_LREAL,
    }
    plc_type = mapping.get(type_name)
    if plc_type is None:
        pytest.skip(
            "Unsupported real_runtime.test_rpc_return_type. "
            "Use one of BOOL, INT, DINT, UDINT, REAL, LREAL."
        )
    return plc_type


def _rpc_expected_result() -> int | None:
    value = _cfg_str("test_rpc_expected_result")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        pytest.skip("real_runtime.test_rpc_expected_result must be an integer.")


def _rpc_write_param():
    payload_hex = _cfg_str("test_rpc_write_bytes_hex")
    if payload_hex:
        normalized = payload_hex.replace(" ", "")
        if len(normalized) % 2 != 0:
            pytest.skip("real_runtime.test_rpc_write_bytes_hex must have even hex length.")
        try:
            payload = bytes.fromhex(normalized)
        except ValueError:
            pytest.skip("real_runtime.test_rpc_write_bytes_hex is not valid hex.")
        if not payload:
            return None, None
        write_type = ctypes.c_ubyte * len(payload)
        return list(payload), write_type

    type_name = _cfg_str("test_rpc_write_type").upper()
    raw_value = _cfg_str("test_rpc_write_value")
    if not type_name:
        return None, None

    mapping = {
        "BOOL": pyads.PLCTYPE_BOOL,
        "INT": pyads.PLCTYPE_INT,
        "DINT": pyads.PLCTYPE_DINT,
        "UDINT": pyads.PLCTYPE_UDINT,
        "REAL": pyads.PLCTYPE_REAL,
        "LREAL": pyads.PLCTYPE_LREAL,
        "STRING": pyads.PLCTYPE_STRING,
    }
    write_type = mapping.get(type_name)
    if write_type is None:
        pytest.skip(
            "Unsupported real_runtime.test_rpc_write_type. "
            "Use one of BOOL, INT, DINT, UDINT, REAL, LREAL, STRING."
        )
    if raw_value == "":
        pytest.skip("Set real_runtime.test_rpc_write_value when test_rpc_write_type is configured.")
    if type_name == "STRING":
        return raw_value, write_type
    if type_name == "BOOL":
        return raw_value.lower() in ("1", "true", "yes", "on"), write_type
    if type_name in ("REAL", "LREAL"):
        try:
            return float(raw_value), write_type
        except ValueError:
            pytest.skip("real_runtime.test_rpc_write_value must be numeric for REAL/LREAL.")
    try:
        return int(raw_value), write_type
    except ValueError:
        pytest.skip("real_runtime.test_rpc_write_value must be an integer for selected type.")


def _struct_def():
    return (
        ("i", pyads.PLCTYPE_INT, 1),
        ("_s", pyads.PLCTYPE_STRING, 1, _struct_strlen()),
    )


@pytest.fixture
def plc() -> Generator[pyads.Connection, None, None]:
    conn = pyads.Connection(_plc_ams_net_id(), _plc_ams_port(), _plc_ip())
    conn.open()
    conn.set_timeout(_ads_timeout_ms())
    try:
        yield conn
    finally:
        conn.close()


def test_get_ams_real_runtime() -> None:
    expected = _cfg_str("plc_ams_net_id")
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
    if ads_state != pyads.ADSSTATE_RUN:
        pytest.skip("write_control real test requires runtime to start in RUN state.")

    stopped = False
    try:
        plc.write_control(pyads.ADSSTATE_STOP, device_state, 0, pyads.PLCTYPE_INT)
        stopped = True
        state_after_stop = plc.read_state()
        assert state_after_stop is not None
        assert state_after_stop[0] == pyads.ADSSTATE_STOP
    finally:
        if stopped:
            plc.write_control(pyads.ADSSTATE_RUN, device_state, 0, pyads.PLCTYPE_INT)
            state_after_run = plc.read_state()
            assert state_after_run is not None
            assert state_after_run[0] == pyads.ADSSTATE_RUN


def test_rpc_method_call_real(plc: pyads.Connection) -> None:
    method_name = _required_rpc_method()
    write_value, write_type = _rpc_write_param()
    handle = plc.get_handle(method_name)
    if handle is None:
        pytest.fail("Failed to obtain ADS handle for configured RPC method.")
    try:
        try:
            result = plc.read_write(
                ADSIGRP_SYM_VALBYHND,
                handle,
                _rpc_return_type(),
                write_value,
                write_type,
            )
        except pyads.ADSError as exc:
            if getattr(exc, "err_code", None) == 1797:
                pytest.skip(
                    "RPC parameter size mismatch (1797). "
                    "Configure test_rpc_write_type/test_rpc_write_value "
                    "or test_rpc_write_bytes_hex in real_runtime.toml."
                )
            raise
    finally:
        plc.release_handle(handle)

    expected = _rpc_expected_result()
    if expected is not None:
        assert int(result) == expected
    else:
        assert isinstance(result, (bool, int, float))


def test_rpc_method_call_helper_real(plc: pyads.Connection) -> None:
    method_name = _required_rpc_method()
    write_value, write_type = _rpc_write_param()
    try:
        result = plc.call_rpc_method(
            method_name,
            return_type=_rpc_return_type(),
            write_value=write_value,
            write_type=write_type,
        )
    except pyads.ADSError as exc:
        if getattr(exc, "err_code", None) == 1797:
            pytest.skip(
                "RPC parameter size mismatch (1797). "
                "Configure test_rpc_write_type/test_rpc_write_value "
                "or test_rpc_write_bytes_hex in real_runtime.toml."
            )
        raise

    expected = _rpc_expected_result()
    if expected is not None:
        assert int(result) == expected
    else:
        assert isinstance(result, (bool, int, float))


def test_get_object_rpc_real(plc: pyads.Connection) -> None:
    object_name, rpc_method = _required_rpc_target_parts()
    write_value, write_type = _rpc_write_param()
    method_parameters = (
        {rpc_method: [write_type]} if write_type is not None else None
    )
    rpc_obj = plc.get_object(
        object_name,
        method_return_types={rpc_method: _rpc_return_type()},
    )
    try:
        if write_value is None:
            result = getattr(rpc_obj, rpc_method)()
        else:
            result = getattr(rpc_obj, rpc_method)(write_value)
    except pyads.ADSError as exc:
        if getattr(exc, "err_code", None) == 1797:
            pytest.skip(
                "RPC parameter size mismatch (1797). "
                "Configure test_rpc_write_type/test_rpc_write_value "
                "or test_rpc_write_bytes_hex in real_runtime.toml."
            )
        raise

    expected = _rpc_expected_result()
    if expected is not None:
        assert int(result) == expected
    else:
        assert isinstance(result, (bool, int, float))


def test_get_object_rpc_multi_param_real(plc: pyads.Connection) -> None:
    object_name, _ = _required_rpc_target_parts()
    rpc = plc.get_object(
        object_name,
        method_return_types={"m_iSum": pyads.PLCTYPE_INT},
        method_parameters={"m_iSum": [pyads.PLCTYPE_INT, pyads.PLCTYPE_INT]},
    )
    try:
        result = rpc.m_iSum(5, 5)
    except pyads.ADSError as exc:
        if getattr(exc, "err_code", None) == 1808:
            pytest.skip(
                "RPC method m_iSum not found on configured object. "
                "Adjust PLC code or real_runtime.test_rpc_method object."
            )
        raise

    assert int(result) == 10


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
    assert "_s" in value


def test_symbol_structure_write_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_struct()
    symbol = plc.get_symbol(symbol_name, structure_def=_struct_def())
    old_value = symbol.read()
    new_value = {"i": 42, "_s": "pyads-agile-struct"}
    try:
        symbol.write(new_value)
        read_back = symbol.read()
        assert int(read_back["i"]) == 42
        assert str(read_back["_s"]).startswith("pyads-agile-struct")
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
    assert all("i" in item and "_s" in item for item in value)


def test_symbol_structure_array_write_real(plc: pyads.Connection) -> None:
    symbol_name = _required_symbol_struct_array()
    n = _struct_array_size()
    symbol = plc.get_symbol(symbol_name, structure_def=_struct_def(), array_size=n)
    old_value = symbol.read()
    new_value = [{"i": i + 100, "_s": f"pyads-arr-{i}"} for i in range(n)]
    try:
        symbol.write(new_value)
        read_back = symbol.read()
        assert len(read_back) == n
        for i in range(n):
            assert int(read_back[i]["i"]) == i + 100
            assert str(read_back[i]["_s"]).startswith(f"pyads-arr-{i}")
    finally:
        symbol.write(old_value)
