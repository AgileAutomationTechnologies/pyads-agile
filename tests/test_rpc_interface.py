import asyncio
import types
from typing import Any, Awaitable

import pyads
import pytest

from pyads.connection import RpcObject
from pyads.rpc_interface import resolve_rpc_interface_definition


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


def test_ads_stepchain_path_adds_stepchain_metadata():
    @pyads.ads_stepchain_path("GVL.fbStepChain")
    class FB_StepChain:
        def m_Start(self, udiRequestId: pyads.PLCTYPE_UDINT) -> pyads.PLCTYPE_BOOL:
            ...

    definition = resolve_rpc_interface_definition(FB_StepChain)
    assert definition.object_name == "GVL.fbStepChain"
    assert definition.stepchain is True
    assert definition.stepchain_config is not None
    assert definition.stepchain_config.request_id_arg == "udiRequestId"
    assert definition.stepchain_config.step_field == "udiStep"
    assert definition.stepchain_config.step_name_field == "sStepName"
    assert definition.method_argument_names["m_Start"] == ("udiRequestId",)
    assert definition.stepchain_config.completion == "poll"
    assert definition.method_return_types["m_Start"] == pyads.PLCTYPE_BOOL


def test_ads_stepchain_path_completion_notify_is_supported():
    @pyads.ads_stepchain_path("GVL.fbStepChain", completion="notify")
    class FB_StepChainNotify:
        def m_Start(self, udiRequestId: pyads.PLCTYPE_UDINT) -> pyads.StepChainOperation[Any]:
            ...

    definition = resolve_rpc_interface_definition(FB_StepChainNotify)
    assert definition.stepchain_config is not None
    assert definition.stepchain_config.completion == "notify"


def test_ads_stepchain_path_rejects_invalid_completion():
    with pytest.raises(ValueError, match="completion must be either 'poll' or 'notify'"):
        @pyads.ads_stepchain_path("GVL.fbStepChain", completion="invalid")
        class FB_Invalid:
            def m_Start(self, udiRequestId: pyads.PLCTYPE_UDINT) -> pyads.StepChainOperation[Any]:
                ...


def test_ads_async_path_adds_metadata_and_unwraps_future_return_type():
    @pyads.ads_async_path("GVL.fbAsync")
    class FB_Async:
        def m_iSum(
            self,
            a: pyads.PLCTYPE_INT,
            b: pyads.PLCTYPE_INT,
        ) -> asyncio.Future[pyads.PLCTYPE_INT]:
            ...

    definition = resolve_rpc_interface_definition(FB_Async)
    assert definition.object_name == "GVL.fbAsync"
    assert definition.async_interface is True
    assert definition.method_parameters["m_iSum"] == (pyads.PLCTYPE_INT, pyads.PLCTYPE_INT)
    assert definition.method_return_types["m_iSum"] == pyads.PLCTYPE_INT


def test_get_object_rejects_async_only_interface():
    @pyads.ads_async_path("GVL.fbAsync")
    class FB_Async:
        def m_iSum(
            self,
            a: pyads.PLCTYPE_INT,
            b: pyads.PLCTYPE_INT,
        ) -> asyncio.Future[pyads.PLCTYPE_INT]:
            ...

    conn = pyads.Connection("1.1.1.1.1.1", pyads.PORT_TC3PLC1)
    with pytest.raises(TypeError, match="ads_async_path"):
        conn.get_object(FB_Async)


def test_ads_async_path_unwraps_awaitable_return_type():
    @pyads.ads_async_path("GVL.fbAsyncAwaitable")
    class FB_AsyncAwaitable:
        def m_iSum(
            self,
            a: pyads.PLCTYPE_INT,
            b: pyads.PLCTYPE_INT,
        ) -> Awaitable[pyads.PLCTYPE_INT]:
            ...

    definition = resolve_rpc_interface_definition(FB_AsyncAwaitable)
    assert definition.method_return_types["m_iSum"] == pyads.PLCTYPE_INT
