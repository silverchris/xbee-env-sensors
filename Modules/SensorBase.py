import binascii
import logging

class Sensor(object):
        Type = "Dummy"
        def __init__(self,address,dispatch):
                self.address = address
                self.address_ascii = binascii.hexlify(self.address)
                self.location = "ROOM_GOES_HERE"
                #Munin_Commands = {'config':self.Munin_config,'list':self.Munin_list,'fetch':self.Munin_fetch}
                logging.info("%s: Connected to %s Module"%(self.address_ascii,self.Type))
                self._localinit(dispatch)
                #dispatch.register(binascii.hexlify(self.address),self.update,lambda packet: packet['source_addr_long']==self.address)

        
        
        def nd(self):
                pass
                
        def update(self,name,packet):
                print "class sensor update"
                print packet
        
        def report(self):
                print self
        
        def Munin_config(self,parameter):
                return ""
        def Munin_list(self):
                return ""
        def Munin_fetch(self,parameter):
                return ""