"""Helpers for declaring strongly typed RPC interfaces."""

from __future__ import annotations

import inspect
import sys
from collections.abc import Awaitable as AwaitableABC
from dataclasses import dataclass
from types import FunctionType
from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
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
_ADS_STEPCHAIN_ATTR = "__ads_stepchain__"
_ADS_ASYNC_ATTR = "__ads_async__"


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
    async_interface: bool = False
    stepchain: bool = False
    stepchain_config: Optional[StepChainConfig] = None


_RpcInterfaceCls = TypeVar("_RpcInterfaceCls", bound=type[Any])


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


def ads_stepchain_path(
        object_name: str,
        *,
        status_symbol: Optional[str] = None,
        status_field: str = "stStepStatus",
        request_id_field: str = "udiRequestId",
        request_id_arg: str = "udiRequestId",
        busy_field: Optional[str] = "xBusy",
        done_field: str = "xDone",
        done_value: Union[bool, int] = True,
        error_field: str = "xError",
        error_value: Union[bool, int] = True,
        error_code_field: str = "diErrorCode",
        step_field: Optional[str] = "udiStep",
        step_name_field: Optional[str] = "sStepName",
        step_name_length: int = 80,
        completion: str = "poll",
        poll_interval: float = 0.05,
        timeout_s: Optional[float] = None,
) -> Callable[[_RpcInterfaceCls], _RpcInterfaceCls]:
    """Decorator for declaring a stepchain-aware ADS RPC interface.

    The object path is declared like :func:`ads_path`, plus optional
    configuration for completion tracking via status symbols.
    """
    if not isinstance(status_field, str) or not status_field.strip():
        raise ValueError("ads_stepchain_path requires a non-empty status_field.")
    if not isinstance(request_id_field, str) or not request_id_field.strip():
        raise ValueError("ads_stepchain_path requires a non-empty request_id_field.")
    if not isinstance(request_id_arg, str) or not request_id_arg.strip():
        raise ValueError("ads_stepchain_path requires a non-empty request_id_arg.")
    if busy_field is not None:
        if not isinstance(busy_field, str) or not busy_field.strip():
            raise ValueError("ads_stepchain_path busy_field must be a non-empty string when set.")
    if not isinstance(done_field, str) or not done_field.strip():
        raise ValueError("ads_stepchain_path requires a non-empty done_field.")
    if not isinstance(error_field, str) or not error_field.strip():
        raise ValueError("ads_stepchain_path requires a non-empty error_field.")
    if not isinstance(error_code_field, str) or not error_code_field.strip():
        raise ValueError("ads_stepchain_path requires a non-empty error_code_field.")
    if step_field is not None:
        if not isinstance(step_field, str) or not step_field.strip():
            raise ValueError("ads_stepchain_path step_field must be a non-empty string when set.")
    if step_name_field is not None:
        if not isinstance(step_name_field, str) or not step_name_field.strip():
            raise ValueError("ads_stepchain_path step_name_field must be a non-empty string when set.")
    if step_name_length <= 0:
        raise ValueError("ads_stepchain_path step_name_length must be > 0.")
    if completion not in ("poll", "notify"):
        raise ValueError("ads_stepchain_path completion must be either 'poll' or 'notify'.")
    if poll_interval <= 0:
        raise ValueError("ads_stepchain_path poll_interval must be > 0.")
    if timeout_s is not None and timeout_s <= 0:
        raise ValueError("ads_stepchain_path timeout_s must be > 0 when set.")
    if status_symbol is not None:
        if not isinstance(status_symbol, str) or not status_symbol.strip():
            raise ValueError("ads_stepchain_path status_symbol must be a non-empty string when set.")

    path_decorator = ads_path(object_name)
    cfg = StepChainConfig(
        status_symbol=status_symbol.strip() if isinstance(status_symbol, str) else None,
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
        step_name_length=int(step_name_length),
        completion=completion,
        poll_interval=float(poll_interval),
        timeout_s=timeout_s,
    )

    def _decorate(cls: _RpcInterfaceCls) -> _RpcInterfaceCls:
        cls = path_decorator(cls)
        setattr(cls, _ADS_STEPCHAIN_ATTR, cfg)
        return cls

    return _decorate


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

    stepchain_cfg = getattr(interface, _ADS_STEPCHAIN_ATTR, None)
    async_interface = bool(getattr(interface, _ADS_ASYNC_ATTR, False))
    stepchain = isinstance(stepchain_cfg, StepChainConfig)

    definition = RpcInterfaceDefinition(
        object_name=object_name.strip(),
        method_return_types=method_return_types,
        method_parameters=method_parameters,
        method_argument_names=method_argument_names,
        async_interface=async_interface,
        stepchain=stepchain,
        stepchain_config=stepchain_cfg if stepchain else None,
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
    annotation = _unwrap_async_annotation(annotation)
    if isinstance(annotation, type):
        return annotation
    return None


def _unwrap_async_annotation(annotation: Any) -> Any:
    """Extract inner return type from Future[T]/Awaitable[T] annotations."""
    origin = get_origin(annotation)
    if origin is None:
        return annotation

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
