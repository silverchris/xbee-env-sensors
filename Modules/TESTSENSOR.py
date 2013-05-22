import SensorBase
import binascii
import logging
from datetime import datetime
import time
import collections

cal_data = {'0013a20040aa16e4':-0.584,'0013a20040aa16bd':0,'0013a2004086a9de':2.209}
#cal_data = {'0013a20040aa16e4':-.55,'0013a20040aa16bd':0,'0013a2004086a9de':+3.2}

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
multigraph {address}_battery
battery.value {battery}
."""

class Sensor(SensorBase.Sensor):
    def adc_convert(self,samples,scale=1):
        sample = self.get_mode(samples)
        return round((((float(sample)*1200)/1024)*scale)/1000, 3)

    def max6605(self,voltage):
        return ((voltage-0.744)/0.0119)+self.temperature_cal

    def hih5030(self,sens_volts, bat_volts,temp):
        rh = ((sens_volts/bat_volts)-0.1515)/0.00636
        corrected_rh = (rh)/(1.0546-0.00216*temp)
        return corrected_rh
    
    def get_mode(self,data):
        if len(data) > 0:
            return collections.Counter(data).most_common(1)[0][0]
        return 0
    
    Type = "TESTSENSOR"
    
    def _localinit(self,dispatch):
        dispatch.register(self.address_ascii+' rx_io_data_long_addr',
                self.rx_io_data_long_addr,
                lambda packet: packet['source_addr_long']==self.address
                and packet['id']== 'rx_io_data_long_addr')
        self.timestamp = datetime.now()
        self.raw_humidity = []
        self.raw_temperature = []
        self.raw_light = []
        self.raw_battery = []
        self.temperature_cal = cal_data[self.address_ascii]
        
    def rx_io_data_long_addr(self,name,packet):
        now = datetime.now()
        timedelta = (now-self.timestamp).total_seconds()
        if timedelta <.400:
            self.timestamp = now
            logging.debug("{address}: Time from last Update: {0}".format(timedelta,address=self.address_ascii))
            #ignore updates that come too quickly or too slowly, to make sure sensors have had time
            #to stabilize
            self.raw_humidity.append(packet['samples'][0]['adc-1'])
            self.raw_temperature.append(packet['samples'][0]['adc-2'])
            self.raw_light.append(packet['samples'][0]['adc-3'])
            self.raw_battery.append(packet['samples'][0]['adc-7'])
            logging.debug("{address}: Valid update processed".format(address=self.address_ascii))
        elif timedelta > .400:
            self.timestamp = datetime.now()
            self.raw_humidity = []
            self.raw_temperature = []
            self.raw_light = []
            self.raw_battery = []
            self.timestamp = now
            logging.debug("{address}: Updating too slowly, ignored. {time}s".format(address=self.address_ascii, time=timedelta))
                
    def report(self):
        self.temperature = self.max6605(self.adc_convert(self.raw_temperature,1))
        self.battery = self.adc_convert(self.raw_battery)
        self.humidity = self.hih5030(self.adc_convert(self.raw_humidity,2),self.battery,self.temperature)
        
    def Munin_config(self):
        return munin_config.format(address=self.address_ascii,category=self.location)
    def Munin_fetch(self):
         self.report()
         return munin_fetch.format(address=self.address_ascii,temperature=self.temperature,humidity=self.humidity,battery=self.battery)