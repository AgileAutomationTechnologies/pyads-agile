"""Async ADS connection utilities with serialized worker execution.

This module provides an asyncio-facing wrapper around :class:`pyads.Connection`
that guarantees in-order execution of ADS calls by running all sync operations
on a dedicated single worker thread per connection.
"""

from __future__ import annotations

import asyncio
import inspect
import itertools
import queue
import threading
from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, Dict, Generic, List, Optional, Sequence, Set, Tuple, Type, TypeVar, Union, cast, overload

from .ads import StructureDef
from .connection import Connection, RpcInterfaceT, RpcObject
from .constants import (
    MAX_ADS_SUB_COMMANDS,
    PLCTYPE_BOOL,
    PLCTYPE_DINT,
    PLCTYPE_STRING,
    PLCTYPE_UDINT,
    PLCDataType,
)
from .pyads_ex import adsGetSymbolInfo
from .rpc_interface import StepChainConfig, resolve_rpc_interface_definition
from .structs import AdsVersion, AmsAddr, NotificationAttrib

T = TypeVar("T")
AsyncRpcInterfaceT = TypeVar("AsyncRpcInterfaceT")
StepChainAcceptedT = TypeVar("StepChainAcceptedT")


@dataclass(frozen=True)
class _QueuedCall:
    """Single queued operation for worker execution."""

    fn: Callable[..., Any]
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[Any]


class _ShutdownSignal:
    """Marker object to stop the worker thread."""


class StepChainOperation(Generic[StepChainAcceptedT]):
    """Handle for a stepchain-style async RPC call.

    ``accepted`` resolves when the underlying RPC method has returned.
    ``done`` resolves when stepchain status indicates completion.
    Awaiting the operation itself is equivalent to awaiting ``done``.
    """

    def __init__(
            self,
            request_id: int,
            accepted: "asyncio.Future[StepChainAcceptedT]",
            done: "asyncio.Future[Any]",
    ) -> None:
        self.request_id = request_id
        self.accepted = accepted
        self.done = done

    def cancel(self) -> bool:
        """Cancel waiting for completion."""
        return self.done.cancel()

    def __await__(self) -> Any:
        return self.done.__await__()


class AsyncRpcObject:
    """Async proxy wrapper around :class:`RpcObject`.

    Dynamic RPC method calls return an ``asyncio.Future`` that resolves when
    the synchronous RPC invocation has returned on the ADS side.
    """

    def __init__(self, connection: "AsyncConnection", rpc_object: RpcObject) -> None:
        self._connection = connection
        self._rpc_object = rpc_object

    def set_return_type(self, method_name: str, plc_type: Type["PLCDataType"]) -> None:
        """Configure or override the return type for a method."""
        self._rpc_object.set_return_type(method_name, plc_type)

    def __getattr__(self, method_name: str) -> Callable[..., asyncio.Future[Any]]:
        if method_name.startswith("_"):
            raise AttributeError(method_name)

        sync_method = getattr(self._rpc_object, method_name)

        def _invoke(*args: Any, **kwargs: Any) -> asyncio.Future[Any]:
            return self._connection._submit(sync_method, *args, **kwargs)

        return _invoke


class AsyncStepChainRpcObject(AsyncRpcObject):
    """Async RPC proxy with built-in stepchain completion tracking."""

    def __init__(
            self,
            connection: "AsyncConnection",
            rpc_object: RpcObject,
            object_name: str,
            method_argument_names: Dict[str, Tuple[str, ...]],
            stepchain_methods: Set[str],
            stepchain_config: StepChainConfig,
    ) -> None:
        super().__init__(connection, rpc_object)
        self._object_name = object_name
        self._method_argument_names = method_argument_names
        self._stepchain_methods = set(stepchain_methods)
        self._cfg = stepchain_config

    def status_symbol(self) -> str:
        """Return the root PLC symbol that stores stepchain status."""
        status_root = self._cfg.status_symbol
        if status_root is None:
            status_root = f"{self._object_name}.{self._cfg.status_field}"
        return status_root

    def get_status_structure_def(self) -> StructureDef:
        """Return the predefined structure definition for stepchain status."""
        field_types: Dict[str, Type[Any]] = {}

        field_types[self._cfg.request_id_field] = PLCTYPE_UDINT
        if self._cfg.busy_field:
            field_types[self._cfg.busy_field] = PLCTYPE_BOOL

        done_type: Type[Any] = (
            PLCTYPE_BOOL if isinstance(self._cfg.done_value, bool) else PLCTYPE_DINT
        )
        error_type: Type[Any] = (
            PLCTYPE_BOOL if isinstance(self._cfg.error_value, bool) else PLCTYPE_DINT
        )
        field_types[self._cfg.done_field] = done_type
        field_types[self._cfg.error_field] = error_type

        if self._cfg.error_code_field:
            field_types[self._cfg.error_code_field] = PLCTYPE_DINT
        if self._cfg.step_field:
            field_types[self._cfg.step_field] = PLCTYPE_UDINT
        if self._cfg.step_name_field:
            field_types[self._cfg.step_name_field] = PLCTYPE_STRING

        order: List[str] = [self._cfg.request_id_field]
        if self._cfg.busy_field:
            order.append(self._cfg.busy_field)
        order.extend([self._cfg.done_field, self._cfg.error_field])
        if self._cfg.error_code_field:
            order.append(self._cfg.error_code_field)
        if self._cfg.step_field:
            order.append(self._cfg.step_field)
        if self._cfg.step_name_field:
            order.append(self._cfg.step_name_field)

        unique_order: List[str] = list(dict.fromkeys(order))

        structure_items: List[Tuple[Any, ...]] = []
        for field_name in unique_order:
            plc_type = field_types[field_name]
            if field_name == self._cfg.step_name_field:
                structure_items.append((field_name, plc_type, 1, self._cfg.step_name_length))
            else:
                structure_items.append((field_name, plc_type, 1))

        return cast(StructureDef, tuple(structure_items))

    def submit_read_status(self) -> "asyncio.Future[Any]":
        """Submit reading stepchain status fields without relying on struct packing."""
        return asyncio.create_task(self._read_status_fields())

    async def read_status(self) -> Any:
        """Read the stepchain status structure asynchronously."""
        return await self.submit_read_status()

    async def _read_status_fields(self) -> Dict[str, Any]:
        field_map = self._status_field_symbol_map()
        values = await self._connection.sum_read(list(field_map.values()))
        return {
            field_name: values[symbol_name]
            for field_name, symbol_name in field_map.items()
        }

    def __getattr__(self, method_name: str) -> Callable[..., Any]:
        if method_name not in self._stepchain_methods:
            return super().__getattr__(method_name)

        sync_method = getattr(self._rpc_object, method_name)
        arg_names = self._method_argument_names.get(method_name, tuple())

        def _invoke(*args: Any, **kwargs: Any) -> StepChainOperation[Any]:
            request_id, call_args, call_kwargs = self._resolve_request_id(
                method_name, arg_names, args, kwargs
            )
            accepted = self._connection._submit(sync_method, *call_args, **call_kwargs)
            done = asyncio.create_task(
                self._wait_until_done(method_name, request_id, accepted)
            )
            return StepChainOperation(request_id=request_id, accepted=accepted, done=done)

        return _invoke

    def _resolve_request_id(
            self,
            method_name: str,
            arg_names: Tuple[str, ...],
            args: Tuple[Any, ...],
            kwargs: Dict[str, Any],
    ) -> Tuple[int, Tuple[Any, ...], Dict[str, Any]]:
        request_arg = self._cfg.request_id_arg
        call_kwargs = dict(kwargs)
        call_args = list(args)

        unknown = set(call_kwargs.keys()) - {request_arg}
        if unknown:
            names = ", ".join(sorted(unknown))
            raise TypeError(f"Unknown keyword argument(s): {names}")

        if request_arg in arg_names:
            arg_index = arg_names.index(request_arg)

            if request_arg in call_kwargs:
                request_id = int(call_kwargs.pop(request_arg))
                if arg_index < len(call_args):
                    raise TypeError(
                        f"{method_name} got multiple values for argument '{request_arg}'."
                    )
                if arg_index != len(call_args):
                    raise TypeError(
                        f"{method_name} requires positional arguments before '{request_arg}'."
                    )
                call_args.append(request_id)
                return request_id, tuple(call_args), {}

            if arg_index < len(call_args):
                return int(call_args[arg_index]), tuple(call_args), {}

            request_id = self._connection._next_request_id()
            if arg_index != len(call_args):
                raise TypeError(
                    f"{method_name} requires positional arguments before '{request_arg}'."
                )
            call_args.append(request_id)
            return request_id, tuple(call_args), {}

        raise TypeError(
            f"{method_name} does not expose required stepchain request id argument "
            f"'{request_arg}'."
        )

    async def _wait_until_done(
            self,
            method_name: str,
            request_id: int,
            accepted_future: "asyncio.Future[Any]",
    ) -> Any:
        accepted_value = await accepted_future
        if isinstance(accepted_value, bool) and not accepted_value:
            raise RuntimeError(
                f"Stepchain method {method_name} was rejected by PLC."
            )

        symbols = self._status_symbols_for_read()

        timeout_deadline = (
            monotonic() + self._cfg.timeout_s if self._cfg.timeout_s is not None else None
        )

        while True:
            values = await self._connection.sum_read(symbols)
            if self._is_completed(values, method_name, request_id):
                return values

            if timeout_deadline is not None and monotonic() >= timeout_deadline:
                raise TimeoutError(
                    f"Timed out waiting for stepchain completion for {method_name} "
                    f"(request_id={request_id})."
                )

            await asyncio.sleep(self._cfg.poll_interval)

    def _status_symbols_for_read(self) -> List[str]:
        req_symbol, busy_symbol, done_symbol, err_symbol, err_code_symbol = self._status_symbols()
        symbols = [req_symbol, done_symbol]
        if busy_symbol and busy_symbol not in symbols:
            symbols.append(busy_symbol)
        if err_symbol not in symbols:
            symbols.append(err_symbol)
        if err_code_symbol and err_code_symbol not in symbols:
            symbols.append(err_code_symbol)
        status_root = self.status_symbol()
        if self._cfg.step_field:
            step_symbol = f"{status_root}.{self._cfg.step_field}"
            if step_symbol not in symbols:
                symbols.append(step_symbol)
        if self._cfg.step_name_field:
            step_name_symbol = f"{status_root}.{self._cfg.step_name_field}"
            if step_name_symbol not in symbols:
                symbols.append(step_name_symbol)
        return symbols

    def _is_completed(
            self,
            values: Dict[str, Any],
            method_name: str,
            request_id: int,
    ) -> bool:
        req_symbol, _busy_symbol, done_symbol, err_symbol, err_code_symbol = self._status_symbols()
        current_request = self._coerce_int(values.get(req_symbol))
        if current_request != request_id:
            return False

        done_value = values.get(done_symbol)
        err_value = values.get(err_symbol)

        if self._matches(err_value, self._cfg.error_value):
            err_code = values.get(err_code_symbol) if err_code_symbol else None
            if err_code is None:
                raise RuntimeError(
                    f"Stepchain {method_name} failed for request_id={request_id}."
                )
            raise RuntimeError(
                f"Stepchain {method_name} failed for request_id={request_id}, "
                f"error_code={err_code}."
            )

        return self._matches(done_value, self._cfg.done_value)

    def _status_symbols(self) -> Tuple[str, Optional[str], str, str, Optional[str]]:
        status_root = self._cfg.status_symbol
        if status_root is None:
            status_root = f"{self._object_name}.{self._cfg.status_field}"
        req_symbol = f"{status_root}.{self._cfg.request_id_field}"
        busy_symbol = (
            f"{status_root}.{self._cfg.busy_field}"
            if self._cfg.busy_field
            else None
        )
        done_symbol = f"{status_root}.{self._cfg.done_field}"
        err_symbol = f"{status_root}.{self._cfg.error_field}"
        err_code_symbol = (
            f"{status_root}.{self._cfg.error_code_field}"
            if self._cfg.error_code_field
            else None
        )
        return req_symbol, busy_symbol, done_symbol, err_symbol, err_code_symbol

    def _status_field_symbol_map(self) -> Dict[str, str]:
        status_root = self.status_symbol()
        field_map: Dict[str, str] = {
            self._cfg.request_id_field: f"{status_root}.{self._cfg.request_id_field}",
            self._cfg.done_field: f"{status_root}.{self._cfg.done_field}",
            self._cfg.error_field: f"{status_root}.{self._cfg.error_field}",
        }
        if self._cfg.busy_field:
            field_map[self._cfg.busy_field] = f"{status_root}.{self._cfg.busy_field}"
        if self._cfg.error_code_field:
            field_map[self._cfg.error_code_field] = f"{status_root}.{self._cfg.error_code_field}"
        if self._cfg.step_field:
            field_map[self._cfg.step_field] = f"{status_root}.{self._cfg.step_field}"
        if self._cfg.step_name_field:
            field_map[self._cfg.step_name_field] = f"{status_root}.{self._cfg.step_name_field}"
        return field_map

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _matches(actual: Any, expected: Union[bool, int]) -> bool:
        if isinstance(expected, bool):
            return bool(actual) is expected
        actual_num = AsyncStepChainRpcObject._coerce_int(actual)
        return actual_num == int(expected)


class AsyncNotifyStepChainRpcObject(AsyncStepChainRpcObject):
    """Stepchain RPC proxy using ADS notifications to trigger status checks."""

    def __getattr__(self, method_name: str) -> Callable[..., Any]:
        if method_name not in self._stepchain_methods:
            return AsyncRpcObject.__getattr__(self, method_name)

        sync_method = getattr(self._rpc_object, method_name)
        arg_names = self._method_argument_names.get(method_name, tuple())

        def _invoke(*args: Any, **kwargs: Any) -> StepChainOperation[Any]:
            request_id, call_args, call_kwargs = self._resolve_request_id(
                method_name, arg_names, args, kwargs
            )
            loop = asyncio.get_running_loop()
            event_queue: "asyncio.Queue[None]" = asyncio.Queue(maxsize=64)
            register_future = self._connection._submit(
                self._register_notification_handles,
                loop,
                event_queue,
            )
            accepted = self._connection._submit(sync_method, *call_args, **call_kwargs)
            done = asyncio.create_task(
                self._wait_until_done_notify(
                    method_name,
                    request_id,
                    accepted,
                    register_future,
                    event_queue,
                )
            )
            return StepChainOperation(request_id=request_id, accepted=accepted, done=done)

        return _invoke

    def _register_notification_handles(
            self,
            loop: asyncio.AbstractEventLoop,
            event_queue: "asyncio.Queue[None]",
    ) -> List[Tuple[int, Optional[int]]]:
        handles: List[Tuple[int, Optional[int]]] = []
        for symbol in self._status_symbols_for_read():
            callback = self._make_callback(loop, event_queue)
            handles.append(self._connection._add_notification_with_auto_attr(symbol, callback))
        return handles

    @staticmethod
    def _make_callback(
            loop: asyncio.AbstractEventLoop,
            event_queue: "asyncio.Queue[None]",
    ) -> Callable[[Any, str], None]:
        def _callback(_notification: Any, _name: str) -> None:
            try:
                loop.call_soon_threadsafe(
                    AsyncNotifyStepChainRpcObject._enqueue_notification_event,
                    event_queue,
                )
            except RuntimeError:
                # Event loop is closed while shutting down.
                return

        return _callback

    @staticmethod
    def _enqueue_notification_event(event_queue: "asyncio.Queue[None]") -> None:
        try:
            event_queue.put_nowait(None)
        except asyncio.QueueFull:
            # Collapse bursts; one wake-up is enough to trigger a status read.
            return

    async def _wait_until_done_notify(
            self,
            method_name: str,
            request_id: int,
            accepted_future: "asyncio.Future[Any]",
            register_future: "asyncio.Future[List[Tuple[int, Optional[int]]]]",
            event_queue: "asyncio.Queue[None]",
    ) -> Any:
        handles = await register_future
        try:
            accepted_value = await accepted_future
            if isinstance(accepted_value, bool) and not accepted_value:
                raise RuntimeError(
                    f"Stepchain method {method_name} was rejected by PLC."
                )

            symbols = self._status_symbols_for_read()

            # Immediate check in case completion happened before first callback dispatch.
            values = await self._connection.sum_read(symbols)
            if self._is_completed(values, method_name, request_id):
                return values

            timeout_deadline = (
                monotonic() + self._cfg.timeout_s if self._cfg.timeout_s is not None else None
            )

            while True:
                if timeout_deadline is None:
                    await event_queue.get()
                else:
                    remaining = timeout_deadline - monotonic()
                    if remaining <= 0:
                        raise TimeoutError(
                            f"Timed out waiting for stepchain completion for {method_name} "
                            f"(request_id={request_id})."
                        )
                    await asyncio.wait_for(event_queue.get(), timeout=remaining)

                values = await self._connection.sum_read(symbols)
                if self._is_completed(values, method_name, request_id):
                    return values
        finally:
            try:
                await self._connection._submit(self._connection._del_notifications, handles)
            except RuntimeError:
                # Connection already closed.
                pass


class AsyncConnection:
    """Async wrapper around :class:`pyads.Connection` with serialized calls.

    All ADS operations are queued and executed by one dedicated worker thread
    per instance, preventing races on mutable connection state.
    """

    def __init__(
            self,
            ams_net_id: str = None,
            ams_net_port: int = None,
            ip_address: str = None,
    ) -> None:
        self._sync = Connection(ams_net_id, ams_net_port, ip_address)
        self._queue: "queue.Queue[Union[_QueuedCall, _ShutdownSignal]]" = queue.Queue()
        self._state_lock = threading.Lock()
        self._request_id_lock = threading.Lock()
        self._request_id_counter = itertools.count(1)
        self._closed = False
        self._worker = threading.Thread(
            target=self._worker_main,
            name="pyads-async-worker",
            daemon=True,
        )
        self._worker.start()

    @property
    def sync_connection(self) -> Connection:
        """Return the underlying synchronous connection."""
        return self._sync

    @property
    def is_open(self) -> bool:
        """Return True when the underlying ADS port is open."""
        return self._sync.is_open

    def _worker_main(self) -> None:
        """Run queued work items sequentially."""
        while True:
            item = self._queue.get()
            if isinstance(item, _ShutdownSignal):
                return

            if item.future.cancelled():
                continue

            try:
                result = item.fn(*item.args, **item.kwargs)
            except Exception as exc:
                item.loop.call_soon_threadsafe(
                    self._set_exception_if_pending, item.future, exc
                )
            else:
                item.loop.call_soon_threadsafe(
                    self._set_result_if_pending, item.future, result
                )

    @staticmethod
    def _set_result_if_pending(future: asyncio.Future[Any], result: Any) -> None:
        if not future.done():
            future.set_result(result)

    @staticmethod
    def _set_exception_if_pending(
            future: asyncio.Future[Any], exc: Exception
    ) -> None:
        if not future.done():
            future.set_exception(exc)

    def _submit(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> "asyncio.Future[T]":
        """Submit a callable to the worker and return an asyncio future."""
        with self._state_lock:
            if self._closed:
                raise RuntimeError("AsyncConnection is closed.")

        loop = asyncio.get_running_loop()
        future: "asyncio.Future[T]" = loop.create_future()
        self._queue.put(
            _QueuedCall(
                fn=cast(Callable[..., Any], fn),
                args=args,
                kwargs=kwargs,
                loop=loop,
                future=cast(asyncio.Future[Any], future),
            )
        )
        return future

    def _next_request_id(self) -> int:
        """Return the next auto-generated request id."""
        with self._request_id_lock:
            return next(self._request_id_counter) & 0xFFFFFFFF

    def _add_notification_with_auto_attr(
            self,
            symbol_name: str,
            callback: Callable[[Any, str], None],
    ) -> Tuple[int, Optional[int]]:
        """Register ADS notification for a symbol with inferred buffer length.

        This method runs on the serialized worker thread.
        """
        port = self._sync._port
        if port is None:
            raise RuntimeError("Connection must be open before registering notifications.")
        symbol_info = adsGetSymbolInfo(port, self._sync._adr, symbol_name)
        attr = NotificationAttrib(length=symbol_info.size)
        handles = self._sync.add_device_notification(symbol_name, attr, callback)
        if handles is None:
            raise RuntimeError(f"Failed to register notification for {symbol_name}.")
        return handles

    def _del_notifications(self, handles: List[Tuple[int, Optional[int]]]) -> None:
        """Remove registered ADS notification handles.

        This method runs on the serialized worker thread.
        """
        for notification_handle, user_handle in handles:
            self._sync.del_device_notification(notification_handle, user_handle)

    async def __aenter__(self) -> "AsyncConnection":
        await self.open()
        return self

    async def __aexit__(self, _type: Any, _val: Any, _traceback: Any) -> None:
        await self.aclose()

    def submit_open(self) -> "asyncio.Future[None]":
        """Submit opening the ADS connection."""
        return self._submit(self._sync.open)

    async def open(self) -> None:
        """Open the ADS connection."""
        await self.submit_open()

    def submit_close(self) -> "asyncio.Future[None]":
        """Submit closing the ADS connection."""
        return self._submit(self._sync.close)

    async def close(self) -> None:
        """Close the ADS connection."""
        await self.submit_close()

    async def aclose(self) -> None:
        """Close ADS connection and stop worker thread permanently."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True

        loop = asyncio.get_running_loop()
        close_future: asyncio.Future[None] = loop.create_future()
        self._queue.put(
            _QueuedCall(
                fn=self._sync.close,
                args=(),
                kwargs={},
                loop=loop,
                future=cast(asyncio.Future[Any], close_future),
            )
        )
        await close_future
        self._queue.put(_ShutdownSignal())
        await asyncio.to_thread(self._worker.join)

    def submit_rpc_method(
            self,
            method_name: str,
            return_type: Optional[Type["PLCDataType"]] = None,
            write_value: Any = None,
            write_type: Optional[Type["PLCDataType"]] = None,
    ) -> "asyncio.Future[Any]":
        """Submit a RPC method call and return an asyncio future."""
        return self._submit(
            self._sync.call_rpc_method,
            method_name,
            return_type=return_type,
            write_value=write_value,
            write_type=write_type,
        )

    async def call_rpc_method(
            self,
            method_name: str,
            return_type: Optional[Type["PLCDataType"]] = None,
            write_value: Any = None,
            write_type: Optional[Type["PLCDataType"]] = None,
    ) -> Any:
        """Await a RPC method call."""
        return await self.submit_rpc_method(
            method_name=method_name,
            return_type=return_type,
            write_value=write_value,
            write_type=write_type,
        )

    def submit_get_local_address(self) -> "asyncio.Future[Optional[AmsAddr]]":
        """Submit local address lookup."""
        return self._submit(self._sync.get_local_address)

    async def get_local_address(self) -> Optional[AmsAddr]:
        """Await local address lookup."""
        return await self.submit_get_local_address()

    def submit_read_state(self) -> "asyncio.Future[Optional[Tuple[int, int]]]":
        """Submit ADS/device state read."""
        return self._submit(self._sync.read_state)

    async def read_state(self) -> Optional[Tuple[int, int]]:
        """Await ADS/device state read."""
        return await self.submit_read_state()

    def submit_read_device_info(
            self,
    ) -> "asyncio.Future[Optional[Tuple[str, AdsVersion]]]":
        """Submit ADS device info read."""
        return self._submit(self._sync.read_device_info)

    async def read_device_info(self) -> Optional[Tuple[str, AdsVersion]]:
        """Await ADS device info read."""
        return await self.submit_read_device_info()

    def submit_write_control(
            self,
            ads_state: int,
            device_state: int,
            data: Any,
            plc_datatype: Type,
    ) -> "asyncio.Future[None]":
        """Submit ADS write-control command."""
        return self._submit(
            self._sync.write_control,
            ads_state,
            device_state,
            data,
            plc_datatype,
        )

    async def write_control(
            self,
            ads_state: int,
            device_state: int,
            data: Any,
            plc_datatype: Type,
    ) -> None:
        """Await ADS write-control command."""
        await self.submit_write_control(
            ads_state=ads_state,
            device_state=device_state,
            data=data,
            plc_datatype=plc_datatype,
        )

    def submit_read(
            self,
            index_group: int,
            index_offset: int,
            plc_datatype: Type["PLCDataType"],
            return_ctypes: bool = False,
            check_length: bool = True,
    ) -> "asyncio.Future[Any]":
        """Submit ADS read by index group/offset."""
        return self._submit(
            self._sync.read,
            index_group,
            index_offset,
            plc_datatype,
            return_ctypes=return_ctypes,
            check_length=check_length,
        )

    async def read(
            self,
            index_group: int,
            index_offset: int,
            plc_datatype: Type["PLCDataType"],
            return_ctypes: bool = False,
            check_length: bool = True,
    ) -> Any:
        """Await ADS read by index group/offset."""
        return await self.submit_read(
            index_group=index_group,
            index_offset=index_offset,
            plc_datatype=plc_datatype,
            return_ctypes=return_ctypes,
            check_length=check_length,
        )

    def submit_write(
            self,
            index_group: int,
            index_offset: int,
            value: Any,
            plc_datatype: Type["PLCDataType"],
    ) -> "asyncio.Future[None]":
        """Submit ADS write by index group/offset."""
        return self._submit(
            self._sync.write,
            index_group,
            index_offset,
            value,
            plc_datatype,
        )

    async def write(
            self,
            index_group: int,
            index_offset: int,
            value: Any,
            plc_datatype: Type["PLCDataType"],
    ) -> None:
        """Await ADS write by index group/offset."""
        await self.submit_write(
            index_group=index_group,
            index_offset=index_offset,
            value=value,
            plc_datatype=plc_datatype,
        )

    def submit_read_write(
            self,
            index_group: int,
            index_offset: int,
            plc_read_datatype: Optional[Type["PLCDataType"]],
            value: Any,
            plc_write_datatype: Optional[Type["PLCDataType"]],
            return_ctypes: bool = False,
            check_length: bool = True,
    ) -> "asyncio.Future[Any]":
        """Submit ADS read-write command."""
        return self._submit(
            self._sync.read_write,
            index_group,
            index_offset,
            plc_read_datatype,
            value,
            plc_write_datatype,
            return_ctypes=return_ctypes,
            check_length=check_length,
        )

    async def read_write(
            self,
            index_group: int,
            index_offset: int,
            plc_read_datatype: Optional[Type["PLCDataType"]],
            value: Any,
            plc_write_datatype: Optional[Type["PLCDataType"]],
            return_ctypes: bool = False,
            check_length: bool = True,
    ) -> Any:
        """Await ADS read-write command."""
        return await self.submit_read_write(
            index_group=index_group,
            index_offset=index_offset,
            plc_read_datatype=plc_read_datatype,
            value=value,
            plc_write_datatype=plc_write_datatype,
            return_ctypes=return_ctypes,
            check_length=check_length,
        )

    @overload
    def get_async_object(
            self,
            object_name: str,
            method_separator: str = "#",
            method_prefixes: Tuple[str, ...] = ("", "m_"),
            method_return_types: Optional[Dict[str, Type["PLCDataType"]]] = None,
            method_parameters: Optional[
                Dict[str, Sequence[Type["PLCDataType"]]]
            ] = None,
    ) -> AsyncRpcObject: ...

    @overload
    def get_async_object(
            self,
            object_name: Type[AsyncRpcInterfaceT],
            method_separator: str = "#",
            method_prefixes: Tuple[str, ...] = ("", "m_"),
            method_return_types: Optional[Dict[str, Type["PLCDataType"]]] = None,
            method_parameters: Optional[
                Dict[str, Sequence[Type["PLCDataType"]]]
            ] = None,
    ) -> AsyncRpcInterfaceT: ...

    def get_async_object(
            self,
            object_name: Union[str, Type[AsyncRpcInterfaceT]],
            method_separator: str = "#",
            method_prefixes: Tuple[str, ...] = ("", "m_"),
            method_return_types: Optional[Dict[str, Type["PLCDataType"]]] = None,
            method_parameters: Optional[
                Dict[str, Sequence[Type["PLCDataType"]]]
            ] = None,
    ) -> Union[AsyncRpcObject, AsyncRpcInterfaceT]:
        """Create an async RPC proxy.

        Dynamic RPC method calls return ``asyncio.Future`` instances.
        """
        interface_class: Optional[Type[AsyncRpcInterfaceT]] = (
            object_name if inspect.isclass(object_name) else None
        )
        stepchain_cfg: Optional[StepChainConfig] = None
        stepchain_methods: Set[str] = set()
        async_interface = False
        method_argument_names: Dict[str, Tuple[str, ...]] = {}
        inferred_returns: Optional[Dict[str, Type["PLCDataType"]]] = None
        inferred_parameters: Optional[Dict[str, Tuple[Type["PLCDataType"], ...]]] = None
        resolved_object_name: Optional[str] = None

        if interface_class is not None:
            interface_definition = resolve_rpc_interface_definition(interface_class)
            async_interface = interface_definition.async_interface
            stepchain_cfg = interface_definition.stepchain_config
            stepchain_methods = set(interface_definition.stepchain_methods)
            method_argument_names = dict(interface_definition.method_argument_names)
            resolved_object_name = interface_definition.object_name
            if interface_definition.method_return_types:
                inferred_returns = dict(interface_definition.method_return_types)
            if interface_definition.method_parameters:
                inferred_parameters = dict(interface_definition.method_parameters)

        final_return_types: Optional[Dict[str, Type["PLCDataType"]]] = None
        if inferred_returns:
            final_return_types = inferred_returns
        if method_return_types:
            final_return_types = {**(final_return_types or {}), **method_return_types}

        normalized_parameters: Optional[Dict[str, Tuple[Type["PLCDataType"], ...]]] = None
        if method_parameters:
            normalized_parameters = {
                name: tuple(values)
                for name, values in method_parameters.items()
            }
        if inferred_parameters:
            normalized_parameters = {
                **(inferred_parameters or {}),
                **(normalized_parameters or {}),
            }

        sync_lookup_object: Union[str, Type[RpcInterfaceT]]
        if interface_class is not None and async_interface:
            if not resolved_object_name:
                raise TypeError("Async RPC interface is missing resolved object name metadata.")
            sync_lookup_object = resolved_object_name
        else:
            sync_lookup_object = cast(Union[str, Type[RpcInterfaceT]], object_name)

        sync_rpc = self._sync.get_object(
            sync_lookup_object,
            method_separator=method_separator,
            method_prefixes=method_prefixes,
            method_return_types=final_return_types,
            method_parameters=normalized_parameters,
        )
        if stepchain_cfg is not None:
            if stepchain_cfg.completion == "notify":
                async_rpc = AsyncNotifyStepChainRpcObject(
                    self,
                    cast(RpcObject, sync_rpc),
                    resolved_object_name if resolved_object_name is not None else "",
                    method_argument_names,
                    stepchain_methods,
                    stepchain_cfg,
                )
            else:
                async_rpc = AsyncStepChainRpcObject(
                    self,
                    cast(RpcObject, sync_rpc),
                    resolved_object_name if resolved_object_name is not None else "",
                    method_argument_names,
                    stepchain_methods,
                    stepchain_cfg,
                )
        else:
            async_rpc = AsyncRpcObject(self, cast(RpcObject, sync_rpc))

        if interface_class is not None:
            return cast(AsyncRpcInterfaceT, async_rpc)
        return async_rpc

    def submit_sum_read(
            self,
            data_names: List[str],
            cache_symbol_info: bool = True,
            ads_sub_commands: int = MAX_ADS_SUB_COMMANDS,
            structure_defs: Optional[Dict[str, StructureDef]] = None,
    ) -> "asyncio.Future[Dict[str, Any]]":
        """Submit sum-read and return a future with the resulting dictionary."""
        return self._submit(
            self._sync.read_list_by_name,
            data_names,
            cache_symbol_info=cache_symbol_info,
            ads_sub_commands=ads_sub_commands,
            structure_defs=structure_defs,
        )

    def submit_read_by_name(
            self,
            data_name: str,
            plc_datatype: Optional[Type["PLCDataType"]] = None,
            return_ctypes: bool = False,
            handle: Optional[int] = None,
            check_length: bool = True,
            cache_symbol_info: bool = True,
    ) -> "asyncio.Future[Any]":
        """Submit ADS read by symbol name."""
        return self._submit(
            self._sync.read_by_name,
            data_name,
            plc_datatype=plc_datatype,
            return_ctypes=return_ctypes,
            handle=handle,
            check_length=check_length,
            cache_symbol_info=cache_symbol_info,
        )

    async def read_by_name(
            self,
            data_name: str,
            plc_datatype: Optional[Type["PLCDataType"]] = None,
            return_ctypes: bool = False,
            handle: Optional[int] = None,
            check_length: bool = True,
            cache_symbol_info: bool = True,
    ) -> Any:
        """Await ADS read by symbol name."""
        return await self.submit_read_by_name(
            data_name=data_name,
            plc_datatype=plc_datatype,
            return_ctypes=return_ctypes,
            handle=handle,
            check_length=check_length,
            cache_symbol_info=cache_symbol_info,
        )

    async def sum_read(
            self,
            data_names: List[str],
            cache_symbol_info: bool = True,
            ads_sub_commands: int = MAX_ADS_SUB_COMMANDS,
            structure_defs: Optional[Dict[str, StructureDef]] = None,
    ) -> Dict[str, Any]:
        """Await sum-read."""
        return await self.submit_sum_read(
            data_names=data_names,
            cache_symbol_info=cache_symbol_info,
            ads_sub_commands=ads_sub_commands,
            structure_defs=structure_defs,
        )

    def submit_read_structure_by_name(
            self,
            data_name: str,
            structure_def: StructureDef,
            array_size: Optional[int] = 1,
            structure_size: Optional[int] = None,
            handle: Optional[int] = None,
    ) -> "asyncio.Future[Any]":
        """Submit structured ADS read by symbol name."""
        return self._submit(
            self._sync.read_structure_by_name,
            data_name,
            structure_def,
            array_size=array_size,
            structure_size=structure_size,
            handle=handle,
        )

    async def read_structure_by_name(
            self,
            data_name: str,
            structure_def: StructureDef,
            array_size: Optional[int] = 1,
            structure_size: Optional[int] = None,
            handle: Optional[int] = None,
    ) -> Any:
        """Await structured ADS read by symbol name."""
        return await self.submit_read_structure_by_name(
            data_name=data_name,
            structure_def=structure_def,
            array_size=array_size,
            structure_size=structure_size,
            handle=handle,
        )

    def submit_sum_write(
            self,
            data_names_and_values: Dict[str, Any],
            cache_symbol_info: bool = True,
            ads_sub_commands: int = MAX_ADS_SUB_COMMANDS,
            structure_defs: Optional[Dict[str, StructureDef]] = None,
    ) -> "asyncio.Future[Dict[str, str]]":
        """Submit sum-write and return a future with per-item status text."""
        return self._submit(
            self._sync.write_list_by_name,
            data_names_and_values,
            cache_symbol_info=cache_symbol_info,
            ads_sub_commands=ads_sub_commands,
            structure_defs=structure_defs,
        )

    def submit_write_by_name(
            self,
            data_name: str,
            value: Any,
            plc_datatype: Optional[Type["PLCDataType"]] = None,
            handle: Optional[int] = None,
            cache_symbol_info: bool = True,
    ) -> "asyncio.Future[None]":
        """Submit ADS write by symbol name."""
        return self._submit(
            self._sync.write_by_name,
            data_name,
            value,
            plc_datatype=plc_datatype,
            handle=handle,
            cache_symbol_info=cache_symbol_info,
        )

    async def write_by_name(
            self,
            data_name: str,
            value: Any,
            plc_datatype: Optional[Type["PLCDataType"]] = None,
            handle: Optional[int] = None,
            cache_symbol_info: bool = True,
    ) -> None:
        """Await ADS write by symbol name."""
        await self.submit_write_by_name(
            data_name=data_name,
            value=value,
            plc_datatype=plc_datatype,
            handle=handle,
            cache_symbol_info=cache_symbol_info,
        )

    async def sum_write(
            self,
            data_names_and_values: Dict[str, Any],
            cache_symbol_info: bool = True,
            ads_sub_commands: int = MAX_ADS_SUB_COMMANDS,
            structure_defs: Optional[Dict[str, StructureDef]] = None,
    ) -> Dict[str, str]:
        """Await sum-write."""
        return await self.submit_sum_write(
            data_names_and_values=data_names_and_values,
            cache_symbol_info=cache_symbol_info,
            ads_sub_commands=ads_sub_commands,
            structure_defs=structure_defs,
        )

    def submit_write_structure_by_name(
            self,
            data_name: str,
            value: Any,
            structure_def: StructureDef,
            array_size: Optional[int] = 1,
            structure_size: Optional[int] = None,
            handle: Optional[int] = None,
    ) -> "asyncio.Future[None]":
        """Submit structured ADS write by symbol name."""
        return self._submit(
            self._sync.write_structure_by_name,
            data_name,
            value,
            structure_def,
            array_size=array_size,
            structure_size=structure_size,
            handle=handle,
        )

    async def write_structure_by_name(
            self,
            data_name: str,
            value: Any,
            structure_def: StructureDef,
            array_size: Optional[int] = 1,
            structure_size: Optional[int] = None,
            handle: Optional[int] = None,
    ) -> None:
        """Await structured ADS write by symbol name."""
        await self.submit_write_structure_by_name(
            data_name=data_name,
            value=value,
            structure_def=structure_def,
            array_size=array_size,
            structure_size=structure_size,
            handle=handle,
        )

    def submit_get_handle(self, data_name: str) -> "asyncio.Future[Optional[int]]":
        """Submit ADS handle acquisition."""
        return self._submit(self._sync.get_handle, data_name)

    async def get_handle(self, data_name: str) -> Optional[int]:
        """Await ADS handle acquisition."""
        return await self.submit_get_handle(data_name)

    def submit_release_handle(self, handle: int) -> "asyncio.Future[None]":
        """Submit ADS handle release."""
        return self._submit(self._sync.release_handle, handle)

    async def release_handle(self, handle: int) -> None:
        """Await ADS handle release."""
        await self.submit_release_handle(handle)

    def submit_set_timeout(self, ms: int) -> "asyncio.Future[None]":
        """Submit timeout update on ADS connection."""
        return self._submit(self._sync.set_timeout, ms)

    async def set_timeout(self, ms: int) -> None:
        """Await timeout update on ADS connection."""
        await self.submit_set_timeout(ms)
