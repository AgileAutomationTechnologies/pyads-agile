pyads-agile
===========

`pyads-agile` is a Python wrapper for the Beckhoff TwinCAT ADS library.

This distribution is maintained by Agile Automation Technologies GmbH and is
based on the excellent upstream `pyads` project created by Stefan Lehmann:
https://github.com/stlehmann/pyads

`pyads-agile` intentionally stays drop-in compatible with `pyads`. The public API,
module name (`import pyads`), and supported interpreter/OS matrix mirror upstream,
so existing applications can switch distributions without code changes.

## Attribution

- Original project: `pyads` by Stefan Lehmann
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

## Scope

This package provides Python APIs for communicating with TwinCAT devices using:

- `TcAdsDll.dll` on Windows
- `adslib.so` on Linux

## Agile-specific enhancements

Beyond compatibility, this fork currently focuses on improved RPC ergonomics:

- **Convenient RPC object proxies.** `Connection.get_object()` exposes TwinCAT
  function blocks as Python objects and lets you pin each method’s return type:

  ```python
  rpc = plc.get_object(
      "GVL.fbTestRemoteMethodCall",
      method_return_types={"m_iSimpleCall": pyads.PLCTYPE_INT},
  )
  result = rpc.m_iSimpleCall()
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

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md).
