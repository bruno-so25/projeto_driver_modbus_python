from pymodbus.server.sync import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification

store = ModbusSequentialDataBlock(0, [0]*10)
context = ModbusServerContext(slaves=ModbusSlaveContext(hr=store), single=True)

identity = ModbusDeviceIdentification()
identity.VendorName = "Test"
identity.ProductName = "SyncServer"
identity.MajorMinorRevision = "1.0"

print("Iniciando servidor Modbus TCP...")
StartTcpServer(context=context, identity=identity, address=("0.0.0.0", 5020))
