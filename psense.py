#!/usr/bin/python
'''
    MCP2221A + PAC1720 interface.
'''
import sys
if sys.platform == 'win32':
    import pywinusb.hid as hid
else:
    import usb.core

class Mcp2221aI2c(object):
    ''' I2C interface to MCP2221A '''

    CMD_MCP2221_STATUS = 0x10
    SUBCMD_STATUS_SPEED = 0x20
    CMD_MCP2221_RDDATA7 = 0x91
    CMD_MCP2221_GET_RDDATA = 0x40
    CMD_MCP2221_WRDATA7 = 0x90

    def __init__(self, bus_speed=400000, address=0x18):
        '''Optionally can be overridden by child class'''
        self.device = None
        self.reattach = []
        self.bus_speed = bus_speed
        self.address = address

    def hidwrite(self, data):
        '''Write raw HID data to EP3. Stub that must be implemented in child class.'''
        raise NotImplementedError

    def hidread(self, timeout=100):
        '''Read raw HID data from EP3'''
        raise NotImplementedError

    def write(self, data, address=None):
        '''Execute I2C write, optional address override'''
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
        '''Execute I2C read, optional address override'''
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
        '''Try to connect to the device. Stub that must be implemented in child class.'''
        raise NotImplementedError

class Mcp2221aI2cWin32(Mcp2221aI2c):
    '''Windows HID interface to MCP2221A'''

    def hidread(self, timeout=100):
        '''Raw HID read of input report id=0x00 on EP3, 64 bytes'''
        return self.device.input_report.get()

    def hidwrite(self, data):
        '''Raw HID write to output report id=0x00 on EP3, up to 64 bytes'''
        self.device.output_report.set_raw_data([0x00] + data + [0] * (64-len(data)))
        self.device.output_report.send()

    def connect(self):
        ''' Try to connect to the device '''
        devices = hid.HidDeviceFilter(vendor_id=0x04d8, product_id=0x00dd).get_devices()
        if len(devices):
            self.device = devices[0]
            self.device.open()

            # get the input/output reports
            self.device.input_report = self.device.find_input_reports()[0]
            self.device.output_report = self.device.find_output_reports()[0]

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

            return True
        else:
            return False


class Mcp2221aI2cUnix(Mcp2221aI2c):
    '''Linux HID interface to MCP2221A'''

    def hidread(self, timeout=100):
        '''Raw HID read of EP3, 64 bytes'''
        return self.device.read(0x83, 64, timeout)

    def hidwrite(self, data):
        '''Raw HID write to EP3, up to 64 bytes'''
        return self.device.write(0x03, data+[0]*(64-len(data)))

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
            return True

        return False

if __name__ == '__main__':
    if sys.platform == 'win32':
        I2C = Mcp2221aI2cWin32()
    else: # unix, probably
        I2C = Mcp2221aI2cUnix()

    if not I2C.connect():
        print 'Error connecting!'
        sys.exit(-1)

    # read PAC1720 Product ID register
    I2C.write([0xFD])
    print I2C.read(1)
