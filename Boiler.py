import time
import properties
import requests
import logging
from bs4 import BeautifulSoup
from tuya_connector import (
    TuyaOpenAPI,
)

LOG_FILE = "Boiler.log"
LIMITS_FILE = "Limits.txt"
BOILER_NO_ACTION = None
BOILER_OPEN = True
BOILER_CLOSE = False
WEB_SERVER_CONNECTION_FAIL = (-1, -1)

TUYA_API_CONNECTION_SUCCESS = True
TUYA_API_CONNECTION_FAIL = False
TUYA_OPENAPI = TuyaOpenAPI(properties.API_ENDPOINT, properties.ACCESS_ID, properties.ACCESS_KEY)

# Functions ========================================================
def connect(openapi: TuyaOpenAPI) -> bool:
    """
    Establishes connection with Tuya's server.
    """

    try:
        openapi.connect()
    except requests.exceptions.ConnectionError as e:
        logging.exception(f"OpenAPI Connection Exception - {e}\n", exc_info=True)
        return TUYA_API_CONNECTION_FAIL
    except requests.exceptions.ReadTimeout as e:
        logging.exception(f"OpenAPI Connection Exception - {e}\n", exc_info=True)
        return TUYA_API_CONNECTION_FAIL

    return TUYA_API_CONNECTION_SUCCESS

def control_boiler(openapi: TuyaOpenAPI, action: bool) -> None:
    """
    Three possible actions to control the heater:
    1. BOILER_OPEN
    2. BOILER_CLOSE
    
    The value of parameter action in each case is
    True or False respectively.
    """

    connection_status = connect(openapi)
    if connection_status == TUYA_API_CONNECTION_FAIL:
        return

    commands = {
        'commands': [{'code': 'switch_1', 'value': action}]
    }
    openapi.post(f'/v1.0/iot-03/devices/{properties.DEVICE_ID}/commands', commands)

    return

def read_boiler_status(openapi: TuyaOpenAPI) -> bool:
    """
    Returns boiler's status.
    """

    connection_status = connect(openapi)
    if connection_status == TUYA_API_CONNECTION_FAIL:
        return TUYA_API_CONNECTION_FAIL

    try:
        response = openapi.get(f'/v1.0/iot-03/devices/{properties.DEVICE_ID}/status')
    except requests.exceptions.ConnectionError as e:
        logging.exception(f"ConnectionError in Boiler Status Request - {e}\n", exc_info=True)
        return TUYA_API_CONNECTION_FAIL
    
    try:
        boiler_status = response.get('result')[0].get('value')
    except TypeError as e:
        logging.exception(f"TypeError in Boiler Status Response - {e}\n", exc_info=True)
        boiler_status = None
    
    return boiler_status

def read_boiler_temp() -> tuple:
    """
    Returns boiler's Current Temperature and Average Temperature provided by Web server API. 
    """

    try:
        response = requests.get(url=properties.URL)
    except requests.exceptions.ConnectionError as e:
        logging.exception(f"Web Server Connection Exception - {e}\n", exc_info=True)
        return WEB_SERVER_CONNECTION_FAIL
    except requests.exceptions.ReadTimeout as e:
        logging.exception(f"Web Server Connection Exception - {e}\n", exc_info=True)
        return WEB_SERVER_CONNECTION_FAIL
    
    parsed_text = BeautifulSoup(response.text, features='html.parser')
    parsed_text = parsed_text.find('body').text
    
    boiler_temprerature_list = parsed_text.replace('[', '').replace(']', '').split(',')[1:]
    boiler_temprerature_list = [float(x) for x in boiler_temprerature_list]

    average_temp = sum(boiler_temprerature_list[:-2]) / len(boiler_temprerature_list[:-2])
    current_temp = boiler_temprerature_list[-1]
    
    return current_temp, average_temp

def read_limits(limits_filepath: str) -> tuple:
    """
    Reads the .txt file that stores the temperature range that
    the boiler should be in and returns those values.
    """

    with open(limits_filepath, 'r') as limitsf:
        limits_dict = {}
        for line in limitsf:
            k, v = line.strip().split('=')
            limits_dict[k.strip()] = v.strip()

    return float(limits_dict.get('Upper_Limit')), float(limits_dict.get('Lower_Limit')), int(limits_dict.get('Update_Interval_Minutes'))


# Main ========================================================
if __name__ == '__main__':
    
    logging.basicConfig(
        filename=LOG_FILE,
        filemode='a',
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S %p'
        )

    upper_temp_limit, lower_temp_limit, limits_update_interval_minutes = read_limits(LIMITS_FILE)
    current_minute = 0
    
    while True:

        current_temp, average_temp = read_boiler_temp()
        boiler_status = read_boiler_status(TUYA_OPENAPI)

        logging.info(f'Current Temperature: {current_temp}')
        logging.info(f'Boiler Powered On:   {boiler_status}')
   
        if current_temp > upper_temp_limit or (current_temp, average_temp) == WEB_SERVER_CONNECTION_FAIL:
            action = BOILER_CLOSE
        elif current_temp < lower_temp_limit :
            action = BOILER_OPEN
        else: action = BOILER_NO_ACTION
        
        if boiler_status != action != BOILER_NO_ACTION:
            control_boiler(TUYA_OPENAPI, action)

        current_minute += 1
        if current_minute >= limits_update_interval_minutes : # check for changes in Limits.txt
            current_minute = 0
            upper_temp_limit, lower_temp_limit, limits_update_interval_minutes = read_limits(LIMITS_FILE)

        time.sleep (59)
