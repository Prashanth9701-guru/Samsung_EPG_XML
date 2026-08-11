import requests
import logging


from utilities.helper import *

logger = logging.getLogger(__name__)

def data_fetch(url, name, report_path) -> tuple[int, bytes|str, bytes|str]:
    xml_data = ''
    json_data = ''
    logger.info('Requesting JSON/XML URL')
    response = requests.get(url)
    if response.status_code == 200:
        logger.info(f'{name} is loaded successfully with {response.status_code}')
        xml_data = response.content
        json_data = response.content
        file_name = (url.split('/'))[len(url.split('/')) - 1].replace('-', '_').replace('.', '_')
        with open(f"{report_path}/{file_name}", 'a') as file:
            file.write(response.text)

        return response.status_code, xml_data, json_data

    else:
        logger.info(f'{name} is NOT loaded with {response.status_code}')
        return response.status_code, xml_data, json_data


