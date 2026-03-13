import asyncio
import time
import types
from typing import Any, Dict, List

import pyads
import pytest


def test_submit_sum_read_returns_future() -> None:
    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            called: Dict[str, Any] = {}

            def _fake_read_list_by_name(
                    self: pyads.Connection,
                    data_names: List[str],
                    cache_symbol_info: bool = True,
                    ads_sub_commands: int = 500,
                    structure_defs: Dict[str, Any] = None,
            ) -> Dict[str, Any]:
                called["data_names"] = data_names
                called["cache_symbol_info"] = cache_symbol_info
                called["ads_sub_commands"] = ads_sub_commands
                called["structure_defs"] = structure_defs
                return {name: ix for ix, name in enumerate(data_names)}

            conn.sync_connection.read_list_by_name = types.MethodType(
                _fake_read_list_by_name, conn.sync_connection
            )

            fut = conn.submit_sum_read(["MAIN.a", "MAIN.b"])
            assert isinstance(fut, asyncio.Future)

            result = await fut
            assert result == {"MAIN.a": 0, "MAIN.b": 1}
            assert called["data_names"] == ["MAIN.a", "MAIN.b"]
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_submit_sum_read_is_serialized_per_connection() -> None:
    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            state: Dict[str, Any] = {
                "active_calls": 0,
                "max_active_calls": 0,
                "events": [],
            }

            def _fake_read_list_by_name(
                    self: pyads.Connection,
                    data_names: List[str],
                    cache_symbol_info: bool = True,
                    ads_sub_commands: int = 500,
                    structure_defs: Dict[str, Any] = None,
            ) -> Dict[str, Any]:
                label = data_names[0]
                state["active_calls"] += 1
                state["max_active_calls"] = max(
                    state["max_active_calls"], state["active_calls"]
                )
                state["events"].append(f"start:{label}")
                time.sleep(0.03)
                state["events"].append(f"end:{label}")
                state["active_calls"] -= 1
                return {label: label}

            conn.sync_connection.read_list_by_name = types.MethodType(
                _fake_read_list_by_name, conn.sync_connection
            )

            first = conn.submit_sum_read(["first"])
            second = conn.submit_sum_read(["second"])
            results = await asyncio.gather(first, second)

            assert results == [{"first": "first"}, {"second": "second"}]
            assert state["max_active_calls"] == 1
            assert state["events"] == [
                "start:first",
                "end:first",
                "start:second",
                "end:second",
            ]
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_object_returns_future() -> None:
    @pyads.ads_path("GVL.fbTestRemoteMethodCall")
    class AsyncFB:
        def m_iSum(
                self,
                a: pyads.PLCTYPE_INT,
                b: pyads.PLCTYPE_INT,
        ) -> Any:
            pass

    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            calls: List[Any] = []

            def _fake_call_rpc_method(
                    self: pyads.Connection,
                    method_name: str,
                    return_type: Any = None,
                    write_value: Any = None,
                    write_type: Any = None,
            ) -> int:
                calls.append((method_name, return_type, write_value, write_type))
                return 10

            conn.sync_connection.call_rpc_method = types.MethodType(
                _fake_call_rpc_method, conn.sync_connection
            )

            rpc = conn.get_async_object(AsyncFB)
            fut = rpc.m_iSum(5, 5)
            assert isinstance(fut, asyncio.Future)
            result = await fut
            assert result == 10
            assert calls
            assert calls[0][0] == "GVL.fbTestRemoteMethodCall#m_iSum"
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_object_with_ads_async_path_infers_return_type() -> None:
    @pyads.ads_async_path("GVL.fbTestRemoteMethodCall")
    class AsyncFB:
        def m_iSum(
                self,
                a: pyads.PLCTYPE_INT,
                b: pyads.PLCTYPE_INT,
        ) -> asyncio.Future[pyads.PLCTYPE_INT]:
            ...

    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            calls: List[Any] = []

            def _fake_call_rpc_method(
                    self: pyads.Connection,
                    method_name: str,
                    return_type: Any = None,
                    write_value: Any = None,
                    write_type: Any = None,
            ) -> int:
                calls.append((method_name, return_type, write_value, write_type))
                return 10

            conn.sync_connection.call_rpc_method = types.MethodType(
                _fake_call_rpc_method, conn.sync_connection
            )

            rpc = conn.get_async_object(AsyncFB)
            fut = rpc.m_iSum(5, 5)
            assert isinstance(fut, asyncio.Future)
            result = await fut
            assert result == 10
            assert calls
            assert calls[0][0] == "GVL.fbTestRemoteMethodCall#m_iSum"
            assert calls[0][1] == pyads.PLCTYPE_INT
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_submit_after_aclose_raises_runtime_error() -> None:
    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        await conn.aclose()
        with pytest.raises(RuntimeError):
            conn.submit_sum_read(["MAIN.a"])

    asyncio.run(_scenario())


def test_async_wrappers_for_sync_methods() -> None:
    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            calls: List[Any] = []

            def _fake_read_by_name(
                    self: pyads.Connection,
                    data_name: str,
                    plc_datatype: Any = None,
                    return_ctypes: bool = False,
                    handle: Any = None,
                    check_length: bool = True,
                    cache_symbol_info: bool = True,
            ) -> int:
                calls.append(("read_by_name", data_name, plc_datatype))
                return 123

            def _fake_write_by_name(
                    self: pyads.Connection,
                    data_name: str,
                    value: Any,
                    plc_datatype: Any = None,
                    handle: Any = None,
                    cache_symbol_info: bool = True,
            ) -> None:
                calls.append(("write_by_name", data_name, value, plc_datatype))

            conn.sync_connection.read_by_name = types.MethodType(
                _fake_read_by_name, conn.sync_connection
            )
            conn.sync_connection.write_by_name = types.MethodType(
                _fake_write_by_name, conn.sync_connection
            )

            result = await conn.read_by_name("MAIN.x", pyads.PLCTYPE_INT)
            assert result == 123
            await conn.write_by_name("MAIN.x", 7, pyads.PLCTYPE_INT)
            assert calls == [
                ("read_by_name", "MAIN.x", pyads.PLCTYPE_INT),
                ("write_by_name", "MAIN.x", 7, pyads.PLCTYPE_INT),
            ]
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_stepchain_object_returns_operation_and_completes() -> None:
    @pyads.ads_async_path("GVL.fbStepChain")
    class AsyncFBStepChain(pyads.StepChainRpcInterface):
        @pyads.stepchain_start
        def m_Start(
                self,
                udiRequestId: pyads.PLCTYPE_UDINT,
        ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
            ...

    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            poll_count = {"count": 0}

            def _fake_call_rpc_method(
                    self: pyads.Connection,
                    method_name: str,
                    return_type: Any = None,
                    write_value: Any = None,
                    write_type: Any = None,
            ) -> bool:
                return True

            def _fake_read_list_by_name(
                    self: pyads.Connection,
                    data_names: List[str],
                    cache_symbol_info: bool = True,
                    ads_sub_commands: int = 500,
                    structure_defs: Dict[str, Any] = None,
            ) -> Dict[str, Any]:
                poll_count["count"] += 1
                done_now = poll_count["count"] >= 2
                values: Dict[str, Any] = {}
                for name in data_names:
                    if name.endswith(".udiRequestId"):
                        values[name] = 1
                    elif name.endswith(".xBusy"):
                        values[name] = not done_now
                    elif name.endswith(".xDone"):
                        values[name] = done_now
                    elif name.endswith(".xError"):
                        values[name] = False
                    elif name.endswith(".diErrorCode"):
                        values[name] = 0
                    else:
                        values[name] = 0
                return values

            conn.sync_connection.call_rpc_method = types.MethodType(
                _fake_call_rpc_method, conn.sync_connection
            )
            conn.sync_connection.read_list_by_name = types.MethodType(
                _fake_read_list_by_name, conn.sync_connection
            )

            rpc = conn.get_async_object(AsyncFBStepChain)
            status_root = rpc.status_symbol()
            op = rpc.m_Start()
            assert isinstance(op, pyads.StepChainOperation)
            assert op.request_id == 1
            accepted = await op.accepted
            assert accepted is True
            done_result = await op
            assert isinstance(done_result, dict)
            assert done_result[f"{status_root}.udiRequestId"] == 1
            assert done_result[f"{status_root}.xDone"] is True
            assert done_result[f"{status_root}.xError"] is False
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_stepchain_object_raises_on_error_status() -> None:
    @pyads.ads_async_path("GVL.fbStepChain")
    class AsyncFBStepChain(pyads.StepChainRpcInterface):
        @pyads.stepchain_start
        def m_Start(
                self,
                udiRequestId: pyads.PLCTYPE_UDINT,
        ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
            ...

    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            def _fake_call_rpc_method(
                    self: pyads.Connection,
                    method_name: str,
                    return_type: Any = None,
                    write_value: Any = None,
                    write_type: Any = None,
            ) -> bool:
                return True

            def _fake_read_list_by_name(
                    self: pyads.Connection,
                    data_names: List[str],
                    cache_symbol_info: bool = True,
                    ads_sub_commands: int = 500,
                    structure_defs: Dict[str, Any] = None,
            ) -> Dict[str, Any]:
                values: Dict[str, Any] = {}
                for name in data_names:
                    if name.endswith(".udiRequestId"):
                        values[name] = 1
                    elif name.endswith(".xBusy"):
                        values[name] = False
                    elif name.endswith(".xDone"):
                        values[name] = False
                    elif name.endswith(".xError"):
                        values[name] = True
                    elif name.endswith(".diErrorCode"):
                        values[name] = 1234
                    else:
                        values[name] = 0
                return values

            conn.sync_connection.call_rpc_method = types.MethodType(
                _fake_call_rpc_method, conn.sync_connection
            )
            conn.sync_connection.read_list_by_name = types.MethodType(
                _fake_read_list_by_name, conn.sync_connection
            )

            rpc = conn.get_async_object(AsyncFBStepChain)
            op = rpc.m_Start()
            with pytest.raises(RuntimeError, match="error_code=1234"):
                await op
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_stepchain_object_notify_completion() -> None:
    @pyads.ads_async_path("GVL.fbStepChain")
    class AsyncFBStepChainNotify(pyads.StepChainRpcInterface):
        __stepchain_completion__ = "notify"

        @pyads.stepchain_start
        def m_Start(
                self,
                udiRequestId: pyads.PLCTYPE_UDINT,
        ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
            ...

    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            state = {"done": False}
            callbacks: List[Any] = []
            cleanup_calls: List[Any] = []

            def _fake_call_rpc_method(
                    self: pyads.Connection,
                    method_name: str,
                    return_type: Any = None,
                    write_value: Any = None,
                    write_type: Any = None,
            ) -> bool:
                return True

            def _fake_read_list_by_name(
                    self: pyads.Connection,
                    data_names: List[str],
                    cache_symbol_info: bool = True,
                    ads_sub_commands: int = 500,
                    structure_defs: Dict[str, Any] = None,
            ) -> Dict[str, Any]:
                values: Dict[str, Any] = {}
                for name in data_names:
                    if name.endswith(".udiRequestId"):
                        values[name] = 1
                    elif name.endswith(".xBusy"):
                        values[name] = not state["done"]
                    elif name.endswith(".xDone"):
                        values[name] = state["done"]
                    elif name.endswith(".xError"):
                        values[name] = False
                    elif name.endswith(".diErrorCode"):
                        values[name] = 0
                    else:
                        values[name] = 0
                return values

            def _fake_add_notification_with_auto_attr(
                    self: pyads.AsyncConnection,
                    symbol_name: str,
                    callback: Any,
            ) -> Any:
                callbacks.append(callback)
                return (len(callbacks), 0)

            def _fake_del_notifications(
                    self: pyads.AsyncConnection,
                    handles: List[Any],
            ) -> None:
                cleanup_calls.append(list(handles))

            conn.sync_connection.call_rpc_method = types.MethodType(
                _fake_call_rpc_method, conn.sync_connection
            )
            conn.sync_connection.read_list_by_name = types.MethodType(
                _fake_read_list_by_name, conn.sync_connection
            )
            conn._add_notification_with_auto_attr = types.MethodType(
                _fake_add_notification_with_auto_attr, conn
            )
            conn._del_notifications = types.MethodType(
                _fake_del_notifications, conn
            )

            rpc = conn.get_async_object(AsyncFBStepChainNotify)
            status_root = rpc.status_symbol()
            op = rpc.m_Start()

            accepted = await op.accepted
            assert accepted is True
            assert callbacks  # ensure notification registration happened

            state["done"] = True
            for cb in callbacks:
                cb(None, "")

            result = await op
            assert isinstance(result, dict)
            assert result[f"{status_root}.xDone"] is True
            assert result[f"{status_root}.xError"] is False
            assert cleanup_calls
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_stepchain_status_helpers_are_predefined() -> None:
    @pyads.ads_async_path("GVL.fbStepChain")
    class AsyncFBStepChain(pyads.StepChainRpcInterface):
        @pyads.stepchain_start
        def m_xStartStepChain(
                self,
                udiRequestId: pyads.PLCTYPE_UDINT,
        ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
            ...

    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            captured: Dict[str, Any] = {}

            def _fake_read_list_by_name(
                    self: pyads.Connection,
                    data_names: List[str],
                    cache_symbol_info: bool = True,
                    ads_sub_commands: int = 500,
                    structure_defs: Dict[str, Any] = None,
            ) -> Dict[str, Any]:
                captured["data_names"] = list(data_names)
                return {
                    "GVL.fbStepChain.stStepStatus.udiRequestId": 12,
                    "GVL.fbStepChain.stStepStatus.xBusy": False,
                    "GVL.fbStepChain.stStepStatus.xDone": True,
                    "GVL.fbStepChain.stStepStatus.xError": False,
                    "GVL.fbStepChain.stStepStatus.diErrorCode": 0,
                    "GVL.fbStepChain.stStepStatus.udiStep": 100,
                    "GVL.fbStepChain.stStepStatus.sStepName": "Done",
                }

            conn.sync_connection.read_list_by_name = types.MethodType(
                _fake_read_list_by_name, conn.sync_connection
            )

            rpc = conn.get_async_object(AsyncFBStepChain)
            status_symbol = rpc.status_symbol()
            assert status_symbol == "GVL.fbStepChain.stStepStatus"

            structure_def = rpc.get_status_structure_def()
            assert structure_def[0][0] == "udiRequestId"
            assert structure_def[1][0] == "xBusy"
            assert structure_def[2][0] == "xDone"
            assert structure_def[3][0] == "xError"
            assert structure_def[4][0] == "diErrorCode"
            assert structure_def[5][0] == "udiStep"
            assert structure_def[6][0] == "sStepName"
            assert structure_def[6][3] == 80

            status = await rpc.read_status()
            assert status["sStepName"] == "Done"
            assert "GVL.fbStepChain.stStepStatus.udiRequestId" in captured["data_names"]
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_object_supports_mixed_plain_and_stepchain_methods() -> None:
    @pyads.ads_async_path("GVL.fbStepChain")
    class AsyncFBStepChain(pyads.StepChainRpcInterface):
        @pyads.stepchain_start
        def m_Start(
                self,
                udiRequestId: pyads.PLCTYPE_UDINT,
        ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
            ...

        def m_iPlain(self, value: pyads.PLCTYPE_INT) -> asyncio.Future[pyads.PLCTYPE_INT]:
            ...

    async def _scenario() -> None:
        conn = pyads.AsyncConnection("1.2.3.4.5.6", pyads.PORT_TC3PLC1)
        try:
            calls: List[Any] = []

            def _fake_call_rpc_method(
                    self: pyads.Connection,
                    method_name: str,
                    return_type: Any = None,
                    write_value: Any = None,
                    write_type: Any = None,
            ) -> Any:
                calls.append((method_name, return_type, write_value, write_type))
                if method_name.endswith("#m_iPlain"):
                    return 42
                return True

            def _fake_read_list_by_name(
                    self: pyads.Connection,
                    data_names: List[str],
                    cache_symbol_info: bool = True,
                    ads_sub_commands: int = 500,
                    structure_defs: Dict[str, Any] = None,
            ) -> Dict[str, Any]:
                values: Dict[str, Any] = {}
                for name in data_names:
                    if name.endswith(".udiRequestId"):
                        values[name] = 1
                    elif name.endswith(".xBusy"):
                        values[name] = False
                    elif name.endswith(".xDone"):
                        values[name] = True
                    elif name.endswith(".xError"):
                        values[name] = False
                    elif name.endswith(".diErrorCode"):
                        values[name] = 0
                    else:
                        values[name] = 0
                return values

            conn.sync_connection.call_rpc_method = types.MethodType(
                _fake_call_rpc_method, conn.sync_connection
            )
            conn.sync_connection.read_list_by_name = types.MethodType(
                _fake_read_list_by_name, conn.sync_connection
            )

            rpc = conn.get_async_object(AsyncFBStepChain)
            plain = rpc.m_iPlain(10)
            assert isinstance(plain, asyncio.Future)
            assert await plain == 42

            op = rpc.m_Start()
            assert isinstance(op, pyads.StepChainOperation)
            assert await op.accepted is True
            result = await op
            assert result["GVL.fbStepChain.stStepStatus.xDone"] is True
        finally:
            await conn.aclose()

    asyncio.run(_scenario())
