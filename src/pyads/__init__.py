"""The pyads package.

:author: Stefan Lehmann <stlm@posteo.de>
:maintainer: Filippo Boido <filippo.boido@agileautomation.eu> (Agile Automation Technologies GmbH)
:license: MIT, see license file or https://opensource.org/licenses/MIT
:created on: 2018-06-11 18:15:53

"""
from typing import Any, TypeAlias

from .structs import AmsAddr, NotificationAttrib

from .ads import (
    open_port,
    close_port,
    get_local_address,
    add_route,
    add_route_to_plc,
    delete_route,
    set_local_address,
    set_timeout,
    size_of_structure,
    dict_from_bytes,
    bytes_from_dict,
    StructureDef,
)

from .connection import Connection
from .async_connection import AsyncConnection, AsyncRpcObject, StepChainOperation
from .rpc_interface import StepChainRpcInterface, ads_path, ads_async_path, stepchain_start

from .pyads_ex import ADSError

from .constants import (
    PLCTYPE_BOOL,
    PLCTYPE_BYTE,
    PLCTYPE_DATE,
    PLCTYPE_DINT,
    PLCTYPE_DT,
    PLCTYPE_DWORD,
    PLCTYPE_INT,
    PLCTYPE_LINT,
    PLCTYPE_LREAL,
    PLCTYPE_REAL,
    PLCTYPE_SINT,
    PLCTYPE_STRING,
    PLCTYPE_WSTRING,
    PLCTYPE_TIME,
    PLCTYPE_TOD,
    PLCTYPE_ULINT,
    PLCTYPE_UDINT,
    PLCTYPE_UINT,
    PLCTYPE_USINT,
    PLCTYPE_WORD,
    PLCTYPE_ARR_DINT,
    PLCTYPE_ARR_INT,
    PLCTYPE_ARR_LREAL,
    PLCTYPE_ARR_REAL,
    PLCTYPE_ARR_SHORT,
    PLC_DEFAULT_STRING_SIZE,
    DATATYPE_MAP,
)

from .constants import (
    PORT_EVENTLOGGER,
    PORT_IO,
    PORT_LOGGER,
    PORT_NC,
    PORT_NOCKE,
    PORT_SCOPE,
    PORT_SPECIALTASK1,
    PORT_SPECIALTASK2,
    PORT_SPS1,
    PORT_SPS2,
    PORT_SPS3,
    PORT_SPS4,
    PORT_SYSTEMSERVICE,
    PORT_CAM,
    PORT_TC2PLC1,
    PORT_TC2PLC2,
    PORT_TC2PLC3,
    PORT_TC2PLC4,
    PORT_TC3PLC1,
)

from .constants import (
    INDEXGROUP_MEMORYBYTE,
    INDEXGROUP_MEMORYBIT,
    INDEXGROUP_MEMORYSIZE,
    INDEXGROUP_RETAIN,
    INDEXGROUP_RETAINSIZE,
    INDEXGROUP_DATA,
    INDEXGROUP_DATASIZE,
)

from .constants import (
    ADSSTATE_INVALID,
    ADSSTATE_IDLE,
    ADSSTATE_RESET,
    ADSSTATE_INIT,
    ADSSTATE_START,
    ADSSTATE_RUN,
    ADSSTATE_STOP,
    ADSSTATE_SAVECFG,
    ADSSTATE_LOADCFG,
    ADSSTATE_POWERFAILURE,
    ADSSTATE_POWERGOOD,
    ADSSTATE_ERROR,
    ADSSTATE_SHUTDOWN,
    ADSSTATE_SUSPEND,
    ADSSTATE_RESUME,
    ADSSTATE_CONFIG,
    ADSSTATE_RECONFIG,
)

from .constants import (
    ADSTRANS_NOTRANS,
    ADSTRANS_CLIENTCYCLE,
    ADSTRANS_CLIENT1REQ,
    ADSTRANS_SERVERCYCLE,
    ADSTRANS_SERVERONCHA,
)

from .symbol import AdsSymbol

# Convenience alias so users can write ``pyads.StepChainOp`` instead of
# ``pyads.StepChainOperation[Any]`` when the accepted-phase transport type
# is not specialized.
StepChainOp: TypeAlias = StepChainOperation[Any]

__version__ = '0.3.3'
