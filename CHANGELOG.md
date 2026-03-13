# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

### Changed

### Removed

## [0.3.3] - 2026-03-13

### Added

### Changed
- `StepChainRpcInterface.read_status()` now reads configured status fields
  individually instead of decoding the raw PLC struct payload.
- Stepchain completion snapshots now include optional diagnostic fields such as
  `udiStep` and `sStepName` when configured.
- Stepchain documentation now explains why `read_status()` is safe without
  TwinCAT `pack_mode := '1'`, while generic structured reads still require it
  for mixed-type structs.

### Removed

## [0.3.2] - 2026-03-13

### Added
- Method-level stepchain typing via `StepChainRpcInterface` and
  `@pyads.stepchain_start`.
- Readable real async integration tests covering ported async wrappers,
  mixed async RPC interfaces, and stepchain abort behavior.
- TwinCAT reference materials:
  - importable PLC project archive (`.tpzip`)
  - readable ST reference source
  - dedicated stepchain documentation with TwinCAT design guidance

### Changed
- `AsyncConnection.get_async_object(...)` now supports mixed plain async RPC
  methods and stepchain start methods on the same interface class.
- Stepchain transport typing now derives from
  `StepChainOperation[PLCTYPE_*]`, while helper methods are exposed through
  `StepChainRpcInterface`.
- Real integration examples and configuration were aligned with Hungarian-style
  TwinCAT naming and explicit abort/error semantics.
- Notification-based stepchain completion now returns the final status snapshot
  consistently with polling mode.

### Removed
- Class-level `@pyads.ads_stepchain_path(...)` API in favor of
  `@pyads.ads_async_path(...)` + `StepChainRpcInterface` +
  `@pyads.stepchain_start`.

## [0.3.1] - 2026-03-12

### Added
- `pyads.StepChainOp` alias so developers can annotate stepchain methods
  without spelling `StepChainOperation[Any]` repeatedly.

### Changed
- `StepChainOperation` completion futures (both polling and notification
  backends) now return the latest ADS status snapshot dictionary instead of the
  RPC acceptance bool, exposing request/busy/done/error fields directly.
- Stepchain examples, documentation, and async tests updated to assert the new
  completion payload and to annotate interfaces with `StepChainOperation`
  return types.

### Removed

## [0.3.0] - 2026-03-12

### Added
- `AsyncConnection` with serialized worker-thread execution for race-safe asyncio usage.
- Async wrappers for core sync APIs (`submit_*` + awaitable methods), including:
  `read/write/read_write`, `read_by_name/write_by_name`,
  `read_structure_by_name/write_structure_by_name`, `sum_read/sum_write`,
  `read_state/read_device_info/write_control`, `get_local_address`,
  `get_handle/release_handle`, and `set_timeout`.
- Async RPC proxies via `AsyncConnection.get_async_object(...)`.
- `@pyads.ads_async_path(...)` for type-safe async RPC interface declarations.
- Stepchain async RPC framework via `@pyads.ads_stepchain_path(...)` and
  `StepChainOperation` (`accepted`, `done`, `await op`).
- Stepchain completion backends:
  - polling (`completion="poll"`)
  - ADS-notification driven (`completion="notify"`)
- Built-in stepchain status helpers on async stepchain proxies:
  `status_symbol()`, `get_status_structure_def()`, `read_status()`.
- Auto-generated stepchain request IDs when omitted.
- Real/fake integration test coverage for async runtime, async RPC, and stepchain flows.
- Typing distribution files (`py.typed`, `constants.pyi`) included in package artifacts.

### Changed
- Typed RPC metadata resolution now supports async return annotations
  (`Future[T]` / `Awaitable[T]`) by inferring PLC return type from inner `T`.
- `Connection.get_object(...)` now rejects interfaces decorated with
  `@ads_async_path(...)` and guides callers to `AsyncConnection.get_async_object(...)`.
- README and Sphinx docs updated for async runtime, async RPC, stepchain behavior,
  and new async decorator usage.

### Removed

## [0.2.0] - 2026-03-12

### Added
- `@pyads.ads_path(...)` decorator plus class-based `Connection.get_object(MyRpcInterface)`
  overload for IntelliSense-aware RPC stubs inferred from type hints.
- Real-target integration test that exercises class-based RPC interfaces.

### Changed
- README and connection documentation updated with typed RPC interface examples.

### Removed

## [0.1.1] - 2026-03-11

### Added
- Native RPC object proxy API via `Connection.get_object()` with declarative
  method signatures:
  - `method_return_types` for per-method return type mapping
  - `method_parameters` for per-method parameter type mapping
- Convenience RPC call helper: `Connection.call_rpc_method(...)`.
- Real-target integration tests for RPC helper and object-style RPC calls in
  `tests/integration_real/test_real_runtime.py`.
- GitHub Pages workflow for publishing Sphinx docs:
  `.github/workflows/docs-pages.yml`.
- Trusted-publishing release workflow improvements for TestPyPI/PyPI target
  selection in `.github/workflows/python-publish.yml`.

### Changed
- RPC docs added to `doc/documentation/connection.rst` with examples and
  TwinCAT `{attribute 'TcRpcEnable'}` requirement.
- README updated for new RPC usage, contribution policy, and versioning policy.
- Project URLs now point to the `AgileAutomationTechnologies/pyads-agile`
  repository, including documentation link.
- Supported Python versions narrowed to 3.13 and 3.14.

### Removed

## [0.1.0] - 2026-03-11

### Added

### Changed
- Switched `pyads-agile` to independent Semantic Versioning (`MAJOR.MINOR.PATCH`)
  starting at `0.1.0`.

### Removed

## 3.6

### Added

### Changed
* [#502](https://github.com/stlehmann/pyads/pull/502) Update adslib to Upstream version 113.0.31-1

### Removed

## 3.5.2

### Added
* [#487](https://github.com/stlehmann/pyads/issues/487) Switch to cibuildwheel for building wheels in CI (including Windows, Linux and MacOS wheels)
* [#482](https://github.com/stlehmann/pyads/issues/482) Support for Python 3.13 and 3.14 is included

### Changed
* [#488](https://github.com/stlehmann/pyads/issues/488) `datetime` objects passed on by notifications now have an explicit UTC timezone, instead of `None` 
* [#495](https://github.com/stlehmann/pyads/issues/495) Organizing of metadata in `pyproject.toml` 

### Removed
* [#488](https://github.com/stlehmann/pyads/issues/488) Removed custom `UTC` class, replaced by regular `datetime.timezone.utc`
* Minimum Python version changed to 3.9 (Python 3.8 is no longer supported)

## 3.5.1

### Added
* [#462](https://github.com/stlehmann/pyads/issues/462) Short description on Linux build dependencies in docs
* [#479](https://github.com/stlehmann/pyads/pull/479) Support for Beckhoff RT-Linux operating system
* [#480](https://github.com/stlehmann/pyads/pull/480) Added NC Error codes

### Changed
* [#400](https://github.com/stlehmann/pyads/issues/400) Full support for pyproject.toml

## 3.5.0

### Added
* [#384](https://github.com/stlehmann/pyads/pull/384) Enable processing of nested structures

### Changed

* [#437](https://github.com/stlehmann/pyads/pull/437) Solve issue of too little buffer space allocated to receive for automatic AMS NetID query
* [#438](https://github.com/stlehmann/pyads/pull/438) Fix issue with read list by name using structure defs if more than MAX_SUB_ADS_COMMANDS

### Fixed
* [#342](https://github.com/stlehmann/pyads/pull/342) Array support in read by list
* [#427](https://github.com/stlehmann/pyads/pull/427) Fixed issue with auto-update with structures

## 3.4.2

### Changed

* [#402](https://github.com/stlehmann/pyads/pull/402) Universal DLL path for TwinCat 4026 and 4024

## 3.4.1

### Changed
* [#392](https://github.com/stlehmann/pyads/pull/392) Fixed bug where port left open in Linux if exception during connecting
* [#389](https://github.com/stlehmann/pyads/pull/389) / [#393](https://github.com/stlehmann/pyads/pull/393) Fix for DLL path in TwinCT 4026
* [#369](https://github.com/stlehmann/pyads/pull/304) Add test for [#304](https://github.com/stlehmann/pyads/pull/304) in `tests/test_testserver.py`
* [#304](https://github.com/stlehmann/pyads/pull/304) Implemented try-catch when closing ADS notifications in AdsSymbol destructor
* [#325](https://github.com/stlehmann/pyads/pull/325) Added missing ADS return codes

## 3.4.0

### Added
* [#293](https://github.com/stlehmann/pyads/pull/2939) Support WSTRINGS in structures

### Changed
* [#292](https://github.com/stlehmann/pyads/pull/292) Improve performance of get_value_from_ctype_data for arrays
* [#363](https://github.com/stlehmann/pyads/pull/363) Allow for platform independent builds

### Removed

## 3.3.9

### Added
* [#273](https://github.com/stlehmann/pyads/pull/273) Add TC3 port 2, 3, 4 constants
* [#247](https://github.com/stlehmann/pyads/pull/247) Add support for FreeBSD (tc/bsd)
* [#274](https://github.com/stlehmann/pyads/pull/274) Support WSTRING datatype

### Changed
* [#269](https://github.com/stlehmann/pyads/pull/269) Refactor Connection class in its own module, add helper functions
* [#260](https://github.com/stlehmann/pyads/pull/260) Fix decoding of symbol comments

### Removed
* [#282](https://github.com/stlehmann/pyads/pull/282]) Removed sample project in adslib to fix install error on Windows

## 3.3.8

### Added

### Changed
* [#264](https://github.com/stlehmann/pyads/pull/264) Fix error when using read_list_by_name on Linux machines

### Removed

## 3.3.6

### Added
* [#249](https://github.com/stlehmann/pyads/pull/249) Add testserver package to setup.py

### Changed

### Removed

## 3.3.5

### Added
* [#223](https://github.com/stlehmann/pyads/pull/223) Add structure support for symbols
* [#238](https://github.com/stlehmann/pyads/pull/238) Add LINT type to DATATYPE_MAP
* [#239](https://github.com/stlehmann/pyads/pull/239) Add device notification handling for AdvancedHandler in testserver

### Changed
* [#221](https://github.com/stlehmann/pyads/pull/221) CI now uses Github Actions instead of TravisCI. Also Upload to PyPi is now on automatic.
* [#242](https://github.com/stlehmann/pyads/pull/242) Upgrade requirements.txt
* [#243](https://github.com/stlehmann/pyads/pull/243) Refactor testserver as a package with multiple files
* Use TwinCAT3 default port 851 (PORT_TC3PLC1) in docs

### Removed

## 3.3.4

### Added
* [#187](https://github.com/stlehmann/pyads/pull/187) Support structured data types in `read_list_by_name`
* [#220](https://github.com/stlehmann/pyads/pull/220) Support structured data types in `write_list_by_name`. Also the
  AdvancedHandler of the testserver now support sumup_read and sumup_write commands.
* [#195](https://github.com/stlehmann/pyads/pull/195) Read/write by name without passing the datatype
* [#200](https://github.com/stlehmann/pyads/pull/200) Split read write by list into max-ads-sub-comands chunks
* [#206](https://github.com/stlehmann/pyads/pull/206) AdsSymbol now supports DT, DATE_TIME and TIME datatypes 

### Changed
* [#202](https://github.com/stlehmann/pyads/pull/202) Testserver now support variable sumread and sumwrite with 
  variable length for uint8 and string datatypes
* [#209](https://github.com/stlehmann/pyads/pull/209) Removed duplicate tests and added addtional asserts to existing tests
* [#212](https://github.com/stlehmann/pyads/pull/212) Add type annotations to structs.py

### Removed

## 3.3.3

### Added
* comprehensive documentation and short Quickstart guide

### Changed
* [#192](https://github.com/stlehmann/pyads/pull/192) Make AdsSymbol even more pythonic
  * Replace AdsSymbol.set_auto_update function by AdsSymbol.auto_update property
  * Make AdsSymbol.value a property
  * AdsSymbol.value setter writes to plc if AdsSymbol.auto_update is True

### Removed
* [#193](https://github.com/stlehmann/pyads/pull/193) Remove testserver_ex package which is still in development. 
  The testserver_ex package can be found in the [testserver_ex branch](https://github.
  com/stlehmann/pyads/tree/testserver_ex).

## 3.3.2

### Added

### Changed
* fixed error with source distribution not containing adslib directory

### Removed

## 3.3.1

### Added
* [#174](https://github.com/stlehmann/pyads/pull/174) Add `AdsSymbol` class for pythonic access
* [#169](https://github.com/stlehmann/pyads/pull/169) Add adsGetNetIdForPLC to pyads_ex
* [#179](https://github.com/stlehmann/pyads/pull/179) Added destructor to `pyads.Connection`

### Changed

### Removed

## 3.3.0

### Added
* [#155](https://github.com/stlehmann/pyads/pull/155) Add get_all_symbols method to Connection
* [#157](https://github.com/stlehmann/pyads/pull/157) Add write_structure_by_name method to Connection
* [#161](https://github.com/stlehmann/pyads/pull/161) Add sum read and write commands

### Changed
* [#150](https://github.com/stlehmann/pyads/pull/150) Use function annotations and variable annotations for type annotations

### Removed
* [#152](https://github.com/stlehmann/pyads/pull/152) Remove deprecated functions
* [#150](https://github.com/stlehmann/pyads/pull/150) Drop support for Python 2.7 and Python 3.5

## 3.2.2

### Added
* [#141](https://github.com/stlehmann/pyads/issues/141) Add ULINT support to read_structure_by_name
* [#143](https://github.com/stlehmann/pyads/issues/143) Add parse_notification method to Connection

### Changed
* [#140](https://github.com/stlehmann/pyads/pull/140) Fix lineendings to LF in the repository
* [#139](https://github.com/stlehmann/pyads/pull/139) Fix documentation and test issues with DeviceNotifications
* [ea707](https://github.com/stlehmann/pyads/tree/ea7073d93feac75c1864d1fe8ab2e14a2068b552) Fix documentation on
 ReadTheDocs
* [45859](https://github.com/stlehmann/pyads/tree/45859d6e9038b55d319efdbda95d3d6eeadd45e3) Fix issue with async handling in adslib

### Removed

## 3.2.1

### Added
* [#130](https://github.com/stlehmann/pyads/pull/130) Allow read_write with NULL read/write data
* [#131](https://github.com/stlehmann/pyads/pull/131) Add FILETIME passthrough to notification decorator

### Changed
* [#135](https://github.com/stlehmann/pyads/pull/135) Bug fix for setting up remote route from linux
* [#137](https://github.com/stlehmann/pyads/pull/137) Update adslib from upstream

### Removed

## 3.2.0

### Added
* [#111](https://github.com/stlehmann/pyads/pull/111) test cases for notification decorators
* [#113](https://github.com/stlehmann/pyads/pull/113) Add option not to check for data size
* [#118](https://github.com/stlehmann/pyads/pull/118) Add support for arrays in notification decorator
* [#112](https://github.com/stlehmann/pyads/pull/112) Add getters/setters for connection netid and port 

### Changed
* [#128](https://github.com/stlehmann/pyads/pull/128) Deprecation warning for older non-class functions. In
future versions only methods of the Connection class are supported.

### Removed
* [#127](https://github.com/stlehmann/pyads/pull/127) Drop support for Python 2

## 3.1.3

### Added
* [#120](https://github.com/stlehmann/pyads/pull/120) Allow to write ctypes directly

### Changed
* [#125](https://github.com/stlehmann/pyads/pull/125) Add notifications by address. The `data_name
` parameter changed to `data` as now not only strings can be passed but also a tuple with index group and offset.
* [#123](https://github.com/stlehmann/pyads/pull/123) Add ULINT data type
* [#106](https://github.com/stlehmann/pyads/pull/106) Store notification callbacks per AmsAddr 

### Removed

## 3.1.2
* new function read_structure_by_name to read a structure with multiple 
datatypes from the plc (issue #82, many thanks to @chrisbeardy)
* simplify pyads.add_route, now the ams address can be supplied by a string
instead of an AmsAddr object

## 3.1.1
* get/release handle methods for faster read/write by name

## 3.1.0

* add routes to a plc remotely with pyads.add_route_to_plc()

## 3.0.12

* update adslib to current upstream version (2018-03-22)
* fix structure definition inaccurarcies (issue #72)
* fix compatibility issue with new version of adslib (issue #78)

## 3.0.11

* fixed bug where parameter return_ctypes has not been passed through call
hierarchy of all calls, thanks to pyhannes

## 3.0.10

* rename src directory to adslib to prevent naming conflicts

## 3.0.9

* add return_ctypes parameter for read functions to omit time-costy time conversion

## 3.0.8

* add array datatype support for read_write function
* add test with array datatype for read and read/write function
* add section for usage of array datatypes in Readme

## 3.0.6

*  AdsLib: allow UNIX flavors to build more easily

## 3.0.5

* add support for ctypes.Structure in notification callback decorators

## 3.0.4

* remove race-condition related to the notification decorator, thanks to Luka
Belingar for the bugfix

## Version 3.0.3

* bugfix: notifications on Windows didn't work

## Version 3.0.2

* bugfix: do not call add_route or delete_rout on Windows platform in Connection class
* increased coverage


## Version 3.0.1

With version **3.0.1** only the extended ADS functions will be used. This allows to use
the same library functions for Linux and Windows. As a result the *pyads.py* module has
been removed from the package. Certain older versions of TcAdsDll don't support the 'Ex'
set of functions. If you experience trouble please update your TwinCAT version.

The new version also comes with completely covered PEP484 compliant type-annotations. So
you can conveniently apply static type-checking with mypy or others.

## Version 2.2.13

* Apply to new PyPi
* Add `set_local_address` function to change local address on Linuxjk:w

## Version 2.2.7

Long Description for PyPi

## Version 2.2.6

Fix error with older TwinCAT2 versions and notifications.

## Version 2.2.5

Extended Testserver supports multiple device notifications

## Version 2.2.4

Notification callback decorator

## Version 2.2.3

Extended testserver that keeps written values and supports Device Notifications.

## Version 2.2.0

Include shared library for Linux ADS communication. No manual installation
necessary anymore.

`Connection` class to allow a more convenient object oriented workflow. Each
device connection is now an object with methods for reading, writing, ...
However it is still possible to use the old-style functional approach.

Added device notifications. Device notifications can now be used to monitor
values on the PLC. On certain changes callbacks can be used to react. Thanks
to the great implementation by Peter Janeck.

## Version 2.1.0
Linux support!

Pyads now has Linux compatibility by wrapping the [open source ADS library](https://github.com/dabrowne/ADS) provided by Beckhoff. The main API is identical on both Linux and Windows, however the Linux implementation includes a built in router which needs to be managed programmatically using `pyads.add_route(ams_address, ip_address)` and `pyads.delete_route(ams_address)`.

Version 2.1.0 also features vastly improved test coverage of the API, and the addition of a dummy test server for full integration testing.

## Version 2.0.0

I wanted to make the Wrapper more pythonic so I created a new module named
pyads.ads that contains all the functions from pyads.pyads but in a more
pythonic way. You can still access the old functions by using the pyads.pyads
module.

Improvements:

* more pythonic function names (e.g. 'write' instead of 'adsSyncWrite')
* easier handling of reading and writing Strings
* no error codes, if errors occur an Exception with the error code will be
raised
