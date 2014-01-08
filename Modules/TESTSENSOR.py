import SensorBase
import binascii
import logging
from datetime import datetime
import time
import collections

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
        try:
            sample = self.get_mode(samples)
            value = round((((float(sample)*1200)/1024)*scale)/1000, 3)
        except:
            self.logger.exception("Could't convert ADC value {0} to voltage".format(sample))
            value = "U"
        return value

    def max6605(self,voltage):
        try:
            value = (((voltage-0.744)/0.0119)+float(self.config['temp_cal']))
        except:
            self.logger.exception("Could't convert voltage {0} to temperature".format(sample))
            value = "U"
        return value

    def hih5030(self,sens_volts, bat_volts,temp):
        try:
            rh = ((sens_volts/bat_volts)-0.1515)/0.00636
            corrected_rh = (rh)/(1.0546-0.00216*temp)
        except:
            self.logger.exception("Couldn't convert Sensor Voltage {0}, Battery Voltage {1} to humidity".format(sens_volts,bat_volts))
            corrected_rh = "U"
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
        
    def rx_io_data_long_addr(self,name,packet):
        now = datetime.now()
        timedelta = (now-self.timestamp).total_seconds()
        if timedelta <.400:
            self.timestamp = now
            self.logger.debug("Time from last Update: {0}".format(timedelta))
            #ignore updates that come too quickly or too slowly, to make sure sensors have had time
            #to stabilize
            if packet['samples'][0]['adc-7'] > 2300:
                self.raw_humidity.append(packet['samples'][0]['adc-1'])
                self.raw_temperature.append(packet['samples'][0]['adc-2'])
                self.raw_light.append(packet['samples'][0]['adc-3'])
                self.raw_battery.append(packet['samples'][0]['adc-7'])
                self.logger.debug("Valid update processed")
            else:
                self.logger.warning("Battery voltage low, report thrown away")
        elif timedelta > .400:
            self.timestamp = datetime.now()
            self.raw_humidity = []
            self.raw_temperature = []
            self.raw_light = []
            self.raw_battery = []
            self.timestamp = now
            self.logger.debug("Updating too slowly, ignored. {time}s".format(
                    time=timedelta))
                
    def report(self):
        self.temperature = self.max6605(self.adc_convert(self.raw_temperature,1))
        self.battery = self.adc_convert(self.raw_battery)
        self.humidity = self.hih5030(self.adc_convert(self.raw_humidity,2)
                ,self.battery,self.temperature)
        
    def Munin_config(self):
        return munin_config.format(address=self.address_ascii,
                        category=self.config['location'])
    def Munin_fetch(self):
         self.report()
         if self.battery > 2.95:
             return munin_fetch.format(address=self.address_ascii,
                                       temperature=self.temperature,
                                       humidity=self.humidity,
                                       battery=self.battery)
         else:
             return munin_fetch.format(address='NaN', temperature='NaN',
                                       humidity='NaN',battery=self.battery
                    