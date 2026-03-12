import types

import pyads
import pytest

from pyads.connection import RpcObject


def _bind_fake_rpc(conn: pyads.Connection, return_value=None):
    calls = []

    def _fake_call(self, method_name, return_type=None, write_value=None, write_type=None):
        calls.append((method_name, return_type, write_value, write_type))
        return return_value

    conn.call_rpc_method = types.MethodType(_fake_call, conn)
    return calls


def test_get_object_from_class_infers_signatures():
    @pyads.ads_path("GVL.fbTestRemoteMethodCall")
    class FB_TestRemoteMethodCall:
        def m_iSum(
            self,
            a: pyads.PLCTYPE_INT,
            b: pyads.PLCTYPE_INT,
        ) -> pyads.PLCTYPE_INT:
            pass

        def m_iSimpleCall(self) -> pyads.PLCTYPE_INT:
            pass

    conn = pyads.Connection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
    calls = _bind_fake_rpc(conn, return_value=42)

    rpc = conn.get_object(FB_TestRemoteMethodCall)
    assert isinstance(rpc, RpcObject)
    assert rpc._object_name == "GVL.fbTestRemoteMethodCall"
    assert rpc._method_parameters["m_iSum"] == (pyads.PLCTYPE_INT, pyads.PLCTYPE_INT)
    assert rpc._method_return_types["m_iSimpleCall"] == pyads.PLCTYPE_INT

    result = rpc.m_iSum(5, 7)
    assert result == 42

    method_name, return_type, write_value, write_type = calls[0]
    assert method_name == "GVL.fbTestRemoteMethodCall#m_iSum"
    assert return_type == pyads.PLCTYPE_INT
    assert write_value is not None
    assert write_type is not None


def test_get_object_manual_overrides_take_precedence():
    @pyads.ads_path("GVL.fbOverride")
    class FB_Override:
        def m_iSum(self, value: pyads.PLCTYPE_INT) -> pyads.PLCTYPE_INT:
            pass

        def m_custom(self, raw) -> None:  # type: ignore[no-untyped-def]
            pass

    conn = pyads.Connection("1.1.1.1.1.1", pyads.PORT_TC3PLC1)
    calls = _bind_fake_rpc(conn, return_value=11)

    rpc = conn.get_object(
        FB_Override,
        method_return_types={"m_iSum": pyads.PLCTYPE_DINT},
        method_parameters={"m_custom": [pyads.PLCTYPE_INT]},
    )

    rpc.m_iSum(1)
    assert calls[0][1] == pyads.PLCTYPE_DINT

    rpc.m_custom(5)
    assert calls[1][0] == "GVL.fbOverride#m_custom"


def test_get_object_rejects_class_without_ads_path():
    class NotDecorated:
        def method(self) -> pyads.PLCTYPE_INT:
            pass

    conn = pyads.Connection("1.1.1.1.1.1", pyads.PORT_TC3PLC1)
    with pytest.raises(TypeError):
        conn.get_object(NotDecorated)
