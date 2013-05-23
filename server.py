#!/usr/bin/python
# -*- coding: utf-8 -*-
from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import LineReceiver
import logging
import re
import binascii
import struct
import textwrap

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

    #delimiter = '\n'

    def __init__(self,sensors,zigbee,dispatch,frames,):
        self.sensors = sensors
        self.zigbee = zigbee
        self.dispatch = dispatch
        self.frames = frames
        self.logger = logging

    def connectionMade(self):
        self.logger = logging.getLogger('{0} Server'.format(
                self.transport.getPeer().host))
        self.logger.info('Connected')
        self.sendLine("#")

    def callback(self,name,packet):
        print "called back"
        self.frames.return_id(packet['frame_id'])
        print "lol"
        self.dispatch.unregister(name)
        print " extra lol"
        self.sendLine(packet.__str__())

    def lineReceived(self,line):
        # Ignore blank lines
        if not line: return
        line.__repr__()
        # Parse the command
        commandParts = line.split()
        command = commandParts[0].lower()
        args = commandParts[1:]

        # Dispatch the command to the appropriate method.  Note that all you
        # need to do to implement a new command is add another do_* method.
        try:
            method = getattr(self, 'do_' + command)
        except AttributeError, e:
            self.sendLine('Error: no such command.')
            self.do_help()
        else:
            try:
                method(*args)
            except TypeError, e:
                self.sendLine(str(e))
                self.do_help(command)
            except Exception, e:
                self.sendLine('Error: ' + str(e))

    def do_help(self, command=None):
        """help [command]: List commands, or show help on the given command"""
        if command:
            self.sendLine(textwrap.dedent(
                    getattr(self, 'do_' + command).__doc__))
        else:
            commands = [cmd[3:] for cmd in dir(self) if cmd.startswith('do_')]
            self.sendLine("Valid commands: " +" ".join(commands))



    def do_remote_at(self,*args):
        """\
        Send a at command to remote XBee. 
        Input format: Address(Long or short) Command [Parameter] [Options]
        Arguments enclosed in [] are optional"""
        print len(args)
        print args
        if len(args) <= 1:
            raise TypeError('Not enough Arguments')
        packet = {}
        if len(args[0]) == 16:
            packet['dest_addr_long'] = binascii.unhexlify(args[0])
        elif len(args[0]) == 4:
            packet['dest_addr'] = binascii.unhexlify(args[0])
        packet['command'] = args[1]
        try:
            if any(packet['command'] in i for i in string_commands) != True:
                try:
                    packet['parameter'] = binascii.unhexlify(args[2])
                except TypeError:
                    self.sendLine("Parameter must be a value in hex, except on"
                            "commands: ND, DN, NI")
                    return
            else:
                packet['parameter'] = args[2]
        except IndexError:
            pass
        try:
            packet['options'] = binascii.unhexlify[args[3]]
        except IndexError:
            packet['options'] = '\x42'
        packet['frame_id'] = self.frames.get_id()
        self.zigbee.send('remote_at',**packet)
        self.sendLine(packet.__repr__())
    
    def do_at(self,*args):
        """\
        Send a at command to local XBee. 
        Input format: Command [Parameter]
        Arguments enclosed in [] are optional"""
        self.sendLine("at")
    
    def do_queued_at(self,*args):
        """\
        Send a queued at command to local XBee. 
        Input format: Command [Parameter]
        Arguments enclosed in [] are optional"""
        self.sendLine("queied_at")

    def do_tx(self,*args):
        """Not Yet Implemented"""
        pass
    
    def do_tx_explicit(self,*args):
        """Not Yet Implemented"""
        pass

class CommandsFactory(Factory):

    def __init__(self,sensors,zigbee,dispatch,):
        self.sensors = sensors
        self.zigbee = zigbee
        self.dispatch = dispatch
        self.frames = frame_id()

    def buildProtocol(self,addr):
        return Commands(self.sensors,self.zigbee,self.dispatch,self.frames)


