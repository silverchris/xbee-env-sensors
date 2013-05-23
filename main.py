#! /usr/bin/python

from xbee import ZigBee
import time
import serial
from datetime import datetime, timedelta
import binascii
import os
import sys
import importlib
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor
import logging
import copy


import munin
import server

PORT = '/dev/ttyUSB0'

#PORT = '/dev/pts/3'
BAUD_RATE = 9600

Module_Path = os.path.join(os.path.dirname(os.path.realpath(__file__)),"Modules")

logging.basicConfig(filename='Sensor.log',level=logging.DEBUG,
        format='%(asctime)s [%(name)s].%(levelname)s: %(message)s')

logger = logging.getLogger('Main')

class SensorFactory:
        factories = {}
        def addFactory(id, sensorFactory):
                SensorFactory.factories[id] = sensorFactory
        addFactory = staticmethod(addFactory)
        # A Template Method:
        def createSensor(id):
                return SensorFactory.factories[id]
        createSensor = staticmethod(createSensor)

class Dispatch(object):
        def __init__(self, ser=None, xbee=None, unhandled_callback=None):
                self.xbee = None
                if xbee:
                        self.xbee = xbee
                elif ser:
                        self.xbee = ZigBee(ser,escaped=True)
                self.unhandled = unhandled_callback
                self.handlers = []
                self.names = set()
        
        def register(self, name, callback, filter):
                """
                register: string, function: string, data -> None, function: data -> boolean -> None
                
                Register will save the given name, callback, and filter function
                for use when a packet arrives. When one arrives, the filter
                function will be called to determine whether to call its associated
                callback function. If the filter method returns true, the callback
                method will be called with its associated name string and the packet
                which triggered the call.
                """
                if name in self.names:
                        raise ValueError("A callback has already been registered with the name '%s'" % name)
                
                self.handlers.append({'name':name,'callback':callback,'filter':filter})
                self.names.add(name)
                
        def unregister(self,name):
                for handler in self.handlers:
                        if handler['name'] == name:
                                self.handlers.remove(handler)
                self.names.remove(name)
            
        def run(self, oneshot=False):
                """
                run: boolean -> None
                
                run will read and dispatch any packet which arrives from the 
                XBee device
                """
                if not self.xbee:
                        raise ValueError("Either a serial port or an XBee must be provided to __init__ to execute run()")
                
                while True:
                        self.dispatch(self.xbee.wait_read_frame())
                        
                        if oneshot:
                                break

        def dispatch(self, packet):
                """
                dispatch: XBee data dict -> None
                
                When called, dispatch checks the given packet against each 
                registered callback method and calls each callback whose filter 
                function returns true.
                """
                print "Frame Received"
                #print packet
                handled = False
                for handler in self.handlers:
                        try:
                                if handler['filter'](packet):
                                        # Call the handler method with its associated
                                        # name and the packet which passed its filter check
                                        handler['callback'](handler['name'], packet)
                                        handled = True
                        except KeyError:
                                pass
                if handled == False:
                        self.unhandled(packet)

# Open serial port
ser = serial.Serial(PORT, BAUD_RATE)

def load_modules(mod_path):
        
        if os.path.isdir(mod_path):
                sys.path.append(mod_path)

        modules = {}

        for f in os.listdir(os.path.abspath(mod_path)):
                module_name, ext = os.path.splitext(f) # Handles no-extension files, etc.
                if ext == '.py': # Important, ignore .pyc/other files.
                        logger.info('imported module: %s'%(module_name))
                        module = importlib.import_module(module_name,package=module_name)
                        modules[module_name] = module.Sensor
                        SensorFactory.addFactory(module_name, modules[module_name])

sensor_id_timeout = {}
def unhandled(packet):
        if 'source_addr_long' in packet:
                tmp_packet = copy.copy(packet)
                address_ascii = binascii.hexlify(packet['source_addr_long'])
                del tmp_packet['source_addr_long']
                logger.debug("%s: Unhandled packet:%s"%(address_ascii,repr(tmp_packet)))
                try:
                        if packet.get('command','') != 'NI':
                                id_time = sensor_id_timeout.get(address_ascii, datetime(1970,1,1))
                                if (datetime.now()-id_time).total_seconds() > 60:
                                        zigbee.send('remote_at',command="NI", dest_addr_long=packet['source_addr_long'], options='\x40', frame_id="1")
                                        logger.info("%s: Node ID query sent"%binascii.hexlify(packet['source_addr_long']))
                                        sensor_id_timeout[address_ascii] = datetime.now()
                                else:
                                        logger.info("%s: Node ID query already sent, lets wait"%binascii.hexlify(packet['source_addr_long']))
                except KeyError:
                        pass

        else:
                logger.debug("Unhandled Packet: %s"%repr(packet))
        
sensors = {}
        
def NI_handler(name,packet):
        address_ascii = binascii.hexlify(packet['source_addr_long'])
        if address_ascii not in sensors:
                logger.info("%s: Discovered type %s"%(address_ascii,repr(packet['parameter'])))
                sensorclass = SensorFactory.createSensor(packet['parameter'])
                try:
                        sensors[address_ascii] = sensorclass(packet['source_addr_long'],dispatch)
                except ValueError:
                        logger.warning("Sensor Class %s Not Registered"%packet['parameter'])

# When a Dispatch is created with a serial port, it will automatically
# create an XBee object on your behalf for accessing the device.
# If you wish, you may explicitly provide your own XBee:
#
#  xbee = XBee(ser)
#  dispatch = Dispatch(xbee=xbee)
#
# Functionally, these are the same.
dispatch = Dispatch(ser=ser,unhandled_callback=unhandled)

# Register the packet handlers with the dispatch:
#  The string name allows one to distinguish between mutiple registrations
#   for a single callback function
#  The second argument is the function to call
#  The third argument is a function which determines whether to call its
#   associated callback when a packet arrives. It should return a boolean.
dispatch.register("NI", NI_handler, lambda packet: packet['command']=='NI')

# Create API object, which spawns a new thread
# Point the asyncronous callback at Dispatch.dispatch()
#  This method will dispatch a single XBee data packet when called
zigbee = ZigBee(ser, callback=dispatch.dispatch, escaped=True)

#zigbee.send('remote_at',options='\x40',frame_id="A",command="DD",dest_addr_long='\x00\x13\xa2\x00@\xaa\x16\xe4')
#zigbee.send('at',options='\x40',frame="1",command="NC")
load_modules(Module_Path)

reactor.listenTCP(8007, munin.MuninFactory(sensors))
reactor.listenTCP(8008, server.CommandsFactory(sensors,zigbee,dispatch))
reactor.run()

# halt() must be called before closing the serial
# port in order to ensure proper thread shutdown
zigbee.halt()
ser.close()
