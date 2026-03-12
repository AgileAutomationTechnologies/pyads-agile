Connections
~~~~~~~~~~~

.. important::

    Before starting a connection to a target make sure you created proper routes on the
    client and the target like described in the :doc:`routing` chapter.

Connect to a remote device
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

   >>> import pyads
   >>> plc = pyads.Connection('127.0.0.1.1.1', pyads.PORT_TC3PLC1)
   >>> plc.open()
   >>> plc.close()

The connection will be closed automatically if the object runs out of scope, making
:py:meth:`.Connection.close` optional.

A context notation (using ``with:``) can be used to open a connection:

.. code:: python

   >>> import pyads
   >>> plc = pyads.Connection('127.0.0.1.1.1', pyads.PORT_TC3PLC1)
   >>> with plc:
   >>>     # ...

The context manager will make sure the connection is closed, either when
the ``with`` clause runs out, or an uncaught error is thrown.

RPC method calls
^^^^^^^^^^^^^^^^

TwinCAT requirement:
Each callable RPC method must be annotated with ``{attribute 'TcRpcEnable'}``
directly above the method declaration in PLC code.

Native object-style RPC calls
"""""""""""""""""""""""""""""

Use :py:meth:`.Connection.get_object` to obtain an RPC proxy for a function
block. Configure return types in ``method_return_types`` and parameter types in
``method_parameters``.

Example:

.. code:: python

   import pyads

   def main():
       plc = pyads.Connection("127.0.0.1.1.1", 851, "127.0.0.1")
       plc.open()
       try:
           rpc = plc.get_object(
               "GVL.fbTestRemoteMethodCall",
               method_return_types={
                   "m_iSimpleCall": pyads.PLCTYPE_INT,
                   "m_iSum": pyads.PLCTYPE_INT,
               },
               method_parameters={
                   "m_iSum": [pyads.PLCTYPE_INT, pyads.PLCTYPE_INT],
               },
           )

           print("Calling method m_iSimpleCall()")
           print("Result: {}".format(rpc.m_iSimpleCall()))

           print("Calling method m_iSum() with parameters 5 and 10")
           print("Result: {}".format(rpc.m_iSum(5, 10)))
       finally:
           plc.close()


   if __name__ == "__main__":
       main()

Typed RPC interfaces via ``@ads_path``
""""""""""""""""""""""""""""""""""""""

Instead of configuring method signatures manually, decorate a Python class with
:py:func:`pyads.ads_path` and annotate PLC argument/return types. Passing the
class to :py:meth:`.Connection.get_object` yields a proxy typed as that class,
which improves IntelliSense and reduces boilerplate.

.. code:: python

   import pyads

   @pyads.ads_path("GVL.fbTestRemoteMethodCall")
   class FB_TestRemoteMethodCall:
       def m_iSum(
           self,
           a: pyads.PLCTYPE_INT,
           b: pyads.PLCTYPE_INT,
       ) -> pyads.PLCTYPE_INT:
           ...

       def m_iSimpleCall(self) -> pyads.PLCTYPE_INT:
           ...

   plc = pyads.Connection("127.0.0.1.1.1", pyads.PORT_TC3PLC1)
   plc.open()
   try:
       rpc = plc.get_object(FB_TestRemoteMethodCall)
       print(rpc.m_iSum(5, 10))
   finally:
       plc.close()

Low-level RPC call by fully-qualified method name
"""""""""""""""""""""""""""""""""""""""""""""""""

For explicit handle-based calls, use :py:meth:`.Connection.call_rpc_method`.

.. code:: python

   >>> result = plc.call_rpc_method(
   ...     "GVL.fbTestRemoteMethodCall#m_iSimpleCall",
   ...     return_type=pyads.PLCTYPE_INT,
   ... )

Async connection and RPC
^^^^^^^^^^^^^^^^^^^^^^^^

Use :py:class:`pyads.AsyncConnection` when you need asyncio-native orchestration
with serialized ADS access (all ADS calls on a given connection are executed in
order on a dedicated worker thread).

.. code:: python

   import asyncio
   import pyads

   async def main() -> None:
       async with pyads.AsyncConnection("127.0.0.1.1.1", pyads.PORT_TC3PLC1) as plc:
           # submit_* returns asyncio.Future immediately
           fut = plc.submit_sum_read(["GVL.int_val", "GVL.bool_val"])
           values = await fut

           await plc.sum_write({"GVL.int_val": int(values["GVL.int_val"]) + 1})

   asyncio.run(main())

Async wrappers for core Connection methods
""""""""""""""""""""""""""""""""""""""""""

In addition to ``sum_read`` / ``sum_write`` and async RPC helpers,
:py:class:`pyads.AsyncConnection` mirrors the core synchronous
:py:class:`pyads.Connection` surface.

For most supported APIs you get:

* ``submit_*`` variant returning :py:class:`asyncio.Future`
* ``async`` method variant that awaits the same queued operation

Supported wrappers include:

* ``read``, ``write``, ``read_write``
* ``read_by_name``, ``write_by_name``
* ``read_structure_by_name``, ``write_structure_by_name``
* ``read_state``, ``read_device_info``, ``write_control``
* ``get_local_address``, ``get_handle``, ``release_handle``, ``set_timeout``
* ``sum_read`` / ``sum_write``

Example:

.. code:: python

   import asyncio
   import pyads

   async def main() -> None:
       async with pyads.AsyncConnection("127.0.0.1.1.1", pyads.PORT_TC3PLC1) as plc:
           # await-style wrappers
           value = await plc.read_by_name("GVL.int_val", pyads.PLCTYPE_INT)
           await plc.write_by_name("GVL.int_val", value + 1, pyads.PLCTYPE_INT)

           # submit-style wrappers
           state_future = plc.submit_read_state()
           state = await state_future
           print(state)

   asyncio.run(main())

Async typed RPC interfaces
"""""""""""""""""""""""""

Use :py:func:`pyads.ads_async_path` for async-typed interface classes with
:py:meth:`pyads.AsyncConnection.get_async_object`.
Method calls return :py:class:`asyncio.Future`.

.. code:: python

   import asyncio
   import pyads

   @pyads.ads_async_path("GVL.fbTestRemoteMethodCall")
   class FB_TestRemoteMethodCall:
       def m_iSum(
           self,
           a: pyads.PLCTYPE_INT,
           b: pyads.PLCTYPE_INT,
       ) -> asyncio.Future[pyads.PLCTYPE_INT]:
           ...

   async def main() -> None:
       async with pyads.AsyncConnection("127.0.0.1.1.1", pyads.PORT_TC3PLC1) as plc:
           rpc = plc.get_async_object(FB_TestRemoteMethodCall)
           future = rpc.m_iSum(5, 5)
           result = await future
           print(result)

   asyncio.run(main())

Stepchain async RPC via ``@ads_stepchain_path``
"""""""""""""""""""""""""""""""""""""""""""""""

For long-running PLC workflows (for example Schrittkette/state-machine style
methods), use :py:func:`pyads.ads_stepchain_path`. The async proxy returns a
:py:class:`pyads.StepChainOperation` (or :pydata:`pyads.StepChainOp` convenience
alias) that tracks two phases:

* ``accepted``: RPC method returned
* ``done``: stepchain completion detected from status symbols
* ``await op`` / ``await op.done``: snapshot dictionary of ADS status symbols
  (request id, busy/done/error/error code, etc.)
* ``read_status()``: read predefined framework status struct

Completion backends:

* ``completion="poll"`` (default): periodic ``sum_read`` polling
* ``completion="notify"``: ADS notifications trigger status checks in asyncio

The default status convention is:

* Status root: ``<ObjectPath>.stStepStatus``
* Request id argument/field: ``udiRequestId``
* Busy field: ``xBusy``
* Done field/value: ``xDone == True``
* Error field/value: ``xError == True``
* Error code field: ``diErrorCode``

Typical PLC status struct shape:

.. code:: text

   TYPE ST_StepStatus :
   STRUCT
       udiRequestId : UDINT;
       xBusy        : BOOL;
       xDone        : BOOL;
       xError       : BOOL;
       diErrorCode  : DINT;
       udiStep      : UDINT;      // optional debug/progress
       sStepName    : STRING(80); // optional debug/progress
   END_STRUCT
   END_TYPE

.. code:: python

   import asyncio
   import pyads

   @pyads.ads_stepchain_path(
       "GVL.fbTestRemoteStepChainMethodCall",
       completion="poll",  # or "notify"
   )
   class FB_TestRemoteStepChainMethodCall:
       def m_xStartStepChain(
           self,
           udiRequestId: pyads.PLCTYPE_UDINT,
       ) -> pyads.StepChainOp:
           ...

   async def main() -> None:
       async with pyads.AsyncConnection("127.0.0.1.1.1", pyads.PORT_TC3PLC1) as plc:
           rpc = plc.get_async_object(FB_TestRemoteStepChainMethodCall)
           status_root = rpc.status_symbol()
           op: pyads.StepChainOp = rpc.m_xStartStepChain()  # udiRequestId auto-generated when omitted

           accepted = await op.accepted
           if not accepted:
               raise RuntimeError("Stepchain start rejected by PLC.")

           completion_snapshot = await op  # same as: await op.done
           print(
               "Completed request",
               completion_snapshot[f"{status_root}.udiRequestId"],
           )
           status = await rpc.read_status()
           print(status["udiStep"], status["sStepName"])

   asyncio.run(main())

If your PLC status struct uses different field names or values, override them
in ``ads_stepchain_path(...)``:

.. code:: python

   @pyads.ads_stepchain_path(
       "GVL.fbTestRemoteStepChainMethodCall",
       status_field="stExecution",
       request_id_field="udiReqId",
       request_id_arg="udiReqId",
       busy_field="xBusy",
       done_field="eState",
       done_value=2,
       error_field="eState",
       error_value=3,
       error_code_field="diErrCode",
       completion="notify",
       poll_interval=0.1,
       timeout_s=30,
   )
   class FB_CustomStepChain:
       def m_xStart(self, udiReqId: pyads.PLCTYPE_UDINT) -> pyads.StepChainOp:
           ...

The framework status reader is always available on stepchain proxies:

* ``rpc.status_symbol()`` returns status root symbol
* ``rpc.get_status_structure_def()`` returns the predefined structure definition
* ``await rpc.read_status()`` reads and parses the struct in one call

Read and write by name
^^^^^^^^^^^^^^^^^^^^^^^

Values
""""""

Reading and writing values from/to variables on the target can be done with :py:meth:`.Connection.read_by_name` and
:py:meth:`.Connection.write_by_name`. Passing the `plc_datatype` is optional for both methods. If `plc_datatype`
is `None` the datatype will be queried from the target on the first call and cached inside the :py:class:`.Connection`
object. You can disable symbol-caching by setting the parameter `cache_symbol_info` to `False`.

.. warning::
  Querying the datatype only works for basic datatypes.
  For structs, lists and lists of structs you need provide proper definitions of the datatype and use
  :py:meth:`.Connection.read_structure_by_name` or :py:meth:`.Connection.read_list_by_name`.

Examples:

.. code:: python

  >>> import pyads
  >>> plc = pyads.Connection('127.0.0.1.1.1', pyads.PORT_TC3PLC1):
  >>> plc.open()
  >>>
  >>> plc.read_by_name('GVL.bool_value')  # datatype will be queried and cached
  True
  >>> plc.read_by_name('GVL.bool_value')  # cached datatype will be used
  True
  >>> plc.read_by_name('GVL.bool_value', cache_symbol_info=False)  # datatype will not be cached and queried on each call
  True
  >>> plc.read_by_name('GVL.int_value', pyads.PLCTYPE_INT)  # datatype is provided and will not be queried
  0
  >>> plc.write_by_name('GVL.int_value', 10)  # write to target
  >>> plc.read_by_name('GVL.int_value')
  10

 >>> plc.close()

If the name could not be found an Exception containing the error message
and ADS Error number is raised.

.. code:: python

   >>> plc.read_by_name('GVL.wrong_name', pyads.PLCTYPE_BOOL)
   ADSError: ADSError: symbol not found (1808)

For reading strings the maximum buffer length is 1024.

.. code:: python

   >>> plc.read_by_name('GVL.sample_string', pyads.PLCTYPE_STRING)
   'Hello World'
   >>> plc.write_by_name('GVL.sample_string', 'abc', pyads.PLCTYPE_STRING)
   >>> plc.read_by_name('GVL.sample_string', pyads.PLCTYPE_STRING)
   'abc'

Arrays
""""""

You can also read/write arrays. For this you simply need to multiply the
datatype by the number of elements in the array or structure you want to
read/write.

.. code:: python

   >>> plc.write_by_name('GVL.sample_array', [1, 2, 3], pyads.PLCTYPE_INT * 3)
   >>> plc.read_by_name('GVL.sample_array', pyads.PLCTYPE_INT * 3)
   [1, 2, 3]

.. code:: python

   >>> plc.write_by_name('GVL.sample_array[0]', 5, pyads.PLCTYPE_INT)
   >>> plc.read_by_name('GVL.sample_array[0]', pyads.PLCTYPE_INT)
   5


Structures of the same datatype
"""""""""""""""""""""""""""""""

TwinCAT declaration:

::

   TYPE sample_structure :
   STRUCT
       rVar : LREAL;
       rVar2 : LREAL;
       rVar3 : LREAL;
       rVar4 : ARRAY [1..3] OF LREAL;
   END_STRUCT
   END_TYPE

Python code:

.. code:: python

   >>> plc.write_by_name('GVL.sample_structure',
                         [11.1, 22.2, 33.3, 44.4, 55.5, 66.6],
                         pyads.PLCTYPE_LREAL * 6)
   >>> plc.read_by_name('GVL.sample_structure', pyads.PLCTYPE_LREAL * 6)
   [11.1, 22.2, 33.3, 44.4, 55.5, 66.6]

.. code:: python

   >>> plc.write_by_name('GVL.sample_structure.rVar2', 1234.5, pyads.PLCTYPE_LREAL)
   >>> plc.read_by_name('GVL.sample_structure.rVar2', pyads.PLCTYPE_LREAL)
   1234.5

Structures with multiple datatypes
""""""""""""""""""""""""""""""""""

**The structure in the PLC must be defined with \`{attribute ‘pack_mode’
:= ‘1’}.**

TwinCAT declaration:

::

   {attribute 'pack_mode' := '1'}
   TYPE sample_structure :
   STRUCT
       rVar : LREAL;
       rVar2 : REAL;
       iVar : INT;
       iVar2 : ARRAY [1..3] OF DINT;
       sVar : STRING;
   END_STRUCT
   END_TYPE

Python code:

First declare a tuple which defines the PLC structure. This should match
the order as declared in the PLC. Information is passed and returned
using the OrderedDict type.

.. code:: python

   >>> structure_def = (
   ...    ('rVar', pyads.PLCTYPE_LREAL, 1),
   ...    ('rVar2', pyads.PLCTYPE_REAL, 1),
   ...    ('iVar', pyads.PLCTYPE_INT, 1),
   ...    ('iVar2', pyads.PLCTYPE_DINT, 3),
   ...    ('sVar', pyads.PLCTYPE_STRING, 1)
   ... )

   >>> vars_to_write = OrderedDict([
   ...     ('rVar', 11.1),
   ...     ('rar2', 22.2),
   ...     ('iVar', 3),
   ...     ('iVar2', [4, 44, 444]),
   ...     ('sVar', 'abc')]
   ... )

   >>> plc.write_structure_by_name('global.sample_structure', vars_to_write, structure_def)
   >>> plc.read_structure_by_name('global.sample_structure', structure_def)
   OrderedDict([('rVar', 11.1), ('rVar2', 22.2), ('iVar', 3), ('iVar2', [4, 44, 444]), ('sVar', 'abc')])

Nested Structures
^^^^^^^^^^^^^^^^^

**The structures in the PLC must be defined with \`{attribute ‘pack_mode’
:= ‘1’}.**

TwinCAT declaration of the sub structure:

::

   {attribute 'pack_mode' := '1'}
   TYPE sub_sample_structure :
   STRUCT
       rVar : LREAL;
       rVar2 : REAL;
       iVar : INT;
       iVar2 : ARRAY [1..3] OF DINT;
       sVar : STRING;
   END_STRUCT
   END_TYPE

TwinCAT declaration of the nested structure:

::

   {attribute 'pack_mode' := '1'}
   TYPE sample_structure :
   STRUCT
      rVar : LREAL;
      structVar: ARRAY [0..1] OF sub_sample_structure; 
   END_STRUCT
   END_TYPE

First declare a tuple which defines the PLC structure. This should match
the order as declared in the PLC.

Declare the tuples either as

.. code:: python

   >>> substructure_def = (
   ...    ('rVar', pyads.PLCTYPE_LREAL, 1),
   ...    ('rVar2', pyads.PLCTYPE_REAL, 1),
   ...    ('iVar', pyads.PLCTYPE_INT, 1),
   ...    ('iVar2', pyads.PLCTYPE_DINT, 3),
   ...    ('sVar', pyads.PLCTYPE_STRING, 1)
   ... )

   >>> structure_def = (
   ...    ('rVar', pyads.PLCTYPE_LREAL, 1),
   ...    ('structVar', substructure_def, 2)
   ... )

or as

.. code:: python

   >>> structure_def = (
   ...    ('rVar', pyads.PLCTYPE_LREAL, 1),
   ...    ('structVar', (
   ...         ('rVar', pyads.PLCTYPE_LREAL, 1),
   ...         ('rVar2', pyads.PLCTYPE_REAL, 1),
   ...         ('iVar', pyads.PLCTYPE_INT, 1),
   ...         ('iVar2', pyads.PLCTYPE_DINT, 3),
   ...         ('sVar', pyads.PLCTYPE_STRING, 1)
   ...    ), 2)
   ... )

Information is passed and returned using the OrderedDict type.

.. code:: python
   
   >>> from collections import OrderedDict

   >>> vars_to_write = collections.OrderedDict([
   ...     ('rVar',0.1),
   ...     ('structVar', (
   ...         OrderedDict([
   ...             ('rVar', 11.1),
   ...             ('rVar2', 22.2),
   ...             ('iVar', 3),
   ...             ('iVar2', [4, 44, 444]),
   ...             ('sVar', 'abc')
   ...         ]),
   ...         OrderedDict([
   ...             ('rVar', 55.5),
   ...             ('rVar2', 66.6),
   ...             ('iVar', 7),
   ...             ('iVar2', [8, 88, 888]),
   ...             ('sVar', 'xyz')
   ...         ]))
   ...     )
   ... ])

   >>> plc.write_structure_by_name('GVL.sample_structure', vars_to_write, structure_def)
   >>> plc.read_structure_by_name('GVL.sample_structure', structure_def)
   ... OrderedDict({'rVar': 0.1, 'structVar': [OrderedDict({'rVar': 11.1, 'rVar2': 22.200000762939453, 'iVar': 3, 'iVar2':
   ... [4, 44, 444], 'sVar': 'abc'}), OrderedDict({'rVar': 55.5, 'rVar2': 66.5999984741211, 'iVar': 7, 'iVar2': [8, 88, 888],
   ... 'sVar': 'xyz'})]})

Read and write by handle
^^^^^^^^^^^^^^^^^^^^^^^^

When reading and writing by name, internally pyads is acquiring a handle
from the PLC, reading/writing the value using that handle, before
releasing the handle. A handle is just a unique identifier that the PLC
associates to an address meaning that should an address change, the ADS
client does not need to know the new address.

It is possible to manage the acquiring, tracking and releasing of
handles yourself, which is advantageous if you plan on reading/writing
the value frequently in your program, or wish to speed up the
reading/writing by up to three times; as by default when reading/writing
by name it makes 3 ADS calls (acquire, read/write, release), where as if
you track the handles manually it only makes a single ADS call.

Using the Connection class:

.. code:: python

   >>> var_handle = plc.get_handle('global.bool_value')
   >>> plc.write_by_name('', True, pyads.PLCTYPE_BOOL, handle=var_handle)
   >>> plc.read_by_name('', pyads.PLCTYPE_BOOL, handle=var_handle)
   True
   >>> plc.release_handle(var_handle)

**Be aware to release handles before closing the port to the PLC.**
Leaving handles open reduces the available bandwidth in the ADS router.

Read and write by address
^^^^^^^^^^^^^^^^^^^^^^^^^

Read and write *UDINT* variables by address.

.. code:: python

   >>> import pyads
   >>> plc = pyads.Connection('127.0.0.1.1.1', pyads.PORT_TC3PLC1)
   >>> plc.open()
   >>> # write 65536 to memory byte MDW0
   >>> plc.write(INDEXGROUP_MEMORYBYTE, 0, 65536, pyads.PLCTYPE_UDINT)
   >>> # write memory byte MDW0
   >>> plc.read(INDEXGROUP_MEMORYBYTE, 0, pyads.PLCTYPE_UDINT)
   65536
   >>> plc.close()

Toggle bitsize variables by address.

.. code:: python

   >>> # read memory bit MX100.0
   >>> data = plc.read(INDEXGROUP_MEMORYBIT, 100*8 + 0, pyads.PLCTYPE_BOOL)
   >>> # write inverted value to memory bit MX100.0
   >>> plc.write(INDEXGROUP_MEMORYBIT, 100*8 + 0, not data)

Read and write multiple variables with one command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Reading and writing of multiple values can be performed in a single
transaction. After the first operation, the symbol info is cached for
future use.

.. code:: python

   >>> import pyads
   >>> plc = pyads.Connection('127.0.0.1.1.1', pyads.PORT_TC3PLC1)
   >>> var_list = ['MAIN.b_Execute', 'MAIN.str_TestString', 'MAIN.r32_TestReal']
   >>> plc.read_list_by_name(var_list)
   {'MAIN.b_Execute': True, 'MAIN.str_TestString': 'Hello World', 'MAIN.r32_TestReal': 123.45}
   >>> write_dict = {'MAIN.b_Execute': False, 'MAIN.str_TestString': 'Goodbye World', 'MAIN.r32_TestReal': 54.321}
   >>> plc.write_list_by_name(write_dict)
   {'MAIN.b_Execute': 'no error', 'MAIN.str_TestString': 'no error', 'MAIN.r32_TestReal': 'no error'}

Device Notifications
^^^^^^^^^^^^^^^^^^^^

ADS supports device notifications, meaning you can pass a callback that
gets executed if a certain variable changes its state. However as the
callback gets called directly from the ADS DLL you need to extract the
information you need from the ctypes variables which are passed as
arguments to the callback function. A sample for adding a notification
for an integer variable can be seen here:

.. code:: python

   >>> import pyads
   >>> from ctypes import sizeof
   >>>
   >>>
   >>> plc = pyads.Connection('127.0.0.1.1.1', pyads.PORT_TC3PLC1)
   >>> plc.open()
   >>> tags = {"GVL.integer_value": pyads.PLCTYPE_INT}
   >>>
   >>> # define the callback which extracts the value of the variable
   >>> def mycallback(notification, data):
   >>>     data_type = tags[data]
   >>>     handle, timestamp, value = plc.parse_notification(notification, data_type)
   >>>     print(value)
   >>>
   >>> attr = pyads.NotificationAttrib(sizeof(pyads.PLCTYPE_INT))
   >>>
   >>> # add_device_notification returns a tuple of notification_handle and
   >>> # user_handle which we just store in handles
   >>> handles = plc.add_device_notification('GVL.integer_value', attr, mycallback)
   >>>
   >>> # To remove the device notification use the del_device_notification function.
   >>> plc.del_device_notification(handles)
   >>> plc.close()

This examples uses the default values for :py:class:`.NotificationAttrib`. The
default behaviour is that you get notified when the value of the
variable changes on the server. If you want to change this behaviour you
can set the :py:attr:`.NotificationAttrib.trans_mode` attribute to one of the
following values:

* :py:const:`.ADSTRANS_SERVERONCHA` *(default)*
    a notification will be sent everytime the value of the specified variable changes
* :py:const:`.ADSTRANS_SERVERCYCLE`
    a notification will be sent on a cyclic base, the interval is specified by the :py:attr:`cycle_time` property
* :py:const:`.ADSTRANS_NOTRANS`
    no notifications will be sent

For more information about the NotificationAttrib settings have a look
at `Beckhoffs specification of the AdsNotificationAttrib
struct <https://infosys.beckhoff.de/content/1033/tcadsdll2/html/tcadsdll_strucadsnotificationattrib.htm>`__.

Device Notification callback decorator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To make the handling of notifications more pythonic a notification
decorator has been introduced in version 2.2.4. This decorator takes
care of converting the ctype values transferred via ADS to python
datatypes.

.. code:: python

   >>> import pyads
   >>> plc = pyads.Connection('127.0.0.1.1.1', 48898)
   >>> plc.open()
   >>>
   >>> @plc.notification(pyads.PLCTYPE_INT)
   >>> def callback(handle, name, timestamp, value):
   >>>     print(
   >>>         '{1}: received new notitifiction for variable "{0}", value: {2}'
   >>>         .format(name, timestamp, value)
   >>>     )
   >>>
   >>> plc.add_device_notification('GVL.intvar', pyads.NotificationAttrib(2),
                                   callback)
   >>> # Write to the variable to trigger a notification
   >>> plc.write_by_name('GVL.intvar', 123, pyads.PLCTYPE_INT)

   2017-10-01 10:41:23.640000: received new notitifiction for variable "GVL.intvar", value: abc

Structures can be read in a this way by requesting bytes directly from
the PLC. Usage is similar to reading structures by name where you must
first declare a tuple defining the PLC structure.

.. code:: python

   >>> structure_def = (
   ...     ('rVar', pyads.PLCTYPE_LREAL, 1),
   ...     ('rVar2', pyads.PLCTYPE_REAL, 1),
   ...     ('iVar', pyads.PLCTYPE_INT, 1),
   ...     ('iVar2', pyads.PLCTYPE_DINT, 3),
   ...     ('sVar', pyads.PLCTYPE_STRING, 1))
   >>>
   >>> size_of_struct = pyads.size_of_structure(structure_def)
   >>>
   >>> @plc.notification(ctypes.c_ubyte * size_of_struct)
   >>> def callback(handle, name, timestamp, value):
   ...     values = pyads.dict_from_bytes(value, structure_def)
   ...     print(values)
   >>>
   >>> attr = pyads.NotificationAttrib(size_of_struct)
   >>> plc.add_device_notification('global.sample_structure', attr, callback)

   OrderedDict([('rVar', 11.1), ('rVar2', 22.2), ('iVar', 3), ('iVar2', [4, 44, 444]), ('sVar', 'abc')])

The notification callback works for all basic plc datatypes but not for
arrays. Since version 3.0.5 the ``ctypes.Structure`` datatype is
supported. Find an example below:

.. code:: python

   >>> class TowerEvent(Structure):
   >>>     _fields_ = [
   >>>         ("Category", c_char * 21),
   >>>         ("Name", c_char * 81),
   >>>         ("Message", c_char * 81)
   >>>     ]
   >>>
   >>> @plc.notification(TowerEvent)
   >>> def callback(handle, name, timestamp, value):
   >>>     print(f'Received new event notification for {name}.Message = {value.Message}')
