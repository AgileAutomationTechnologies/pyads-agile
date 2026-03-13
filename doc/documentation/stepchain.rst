Stepchain Guide
===============

This page documents the recommended way to structure TwinCAT code for the
``pyads-agile`` stepchain framework and how that maps to the Python async API.

Reference sources
^^^^^^^^^^^^^^^^^

The repository contains two concrete PLC references:

* ``examples/twincat_reference/project/Test_PyAdsAgile.tpzip``
  Importable TwinCAT PLC project archive.
* ``examples/twincat_reference/pyads_agile_reference.st``
  Human-readable TwinCAT source bundle meant to be copied into a TwinCAT
  project.
* ``tests/integration_real/plc_symbols_template.st``
  Source used as the basis for the real integration tests.

The real async integration tests live in
``tests/integration_real/test_real_async_runtime.py``.

Mental model
^^^^^^^^^^^^

A stepchain call in ``pyads-agile`` has two phases:

* Accepted phase:
  The RPC method itself returns, for example ``m_xStartStepChain() -> BOOL``.
  This becomes ``await operation.accepted`` in Python.
* Completion phase:
  Python then watches the PLC status structure until the configured ``done`` or
  ``error`` condition is reached. This becomes ``await operation``.

That means the start RPC method should only answer one narrow question:

* "Was the stepchain accepted for execution right now?"

It should not try to block until the workflow is finished. The actual workflow
must advance in the cyclic PLC body.

Recommended TwinCAT structure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For a TwinCAT stepchain function block, keep these responsibilities separate:

1. One exposed FB instance in ``GVL``.
2. One status structure in that FB, usually ``stStepStatus``.
3. One ``{attribute 'TcRpcEnable'}`` start method that initializes the workflow.
4. Optional plain RPC methods such as abort, reset, acknowledge, or force-error.
5. Cyclic execution in the FB body that advances the internal steps.

The important design rule is this:

* ``@pyads.stepchain_start`` should be used only for methods that start a new
  tracked stepchain operation.
* Methods like ``m_xAbortStepChain()`` are plain async RPC methods and should
  return ``asyncio.Future[pyads.PLCTYPE_BOOL]`` in the Python stub.

Recommended naming
^^^^^^^^^^^^^^^^^^

The examples in this repository follow Hungarian-style TwinCAT naming:

* ``st`` for structs
* ``fb`` for function blocks
* ``x`` for BOOL
* ``i`` for INT
* ``udi`` for UDINT
* ``s`` for STRING
* ``m_`` for methods
* ``m_x`` for methods returning BOOL

Typical PLC status structure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: text

   TYPE ST_StepStatus :
   STRUCT
       udiRequestId : UDINT;
       xBusy        : BOOL;
       xDone        : BOOL;
       xError       : BOOL;
       diErrorCode  : DINT;
       udiStep      : UDINT;
       sStepName    : STRING(80);
   END_STRUCT
   END_TYPE

Recommended semantics:

* ``udiRequestId``:
  Copy the request id passed into the start method.
* ``xBusy``:
  True while the PLC workflow is still running.
* ``xDone``:
  True only for successful completion.
* ``xError``:
  True only for failed completion.
* ``diErrorCode``:
  Machine-readable error code. Use ``0`` on success.
* ``udiStep`` and ``sStepName``:
  Optional but strongly recommended for diagnostics and tests.

TwinCAT example
^^^^^^^^^^^^^^^

The following pattern is the recommended one for this library:

.. code:: text

   FUNCTION_BLOCK FB_TestStepChain
   VAR
       stStepStatus : ST_StepStatus;
       _xBusy : BOOL;
       _udiInternalStep : UDINT;
       _xSimulateError : BOOL;
   END_VAR

   // Cyclic body advances the workflow.
   IF NOT _xBusy THEN
       RETURN;
   END_IF

   CASE _udiInternalStep OF
       10:
           stStepStatus.sStepName := 'Prepare';
           // move to next step when condition is reached
       20:
           stStepStatus.sStepName := 'Load';
       30:
           stStepStatus.sStepName := 'Process';
       40:
           stStepStatus.sStepName := 'Finalize';
   END_CASE

   {attribute 'TcRpcEnable'}
   METHOD m_xStartStepChain : BOOL
   VAR_INPUT
       udiRequestId : UDINT;
   END_VAR

   IF _xBusy THEN
       m_xStartStepChain := FALSE;
       RETURN;
   END_IF

   _xBusy := TRUE;
   _udiInternalStep := 10;
   stStepStatus.udiRequestId := udiRequestId;
   stStepStatus.xBusy := TRUE;
   stStepStatus.xDone := FALSE;
   stStepStatus.xError := FALSE;
   stStepStatus.diErrorCode := 0;
   stStepStatus.udiStep := _udiInternalStep;
   stStepStatus.sStepName := 'Prepare';
   m_xStartStepChain := TRUE;

Key point:

* ``m_xStartStepChain`` only initializes the workflow and returns quickly.
* The cyclic body owns the real progress and the final status update.

How to model abort
^^^^^^^^^^^^^^^^^^

There are two valid designs for abort. Pick one and document it clearly.

Abort as error
""""""""""""""

This is the pattern used by your current PLC code.

TwinCAT side:

* ``m_xAbortStepChain()`` is a normal RPC method.
* It forces the workflow to stop.
* It writes:
  * ``xBusy := FALSE``
  * ``xDone := FALSE``
  * ``xError := TRUE``
  * ``diErrorCode := -2``
  * ``sStepName := 'Aborted'``

Python consequence:

* ``await rpc.m_xAbortStepChain()`` returns ``True`` when the abort request was
  accepted.
* ``await operation`` raises ``RuntimeError`` because the completion status
  reports ``xError = TRUE``.

Abort as successful completion
""""""""""""""""""""""""""""""

This is also possible, but then your PLC status must say that explicitly:

* ``xBusy := FALSE``
* ``xDone := TRUE``
* ``xError := FALSE``
* ``diErrorCode := 0``
* ``sStepName := 'Aborted'``

Python consequence:

* ``await operation`` completes normally and returns the final snapshot.

Choose one semantic model and keep it stable. Mixing both patterns across PLC
projects will confuse operators and API users.

Python interface pattern
^^^^^^^^^^^^^^^^^^^^^^^^

Use one async interface class for the whole FB and mix plain async RPC methods
with stepchain start methods.

.. code:: python

   import asyncio
   import pyads

   @pyads.ads_async_path("GVL.fbStepChain")
   class FB_TestStepChain(pyads.StepChainRpcInterface):
       __stepchain_completion__ = "poll"

       @pyads.stepchain_start
       def m_xStartStepChain(
           self,
           udiRequestId: pyads.PLCTYPE_UDINT,
       ) -> pyads.StepChainOperation[pyads.PLCTYPE_BOOL]:
           ...

       def m_xAbortStepChain(self) -> asyncio.Future[pyads.PLCTYPE_BOOL]:
           ...

Important typing rule:

* ``StepChainOperation[pyads.PLCTYPE_BOOL]`` describes the PLC transport type of
  the accepted phase.
* ``await operation`` still returns the completion snapshot dictionary.

Python usage pattern
^^^^^^^^^^^^^^^^^^^^

Successful completion:

.. code:: python

   async with pyads.AsyncConnection("127.0.0.1.1.1", pyads.PORT_TC3PLC1) as plc:
       rpc = plc.get_async_object(FB_TestStepChain)
       operation = rpc.m_xStartStepChain()

       accepted = await operation.accepted
       if not accepted:
           raise RuntimeError("PLC rejected the start request.")

       snapshot = await operation
       print(snapshot[f"{rpc.status_symbol()}.udiRequestId"])

Abort with your current PLC design:

.. code:: python

   async with pyads.AsyncConnection("127.0.0.1.1.1", pyads.PORT_TC3PLC1) as plc:
       rpc = plc.get_async_object(FB_TestStepChain)
       operation = rpc.m_xStartStepChain()

       accepted = await operation.accepted
       if not accepted:
           raise RuntimeError("PLC rejected the start request.")

       abort_result = await rpc.m_xAbortStepChain()
       if not abort_result:
           raise RuntimeError("PLC rejected the abort request.")

       try:
           await operation
       except RuntimeError as exc:
           print("Expected abort error:", exc)

       status = await rpc.read_status()
       print(status["xError"], status["diErrorCode"], status["sStepName"])

Practical TwinCAT rules
^^^^^^^^^^^^^^^^^^^^^^^

These rules make the framework easier to use and easier to debug:

* Keep one status structure per stepchain FB instance.
* Update ``udiRequestId`` only when a new start request is accepted.
* Always write the whole terminal status consistently:
  do not leave ``xBusy`` true after setting ``xDone`` or ``xError``.
* Prefer explicit step names such as ``Prepare``, ``Load``, ``Process``,
  ``Finalize``, ``Done``, ``Error``, ``Aborted``.
* Keep abort, reset, or acknowledge actions as separate RPC methods.
* Do not run the whole long-running procedure inside the RPC method itself.
  Use the cyclic FB body instead.
* If you use timers, drive them from the cyclic body, not from the RPC method.
* For tests, expose a simple fault injection bit such as
  ``GVL.xStepChainForceError`` so error paths can be reproduced deterministically.

Real integration tests in this repository
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The real async integration suite covers:

* core async connection operations
* async wrappers ported from sync calls
* async typed RPC calls
* successful stepchain completion
* stepchain abort behavior

Before running them, make sure these configuration values in
``tests/integration_real/real_runtime.toml`` match your PLC:

* ``test_stepchain_object``
* ``test_stepchain_method``
* ``test_stepchain_abort_method``
* ``test_stepchain_status_symbol`` or ``test_stepchain_status_field``
* the individual status field names if they differ from the defaults
