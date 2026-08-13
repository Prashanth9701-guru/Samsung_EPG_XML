from datetime import datetime

import xmltodict
import logging
import xml.etree.ElementTree as ET

from tests.asset_level_test import validate_time, validate_asset_title
from tests.field_value_test import validate_fileds_value_availability
from tests.fields_test import validate_fields_availability, validate_asset_fields_availability
from tests.xml_json_fetch import *
from utilities.helper import *


logger = logging.getLogger(__name__)

def validate_seven_days_data_fetch(seven_days_urls, seven_days, num, name, report_path) -> tuple[int, list, list] :
    failed_cases = []
    date_xml = []
    date_json = []

    for date, urls in list(zip(seven_days, seven_days_urls)):
        logger.info(f'Fetching data for {name} from {date}')
        status_code, xml_data, json_data = data_fetch(urls, name, report_path)

        if status_code == 200:
            json_data= xmltodict.parse(json_data)

            logger.info(f'Data fetched successfully for {name} from {date}')
            date_xml.append({date: xml_data})
            date_json.append({date: json_data})
        else:
            logger.info(f'Failed to fetch data for {name} from {date}')
            failed_cases.append({date: status_code})

    Validation_Output.append(helper_fuc(num, 'URL', f'Validate the status code of {name} in all 7 days', f'{name} should load successfully in all 7 days', 'Failed', f'{name} is failed to load', ','.join(map(str, failed_cases))) if failed_cases else
                             helper_fuc(num, 'URL', f'Validate the status code of {name} in all 7 days', f'{name} should load successfully in all 7 days', 'Passed', f'{name} is loaded successfully with 200 OK status code'))

    return num + 1, date_xml, date_json


def validate_seven_days_channel_level_data(date_json_data, num, name) -> tuple[int, str]:
    channel_tag_availablity = []
    display_tag_availability = []
    channel_name_availability = []
    channel_level_language_availability = []
    channel_level_language = ''

    logger.info(f'Started channel_level_fields availability validation')
    for single_date_json_data in date_json_data:
        for date, json_data in single_date_json_data.items():
            root = ET.fromstring(json_data)

            channels = root.findall('channel')
            if channels:
                for channel in channels:
                    display_name = channel.find('display-name')
                    logger.info(f'Display-Name: {display_name}')
                    if display_name is not None:
                        channel_name = display_name.text
                        channel_level_language = (display_name.attrib).get('lang', '')
                        if not channel_name:
                            channel_name_availability.append({date : 'Channel Name not available'})

                        if not channel_level_language:
                            channel_level_language_availability.append({date : 'Channel Level Language not available'})
                    else:
                        display_tag_availability.append({date : 'Dis-play tag not available'})
            else:
                channel_tag_availablity.append({date : 'Tag not available'})

    logger.info(f'Finished channel_level_fields availability validation')
    Validation_Output.append(helper_fuc(num, name, f'Validate availability of channel tag in all 7 days', f'Channel Tag should be available in all 7 days', 'Failed', f'Channel Tag not available in XML', ','.join(map(str, channel_tag_availablity))) if channel_tag_availablity else
                             helper_fuc(num, name, f'Validate availability of channel tag in all 7 days', f'Channel Tag should be available in all 7 days', 'Passed', f'Channel Tag is available in XML'))

    num+=1
    Validation_Output.append(helper_fuc(num, name, f'Validate availability of display-name tag under channel in all 7 days', f'Display-name Tag should be available in all 7 days', 'Failed', f'Display-Name Tag not available in XML', ','.join(map(str, display_tag_availability))) if display_tag_availability else
                             helper_fuc(num, name, f'Validate availability of display-name tag under channel in all 7 days', f'Display-name Tag should be available in all 7 days', 'Not Tested', f'Channel Tag not available in XML') if channel_tag_availablity else
                             helper_fuc(num, name, f'Validate availability of display-name tag under channel in all 7 days', f'Display-name Tag should be available in all 7 days', 'Passed', f'Display-Name Tag is available in XML'))

    num+=1
    Validation_Output.append(helper_fuc(num, name, f'Validate availability of channel_name in all 7 days', f'Channel Name should be available in all 7 days', 'Failed', f'Channel Name not available in XML', ','.join(map(str, channel_name_availability))) if channel_name_availability else
                             helper_fuc(num, name, f'Validate availability of channel_name in all 7 days', f'Channel Name should be available in all 7 days', 'Not Tested', f'Channel Tag not available in XML') if channel_tag_availablity else
                             helper_fuc(num, name, f'Validate availability of channel_name in all 7 days', f'Channel Name should be available in all 7 days', 'Not Tested', f'Display-Name Tag not available in XML') if display_tag_availability else
                             helper_fuc(num, name, f'Validate availability of channel_name in all 7 days', f'Channel Name should be available in all 7 days', 'Passed', f'Channel Name is available in XML'))

    num+=1
    Validation_Output.append(helper_fuc(num, name, f'Validate availability of channel level language in all 7 days', f'Channel Level Language should be available in all 7 days', 'Failed', f'Channel Level Language not available in XML', ','.join(map(str, channel_level_language_availability))) if channel_level_language_availability else
                             helper_fuc(num, name, f'Validate availability of channel level language in all 7 days', f'Channel Level Language should be available in all 7 days', 'Not Tested', f'Channel Tag not available in XML') if channel_tag_availablity else
                             helper_fuc(num, name, f'Validate availability of channel level language in all 7 days', f'Channel Level Language should be available in all 7 days', 'Not Tested', f'Display-Name Tag not available in XML') if display_tag_availability else
                             helper_fuc(num, name, f'Validate availability of channel level language in all 7 days', f'Channel Level Language should be available in all 7 days', 'Passed', f'Channel Level Language is available in XML'))

    return num+1, channel_level_language

def validate_asset_fields_availability_seven_days(date_json_data, date_xml_data, num, channel_level_language, name, content_type) -> int:
    failed_cases = []

    logger.info(f'Started Asset Level fields availability validation')
    for single_date_json_data in date_json_data:
        for date, json_data in single_date_json_data.items():
            program_data = (json_data.get('tv')).get('programme')
            status, data = validate_asset_fields_availability(program_data, ['sub-title', 'episode-num'], ['onscreen'], content_type)
            if not status:
                failed_cases.append({date: data})

    logger.info(f'Finished Asset Level fields availability validation: {failed_cases}')
    Validation_Output.append(helper_fuc(num, name, f'Validate mandatory fields availability for Assets in all 7 days', f'Mandatory fields should be available for Assets in all 7 days', 'Failed', f'Mandatory Fields are not available', ','.join(map(str, failed_cases))) if failed_cases else
                             helper_fuc(num, name, f'Validate mandatory fields availability for Assets in all 7 days', f'Mandatory fields should be available for Assets in all 7 days', 'Passed', f'All Mandatory fields are available for episodic assets'))
    return num+1



def validate_programs_seven_days_json(date_json_data, num, name, method_name, filed, channel_level_language) -> tuple[list, list, list]:
    failed_cases = []
    not_available_cases = []
    no_value = []
    for single_date_json_data in date_json_data:
        for date, json_data in single_date_json_data.items():
            program_data = (json_data.get('tv')).get('programme')
            logger.info(f'calling required function {method_name}')
            status, data = method_name(program_data, filed)
            if not status and status not in ['not_tested', 'no_value']:
                failed_cases.append({date: data})
            elif status in ['no_value']:
                no_value.append({date: data})
            elif status in ['not_tested']:
                not_available_cases.append({date: data})

    return failed_cases, not_available_cases, no_value



def validate_programs_seven_days_xml(date_xml_data, num, name, method_name, filed, channel_level_language, content_type:str = '', expected_length:int = 0, duration=None) -> list:
    if duration is None:
        duration = []
    not_available_cases = []
    failed_cases_1 = []
    failed_cases_2 = []
    failed_cases_3 = []
    failed_cases_4 = []
    failed_cases_5 = []
    failed_cases_6 = []
    failed_cases_7 = []
    failed_cases_8 = []
    failed_cases_9 = []
    failed_cases_10 = []
    failed_cases_11 = []

    lists = [not_available_cases,
             failed_cases_1,
             failed_cases_2,
             failed_cases_3,
             failed_cases_4,
             failed_cases_5,
             failed_cases_6,
             failed_cases_7,
             failed_cases_8,
             failed_cases_9,
             failed_cases_10,
             failed_cases_11]

    programme_tag_availability = []

    next_asset_time = ''

    for single_date_xml_data in date_xml_data:
        for date, xml_data in single_date_xml_data.items():
            logger.info(f'Next Asset Start Time {date} : {next_asset_time}')
            root = ET.fromstring(xml_data)
            programs = root.findall('programme')
            if programs:
                if name not in ['Schedule']:
                    results = method_name(programs, filed, channel_level_language, content_type, expected_length)
                    logger.info(f'Results in Child File {filed} : {results}')

                    if len(results) < 10:
                        logger.info(f'Entered less than 10')
                        for result, target_list in zip(results, lists):
                            if result:
                                target_list.append({date : result})
                    else:
                        for result, target_list in zip(results, lists):
                            if result:
                                target_list.append({date : result})

                elif name in ['Schedule']:
                    for program in programs:
                        start = program.attrib.get('start', None)
                        stop = program.attrib.get('stop', None)

                        logger.info(f'Asset Start Time: {start} and Asset End Time: {stop}')
                        asset_id = 'Asset ID Not Available'
                        episode = program.findall('episode-num')
                        if episode is not None:
                            for epi in episode:
                                if 'assetID' in str(epi.attrib):
                                    asset_id = epi.text

                        durations = program.findall('length')
                        asset_duration_seconds = 0


                        if start and stop:
                            start_time = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S.%f%z")
                            stop_time = datetime.strptime(stop, "%Y-%m-%dT%H:%M:%S.%f%z")

                            difference = stop_time - start_time
                            logger.info(f'Start Time and Stop Time difference: {difference.total_seconds()}')
                            minutes = difference.total_seconds() / 60
                            logger.info(f'Scheduled Asset in Minutes: {minutes} and Integer: {int(minutes)}')
                            asset_duration_seconds = difference.total_seconds()

                            if int(difference.total_seconds()) < duration[0]:
                                failed_cases_1.append({asset_id: [date, start, int(difference.total_seconds())]})

                            if int(difference.total_seconds()) > duration[1]:
                                failed_cases_2.append({asset_id: [date, stop, int(difference.total_seconds())]})

                            if next_asset_time:
                                if next_asset_time != start:
                                    failed_cases_3.append({asset_id: [date, start, next_asset_time]})
                                next_asset_time = stop

                            else:
                                next_asset_time = stop

                        else:
                            not_available_cases.append({asset_id: [date, 'start or stop tags are not available']})



                        if durations is not None:
                            minutes_tag = next((True for dur in durations if dur.attrib.get('units') and dur.attrib.get('units') == 'minutes'), False)
                            seconds_tag = next((True for dur in durations if dur.attrib.get('units') and dur.attrib.get('units') == 'seconds'), False)

                            if minutes_tag:
                                xml_asset_dur_minutes = next((int(dur.text) for dur in durations if dur.attrib.get('units') == 'minutes' and dur.text), 0)

                                if xml_asset_dur_minutes != 0:
                                    if xml_asset_dur_minutes != int(asset_duration_seconds/60):
                                        failed_cases_7.append({asset_id: [date, xml_asset_dur_minutes, int(asset_duration_seconds/60)]})
                                else:
                                    failed_cases_6.append({asset_id: [date, 'Minutes Value not available in XML']})

                            else:
                                failed_cases_5.append({asset_id: [date, 'Minutes tag not available in XML']})


                            if seconds_tag:
                                xml_asset_dur_seconds = next((int(dur.text) for dur in durations if dur.attrib.get('units') == 'seconds' and dur.text), 0)

                                if xml_asset_dur_seconds != 0:
                                    if xml_asset_dur_seconds != int(asset_duration_seconds):
                                        failed_cases_8.append({asset_id: [date, xml_asset_dur_seconds, int(asset_duration_seconds)]})
                                else:
                                    failed_cases_9.append({asset_id: [date, 'Seconds Value not available in XML']})

                            else:
                                failed_cases_10.append({asset_id: [date, 'Seconds tag not available in XML']})

                        else:
                            failed_cases_4.append({asset_id: [date, 'Length Tag not available']})





                logger.info(f'Next Asset Start Time at End {date} : {next_asset_time}')
            else:
                programme_tag_availability.append({date: 'Programme Tag not available in XML'})


    if name in ['Schedule']:
        logger.info(f'Programme Tag not AVailable: {programme_tag_availability}')
        logger.info(f'Start and Stop Tags not available: {not_available_cases}')
        logger.info(f'Failed Cases 1: {failed_cases_1}')
        logger.info(f'Failed Cases 2: {failed_cases_2}')
        logger.info(f'Failed Cases 3: {failed_cases_3}')
        logger.info(f'Failed Cases 4 Length Tag Availability: {failed_cases_4}')
        logger.info(f'Failed Cases 5 Minutes Tag Availability: {failed_cases_5}')
        logger.info(f'Failed Cases 6 Minutes Value: {failed_cases_6}')
        logger.info(f'Failed Cases 7 Minutes Match with Asset Duration: {failed_cases_7}')
        logger.info(f'Failed Cases 8 Seconds Match with Asset Duration: {failed_cases_8} ')
        logger.info(f'Failed Cases 9 Seconds Value: {failed_cases_9}')
        logger.info(f'Failed Cases 10 Seconds Tag Availability: {failed_cases_10}')

    return [programme_tag_availability,
            not_available_cases,
            failed_cases_1,
            failed_cases_2,
            failed_cases_3,
            failed_cases_4,
            failed_cases_5,
            failed_cases_6,
            failed_cases_7,
            failed_cases_8,
            failed_cases_9,
            failed_cases_10,
            failed_cases_11]














