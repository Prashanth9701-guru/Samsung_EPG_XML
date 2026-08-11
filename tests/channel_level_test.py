import logging

logger = logging.getLogger(__name__)

def capture_channel_level_lang(date_json_data) -> str:
    logger.info(f'Capturing Channel Level Language')
    language = (((list(date_json_data[0].values())[0].get('tv')).get('channel')).get('display-name', '')).get('@lang', 'en')

    return language

