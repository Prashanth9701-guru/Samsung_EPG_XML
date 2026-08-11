import logging
import re
import time

import yaml
import pycountry
import requests
import math
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

config = yaml.safe_load(open('config.yaml'))

def validate_time(programs, key) ->tuple[bool|str,list] :
    status_fail = []
    status_pass = []
    not_available = []
    no_value = []

    program_data = programs if isinstance(programs, list) else [programs]

    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{4}$"
    if program_data:
        for program in program_data:
            asset_id = ''
            if isinstance(program.get('episode-num'), list):
                asset_id = next((episode.get('#text') for episode in program.get('episode-num') if episode.get('@system') == 'assetID'), 'Asset_ID not available')
            elif isinstance(program.get('episode-num'), dict):
                asset_id = (program.get('episode-num')).get('#text') if (program.get('episode-num')).get('@system') == 'assetID' else 'Asset_ID not available'

            timestamp = program.get(key, None)
            if timestamp is not None:
                if timestamp:
                    if not re.match(pattern, timestamp):
                        status_fail.append({asset_id : [timestamp]})
                    else:
                        status_pass.append({asset_id : [timestamp]})
                else:
                    no_value.append({asset_id : [timestamp]})
            else:
                not_available.append({asset_id : [timestamp]})

    if status_fail:
        return False, status_fail
    elif no_value:
        return 'no_value', no_value
    elif not_available:
        return 'not_tested', not_available
    else:
        return True, status_pass


def validate_asset_title(programs, key, channel_level_language, content_type, length) -> list:
    main_availability = []
    title_text_availability = []
    lang_tag_availability = []
    lang_match_channel = []
    category_expected_value = []

    lists = [main_availability,
             title_text_availability,
             lang_tag_availability,
             lang_match_channel,
             category_expected_value]


    def common_function(asset_id):
        main_availability = []
        title_text_availability = []
        lang_tag_availability = []
        lang_match_channel = []
        category_expected_value = []

        main_node = program.findall(key)
        logger.info(f'main_node: {main_node}')
        failed_category_list = []
        if main_node:
            for child in main_node:
                logger.info(f'child node: {child.text}')
                if key in ['title', 'desc', 'sub-title', 'category']:
                    title_lang = child.attrib.get('lang')
                    if title_lang:
                        if not title_lang == channel_level_language:
                            lang_match_channel.append({asset_id: [title_lang, channel_level_language]})
                    else:
                        lang_tag_availability.append(title_lang)

                title = child.text
                if not title:
                    title_text_availability.append({asset_id: title})

                else:
                    if key in ['category']:
                        categories = list(map(str.lower, config.get('categories')))
                        if title.lower() not in categories:
                            failed_category_list.append(child.text)

                    if key in ['language', 'orig-language']:
                        language = (pycountry.languages.get(name=title) or
                                    pycountry.languages.get(alpha_3=title) or
                                    pycountry.languages.get(alpha_2=title))
                        logger.info(f'language: {language} and channel level language: {channel_level_language}')
                        if not language.alpha_2 == channel_level_language:
                            lang_match_channel.append({asset_id: [title, channel_level_language]})

            if failed_category_list:
                category_expected_value.append({asset_id: failed_category_list})

        else:
            main_availability.append({asset_id: f'{key} tag not available'})

        return [main_availability,
                title_text_availability,
                lang_tag_availability,
                lang_match_channel,
                category_expected_value]




    logger.info(f'Content Type: {content_type} and key: {key}')
    for program in programs:
        asset_id = 'Asset ID Not Available'
        episode = program.findall('episode-num')
        if episode is not None:
            for epi in episode:
                if 'assetID' in str(epi.attrib):
                    asset_id = epi.text

        if key == 'sub-title' and content_type.lower() == 'episode':

            results = common_function(asset_id)
            for result, target_list in zip(results, lists):
                if result:
                    target_list.extend(result)

        elif key == 'sub-title' and 'episode' in content_type.lower():
            pass

        elif key != 'sub-title':

            results = common_function(asset_id)
            for result, target_list in zip(results, lists):
                if result:
                    target_list.extend(result)

        elif key == 'sub-title' and content_type != 'episode':
            main_availability.append({asset_id: f'{key} tag not available'})

    return [main_availability,
            title_text_availability,
            lang_tag_availability,
            lang_match_channel,
            category_expected_value]




def validate_thumbnail(programs, key, channel_level_language, content_type, expected_length) ->list:
    main_availability = []
    thum_url_availability = []
    thumbnail_width_availability = []
    thumbnail_height_availability = []
    thum_url_length = []
    thum_status_code = []
    thum_redirect = []
    thum_format = []
    thum_resolution = []
    thum_width_match_xml_width = []
    thum_height_match_xml_height = []
    thum_aspect_ratio = []

    for program in programs:
        asset_id = 'Asset ID Not Available'
        episode = program.findall('episode-num')
        if episode is not None:
            for epi in episode:
                if 'assetID' in str(epi.attrib):
                    asset_id = epi.text

        main_node = program.findall(key)
        logger.info(f'Thumbnail Main Node: {main_node}')
        if main_node is not None:
            for child in main_node:
                #if child is not None:
                thumbnail_url = child.attrib.get('src')
                thumbnail_width_xml = child.attrib.get('width')
                thumbnail_height_xml = child.attrib.get('height')

                if thumbnail_url:
                    if len(thumbnail_url) > expected_length:
                        thum_url_length.append({asset_id: [len(thumbnail_url), thumbnail_url]})

                    try:
                        response = None
                        for attempt in range(5):
                            try:
                                response = requests.get(thumbnail_url, timeout=180)
                                if response.content:
                                    break
                            except requests.exceptions.RequestException as e:
                                logger.info(f"Attempt {attempt + 1} failed: {e}, Thumbnail URL: {thumbnail_url}")
                                time.sleep(2)

                        if response.status_code == 200:
                            image = Image.open(BytesIO(response.content))
                            width, height = image.size
                            gcd = math.gcd(width, height)
                            aspect_ratio = f"{int(width / gcd)}:{int(height / gcd)}"

                            if not str(image.format).lower() in ['jpeg', 'jpg']:
                                thum_format.append({asset_id: [image.format, thumbnail_url]})

                            if image.size != (1920, 1080):
                                thum_resolution.append({asset_id: [f'{width}X{height}', thumbnail_url]})

                            if not thumbnail_width_xml:
                                thumbnail_width_availability.append({asset_id: ['Width not available in XML']})

                            if not thumbnail_height_xml:
                                thumbnail_height_availability.append({asset_id: ['Height not available in XML']})

                            if not thumbnail_width_availability:
                                if width != int(thumbnail_width_xml):
                                    thum_width_match_xml_width.append({asset_id: [thumbnail_width_xml, width, thumbnail_url]})

                            if not thumbnail_height_availability:
                                if height != int(thumbnail_height_xml):
                                    thum_height_match_xml_height.append({asset_id: [thumbnail_height_xml, height, thumbnail_url]})

                            if aspect_ratio != "16:9":
                                thum_aspect_ratio.append({asset_id: [aspect_ratio, thumbnail_url]})


                        elif response.status_code in [301, 302, 303, 307, 308]:
                            thum_redirect.append({asset_id: [response.status_code, thumbnail_url]})
                        else:
                            thum_status_code.append({asset_id: [response.status_code, thumbnail_url]})

                    except requests.exceptions.RequestException as _req_exc:
                        # Network-level failure (connection reset, timeout, DNS, etc.)
                        # Record as a status-code failure and continue to the next asset.
                        logger.warning(f"Thumbnail fetch failed — asset_id={asset_id!r}, "
                                       f"url={thumbnail_url!r}: {_req_exc}")

                        thum_status_code.append({asset_id: [f'network error: {_req_exc}', thumbnail_url]})
                    except Exception as _img_exc:
                        # Image parsing or other unexpected error for this asset.
                        logger.warning(f"Thumbnail processing error — asset_id={asset_id!r}, "
                                       f"url={thumbnail_url!r}: {_img_exc}")

                        thum_status_code.append({asset_id: [f'processing error: {_img_exc}', thumbnail_url]})

                else:
                    thum_url_availability.append({asset_id: 'Thumbnail url not available'})

        else:
            main_availability.append({asset_id: f'{key} tag not available'})

    return [main_availability,
            thum_url_availability,
            thumbnail_width_availability,
            thumbnail_height_availability,
            thum_url_length,
            thum_status_code,
            thum_redirect,
            thum_format,
            thum_resolution,
            thum_width_match_xml_width,
            thum_height_match_xml_height,
            thum_aspect_ratio]


