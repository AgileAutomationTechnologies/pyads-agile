"""Helpers for declaring strongly typed RPC interfaces."""

from __future__ import annotations

import inspect
import sys
from collections.abc import Awaitable as AwaitableABC
from dataclasses import dataclass
from types import FunctionType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from .constants import PLCDataType

_RPC_DEF_CACHE_ATTR = "__pyads_rpc_definition__"
_ADS_ASYNC_ATTR = "__ads_async__"
_STEPCHAIN_START_ATTR = "__pyads_stepchain_start__"

if TYPE_CHECKING:
    from .ads import StructureDef


@dataclass(frozen=True)
class StepChainConfig:
    """Configuration for stepchain-aware async RPC interfaces."""

    status_symbol: Optional[str] = None
    status_field: str = "stStepStatus"
    request_id_field: str = "udiRequestId"
    request_id_arg: str = "udiRequestId"
    busy_field: Optional[str] = "xBusy"
    done_field: str = "xDone"
    done_value: Union[bool, int] = True
    error_field: str = "xError"
    error_value: Union[bool, int] = True
    error_code_field: str = "diErrorCode"
    step_field: Optional[str] = "udiStep"
    step_name_field: Optional[str] = "sStepName"
    step_name_length: int = 80
    completion: str = "poll"
    poll_interval: float = 0.05
    timeout_s: Optional[float] = None


@dataclass(frozen=True)
class RpcInterfaceDefinition:
    """Resolved metadata for an ads_path-decorated RPC interface."""

    object_name: str
    method_return_types: Dict[str, Type["PLCDataType"]]
    method_parameters: Dict[str, Tuple[Type["PLCDataType"], ...]]
    method_argument_names: Dict[str, Tuple[str, ...]]
    stepchain_methods: Set[str]
    async_interface: bool = False
    stepchain_config: Optional[StepChainConfig] = None


_RpcInterfaceCls = TypeVar("_RpcInterfaceCls", bound=type[Any])
_DecoratedFunction = TypeVar("_DecoratedFunction", bound=Callable[..., Any])


def ads_path(object_name: str) -> Callable[[_RpcInterfaceCls], _RpcInterfaceCls]:
    """Decorator for declaring the ADS path for an RPC interface class."""
    if not isinstance(object_name, str):
        raise TypeError("ads_path expects a string object name.")
    normalized = object_name.strip()
    if not normalized:
        raise ValueError("ads_path requires a non-empty object name.")

    def _decorate(cls: _RpcInterfaceCls) -> _RpcInterfaceCls:
        setattr(cls, "__ads_path__", normalized)
        return cls

    return _decorate


def ads_async_path(object_name: str) -> Callable[[_RpcInterfaceCls], _RpcInterfaceCls]:
    """Decorator for declaring an async-only ADS RPC interface class."""
    path_decorator = ads_path(object_name)

    def _decorate(cls: _RpcInterfaceCls) -> _RpcInterfaceCls:
        cls = path_decorator(cls)
        setattr(cls, _ADS_ASYNC_ATTR, True)
        return cls

    return _decorate


class StepChainRpcInterface:
    """Typing base for async RPC interfaces that expose stepchain helpers."""

    __stepchain_status_symbol__: Optional[str] = None
    __stepchain_status_field__: str = "stStepStatus"
    __stepchain_request_id_field__: str = "udiRequestId"
    __stepchain_request_id_arg__: str = "udiRequestId"
    __stepchain_busy_field__: Optional[str] = "xBusy"
    __stepchain_done_field__: str = "xDone"
    __stepchain_done_value__: Union[bool, int] = True
    __stepchain_error_field__: str = "xError"
    __stepchain_error_value__: Union[bool, int] = True
    __stepchain_error_code_field__: str = "diErrorCode"
    __stepchain_step_field__: Optional[str] = "udiStep"
    __stepchain_step_name_field__: Optional[str] = "sStepName"
    __stepchain_step_name_length__: int = 80
    __stepchain_completion__: str = "poll"
    __stepchain_poll_interval__: float = 0.05
    __stepchain_timeout_s__: Optional[float] = None

    def status_symbol(self) -> str:
        raise NotImplementedError

    def get_status_structure_def(self) -> "StructureDef":
        raise NotImplementedError

    def submit_read_status(self) -> Any:
        raise NotImplementedError

    async def read_status(self) -> Any:
        raise NotImplementedError


def stepchain_start(func: _DecoratedFunction) -> _DecoratedFunction:
    """Mark an async RPC method as a stepchain entry point."""
    setattr(func, _STEPCHAIN_START_ATTR, True)
    return func


def resolve_rpc_interface_definition(interface: Type[Any]) -> RpcInterfaceDefinition:
    """Resolve RPC metadata (object path + method signatures) for a class."""
    if not inspect.isclass(interface):
        raise TypeError("RPC interface must be a class decorated with @ads_path.")

    cached: Optional[RpcInterfaceDefinition] = getattr(interface, _RPC_DEF_CACHE_ATTR, None)
    if cached is not None:
        return cached

    object_name = getattr(interface, "__ads_path__", None)
    if not isinstance(object_name, str) or not object_name.strip():
        raise TypeError(
            f"{interface.__name__} must be decorated with @ads_path('...') "
            "before passing it to Connection.get_object()."
        )

    method_return_types: Dict[str, Type["PLCDataType"]] = {}
    method_parameters: Dict[str, Tuple[Type["PLCDataType"], ...]] = {}
    method_argument_names: Dict[str, Tuple[str, ...]] = {}
    stepchain_methods: Set[str] = set()

    for attr_name, attr_value in interface.__dict__.items():
        if attr_name.startswith("_"):
            continue
        function = _unwrap_function(attr_value)
        if function is None:
            continue
        hints = _evaluate_type_hints(function, interface)
        return_type = _coerce_plc_type(hints.get("return"))
        if return_type is not None:
            method_return_types[attr_name] = return_type

        parameter_types = _extract_parameter_types(function, hints)
        if parameter_types is not None:
            method_parameters[attr_name] = parameter_types
        method_argument_names[attr_name] = _extract_argument_names(function)
        if bool(getattr(function, _STEPCHAIN_START_ATTR, False)):
            stepchain_methods.add(attr_name)

    async_interface = bool(getattr(interface, _ADS_ASYNC_ATTR, False))
    if stepchain_methods and not async_interface:
        raise TypeError(
            f"{interface.__name__} declares @stepchain_start methods and must be "
            "decorated with @ads_async_path('...')."
        )
    for method_name in stepchain_methods:
        if method_name not in method_return_types:
            raise TypeError(
                f"{interface.__name__}.{method_name} must return "
                "StepChainOperation[PLCTYPE_*]."
            )
    stepchain_cfg = _resolve_stepchain_config(interface, stepchain_methods)

    definition = RpcInterfaceDefinition(
        object_name=object_name.strip(),
        method_return_types=method_return_types,
        method_parameters=method_parameters,
        method_argument_names=method_argument_names,
        stepchain_methods=stepchain_methods,
        async_interface=async_interface,
        stepchain_config=stepchain_cfg,
    )
    setattr(interface, _RPC_DEF_CACHE_ATTR, definition)
    return definition


def _unwrap_function(value: Any) -> Optional[FunctionType]:
    if inspect.isfunction(value):
        return value
    if isinstance(value, (staticmethod, classmethod)):
        func = value.__func__
        return func if inspect.isfunction(func) else None
    return None


def _evaluate_type_hints(func: FunctionType, interface: Type[Any]) -> Mapping[str, Any]:
    module = sys.modules.get(func.__module__)
    globalns = dict(vars(module)) if module else {}
    localns = dict(vars(interface))
    try:
        return get_type_hints(func, globalns=globalns, localns=localns)
    except Exception:
        return {}


def _extract_parameter_types(
    func: FunctionType, hints: Mapping[str, Any]
) -> Optional[Tuple[Type["PLCDataType"], ...]]:
    signature = inspect.signature(func)
    parameter_types = []
    for param in signature.parameters.values():
        if param.name == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            return None
        coerced = _coerce_plc_type(hints.get(param.name))
        if coerced is None:
            return None
        parameter_types.append(coerced)
    return tuple(parameter_types)


def _extract_argument_names(func: FunctionType) -> Tuple[str, ...]:
    signature = inspect.signature(func)
    arg_names = []
    for param in signature.parameters.values():
        if param.name == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            return tuple()
        arg_names.append(param.name)
    return tuple(arg_names)


def _coerce_plc_type(annotation: Any) -> Optional[Type["PLCDataType"]]:
    annotation = _unwrap_transport_annotation(annotation)
    if isinstance(annotation, type):
        return annotation
    return None


def _unwrap_transport_annotation(annotation: Any) -> Any:
    """Extract transport return type from async/stepchain annotations."""
    origin = get_origin(annotation)
    if origin is None:
        return annotation

    if (
        getattr(origin, "__name__", None) == "StepChainOperation"
        and getattr(origin, "__module__", "").endswith(".async_connection")
    ):
        args = get_args(annotation)
        if args:
            return args[0]

    if origin in (AwaitableABC,):
        args = get_args(annotation)
        if args:
            return args[0]
    try:
        import asyncio

        if origin in (asyncio.Future,):
            args = get_args(annotation)
            if args:
                return args[0]
    except Exception:
        pass

    return annotation


def _resolve_stepchain_config(
        interface: Type[Any],
        stepchain_methods: Set[str],
) -> Optional[StepChainConfig]:
    if not stepchain_methods:
        return None
    if not issubclass(interface, StepChainRpcInterface):
        raise TypeError(
            f"{interface.__name__} declares @stepchain_start methods and must inherit "
            "from StepChainRpcInterface."
        )

    status_symbol = getattr(interface, "__stepchain_status_symbol__", None)
    status_field = getattr(interface, "__stepchain_status_field__", "stStepStatus")
    request_id_field = getattr(interface, "__stepchain_request_id_field__", "udiRequestId")
    request_id_arg = getattr(interface, "__stepchain_request_id_arg__", "udiRequestId")
    busy_field = getattr(interface, "__stepchain_busy_field__", "xBusy")
    done_field = getattr(interface, "__stepchain_done_field__", "xDone")
    done_value = getattr(interface, "__stepchain_done_value__", True)
    error_field = getattr(interface, "__stepchain_error_field__", "xError")
    error_value = getattr(interface, "__stepchain_error_value__", True)
    error_code_field = getattr(interface, "__stepchain_error_code_field__", "diErrorCode")
    step_field = getattr(interface, "__stepchain_step_field__", "udiStep")
    step_name_field = getattr(interface, "__stepchain_step_name_field__", "sStepName")
    step_name_length = getattr(interface, "__stepchain_step_name_length__", 80)
    completion = getattr(interface, "__stepchain_completion__", "poll")
    poll_interval = getattr(interface, "__stepchain_poll_interval__", 0.05)
    timeout_s = getattr(interface, "__stepchain_timeout_s__", None)

    if status_symbol is not None:
        if not isinstance(status_symbol, str) or not status_symbol.strip():
            raise ValueError("StepChainRpcInterface.__stepchain_status_symbol__ must be a non-empty string when set.")
        status_symbol = status_symbol.strip()
    if not isinstance(status_field, str) or not status_field.strip():
        raise ValueError("StepChainRpcInterface.__stepchain_status_field__ must be a non-empty string.")
    if not isinstance(request_id_field, str) or not request_id_field.strip():
        raise ValueError("StepChainRpcInterface.__stepchain_request_id_field__ must be a non-empty string.")
    if not isinstance(request_id_arg, str) or not request_id_arg.strip():
        raise ValueError("StepChainRpcInterface.__stepchain_request_id_arg__ must be a non-empty string.")
    if busy_field is not None and (not isinstance(busy_field, str) or not busy_field.strip()):
        raise ValueError("StepChainRpcInterface.__stepchain_busy_field__ must be a non-empty string when set.")
    if not isinstance(done_field, str) or not done_field.strip():
        raise ValueError("StepChainRpcInterface.__stepchain_done_field__ must be a non-empty string.")
    if not isinstance(error_field, str) or not error_field.strip():
        raise ValueError("StepChainRpcInterface.__stepchain_error_field__ must be a non-empty string.")
    if not isinstance(error_code_field, str) or not error_code_field.strip():
        raise ValueError("StepChainRpcInterface.__stepchain_error_code_field__ must be a non-empty string.")
    if step_field is not None and (not isinstance(step_field, str) or not step_field.strip()):
        raise ValueError("StepChainRpcInterface.__stepchain_step_field__ must be a non-empty string when set.")
    if step_name_field is not None and (not isinstance(step_name_field, str) or not step_name_field.strip()):
        raise ValueError("StepChainRpcInterface.__stepchain_step_name_field__ must be a non-empty string when set.")
    if not isinstance(step_name_length, int) or step_name_length <= 0:
        raise ValueError("StepChainRpcInterface.__stepchain_step_name_length__ must be > 0.")
    if completion not in ("poll", "notify"):
        raise ValueError("StepChainRpcInterface.__stepchain_completion__ must be either 'poll' or 'notify'.")
    if not isinstance(poll_interval, (int, float)) or float(poll_interval) <= 0:
        raise ValueError("StepChainRpcInterface.__stepchain_poll_interval__ must be > 0.")
    if timeout_s is not None and (not isinstance(timeout_s, (int, float)) or float(timeout_s) <= 0):
        raise ValueError("StepChainRpcInterface.__stepchain_timeout_s__ must be > 0 when set.")

    return StepChainConfig(
        status_symbol=status_symbol,
        status_field=status_field.strip(),
        request_id_field=request_id_field.strip(),
        request_id_arg=request_id_arg.strip(),
        busy_field=busy_field.strip() if isinstance(busy_field, str) else None,
        done_field=done_field.strip(),
        done_value=done_value,
        error_field=error_field.strip(),
        error_value=error_value,
        error_code_field=error_code_field.strip(),
        step_field=step_field.strip() if isinstance(step_field, str) else None,
        step_name_field=step_name_field.strip() if isinstance(step_name_field, str) else None,
        step_name_length=step_name_length,
        completion=completion,
        poll_interval=float(poll_interval),
        timeout_s=float(timeout_s) if timeout_s is not None else None,
    )
