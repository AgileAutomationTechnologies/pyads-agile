(*
TwinCAT ST symbol template for pyads-agile real integration tests.

Create a GVL (for example: GVL) and paste these declarations.
Then point tests/integration_real/real_runtime.toml symbols to these names.
*)

{attribute 'qualified_only'}
VAR_GLOBAL
    TestInt : INT := 10;
    TestString : STRING(80) := 'hello';
    TestStruct : ST_PyadsTest := (i := 1, s := 'foo');
    TestStructArray : ARRAY[0..1] OF ST_PyadsTest := [
        (i := 11, s := 'arr0'),
        (i := 22, s := 'arr1')
    ];
END_VAR

TYPE ST_PyadsTest :
STRUCT
    i : INT;
    _s : STRING(80);
END_STRUCT
END_TYPE
