"""Real ADS integration tests for AsyncConnection APIs."""

import asyncio
from typing import Any, Type

import pyads
import pytest

from tests.integration_real import test_real_runtime as rt


pytestmark = pytest.mark.ads_real


def _new_async_conn() -> pyads.AsyncConnection:
    return pyads.AsyncConnection(rt._plc_ams_net_id(), rt._plc_ams_port(), rt._plc_ip())


def _cfg_bool_or_int(key: str, default: bool | int) -> bool | int:
    raw = rt._cfg_str(key, str(default)).strip().lower()
    if raw in {"true", "1", "yes", "on"}:
        return True
    if raw in {"false", "0", "no", "off"}:
        return False
    try:
        return int(raw)
    except ValueError:
        return default


def _required_stepchain_object() -> str:
    object_name = rt._cfg_str("test_stepchain_object")
    if not object_name:
        pytest.skip("Set real_runtime.test_stepchain_object to run stepchain async integration tests.")
    return object_name


def _stepchain_method() -> str:
    return rt._cfg_str("test_stepchain_method", "m_xStartStepChain")


def _stepchain_abort_method() -> str:
    return rt._cfg_str("test_stepchain_abort_method", "m_xAbortStepChain")


def _stepchain_abort_delay_s() -> float:
    return float(rt._cfg_int("test_stepchain_abort_delay_ms", 250)) / 1000.0


def _make_stepchain_interface(
        object_name: str,
        method_name: str,
) -> Type[Any]:
    @pyads.ads_async_path(object_name)
    class FB_TestRemoteStepChainMethodCall(pyads.StepChainRpcInterface):
        __stepchain_status_symbol__ = rt._cfg_str("test_stepchain_status_symbol") or None
        __stepchain_status_field__ = rt._cfg_str("test_stepchain_status_field", "stStepStatus")
        __stepchain_request_id_field__ = rt._cfg_str("test_stepchain_request_id_field", "udiRequestId")
        __stepchain_request_id_arg__ = rt._cfg_str("test_stepchain_request_id_arg", "udiRequestId")
        __stepchain_busy_field__ = rt._cfg_str("test_stepchain_busy_field", "xBusy") or None
        __stepchain_done_field__ = rt._cfg_str("test_stepchain_done_field", "xDone")
        __stepchain_done_value__ = _cfg_bool_or_int("test_stepchain_done_value", True)
        __stepchain_error_field__ = rt._cfg_str("test_stepchain_error_field", "xError")
        __stepchain_error_value__ = _cfg_bool_or_int("test_stepchain_error_value", True)
        __stepchain_error_code_field__ = rt._cfg_str("test_stepchain_error_code_field", "diErrorCode")
        __stepchain_step_field__ = rt._cfg_str("test_stepchain_step_field", "udiStep") or None
        __stepchain_step_name_field__ = rt._cfg_str("test_stepchain_step_name_field", "sStepName") or None
        __stepchain_step_name_length__ = rt._cfg_int("test_stepchain_step_name_length", 80)
        __stepchain_completion__ = rt._cfg_str("test_stepchain_completion", "poll")
        __stepchain_poll_interval__ = float(rt._cfg_int("test_stepchain_poll_interval_ms", 50)) / 1000.0
        __stepchain_timeout_s__ = float(rt._cfg_int("test_stepchain_timeout_s", 15))

        @pyads.stepchain_start
        def m_xStartStepChain(
                self,
                udiRequestId: pyads.PLCTYPE_UDINT,
        ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
            ...

        def m_xAbortStepChain(self) -> asyncio.Future[pyads.PLCTYPE_BOOL]:
            ...

    if method_name != "m_xStartStepChain":
        setattr(
            FB_TestRemoteStepChainMethodCall,
            method_name,
            FB_TestRemoteStepChainMethodCall.m_xStartStepChain,
        )

    return FB_TestRemoteStepChainMethodCall


def test_async_open_close_real() -> None:
    async def _scenario() -> None:
        conn = _new_async_conn()
        try:
            assert not conn.is_open
            await conn.open()
            assert conn.is_open
            await conn.close()
            assert not conn.is_open
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_async_read_state_real_readable() -> None:
    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            state = await plc.read_state()
            assert state is not None
            assert len(state) == 2

    asyncio.run(_scenario())


def test_async_read_device_info_real_readable() -> None:
    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            info = await plc.read_device_info()
            assert info is not None
            name, version = info
            assert isinstance(name, str)
            assert hasattr(version, "version")
            assert hasattr(version, "revision")
            assert hasattr(version, "build")

    asyncio.run(_scenario())


def test_async_get_local_address_real_readable() -> None:
    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            addr = await plc.get_local_address()
            assert addr is not None
            assert isinstance(addr.netid, str)

    asyncio.run(_scenario())


def test_submit_sum_read_real() -> None:
    symbol_name = rt._required_symbol_int()

    async def _scenario() -> None:
        conn = _new_async_conn()
        try:
            await conn.open()
            fut = conn.submit_sum_read([symbol_name])
            assert isinstance(fut, asyncio.Future)
            values = await fut
            assert symbol_name in values
            assert isinstance(values[symbol_name], int)
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_async_read_by_name_real_readable() -> None:
    symbol_name = rt._required_symbol_int()

    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            value = await plc.read_by_name(symbol_name, pyads.PLCTYPE_INT)
            assert isinstance(value, int)

    asyncio.run(_scenario())


def test_async_write_by_name_real_readable() -> None:
    symbol_name = rt._required_symbol_int()

    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            old_value = await plc.read_by_name(symbol_name, pyads.PLCTYPE_INT)
            new_value = old_value + 1 if old_value < 32767 else old_value - 1
            try:
                await plc.write_by_name(symbol_name, new_value, pyads.PLCTYPE_INT)
                check_value = await plc.read_by_name(symbol_name, pyads.PLCTYPE_INT)
                assert check_value == new_value
            finally:
                await plc.write_by_name(symbol_name, old_value, pyads.PLCTYPE_INT)

    asyncio.run(_scenario())


def test_submit_sum_write_real() -> None:
    symbol_name = rt._required_symbol_int()

    async def _scenario() -> None:
        conn = _new_async_conn()
        try:
            await conn.open()
            old_value = (await conn.sum_read([symbol_name]))[symbol_name]
            new_value = old_value + 1 if old_value < 32767 else old_value - 1

            write_result = await conn.submit_sum_write({symbol_name: new_value})
            assert symbol_name in write_result
            assert "no error" in str(write_result[symbol_name]).lower()

            check_value = (await conn.sum_read([symbol_name]))[symbol_name]
            assert check_value == new_value
        finally:
            try:
                if conn.is_open:
                    await conn.submit_sum_write({symbol_name: old_value})
            except Exception:
                pass
            await conn.aclose()

    asyncio.run(_scenario())


def test_async_read_structure_by_name_real_readable() -> None:
    symbol_name = rt._required_symbol_struct()

    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            value = await plc.read_structure_by_name(symbol_name, rt._struct_def())
            assert isinstance(value, dict)
            assert "i" in value
            assert "_s" in value

    asyncio.run(_scenario())


def test_async_write_structure_by_name_real_readable() -> None:
    symbol_name = rt._required_symbol_struct()

    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            old_value = await plc.read_structure_by_name(symbol_name, rt._struct_def())
            new_value = {"i": 42, "_s": "pyads-agile-async-struct"}
            try:
                await plc.write_structure_by_name(symbol_name, new_value, rt._struct_def())
                read_back = await plc.read_structure_by_name(symbol_name, rt._struct_def())
                assert int(read_back["i"]) == 42
                assert str(read_back["_s"]).startswith("pyads-agile-async-struct")
            finally:
                await plc.write_structure_by_name(symbol_name, old_value, rt._struct_def())

    asyncio.run(_scenario())


def test_async_read_structure_array_by_name_real_readable() -> None:
    symbol_name = rt._required_symbol_struct_array()
    array_size = rt._struct_array_size()

    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            value = await plc.read_structure_by_name(
                symbol_name,
                rt._struct_def(),
                array_size=array_size,
            )
            assert isinstance(value, list)
            assert len(value) == array_size
            assert all("i" in item and "_s" in item for item in value)

    asyncio.run(_scenario())


def test_async_write_structure_array_by_name_real_readable() -> None:
    symbol_name = rt._required_symbol_struct_array()
    array_size = rt._struct_array_size()

    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            old_value = await plc.read_structure_by_name(
                symbol_name,
                rt._struct_def(),
                array_size=array_size,
            )
            new_value = [
                {"i": i + 100, "_s": f"pyads-async-arr-{i}"}
                for i in range(array_size)
            ]
            try:
                await plc.write_structure_by_name(
                    symbol_name,
                    new_value,
                    rt._struct_def(),
                    array_size=array_size,
                )
                read_back = await plc.read_structure_by_name(
                    symbol_name,
                    rt._struct_def(),
                    array_size=array_size,
                )
                assert len(read_back) == array_size
                for i in range(array_size):
                    assert int(read_back[i]["i"]) == i + 100
                    assert str(read_back[i]["_s"]).startswith(f"pyads-async-arr-{i}")
            finally:
                await plc.write_structure_by_name(
                    symbol_name,
                    old_value,
                    rt._struct_def(),
                    array_size=array_size,
                )

    asyncio.run(_scenario())


def test_submit_rpc_method_real() -> None:
    method_name = rt._required_rpc_method()
    write_value, write_type = rt._rpc_write_param()

    async def _scenario() -> None:
        conn = _new_async_conn()
        try:
            await conn.open()
            try:
                result = await conn.submit_rpc_method(
                    method_name,
                    return_type=rt._rpc_return_type(),
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

            expected = rt._rpc_expected_result()
            if expected is not None:
                assert int(result) == expected
            else:
                assert isinstance(result, (bool, int, float))
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_async_write_control_real_readable() -> None:
    async def _scenario() -> None:
        async with _new_async_conn() as plc:
            state = await plc.read_state()
            assert state is not None
            ads_state, device_state = state
            if ads_state != pyads.ADSSTATE_RUN:
                pytest.skip("write_control real test requires runtime to start in RUN state.")

            stopped = False
            try:
                await plc.write_control(
                    pyads.ADSSTATE_STOP,
                    device_state,
                    0,
                    pyads.PLCTYPE_INT,
                )
                stopped = True
                state_after_stop = await plc.read_state()
                assert state_after_stop is not None
                assert state_after_stop[0] == pyads.ADSSTATE_STOP
            finally:
                if stopped:
                    await plc.write_control(
                        pyads.ADSSTATE_RUN,
                        device_state,
                        0,
                        pyads.PLCTYPE_INT,
                    )
                    state_after_run = await plc.read_state()
                    assert state_after_run is not None
                    assert state_after_run[0] == pyads.ADSSTATE_RUN

    asyncio.run(_scenario())


def test_get_async_object_rpc_real() -> None:
    object_name, rpc_method = rt._required_rpc_target_parts()
    write_value, write_type = rt._rpc_write_param()

    async def _scenario() -> None:
        conn = _new_async_conn()
        try:
            await conn.open()
            rpc = conn.get_async_object(
                object_name,
                method_return_types={rpc_method: rt._rpc_return_type()},
            )
            try:
                if write_value is None:
                    result = await getattr(rpc, rpc_method)()
                else:
                    result = await getattr(rpc, rpc_method)(write_value)
            except pyads.ADSError as exc:
                if getattr(exc, "err_code", None) == 1797:
                    pytest.skip(
                        "RPC parameter size mismatch (1797). "
                        "Configure test_rpc_write_type/test_rpc_write_value "
                        "or test_rpc_write_bytes_hex in real_runtime.toml."
                    )
                if getattr(exc, "err_code", None) == 1808:
                    pytest.skip(
                        "Configured RPC method not found on target object."
                    )
                raise

            expected = rt._rpc_expected_result()
            if expected is not None:
                assert int(result) == expected
            else:
                assert isinstance(result, (bool, int, float))
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_object_rpc_class_interface_real() -> None:
    object_name, _ = rt._required_rpc_target_parts()

    @pyads.ads_async_path(object_name)
    class FB_TestRemoteMethodCall:
        def m_iSum(
                self,
                a: pyads.PLCTYPE_INT,
                b: pyads.PLCTYPE_INT,
        ) -> asyncio.Future[pyads.PLCTYPE_INT]:
            ...

    async def _scenario() -> None:
        conn = _new_async_conn()
        try:
            await conn.open()
            rpc_iface = conn.get_async_object(FB_TestRemoteMethodCall)
            try:
                fut = rpc_iface.m_iSum(4, 6)
                fut2 = rpc_iface.m_iSum(4, 6)
                #assert isinstance(fut, asyncio.Future)
                #assert isinstance(fut2, asyncio.Future)
                result = await fut
                result2 = await fut2
            except pyads.ADSError as exc:
                if getattr(exc, "err_code", None) == 1808:
                    pytest.skip(
                        "RPC method m_iSum not found on configured object. "
                        "Adjust PLC code or real_runtime.test_rpc_method object."
                    )
                raise
            assert int(result) == 10
            assert int(result2) == 10
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_object_stepchain_interface_real() -> None:
    object_name = _required_stepchain_object()
    method_name = _stepchain_method()
    interface_cls = _make_stepchain_interface(object_name, method_name)
    request_id_field = rt._cfg_str("test_stepchain_request_id_field", "udiRequestId")
    busy_field = rt._cfg_str("test_stepchain_busy_field", "xBusy") or None
    done_field = rt._cfg_str("test_stepchain_done_field", "xDone")
    error_field = rt._cfg_str("test_stepchain_error_field", "xError")
    error_code_field = rt._cfg_str("test_stepchain_error_code_field", "diErrorCode")
    step_field = rt._cfg_str("test_stepchain_step_field", "udiStep") or None
    step_name_field = rt._cfg_str("test_stepchain_step_name_field", "sStepName") or None

    async def _scenario() -> None:
        conn = _new_async_conn()
        try:
            await conn.open()
            rpc_iface = conn.get_async_object(interface_cls)
            status_root = rpc_iface.status_symbol()
            request_symbol = f"{status_root}.{request_id_field}"
            done_symbol = f"{status_root}.{done_field}"
            error_symbol = f"{status_root}.{error_field}"
            error_code_symbol = (
                f"{status_root}.{error_code_field}" if error_code_field else None
            )
            busy_symbol = f"{status_root}.{busy_field}" if busy_field else None
            step_symbol = f"{status_root}.{step_field}" if step_field else None
            step_name_symbol = (
                f"{status_root}.{step_name_field}" if step_name_field else None
            )
            start_stepchain = getattr(rpc_iface, method_name)
            op = start_stepchain()
            assert isinstance(op, pyads.StepChainOperation)
            accepted = await op.accepted
            if isinstance(accepted, bool) and not accepted:
                pytest.skip("Stepchain start method was rejected by PLC (busy or unavailable).")
            try:
                done_result = await op
            except TimeoutError:
                pytest.skip(
                    "Timed out waiting for stepchain completion. "
                    "Adjust stepchain status fields/timeout in real_runtime.toml."
                )
            assert isinstance(done_result, dict)
            assert request_symbol in done_result
            assert done_symbol in done_result and bool(done_result[done_symbol])
            assert error_symbol in done_result and not bool(done_result[error_symbol])
            if busy_symbol:
                assert busy_symbol in done_result
            if step_symbol:
                assert step_symbol in done_result
            if step_name_symbol:
                assert step_name_symbol in done_result
            if error_code_symbol:
                assert error_code_symbol in done_result
            assert int(done_result[request_symbol]) == int(op.request_id)

            status = await rpc_iface.read_status()
            assert isinstance(status, dict)
            expected_fields = [request_id_field, done_field, error_field, error_code_field]
            if busy_field:
                expected_fields.append(busy_field)
            if step_field:
                expected_fields.append(step_field)
            if step_name_field:
                expected_fields.append(step_name_field)
            for field in expected_fields:
                assert field in status
            assert int(status[request_id_field]) == int(op.request_id)
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_object_stepchain_interface_real_readable_usage() -> None:
    """Mimic the README-style stepchain snippet in an end-to-end scenario."""

    object_name = _required_stepchain_object()
    method_name = _stepchain_method()
    status_symbol = rt._cfg_str("test_stepchain_status_symbol") or None
    status_field = rt._cfg_str("test_stepchain_status_field", "stStepStatus")
    request_id_field = rt._cfg_str("test_stepchain_request_id_field", "udiRequestId")
    request_id_arg = rt._cfg_str("test_stepchain_request_id_arg", "udiRequestId")
    busy_field = rt._cfg_str("test_stepchain_busy_field", "xBusy") or None
    done_field = rt._cfg_str("test_stepchain_done_field", "xDone")
    done_value = _cfg_bool_or_int("test_stepchain_done_value", True)
    error_field = rt._cfg_str("test_stepchain_error_field", "xError")
    error_value = _cfg_bool_or_int("test_stepchain_error_value", True)
    error_code_field = rt._cfg_str("test_stepchain_error_code_field", "diErrorCode")
    step_field = rt._cfg_str("test_stepchain_step_field", "udiStep") or None
    step_name_field = rt._cfg_str("test_stepchain_step_name_field", "sStepName") or None
    step_name_length = rt._cfg_int("test_stepchain_step_name_length", 80)
    completion = rt._cfg_str("test_stepchain_completion", "poll")
    poll_interval = float(rt._cfg_int("test_stepchain_poll_interval_ms", 50)) / 1000.0
    timeout_s = float(rt._cfg_int("test_stepchain_timeout_s", 15))

    @pyads.ads_async_path(object_name)
    class FB_TestRemoteStepChainMethodCall(pyads.StepChainRpcInterface):
        __stepchain_status_symbol__ = status_symbol
        __stepchain_status_field__ = status_field
        __stepchain_request_id_field__ = request_id_field
        __stepchain_request_id_arg__ = request_id_arg
        __stepchain_busy_field__ = busy_field
        __stepchain_done_field__ = done_field
        __stepchain_done_value__ = done_value
        __stepchain_error_field__ = error_field
        __stepchain_error_value__ = error_value
        __stepchain_error_code_field__ = error_code_field
        __stepchain_step_field__ = step_field
        __stepchain_step_name_field__ = step_name_field
        __stepchain_step_name_length__ = step_name_length
        __stepchain_completion__ = completion
        __stepchain_poll_interval__ = poll_interval
        __stepchain_timeout_s__ = timeout_s

        @pyads.stepchain_start
        def m_xStartStepChain(
            self,
            udiRequestId: pyads.PLCTYPE_UDINT,
        ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
            ...

        def m_xAbortStepChain(self) ->  asyncio.Future[pyads.PLCTYPE_BOOL]:
            ...
        
    async def _scenario() -> None:
        conn = _new_async_conn()
        try:
            await conn.open()
            rpc_iface = conn.get_async_object(FB_TestRemoteStepChainMethodCall)
            status_root = rpc_iface.status_symbol()
            operation: pyads.StepChainOp = rpc_iface.m_xStartStepChain(10101)
            accepted = await operation.accepted
            if isinstance(accepted, bool) and not accepted:
                pytest.skip("Stepchain start method was rejected by PLC (busy or unavailable).")

            try:
                completion = await operation
            except TimeoutError:
                pytest.skip(
                    "Timed out waiting for stepchain completion. "
                    "Adjust stepchain status fields/timeout in real_runtime.toml."
                )
            assert isinstance(completion, dict)
            assert completion[f"{status_root}.{done_field}"]
            assert not completion[f"{status_root}.{error_field}"]
            assert int(completion[f"{status_root}.{request_id_field}"]) == int(operation.request_id)

            status = await rpc_iface.read_status()
            assert isinstance(status, dict)
            assert request_id_field in status
            assert done_field in status
            assert error_field in status
            assert error_code_field in status
            assert int(status[request_id_field]) == int(operation.request_id)
            if busy_field:
                assert busy_field in status
            if step_field:
                assert step_field in status
            if step_name_field:
                assert step_name_field in status
        finally:
            await conn.aclose()

    asyncio.run(_scenario())


def test_get_async_object_stepchain_abort_real_readable() -> None:
    object_name = _required_stepchain_object()
    method_name = _stepchain_method()
    abort_method_name = _stepchain_abort_method()
    interface_cls = _make_stepchain_interface(object_name, method_name)
    request_id_field = rt._cfg_str("test_stepchain_request_id_field", "udiRequestId")
    busy_field = rt._cfg_str("test_stepchain_busy_field", "xBusy") or None
    done_field = rt._cfg_str("test_stepchain_done_field", "xDone")
    error_field = rt._cfg_str("test_stepchain_error_field", "xError")
    error_code_field = rt._cfg_str("test_stepchain_error_code_field", "diErrorCode")
    step_name_field = rt._cfg_str("test_stepchain_step_name_field", "sStepName") or None
    abort_delay_s = _stepchain_abort_delay_s()

    async def _scenario() -> None:
        async with _new_async_conn() as conn:
            rpc_iface = conn.get_async_object(interface_cls)
            start_stepchain = getattr(rpc_iface, method_name)
            abort_stepchain = getattr(rpc_iface, abort_method_name)

            operation = start_stepchain()
            accepted = await operation.accepted
            if isinstance(accepted, bool) and not accepted:
                pytest.skip("Stepchain start method was rejected by PLC (busy or unavailable).")

            await asyncio.sleep(abort_delay_s)
            try:
                abort_result = await abort_stepchain()
            except pyads.ADSError as exc:
                if getattr(exc, "err_code", None) == 1808:
                    pytest.skip(
                        "Configured abort RPC method not found on target object. "
                        "Add m_xAbortStepChain to the TwinCAT FB or update real_runtime.toml."
                    )
                raise

            assert isinstance(abort_result, bool)
            assert abort_result is True

            try:
                await operation
            except RuntimeError as exc:
                error_text = str(exc)
                assert "error_code=-2" in error_text or "error_code=" in error_text
            except TimeoutError:
                pytest.skip(
                    "Timed out waiting for stepchain abort completion. "
                    "Ensure the PLC abort method clears busy and updates the status struct."
                )
            else:
                pytest.fail("Aborted stepchain should raise RuntimeError because the PLC reports xError = TRUE.")

            status_root = rpc_iface.status_symbol()
            status = await rpc_iface.read_status()
            assert int(status[request_id_field]) == int(operation.request_id)
            if busy_field:
                assert not bool(status[busy_field])
            assert not bool(status[done_field])
            assert bool(status[error_field])
            assert int(status[error_code_field]) == -2
            if step_name_field:
                assert str(status[step_name_field]).lower().startswith("abort")

    asyncio.run(_scenario())
