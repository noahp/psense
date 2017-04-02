#!/usr/bin/python
'''
    MCP2221A + PAC1720 interface.

    Slightly better performance than the Microchip tools:
     ~ 50ms for a single byte register read using Microchip tools
     ~ 15ms using this tool (on windows 10 with pywinusb)
'''
import sys
import time
if sys.platform == 'win32':
    try:
        import pywinusb.hid as hid
    except ImportError:
        print 'Error, please `pip install pywinusb`'
        sys.exit(-1)
else:
    try:
        import usb.core
    except:
        print 'Error, please `pip install pyusb`'
        sys.exit(-1)

class Mcp2221aI2c(object):
    ''' I2C interface to MCP2221A '''

    CMD_MCP2221_STATUS = 0x10
    SUBCMD_STATUS_SPEED = 0x20
    CMD_MCP2221_RDDATA7 = 0x91
    CMD_MCP2221_GET_RDDATA = 0x40
    CMD_MCP2221_WRDATA7 = 0x90

    def __init__(self, bus_speed=100000, address=0x18):
        '''Optionally can be overridden by child class'''
        self.device = None
        self.reattach = []
        self.bus_speed = bus_speed
        self.address = address
        self.readdatatime = 0
        self.readdata = []

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
        # print 'write: ' + str(['%02X'%c for c in outpacket])
        self.hidwrite(outpacket)
        self.hidread()

        # status stage
        outpacket = [
            Mcp2221aI2c.CMD_MCP2221_STATUS
        ] + [0] * 7
        self.hidwrite(outpacket)
        self.hidread()

    def read(self, length, address=None):
        '''Execute I2C read, optional address override'''
        if not address:
            address = self.address

        outpacket = [
            Mcp2221aI2c.CMD_MCP2221_RDDATA7,
            length, # length LSB
            0, # length MSB, unsupported
            (address << 1) & 0xFF, # don't set read bit
        ]
        self.hidwrite(outpacket)
        self.hidread()

        outpacket = [
            Mcp2221aI2c.CMD_MCP2221_GET_RDDATA,
        ]
        self.hidwrite(outpacket)
        readdata = self.hidread()
        if readdata[4] > 0:
            readdata = readdata[5:5 + readdata[4]]
        else:
            readdata = []
        return readdata

    def connect(self):
        '''Try to connect to the device. Stub that must be implemented in child class.'''
        raise NotImplementedError

class Mcp2221aI2cWin32(Mcp2221aI2c):
    '''Windows HID interface to MCP2221A'''

    def hidread(self, timeout=100):
        '''Raw HID read of input report id=0x00 on EP3, 64 bytes'''
        startime = time.time()
        endtime = startime + timeout/1000.0
        data = []
        while (not len(data)) and (time.time() < endtime):
            if self.readdatatime > startime:
                data = self.readdata
            time.sleep(0.001)
        return data

    def __readhandler(self, data):
        self.readdata = data
        self.readdatatime = time.time()
        # print 'read: ' + str(data)

    def hidwrite(self, data):
        '''Raw HID write to output report id=0x00 on EP3, up to 64 bytes'''
        self.device.output_report.send([0x00] + data + [0] * (64-len(data)))

    def connect(self):
        ''' Try to connect to the device '''
        devices = hid.HidDeviceFilter(vendor_id=0x04d8, product_id=0x00dd).get_devices()
        if len(devices):
            self.device = devices[0]
            self.device.open()

            # get the input/output reports
            self.device.input_report = self.device.find_input_reports()[0]
            self.device.output_report = self.device.find_output_reports()[0]

            # attach read handler
            self.device.set_raw_data_handler(self.__readhandler)

            outpacket = [
                Mcp2221aI2c.CMD_MCP2221_STATUS,
                0,
                0,
                Mcp2221aI2c.SUBCMD_STATUS_SPEED,
                12000000/self.bus_speed - 3,
                0,
                0,
                0
            ]
            self.hidwrite(outpacket)
            self.hidread()

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
                12000000/self.bus_speed - 3,
                0,
                0,
                0
            ]
            self.hidwrite(outpacket)
            try:
                self.hidread()
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

    print 'Reading PAC1720 Product ID register...'
    I2C.write([0xFD]) # write the register address
    data = I2C.read(1) # read 1 byte
    print 'Product ID (expects 0x57): ' + ''.join('%c'%c for c in data).encode('hex')
