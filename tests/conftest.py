"""Pytest configuration for selecting ADS test target.

`fake` target:
- Uses the built-in pyads fake ADS test server (default, CI-friendly).

`real` target:
- Uses a real Beckhoff ADS runtime (local/integration).
"""

import os
from typing import List

import pytest
from pathlib import Path

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--ads-target",
        action="store",
        choices=("fake", "real"),
        default=None,
        help="Select ADS backend: fake (testserver) or real (Beckhoff runtime).",
    )
    parser.addoption(
        "--real-config-file",
        action="store",
        default=os.getenv("PYADS_REAL_CONFIG_FILE", "tests/integration_real/real_runtime.toml"),
        help="Path to TOML file with real runtime test settings.",
    )
    parser.addoption(
        "--real-plc-ip",
        action="store",
        default=None,
        help="IP address of real PLC/runtime used when --ads-target=real.",
    )
    parser.addoption(
        "--real-plc-ams-net-id",
        action="store",
        default=None,
        help="AMS Net ID of real PLC/runtime used when --ads-target=real.",
    )
    parser.addoption(
        "--real-plc-ams-port",
        action="store",
        default=None,
        help="AMS port of real PLC/runtime used when --ads-target=real.",
    )
    parser.addoption(
        "--real-test-symbol",
        action="store",
        default=None,
        help="Optional PLC symbol name for real integration notification tests.",
    )
    parser.addoption(
        "--real-test-symbol-int",
        action="store",
        default=None,
        help="Optional PLC INT symbol used for real read/write integration tests.",
    )
    parser.addoption(
        "--real-test-symbol-str",
        action="store",
        default=None,
        help="Optional PLC STRING symbol used for real read/write integration tests.",
    )
    parser.addoption(
        "--real-test-symbol-struct",
        action="store",
        default=None,
        help="Optional PLC structure symbol used for real structure integration tests.",
    )
    parser.addoption(
        "--real-test-symbol-struct-array",
        action="store",
        default=None,
        help="Optional PLC structure-array symbol used for real structure-array integration tests.",
    )
    parser.addoption(
        "--real-test-struct-strlen",
        action="store",
        default=None,
        help="STRING length used in structure test definition.",
    )
    parser.addoption(
        "--real-test-struct-array-size",
        action="store",
        default=None,
        help="Array size used in structure-array test definition.",
    )


def _load_real_config(path_value: str) -> dict:
    if not path_value:
        return {}
    cfg_path = Path(path_value)
    if not cfg_path.exists() or not cfg_path.is_file():
        return {}
    if tomllib is None:
        return {}
    with cfg_path.open("rb") as f:
        data = tomllib.load(f)
    return data.get("real_runtime", {}) if isinstance(data, dict) else {}


def _resolve_setting(
    cli_value: str,
    env_key: str,
    cfg_value: str,
    default_value: str,
) -> str:
    if cli_value:
        return str(cli_value)
    env_value = os.getenv(env_key, "")
    if env_value:
        return env_value
    if cfg_value:
        return str(cfg_value)
    return default_value


def pytest_configure(config: pytest.Config) -> None:
    cfg_path = config.getoption("real_config_file")
    cfg = _load_real_config(cfg_path)

    target = _resolve_setting(
        config.getoption("ads_target"),
        "PYADS_TEST_TARGET",
        cfg.get("ads_target", ""),
        "fake",
    )
    real_plc_ip = _resolve_setting(
        config.getoption("real_plc_ip"),
        "PYADS_REAL_PLC_IP",
        cfg.get("plc_ip", ""),
        "127.0.0.1",
    )
    real_plc_ams_net_id = _resolve_setting(
        config.getoption("real_plc_ams_net_id"),
        "PYADS_REAL_PLC_AMS_NET_ID",
        cfg.get("plc_ams_net_id", ""),
        "",
    )
    real_plc_ams_port = _resolve_setting(
        config.getoption("real_plc_ams_port"),
        "PYADS_REAL_PLC_AMS_PORT",
        cfg.get("plc_ams_port", ""),
        "",
    )
    real_test_symbol = _resolve_setting(
        config.getoption("real_test_symbol"),
        "PYADS_REAL_TEST_SYMBOL",
        cfg.get("test_symbol", ""),
        "",
    )
    real_test_symbol_int = _resolve_setting(
        config.getoption("real_test_symbol_int"),
        "PYADS_REAL_TEST_SYMBOL_INT",
        cfg.get("test_symbol_int", ""),
        real_test_symbol,
    )
    real_test_symbol_str = _resolve_setting(
        config.getoption("real_test_symbol_str"),
        "PYADS_REAL_TEST_SYMBOL_STR",
        cfg.get("test_symbol_str", ""),
        "",
    )
    real_test_symbol_struct = _resolve_setting(
        config.getoption("real_test_symbol_struct"),
        "PYADS_REAL_TEST_SYMBOL_STRUCT",
        cfg.get("test_symbol_struct", ""),
        "",
    )
    real_test_symbol_struct_array = _resolve_setting(
        config.getoption("real_test_symbol_struct_array"),
        "PYADS_REAL_TEST_SYMBOL_STRUCT_ARRAY",
        cfg.get("test_symbol_struct_array", ""),
        "",
    )
    real_test_struct_strlen = _resolve_setting(
        config.getoption("real_test_struct_strlen"),
        "PYADS_REAL_TEST_STRUCT_STRLEN",
        cfg.get("test_struct_strlen", ""),
        "",
    )
    real_test_struct_array_size = _resolve_setting(
        config.getoption("real_test_struct_array_size"),
        "PYADS_REAL_TEST_STRUCT_ARRAY_SIZE",
        cfg.get("test_struct_array_size", ""),
        "",
    )

    # Export options as env vars so unittest-based tests can read them uniformly.
    os.environ["PYADS_TEST_TARGET"] = target
    os.environ["PYADS_REAL_PLC_IP"] = real_plc_ip
    os.environ["PYADS_REAL_PLC_AMS_NET_ID"] = real_plc_ams_net_id
    os.environ["PYADS_REAL_PLC_AMS_PORT"] = real_plc_ams_port
    os.environ["PYADS_REAL_TEST_SYMBOL"] = real_test_symbol
    os.environ["PYADS_REAL_TEST_SYMBOL_INT"] = real_test_symbol_int
    os.environ["PYADS_REAL_TEST_SYMBOL_STR"] = real_test_symbol_str
    os.environ["PYADS_REAL_TEST_SYMBOL_STRUCT"] = real_test_symbol_struct
    os.environ["PYADS_REAL_TEST_SYMBOL_STRUCT_ARRAY"] = real_test_symbol_struct_array
    os.environ["PYADS_REAL_TEST_STRUCT_STRLEN"] = real_test_struct_strlen
    os.environ["PYADS_REAL_TEST_STRUCT_ARRAY_SIZE"] = real_test_struct_array_size


def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    target = os.getenv("PYADS_TEST_TARGET", "fake")
    skip_real = pytest.mark.skip(reason="Skipped: requires --ads-target=real")
    skip_fake = pytest.mark.skip(reason="Skipped: requires --ads-target=fake")

    for item in items:
        if "ads_real" in item.keywords and target != "real":
            item.add_marker(skip_real)
        if "ads_fake" in item.keywords and target != "fake":
            item.add_marker(skip_fake)
