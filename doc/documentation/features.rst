pyads-agile Features
====================

This page summarizes the main additions and integrations maintained in the
``pyads-agile`` repository beyond baseline upstream compatibility.

RPC and typing enhancements
^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Native RPC proxy calls via :py:meth:`pyads.Connection.get_object`.
* Typed RPC interface declarations with :py:func:`pyads.ads_path`, using PLC
  type annotations for IntelliSense and signature inference.
* Manual override support for inferred parameter/return types when needed.

Async runtime and safety
^^^^^^^^^^^^^^^^^^^^^^^^

* :py:class:`pyads.AsyncConnection` with a dedicated worker thread per
  connection.
* In-order serialized ADS call execution to avoid race conditions on mutable
  connection state.
* ``submit_*`` methods returning :py:class:`asyncio.Future` and awaitable async
  method variants for core operations.

Async wrappers for core ADS APIs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The async layer mirrors the core sync APIs, including:

* ``read``, ``write``, ``read_write``
* ``read_by_name``, ``write_by_name``
* ``read_structure_by_name``, ``write_structure_by_name``
* ``sum_read`` / ``sum_write``
* ``read_state``, ``read_device_info``, ``write_control``
* ``get_local_address``, ``get_handle``, ``release_handle``, ``set_timeout``

Async RPC and stepchain integration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Async typed RPC proxies via
  :py:meth:`pyads.AsyncConnection.get_async_object`.
* Async interface decorator for type-safe future-returning methods:
  :py:func:`pyads.ads_async_path`.
* Stepchain-aware async interfaces via :py:class:`pyads.StepChainRpcInterface`
  and :py:func:`pyads.stepchain_start`.
* :py:class:`pyads.StepChainOperation` with:

  * ``accepted`` phase (RPC returned)
  * ``done`` phase (completion detected via configured status symbols)
  * awaitable operation behavior returning the latest ADS status snapshot
    (``await op`` == ``await op.done``)
  * generic transport type extraction via ``StepChainOperation[PLCTYPE_*]``
* Auto-generated request IDs for stepchain methods when the request id argument
  is omitted.
* Default stepchain naming aligned with common TwinCAT conventions:
  ``stStepStatus``, ``udiRequestId``, ``xBusy``, ``xDone``, ``xError``,
  ``diErrorCode``.
* Built-in stepchain status helper methods on ``StepChainRpcInterface`` proxies:
  ``status_symbol()``, ``get_status_structure_def()``, and ``read_status()``.
* Stepchain completion backends selectable per interface:
  ``completion="poll"`` or ``completion="notify"``.

Testing and quality additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Fake-backend async integration tests (testserver target).
* Real-target async integration tests for Beckhoff runtime environments.
* Dedicated tests for typed RPC inference, async serialization behavior, and
  stepchain completion/error paths.
