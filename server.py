#!/usr/bin/python
# -*- coding: utf-8 -*-
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import LineReceiver
import logging
import re
import binascii
import struct

at_commands = [  # Xbee commands
    'DH','DL','MY','MP','NC','SH','SL','NI','SE','DE','CI','NP','DD','CH','ID',
    'OP','NH','BH','OI','NT','NO','SC','SD','ZS','NJ','JV','NW','JN','AR','EE',
    'EO','NK','KY','PL','PM','DB','PP','AP','AO','BD','NB','SB','RO','D7','D6',
    'IR','IC','P0','P1','P2','P3','D0','D1','D2','D3','D4','D5','D8','LT','PR',
    'RP','%V','V+','TP','VR','HV','AI','CT','CN','GT','CC','SM','SN','SP','ST',
    'SO','WH','SI','PO','AC','WR','RE','FR','NR','CB','ND','DN','IS','1S'
    ]

string_commands = ['ND', 'DN', 'NI']  # XBee commands that can have a string for the parameter


def gen_lambda(mode,parameters,frame):
    id = '{0}_response'.format(mode)
    command = parameters['command']
    if 'dest_addr' in parameters:
        addr = parameters['dest_addr'] 
        func = (lambda packet: packet['source_addr']==addr and
                packet['id']== id and packet['command']==command and
                packet['frame_id']==frame)
    elif 'dest_addr_long' in parameters:
        addr = parameters['dest_addr_long'] 
        func = (lambda packet: packet['source_addr_long']==addr and
                packet['id']== id and packet['command']==command and
                packet['frame_id']==frame)
    return func

class frame_id(object):

    def __init__(self):
        self.valid_ids = range(1, 256)

    def get_id(self):
        return struct.pack('>B', self.valid_ids.pop(0))

    def return_id(self,id):
        self.valid_ids.append(struct.unpack('>B', id)[0])
        self.valid_ids.sort()


class Commands(LineReceiver):

    delimiter = '\n'

    def __init__(self,sensors,zigbee,dispatch,frames,):
        self.sensors = sensors
        self.zigbee = zigbee
        self.dispatch = dispatch
        self.frames = frames

    def connectionMade(self):
        logging.debug('Commands: Connection from {0}'.format(
                self.transport.getPeer()))

    def callback(self,name,packet):
        print "called back"
        self.frames.return_id(packet['frame_id'])
        print "lol"
        self.dispatch.unregister(name)
        print " extra lol"
        self.sendLine(packet.__str__())

    def lineReceived(self,line):
        logging.debug('Commands: {0}: Received Command: {1}'.format(
                self.transport.getPeer().host,line))
        data = line.split(' ')
        if line == 'quit':
            self.transport.loseConnection()
        else:
            if data[0] in self.zigbee.api_commands:
                mode = data[0]
                command_re = re.compile('.((?P<dest_addr_long>[0-9A-Fa-f]{16});'
                        '|(?P<dest_addr>[0-9A-Fa-f]{2});'
                        ')(?P<command>[A-Z0-9]{2});'
                        '((?P<parameter>[a-zA-Z0-9 ]+);'
                        '.*|.*)',re.DOTALL)
                try:
                    command = command_re.search(line).groupdict()
                    hex_re = re.compile('^[0-9A-Fa-f]+$')
                    if command['command'] in at_commands:
                        for (k, v) in command.items():
                            if v == None:
                                del command[k]
                            elif hex_re.match(v) and any(v in item
                                    for item in string_commands) != True:
                                command[k] = binascii.unhexlify(v)
                                if 'dest_addr' in k:
                                    ascii_addr = v
                        print command
                        frame = self.frames.get_id()
                        self.zigbee.send(mode, options='\x42',
                                frame_id=frame, **command)
                        self.dispatch.register('{addr}_{frame}'.format(
                            frame=frame,addr=ascii_addr),
                                self.callback, gen_lambda(mode,command,frame))
                        print self.dispatch.handlers
                        self.sendLine('Command Sent')
                    else:
                        self.sendLine('Invalid AT Command')
                #except KeyError:
                except AttributeError:
                    self.sendLine('Invalid format')
            else:
                self.sendLine('Unknown Command')


class CommandsFactory(Factory):

    def __init__(self,sensors,zigbee,dispatch,):
        self.sensors = sensors
        self.zigbee = zigbee
        self.dispatch = dispatch
        self.frames = frame_id()

    def buildProtocol(self,addr):
        return Commands(self.sensors,self.zigbee,self.dispatch,self.frames)


