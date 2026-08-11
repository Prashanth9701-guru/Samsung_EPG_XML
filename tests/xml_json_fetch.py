import requests
import logging


from utilities.helper import *

logger = logging.getLogger(__name__)

def data_fetch(url, name) -> tuple[int, bytes|str, bytes|str]:
    xml_data = ''
    json_data = ''
    logger.info('Requesting JSON/XML URL')
    response = requests.get(url)
    if response.status_code == 200:
        logger.info(f'{name} is loaded successfully with {response.status_code}')
        xml_data = response.content
        json_data = response.content
        return response.status_code, xml_data, json_data

    else:
        logger.info(f'{name} is NOT loaded with {response.status_code}')
        return response.status_code, xml_data, json_data


