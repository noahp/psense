#!/usr/bin/python
'''
    MCP2221A + PAC1720 interface.
'''
import usb.core

class Mcp2221aI2c(object):
    ''' I2C interface to MCP2221A '''

    CMD_MCP2221_STATUS = 0x10
    SUBCMD_STATUS_SPEED = 0x20
    CMD_MCP2221_RDDATA7 = 0x91
    CMD_MCP2221_GET_RDDATA = 0x40
    CMD_MCP2221_WRDATA7 = 0x90

    def __init__(self, bus_speed=400000, address=0x18):
        self.device = None
        self.reattach = []
        self.bus_speed = bus_speed
        self.address = address

    def hidwrite(self, data):
        ''' Write raw HID data to EP3 '''
        return self.device.write(0x03, data+[0]*(64-len(data)))

    def hidread(self, timeout=100):
        ''' Read raw HID data from EP3 '''
        return self.device.read(0x83, 64, timeout)

    def write(self, data, address=None):
        ''' Execute I2C write, optional address override '''
        if not address:
            address = self.address

        outpacket = [
            Mcp2221aI2c.CMD_MCP2221_WRDATA7,
            len(data) & 0xFF,
            0,
            (address << 1) & 0xFF,
        ] + data
        print ['%02X'%c for c in outpacket]
        self.hidwrite(outpacket)
        print self.hidread()

        # status stage
        outpacket = [
            Mcp2221aI2c.CMD_MCP2221_STATUS
        ] + [0] * 7
        self.hidwrite(outpacket)
        print self.hidread()

    def read(self, length, address=None):
        ''' Execute I2C read, optional address override '''
        if not address:
            address = self.address

        outpacket = [
            Mcp2221aI2c.CMD_MCP2221_RDDATA7,
            length,
            0,
            (address << 1) & 0xFF | 1, # set read bit
        ]
        self.hidwrite(outpacket)
        print self.hidread()

        outpacket = [
            Mcp2221aI2c.CMD_MCP2221_GET_RDDATA,
        ]
        self.hidwrite(outpacket)
        readdata = self.hidread()
        return readdata

    def connect(self):
        ''' Try to connect to the device '''
        dev = usb.core.find(idVendor=0x04d8, idProduct=0x00dd)

        if dev:
            print 'Found device'
            for i in range(3):
                if dev.is_kernel_driver_active(i):
                    self.reattach.append(i)
                    dev.detach_kernel_driver(i)
            dev.set_configuration()
            self.device = dev
            outpacket = [
                Mcp2221aI2c.CMD_MCP2221_STATUS,
                0,
                0,
                Mcp2221aI2c.SUBCMD_STATUS_SPEED,
                12000000/self.bus_speed,
                0,
                0,
                0
            ]
            self.hidwrite(outpacket)
            try:
                print self.hidread()
            except usb.core.USBError:
                pass


if __name__ == '__main__':
    I2C = Mcp2221aI2c()
    I2C.connect()

    # read PAC1720 Product ID register
    I2C.write([0xFD])
    print I2C.read(1)
