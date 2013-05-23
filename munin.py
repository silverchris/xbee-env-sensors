from twisted.internet.protocol import Factory, Protocol
from twisted.protocols.basic import LineReceiver
import logging

class Munin(LineReceiver):
        delimiter = '\n'
        def __init__(self, sensors):
                self.sensors = sensors
                self.commands = {'nodes':self._nodes,'config':self._config,'list':self._list_sensors,'fetch':self._fetch,'version':self._version,'cap':self._cap}
                self.logger = logging
                
        def _nodes(self,parameter=""):
                self.logger.debug("nodes called")
                return "sensors"

        def _config(self,parameter=""):
                self.logger.debug("config called on address {address}".format(address=parameter))
                return self.sensors[parameter].Munin_config()

        def _list_sensors(self,parameter=""):
                self.logger.debug("list called")
                commands = ""
                for sensor in self.sensors:
                        if sensor != "":
                                commands = "{0} {1}".format(commands, sensor).lstrip()
                return commands

        def _fetch(self,parameter=""):
                self.logger.debug("fetch called on address {address}".format(address=parameter))
                return self.sensors[parameter].Munin_fetch()

        def _version(self,parameter=""):
                self.logger.debug("version called")
                return "1"

        def _cap(self,parameter=""):
                return "cap multigraph"        
        
        def connectionMade(self):
                self.sendLine("# munin node at Sensors")
                self.logger = logging.getLogger('{0} Munin'.format(
                    self.transport.getPeer().host))
                self.logger.info("Munin: Connected")
                
        def lineReceived(self, line):
                self.logger.debug("Received Command: {0}".format(line))
                data = line.split(" ")
                if line == "quit":
                        self.transport.loseConnection()
                else:
                        try:
                                try:
                                        self.sendLine(self.commands[data[0].strip("\r")](data[1].strip("\r")))
                                except IndexError:
                                        self.sendLine(self.commands[data[0].strip("\r")]())
                        except KeyError:
                                self.sendLine("# Unknown Command")

class MuninFactory(Factory):
        def __init__(self,sensors):
                self.sensors = sensors
        def buildProtocol(self,addr):
                return Munin(self.sensors)