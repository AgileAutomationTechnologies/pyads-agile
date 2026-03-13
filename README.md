pyads-agile
===========

`pyads-agile` is a Python wrapper for the Beckhoff TwinCAT ADS library.

This distribution is maintained by Agile Automation Technologies GmbH and is
based on the excellent upstream `pyads` project created by Stefan Lehmann:
https://github.com/stlehmann/pyads

`pyads-agile` intentionally stays drop-in compatible with `pyads`. The public API,
module name (`import pyads`), and supported interpreter/OS matrix mirror upstream,
so existing applications can switch distributions without code changes.
Current validated support target is Python 3.13 (CI runs on 3.13).

## Attribution

- Original project: `pyads` by Stefan Lehmann
- Fork maintainer: Filippo Boido <filippo.boido@agileautomation.eu> (Agile Automation Technologies GmbH)
- License: MIT
- This repository keeps upstream credit and license notices as required

See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for details.

## Installation

Install the distribution:

```bash
pip install pyads-agile
```

Import stays compatible:

```python
import pyads
```

## Versioning

`pyads-agile` uses its own independent Semantic Versioning (`MAJOR.MINOR.PATCH`).
It does not mirror upstream `pyads` version numbers.

## Scope

This package provides Python APIs for communicating with TwinCAT devices using:

- `TcAdsDll.dll` on Windows
- `adslib.so` on Linux

## Agile-specific enhancements

Beyond compatibility, this fork currently focuses on improved RPC ergonomics:

- **Convenient RPC object proxies.** `Connection.get_object()` exposes TwinCAT
  function blocks as Python objects and lets you configure return and parameter
  types per method:

  TwinCAT requirement: each callable method must be annotated in PLC code with
  `{attribute 'TcRpcEnable'}` directly above the method declaration.

  ```python
  rpc = plc.get_object(
      "GVL.fbTestRemoteMethodCall",
      method_return_types={"m_iSimpleCall": pyads.PLCTYPE_INT},
  )
  result = rpc.m_iSimpleCall()
  ```

- **Multi-parameter RPC calls with native syntax.** Configure method signatures
  once and then call methods like normal Python methods:

  ```python
  rpc = plc.get_object(
      "GVL.fbTestRemoteMethodCall",
      method_return_types={"m_iSum": pyads.PLCTYPE_INT},
      method_parameters={"m_iSum": [pyads.PLCTYPE_INT, pyads.PLCTYPE_INT]},
  )
  result = rpc.m_iSum(5, 5)
  ```

- **Typed RPC interfaces for IntelliSense.** Decorate a Python class with
  `@pyads.ads_path("GVL.fbTestRemoteMethodCall")`, annotate method arguments and
  return types with TwinCAT PLC types, and pass the class into
  `Connection.get_object`. The returned proxy is typed as your class so IDEs can
  offer completions:

  ```python
  @pyads.ads_path("GVL.fbTestRemoteMethodCall")
  class FB_TestRemoteMethodCall:
      def m_iSum(
          self,
          a: pyads.PLCTYPE_INT,
          b: pyads.PLCTYPE_INT,
      ) -> pyads.PLCTYPE_INT:
          ...

  rpc = plc.get_object(FB_TestRemoteMethodCall)
  result = rpc.m_iSum(5, 5)
  ```

  You can still use low-level direct calls when needed:

  ```python
  result = plc.call_rpc_method(
      "GVL.fbTestRemoteMethodCall#m_iSimpleCall",
      return_type=pyads.PLCTYPE_INT,
      write_value=42,
      write_type=pyads.PLCTYPE_INT,
  )
  ```

- **Serialized async ADS runtime.** `AsyncConnection` executes all ADS calls on
  a dedicated worker thread per connection (in-order, race-safe on connection
  state), and exposes awaitable helpers and submit-style futures:

  ```python
  import asyncio
  import pyads

  async def main() -> None:
      async with pyads.AsyncConnection("127.0.0.1.1.1", pyads.PORT_TC3PLC1) as plc:
          fut = plc.submit_sum_read(["GVL.int_val", "GVL.bool_val"])
          # ... do other work
          values = await fut

          await plc.sum_write({"GVL.int_val": int(values["GVL.int_val"]) + 1})

  asyncio.run(main())
  ```

- **Async wrappers for the synchronous pyads Connection API.**
  `AsyncConnection` now mirrors the core synchronous read/write surface while
  keeping single-threaded serialized execution under the hood. For most methods
  you get both:
  - `submit_*` returning `asyncio.Future`
  - `async` method variant that awaits the same operation

  Covered wrappers include:
  - `read`, `write`, `read_write`
  - `read_by_name`, `write_by_name`
  - `read_structure_by_name`, `write_structure_by_name`
  - `read_state`, `read_device_info`, `write_control`
  - `get_local_address`, `get_handle`, `release_handle`, `set_timeout`
  - `sum_read` / `sum_write` (`submit_sum_read` / `submit_sum_write`)

  ```python
  import asyncio
  import pyads

  async def main() -> None:
      async with pyads.AsyncConnection("127.0.0.1.1.1", pyads.PORT_TC3PLC1) as plc:
          # Await-style
          value = await plc.read_by_name("GVL.int_val", pyads.PLCTYPE_INT)
          await plc.write_by_name("GVL.int_val", value + 1, pyads.PLCTYPE_INT)

          # Submit-style
          fut = plc.submit_read_state()
          state = await fut
          print(state)

  asyncio.run(main())
  ```

- **Async typed RPC objects.** Use `@pyads.ads_async_path(...)` with
  `AsyncConnection.get_async_object(...)` for type-safe async RPC interfaces.
  Method calls return `asyncio.Future` objects:

  ```python
  @pyads.ads_async_path("GVL.fbTestRemoteMethodCall")
  class FB_TestRemoteMethodCall:
      def m_iSum(
          self,
          a: pyads.PLCTYPE_INT,
          b: pyads.PLCTYPE_INT,
      ) -> asyncio.Future[pyads.PLCTYPE_INT]:
          ...

  async def main(plc: pyads.AsyncConnection) -> None:
      rpc = plc.get_async_object(FB_TestRemoteMethodCall)
      future = rpc.m_iSum(5, 5)
      result = await future
      print(result)
  ```

- **Native stepchain async RPC interfaces.** Use
  `@pyads.ads_async_path(...)` on the interface, inherit from
  `pyads.StepChainRpcInterface`, and mark stepchain entry methods with
  `@pyads.stepchain_start`. Calls return a `StepChainOperation`
  containing:
  - `accepted`: RPC-return phase
  - `done`: completion phase based on PLC status fields
  - `await op`: completion snapshot with the latest ADS status symbol values
  The generic parameter on `StepChainOperation[...]` describes the ADS
  transport return type for the accepted phase.

  ```python
  @pyads.ads_async_path("GVL.fbTestRemoteStepChainMethodCall")
  class FB_TestRemoteStepChainMethodCall(pyads.StepChainRpcInterface):
      __stepchain_completion__ = "poll"  # or "notify"

      @pyads.stepchain_start
      def m_xStartStepChain(
          self,
          udiRequestId: pyads.PLCTYPE_UDINT,
      ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
          ...

  async def run_stepchain(plc: pyads.AsyncConnection) -> None:
      rpc = plc.get_async_object(FB_TestRemoteStepChainMethodCall)
      status_root = rpc.status_symbol()

      # udiRequestId is auto-generated if omitted.
      op = rpc.m_xStartStepChain()

      accepted = await op.accepted
      if not accepted:
          raise RuntimeError("Stepchain start rejected by PLC.")

      # Wait until status reports completion or error and capture snapshot.
      completion_snapshot = await op
      request_id_symbol = f"{status_root}.udiRequestId"
      print("Completed request", completion_snapshot[request_id_symbol])

      # Built-in framework status read (predefined structure)
      status = await rpc.read_status()
      print(status["udiStep"], status["sStepName"])
  ```

  Completion backend options:
  - `completion="poll"`: periodic `sum_read` checks (`poll_interval`/`timeout_s`)
  - `completion="notify"`: ADS notifications trigger status reads in asyncio

  Built-in predefined stepchain status fields:
  - `udiRequestId`, `xBusy`, `xDone`, `xError`, `diErrorCode`, `udiStep`, `sStepName`

  Repository references:
  - TwinCAT PLC project archive: [`examples/twincat_reference/project/Test_PyAdsAgile.tpzip`](examples/twincat_reference/project/Test_PyAdsAgile.tpzip)
  - TwinCAT reference source: [`examples/twincat_reference/pyads_agile_reference.st`](examples/twincat_reference/pyads_agile_reference.st)
  - Real test PLC template: [`tests/integration_real/plc_symbols_template.st`](tests/integration_real/plc_symbols_template.st)
  - Detailed stepchain guide: [`doc/documentation/stepchain.rst`](doc/documentation/stepchain.rst)

## Features

- connect to remote TwinCAT devices
- create routes on Linux and on remote PLCs
- support for TwinCAT 2 and TwinCAT 3
- read and write values by name or by address
- read and write DUTs (structures)
- notification callbacks
- typed RPC interfaces via `@pyads.ads_path(...)`
- async typed RPC interfaces via `@pyads.ads_async_path(...)`
- serialized asyncio runtime via `pyads.AsyncConnection`
- async wrappers for core sync ADS methods (`submit_*` + awaitable variants)
- async typed RPC proxies via `get_async_object(...)`
- native stepchain async RPC flow via `StepChainRpcInterface` + `@pyads.stepchain_start`
- stepchain completion backends: polling (`poll`) and notification-driven (`notify`)

## Basic usage

```python
import pyads

plc = pyads.Connection("127.0.0.1.1.1", pyads.PORT_TC3PLC1)
plc.open()
i = plc.read_by_name("GVL.int_val")
plc.write_by_name("GVL.int_val", i)
plc.close()
```

## Contribution Policy

This repository is maintained on a best-effort basis for internal and product
needs.

At this time, we do not accept unsolicited pull requests, and we may not be
able to respond to feature requests or general support issues.
