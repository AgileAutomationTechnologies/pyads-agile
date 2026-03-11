pyads-agile
===========

`pyads-agile` is a Python wrapper for the Beckhoff TwinCAT ADS library.

This distribution is maintained by Agile Automation Technologies GmbH and is
based on the excellent upstream `pyads` project created by Stefan Lehmann:
https://github.com/stlehmann/pyads

`pyads-agile` intentionally stays drop-in compatible with `pyads`. The public API,
module name (`import pyads`), and supported interpreter/OS matrix mirror upstream,
so existing applications can switch distributions without code changes.
Current support target is Python 3.13 and 3.14.

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

  You can still use low-level direct calls when needed:

  ```python
  result = plc.call_rpc_method(
      "GVL.fbTestRemoteMethodCall#m_iSimpleCall",
      return_type=pyads.PLCTYPE_INT,
      write_value=42,
      write_type=pyads.PLCTYPE_INT,
  )
  ```

## Features

- connect to remote TwinCAT devices
- create routes on Linux and on remote PLCs
- support for TwinCAT 2 and TwinCAT 3
- read and write values by name or by address
- read and write DUTs (structures)
- notification callbacks

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
