"""Helpers for declaring strongly typed RPC interfaces."""

from __future__ import annotations

import inspect
import sys
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
    get_type_hints,
)

from .constants import PLCDataType

_RpcInterfaceCls = TypeVar("_RpcInterfaceCls", bound=Type[Any])
_RPC_DEF_CACHE_ATTR = "__pyads_rpc_definition__"


@dataclass(frozen=True)
class RpcInterfaceDefinition:
    """Resolved metadata for an ads_path-decorated RPC interface."""

    object_name: str
    method_return_types: Dict[str, Type["PLCDataType"]]
    method_parameters: Dict[str, Tuple[Type["PLCDataType"], ...]]


def ads_path(object_name: str) -> Callable[[Type[_RpcInterfaceCls]], Type[_RpcInterfaceCls]]:
    """Decorator for declaring the ADS path for an RPC interface class."""
    if not isinstance(object_name, str):
        raise TypeError("ads_path expects a string object name.")
    normalized = object_name.strip()
    if not normalized:
        raise ValueError("ads_path requires a non-empty object name.")

    def _decorate(cls: Type[_RpcInterfaceCls]) -> Type[_RpcInterfaceCls]:
        setattr(cls, "__ads_path__", normalized)
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

    definition = RpcInterfaceDefinition(
        object_name=object_name.strip(),
        method_return_types=method_return_types,
        method_parameters=method_parameters,
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


def _coerce_plc_type(annotation: Any) -> Optional[Type["PLCDataType"]]:
    if isinstance(annotation, type):
        return annotation
    return None
