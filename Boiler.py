# Ref: https://www.youtube.com/watch?v=XW17p62AQa4 

# Imports ========================================================
import time
import os
import properties
import requests
import logging
from ast import Pass, parse
from asyncio import constants
from bs4 import BeautifulSoup
from tuya_connector import (
    TuyaOpenAPI,
    TuyaOpenPulsar,
    TuyaCloudPulsarTopic,
    TUYA_LOGGER,
)

# Globals:
# mypath = "/Python/"
# logfile = "Logfile.txt"
# debug_file = "Debugfile.txt"
limits_file = "Limits.txt"
# Init openapi
openapi = TuyaOpenAPI(properties.API_ENDPOINT, properties.ACCESS_ID, properties.ACCESS_KEY)

# Functions ========================================================
def connect(openapi: TuyaOpenAPI):
    try:
        openapi.connect()
    except requests.exceptions.ConnectionError as e:
        print(e)
        return "API_CONNECTION_FAIL"

    return "API_CONNECTION_SUCCESS"

def control_heater(flag):
    connection_status = connect(openapi)
    if connection_status == "API_CONNECTION_FAIL":
        return False

    commands = {
        'commands': [{'code': 'switch_1', 'value': flag}]
    }   
    command_response = openapi.post(f'/v1.0/iot-03/devices/{properties.DEVICE_ID}/commands', commands)
    command_response_success = command_response.get("success")
    return command_response_success

def read_heater_status():
    connection_status = connect(openapi)
    if connection_status == "API_CONNECTION_FAIL":
        return "API_CONNECTION_FAIL"

    response = openapi.get(f'/v1.0/iot-03/devices/{properties.DEVICE_ID}/status')
    heater_status = response.get('result')[0].get('value')
    return heater_status

def read_boiler_temp():
    response = requests.get(url=properties.URL)
    
    parsed_text = BeautifulSoup(response.text, features='html.parser')
    parsed_text = parsed_text.find('body').text
    
    boiler_temprerature_list = parsed_text.replace('[', '').replace(']', '').split(',')[1:]
    boiler_temprerature_list = [float(x) for x in boiler_temprerature_list]

    Average_Temp = sum(boiler_temprerature_list[:-2]) / len(boiler_temprerature_list[:-2])
    Current_Temp = boiler_temprerature_list[-1]
    
    return Current_Temp, Average_Temp

def read_limits(limits_filepath):
    with open(limits_filepath, 'r') as limitsf:
        limits_dict = {}
        for line in limitsf:
            k, v = line.strip().split('=')
            limits_dict[k.strip()] = v.strip()

    return float(limits_dict.get('Upper_Limit')), float(limits_dict.get('Lower_Limit'))
   

# Main ========================================================

if __name__ == '__main__':
    #Preliminaries..................................................
    #Read the Heater PowerOn status 
    PowerIsOn = read_heater_status()

    #Define spesific directory for LogFile and DebugFile
    # log_filepath = os.path.join(mypath, logfile)
    # if not os.path.exists(mypath):
    #     os.makedirs(mypath)
    # debug_filepath = os.path.join(mypath, debug_file)
    # limits_filepath = os.path.join(mypath, limits_file)
    limits_filepath = limits_file

    #Limits---------------------########--------------------------------
    UperLimit,  LowerLimit = read_limits(limits_filepath)
    flag = False
    print(UperLimit, LowerLimit)

    #Body-----------------------------------------------------------------
    n=0
    while 1:

        time_string = time.strftime("%m/%d/%Y, %H:%M:%S", time.localtime())
        
        Current_Temp, Average_Temp = read_boiler_temp()
        print(Current_Temp)
        
        #if  abs (Current_Temp - Average_Temp) > 5 :
            #logf.write("  **Attention Measurement may be Wrong**")

        if  Current_Temp > UperLimit :
            flag = False
        elif Current_Temp < LowerLimit :
            flag = True
        else: flag = "None"
        
        if PowerIsOn != flag != "None":
            success = control_heater(flag)
        
        PowerIsOn = read_heater_status()

        n += 1
        if n>=10:
            n = 0
            UperLimit, LowerLimit = read_limits(limits_filepath)


        time.sleep (59) 
