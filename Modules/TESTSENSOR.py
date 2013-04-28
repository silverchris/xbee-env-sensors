import SensorBase
import binascii
import logging

def adc_convert(sample,scale=1):
        return (((float(sample)*1200)/1023)*scale)/1000

def max6605_volt_temp(voltage):
        return (voltage-0.744)/0.0119

def hih5030(sens_volts, bat_volts,temp):
        rh = ((sens_volts/bat_volts)-0.1515)/0.00636
        corrected_rh = (rh)/(1.0546-0.00216*temp)
        return corrected_rh

def tept5700(sens_volts,bat_volts):
        photocurrent = sens_volts/1600.00
        return photocurrent

munin_config = """multigraph {address}_temperature
graph_title {address} Temperature
graph_vlabel degrees Celsius
graph_args --base 1000 -l -40 -u 40
graph_category {category}
temperature.label Temperature
multigraph {address}_humidity
graph_title {address} Humidity
graph_vlabel %
graph_args --base 1000 -l 0 -u 100
graph_category {category}
humidity.label Humidity
multigraph {address}_light
graph_title {address} Light
graph_vlabel %
graph_args --base 1000
graph_category {category}
light.label Light
multigraph {address}_battery
graph_title {address} Battery
graph_vlabel V
graph_args --base 1000 -l 0 -u 5
graph_category {category}
battery.label Battery Voltage
."""

munin_fetch = """multigraph {address}_temperature
temperature.value {temperature}
multigraph {address}_humidity
humidity.value {humidity}
multigraph {address}_light
light.value {light}
multigraph {address}_battery
battery.value {battery}
."""

class Sensor(SensorBase.Sensor):
        Type = "TESTSENSOR"
        def _localinit(self,dispatch):
                dispatch.register(binascii.hexlify(self.address)+' rx_io_data_long_addr',
                        self.rx_io_data_long_addr,lambda packet: packet['source_addr_long']==self.address
                        and packet['id']== 'rx_io_data_long_addr')
        
        def rx_io_data_long_addr(self,name,packet):
                #print "Update from %s"%binascii.hexlify(packet['source_addr_long'])
                #print "Message #: %s"%name
                #print "Packet Type: %s"%packet['id']
                #print "Device Type: %s"%self.Type
                self.temperature = max6605_volt_temp(adc_convert(packet['samples'][0]['adc-2'],1))
                #self.light = tept5700(adc_convert(packet['samples'][0]['adc-3']),0)
                self.light = (float(packet['samples'][0]['adc-3'])/1023)*100
                #self.battery = battery = round(((packet['samples'][0]['adc-7'])*(float(1200)/float(1024))/1000), 3)
                self.battery = adc_convert(packet['samples'][0]['adc-7'])
                self.humidity = hih5030(adc_convert(packet['samples'][0]['adc-1'],2),self.battery,self.temperature)
                #self.report()
                
        def report(self):
                print "Battery Voltage: %s"%self.battery
                print "Relative Humidity: %s"%self.humidity
                print "Light Voltage: %s"%self.light
                print "Temperature in C: %s"%self.temperature
        
        def Munin_config(self):
                return munin_config.format(address=self.address_ascii,category=self.location)
        def Munin_fetch(self):
                return munin_fetch.format(address=self.address_ascii,temperature=self.temperature,humidity=self.humidity,light=self.light,battery=self.battery)