# TwinCAT Reference Sources

This folder contains both:

- an importable TwinCAT PLC project archive
- a readable ST reference source bundle

for the `pyads-agile` async RPC and stepchain examples.

Contents:

- `project/Test_PyAdsAgile.tpzip`
  Importable TwinCAT PLC project archive containing:
  - DUTs
  - `GVL`
  - `FB_TestRemoteMethodCall`
  - `FB_TestStepChain`
  - `MAIN`
  - task configuration and compiled metadata
- `pyads_agile_reference.st`
  Readable ST source containing:
  - DUTs for the integration tests
  - `FB_TestRemoteMethodCall`
  - `FB_TestStepChain`
  - `GVL` symbols
  - `PROGRAM MAIN` calling `GVL.fbStepChain()`

Recommended usage:

1. Import `project/Test_PyAdsAgile.tpzip` into TwinCAT 3 if you want a ready-to-open project.
2. Use `pyads_agile_reference.st` if you want a readable source reference or want to paste the logic into an existing PLC project.
3. Activate configuration and start the runtime.
4. Align `tests/integration_real/real_runtime.toml` with the symbol names.

Important runtime behavior for the stepchain sample:

- `m_xStartStepChain(udiRequestId)` starts the workflow and writes the status struct.
- `m_xAbortStepChain()` is a plain RPC call, not a stepchain start method.
- Abort is modeled as an error outcome:
  - `xBusy := FALSE`
  - `xDone := FALSE`
  - `xError := TRUE`
  - `diErrorCode := -2`
  - `sStepName := 'Aborted'`
- Because the status reports `xError = TRUE`, `await operation` raises
  `RuntimeError` on the Python side. That is expected.
