(* 
TwinCAT reference source for pyads-agile examples and real integration tests.

Naming conventions:
- st for structs
- fb for function blocks
- x for BOOL
- i for INT
- udi for UDINT
- s for STRING
- m_ for methods
- m_x for methods returning BOOL
*)

TYPE ST_PyAdsTest :
STRUCT
    i : INT;
    _s : STRING;
END_STRUCT
END_TYPE

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

FUNCTION_BLOCK FB_TestRemoteMethodCall
VAR
END_VAR

{attribute 'TcRpcEnable'}
METHOD m_iSimpleCall : INT
m_iSimpleCall := 10;

{attribute 'TcRpcEnable'}
METHOD m_iSum : INT
VAR_INPUT
    iA : INT;
    iB : INT;
END_VAR
m_iSum := iA + iB;

FUNCTION_BLOCK FB_TestStepChain
VAR
    stStepStatus : ST_StepStatus;

    _xBusy           : BOOL;
    _udiInternalStep : UDINT;
    _xSimulateError  : BOOL;

    _tonPrepare  : TON;
    _tonLoad     : TON;
    _tonProcess  : TON;
    _tonFinalize : TON;
END_VAR

_tonPrepare(IN := (_udiInternalStep = 10), PT := T#2S);
_tonLoad(IN := (_udiInternalStep = 20), PT := T#2S);
_tonProcess(IN := (_udiInternalStep = 30), PT := T#3S);
_tonFinalize(IN := (_udiInternalStep = 40), PT := T#1S);

stStepStatus.udiStep := _udiInternalStep;
stStepStatus.xBusy := _xBusy;

IF NOT _xBusy THEN
    RETURN;
END_IF

CASE _udiInternalStep OF
    10:
        stStepStatus.sStepName := 'Prepare';
        IF _tonPrepare.Q THEN
            _udiInternalStep := 20;
        END_IF

    20:
        stStepStatus.sStepName := 'Load';
        IF _tonLoad.Q THEN
            _udiInternalStep := 30;
        END_IF

    30:
        stStepStatus.sStepName := 'Process';
        IF _xSimulateError THEN
            _xBusy := FALSE;
            _udiInternalStep := 901;
            stStepStatus.xBusy := FALSE;
            stStepStatus.xDone := FALSE;
            stStepStatus.xError := TRUE;
            stStepStatus.diErrorCode := 9001;
            stStepStatus.udiStep := _udiInternalStep;
            stStepStatus.sStepName := 'Error';
            RETURN;
        END_IF

        IF _tonProcess.Q THEN
            _udiInternalStep := 40;
        END_IF

    40:
        stStepStatus.sStepName := 'Finalize';
        IF _tonFinalize.Q THEN
            _xBusy := FALSE;
            _udiInternalStep := 100;
            stStepStatus.xBusy := FALSE;
            stStepStatus.xDone := TRUE;
            stStepStatus.xError := FALSE;
            stStepStatus.diErrorCode := 0;
            stStepStatus.udiStep := _udiInternalStep;
            stStepStatus.sStepName := 'Done';
            RETURN;
        END_IF
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
_xSimulateError := GVL.xStepChainForceError;

stStepStatus.udiRequestId := udiRequestId;
stStepStatus.xBusy := TRUE;
stStepStatus.xDone := FALSE;
stStepStatus.xError := FALSE;
stStepStatus.diErrorCode := 0;
stStepStatus.udiStep := _udiInternalStep;
stStepStatus.sStepName := 'Prepare';

m_xStartStepChain := TRUE;

{attribute 'TcRpcEnable'}
METHOD m_xAbortStepChain : BOOL
IF NOT _xBusy THEN
    m_xAbortStepChain := FALSE;
    RETURN;
END_IF

_xBusy := FALSE;
_udiInternalStep := 900;

stStepStatus.xBusy := FALSE;
stStepStatus.xDone := FALSE;
stStepStatus.xError := TRUE;
stStepStatus.diErrorCode := -2;
stStepStatus.udiStep := _udiInternalStep;
stStepStatus.sStepName := 'Aborted';

m_xAbortStepChain := TRUE;

{attribute 'qualified_only'}
VAR_GLOBAL
    iTestInt : INT := 10;
    sTestString : STRING := 'hello';
    stTestStruct : ST_PyAdsTest := (i := 1, _s := 'foo');
    astTestStructArray : ARRAY[0..1] OF ST_PyAdsTest := [
        (i := 11, _s := 'arr0'),
        (i := 22, _s := 'arr1')
    ];
    fbTestRemoteMethodCall : FB_TestRemoteMethodCall;
    xStepChainForceError : BOOL;
    fbStepChain : FB_TestStepChain;
END_VAR

PROGRAM MAIN
GVL.fbStepChain();
