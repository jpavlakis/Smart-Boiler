import time
import properties
import requests
import logging
import datetime
import pymysql
from bs4 import BeautifulSoup
from tuya_connector import (
    TuyaOpenAPI,
)

LOG_FILE = "Boiler.log"
LIMITS_FILE = "Limits.txt"
INITIAL_DATETIME = datetime.datetime(2010, 1, 1, 1, 1, 1) #random datetime to check if boiler status has changed during runtime 

BOILER_NO_ACTION = None
BOILER_OPEN = True
BOILER_CLOSE = False

# WEB_SERVER_CONNECTION_FAIL = (-1, -1)
WEB_SERVER_CONNECTION_FAIL = {}

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

def create_db_conn(usr: str, psw: str, host: str, port: int, db: str) ->  pymysql.Connection:
    return pymysql.connect(host=host, user=usr, password=psw, db=db, port=port)

def insert_to_db(data: dict, db_table: str, connection: pymysql.Connection) -> None:
    try:
        with connection.cursor() as cursor:
            # SQL query for inserting data
            sql = f'INSERT INTO {db_table} (sensor, location, value1, value2, value3, boiler, voltage) VALUES (%s, %s, %s, %s, %s, %s, %s)'

            # Data preparation for insertion
            data = [
                    'BME280', 
                    'Bathroom', 
                    data.get('BME280_temp'), 
                    data.get('BME280_hum'), 
                    data.get('BME280_press'), 
                    data.get('DS18B20_temp'), 
                    data.get('BatteryVoltage')
                ]
            
            # Executing SQL query
            cursor.execute(sql, data)

            # Commiting the changes
            connection.commit()
    finally:
        # Closing connection
        connection.close()

def send_text_to_messenger(curr_boiler_status: bool, action_to_boiler: bool, last_status_change: datetime.datetime) -> None:
    '''
    Sends messages to personal Messenger account in the case of the boiler switching on or off.
    Does nothing if the boiler's status doesn't change.
    '''
    message_switch_on  = '►►►  BOILER SWITCHED ON'
    message_switch_off = '◄◄◄  BOILER SWITCHED OFF'

    message_to_send = message_switch_on if action_to_boiler == BOILER_OPEN and curr_boiler_status == BOILER_CLOSE else \
                    (message_switch_off if action_to_boiler == BOILER_CLOSE and curr_boiler_status == BOILER_OPEN \
                    else '')

    if message_to_send != '':
        if last_boiler_status_change != INITIAL_DATETIME:
            total_time_diff_seconds = (datetime.datetime.now() - last_status_change).total_seconds()
            time_diff_hours = divmod(total_time_diff_seconds, 3600)
            time_diff_minutes = divmod(time_diff_hours[1], 60)
            time_diff_seconds = divmod(time_diff_minutes[1], 1)
            
            message_to_send += f' after {int(time_diff_hours[0])} HOURS {int(time_diff_minutes[0])} MINUTES {int(time_diff_seconds[0])} SECONDS'
        
        url = f'{properties.CHATBOT_WEBHOOK_URL}&text={message_to_send}'
        try:
            response = requests.get(url=url)
        except requests.exceptions.ConnectionError as e:
            logging.exception(f"Messenger Chatbot Connection Exception - {e}\n", exc_info=True)
        except requests.exceptions.ReadTimeout as e:
            logging.exception(f"Messenger Chatbot Connection Exception - {e}\n", exc_info=True)
    
    return

def control_boiler(openapi: TuyaOpenAPI, action: bool) -> bool:
    """
    Two possible actions to control the heater:
    1. BOILER_OPEN
    2. BOILER_CLOSE
    
    The value of parameter action in each case is
    True or False respectively.
    """

    connection_status = connect(openapi)
    if connection_status == TUYA_API_CONNECTION_FAIL:
        return TUYA_API_CONNECTION_FAIL

    if action == BOILER_NO_ACTION:
        return False

    commands = {
        'commands': [{'code': 'switch_1', 'value': action}]
    }
    openapi.post(f'/v1.0/iot-03/devices/{properties.DEVICE_ID}/commands', commands)

    return TUYA_API_CONNECTION_SUCCESS

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

# def read_boiler_temp() -> tuple:
def read_boiler_temp() -> dict:    
    """
    Returns boiler's Current Temperature and Average Temperature provided by Web server API. 
    """

    try:
        response = requests.get(url=properties.WEBSERVER_URL)
    except requests.exceptions.ConnectionError as e:
        logging.exception(f"Web Server Connection Exception - {e}\n", exc_info=True)
        return WEB_SERVER_CONNECTION_FAIL
    except requests.exceptions.ReadTimeout as e:
        logging.exception(f"Web Server Connection Exception - {e}\n", exc_info=True)
        return WEB_SERVER_CONNECTION_FAIL
    
    # parsed_text = BeautifulSoup(response.text, features='html.parser')
    # parsed_text = parsed_text.find('body').text
    
    # boiler_temprerature_list = parsed_text.replace('[', '').replace(']', '').split(',')[1:]
    # boiler_temprerature_list = [float(x) for x in boiler_temprerature_list]

    # average_temp = sum(boiler_temprerature_list[:-2]) / len(boiler_temprerature_list[:-2])
    # current_temp = boiler_temprerature_list[-1]
    
    # return current_temp, average_temp
    return response.json()

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
    last_boiler_status_change = INITIAL_DATETIME
    current_minute = 0
    
    while True:
        #TODO: Add db connection
        #TODO: Add db insertion
        current_temp, average_temp = read_boiler_temp() #TODO: Change this according to the new read_boiler_temp return value
        boiler_status = read_boiler_status(TUYA_OPENAPI)

        logging.info(f'Current Temperature: {current_temp}')
        logging.info(f'Boiler Powered On:   {boiler_status}')
   
        if current_temp >= upper_temp_limit or (current_temp, average_temp) == WEB_SERVER_CONNECTION_FAIL:
            action = BOILER_CLOSE
        elif current_temp <= lower_temp_limit:
            action = BOILER_OPEN
        else: action = BOILER_NO_ACTION
        
        if (boiler_status != action) and (action != BOILER_NO_ACTION):
            control_status = control_boiler(TUYA_OPENAPI, action)
            if control_status:
                change = "Switched On" if action == BOILER_OPEN else "Switched Off"
                logging.info(f'Change to Boiler\'s status: {change}')
                send_text_to_messenger(boiler_status, action, last_boiler_status_change)
                last_boiler_status_change = datetime.datetime.now()

        current_minute += 1
        if current_minute >= limits_update_interval_minutes : # check for changes in Limits.txt
            current_minute = 0
            upper_temp_limit, lower_temp_limit, limits_update_interval_minutes = read_limits(LIMITS_FILE)

        time.sleep (59)
