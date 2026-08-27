import os.path

import requests
import yaml
import logging

from tests.asset_level_test import validate_thumbnail, validate_rating
from tests.channel_level_test import capture_channel_level_lang
from utilities.helper import *
from utilities.test_case_priority import apply_priorities_to_validation_output
from services.xlsx_service import *
from tests.xml_json_fetch import *
from tests.xml_date_format import *
from utilities.child_template import *
from services.amagi_api_service import collect_asset_content_types
from services.gsheet_service import *
from services.upload_drive_service import *
from src.failed_cases_seperator import *
from services.summary_report import *
from services.S3_html_local import *

logger = logging.getLogger(__name__)



def template(url,
             content_type,
             ticket_id,
             channel_name,
             content_partner_name,
             sequence_number = 1,
             token=None) -> dict:

    drive_link: str = ""
    s3_html_url: str = ""

    if url.endswith('.xml'):
        logger.info(f'{ticket_id} XML Template')
        Validation_Output.append(helper_fuc(sequence_number, 'URL', 'Validate URL format', 'URL format should be XML', 'Passed', 'URL format is XML'))
        sequence_number = sequence_number + 1
        sequence_number, seven_days_urls, seven_days = validate_url_date_format(url, sequence_number)
        logger.info(f'{ticket_id} - {seven_days_urls}')
        ticket = ticket_id.split('/')[len(ticket_id.split('/')) - 1]
        timestamp = datetime.today().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports"), f'{ticket}_{timestamp}')
        logger.info(f'{ticket_id} {report_path}')
        os.makedirs(report_path, exist_ok=True)
        if seven_days_urls:
            try:
                sequence_number, date_xml_data, date_json_data = validate_seven_days_data_fetch(seven_days_urls, seven_days, sequence_number, 'XML', report_path)
                #logger.info(f'Data: {date_json_data}')
                if date_xml_data:
                    content_type_list = collect_asset_content_types(
                        token, url, date_xml_data, ticket_id, default_content_type=content_type
                    )
                    logger.info(f'{ticket_id} Captured content_type list: {content_type_list}')
                    logger.info(f'{ticket_id} - Started Channel Level Fields')
                    sequence_number, channel_level_language = validate_seven_days_channel_level_data(date_xml_data, sequence_number, 'Channel_Level')
                    logger.info(f'{ticket_id} - Channel Level Language: {channel_level_language}')
                    sequence_number = validate_asset_fields_availability_seven_days(
                        date_json_data, date_xml_data, sequence_number, channel_level_language,
                        'Asset_Level', content_type, content_type_list=content_type_list
                    )

                    logger.info(f'{ticket_id} - Started Asset Start time format validation')
                    failed_cases, not_available_cases, no_value = validate_programs_seven_days_json(date_json_data, sequence_number, 'Asset_Level', validate_time, '@start', channel_level_language)

                    Validation_Output.append( helper_fuc(sequence_number, 'Asset_Level', f'Validate start time format for Assets in all 7 days', f'Start Time format should be in expected format for all Assets in all 7 days', 'Failed', f'Some assets are having wrong datetime format', ','.join(map(str, failed_cases))) if failed_cases else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Validate start time format for Assets in all 7 days', f'Start Time format should be in expected format for all Assets in all 7 days', 'Not Tested', f'Start Time filed not available', ','.join(map(str, not_available_cases))) if not_available_cases else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Validate start time format for Assets in all 7 days', f'Start Time format should be in expected format for all Assets in all 7 days', 'Not Tested', f'Start Time value not available', ','.join(map(str, no_value))) if no_value else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Validate start time format for Assets in all 7 days', f'Start Time format should be in expected format for all Assets in all 7 days', 'Passed', f'All assets are having expected datetime format'))
                    logger.info(f'{ticket_id} - Finished Asset Start time format validation')

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} - Started Asset End time format validation')
                    failed_cases, not_available_cases, no_value = validate_programs_seven_days_json(date_json_data, sequence_number, 'Asset_Level', validate_time, '@stop', channel_level_language)

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate end time format for Assets in all 7 days', f'End Time format should be in expected format for all Assets in all 7 days', 'Failed', f'Some assets are having wrong datetime format', ','.join(map(str, failed_cases))) if failed_cases else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate end time format for Assets in all 7 days', f'End Time format should be in expected format for all Assets in all 7 days', 'Not Tested', f'End Time not available', ','.join(map(str, not_available_cases))) if not_available_cases else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate end time format for Assets in all 7 days', f'End Time format should be in expected format for all Assets in all 7 days', 'Not Tested', 'End Time value not available', ','.join(map(str, no_value))) if no_value else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate end time format for Assets in all 7 days', f'End Time format should be in expected format for all Assets in all 7 days', 'Passed', f'All assets are having expected datetime format'))
                    logger.info(f'{ticket_id} Finished Asset End time format validation')

                    sequence_number = sequence_number + 1

                    logger.info(f'Started Schedule validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Schedule',
                                                               validate_asset_title, 'title', channel_level_language,
                                                               content_type, 200, [1200, 21600])
                    logger.info(f'Schedule Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate less than 20 minutes (1200 seconds) of Assets are not scheduled in all 7 days', f'Scheduled duration of Assets should be greater than or equal to 20 minutes for all Assets in all 7 days', 'Failed', f'Scheduled asset duration is less than the required 20 minutes (1200 seconds)', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate less than 20 minutes (1200 seconds) of Assets are not scheduled in all 7 days', f'Scheduled duration of Assets should be greater than or equal to 20 minutes for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate less than 20 minutes (1200 seconds) of Assets are not scheduled in all 7 days', f'Scheduled duration of Assets should be greater than or equal to 20 minutes for all Assets in all 7 days', 'Not Tested', 'Start and Stop Tags are not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate less than 20 minutes (1200 seconds) of Assets are not scheduled in all 7 days', f'Scheduled duration of Assets should be greater than or equal to 20 minutes for all Assets in all 7 days', 'Passed', f'Duration of the scheduled assets is greater than or equal to 20 minutes'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate greater than 6 hours (21600 seconds) of Assets are not scheduled in all 7 days', f'Scheduled duration of Assets should be less than or equal to 6 hours for all Assets in all 7 days', 'Failed', f'Scheduled asset duration exceeds the maximum allowed duration of 6 hours (21,600 seconds)', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate greater than 6 hours (21600 seconds) of Assets are not scheduled in all 7 days', f'Scheduled duration of Assets should be less than or equal to 6 hours for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate greater than 6 hours (21600 seconds) of Assets are not scheduled in all 7 days', f'Scheduled duration of Assets should be less than or equal to 6 hours for all Assets in all 7 days', 'Not Tested', 'Start and Stop Tags are not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate greater than 6 hours (21600 seconds) of Assets are not scheduled in all 7 days', f'Scheduled duration of Assets should be less than or equal to 6 hours for all Assets in all 7 days', 'Passed', f'Duration of the scheduled assets is less than or equal to 6 hours'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate schedule gap between Assets in all 7 days', f'Current asset stop time and future asset start time should be equal for all Assets in all 7 days', 'Failed', f"Scheduling gap is observed between assets, where the current asset’s stop time not matching with subsequent asset’s start time", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate schedule gap between Assets in all 7 days', f'Current asset stop time and future asset start time should be equal for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate schedule gap between Assets in all 7 days', f'Current asset stop time and future asset start time should be equal for all Assets in all 7 days', 'Not Tested', 'Start and Stop Tags are not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate schedule gap between Assets in all 7 days', f'Current asset stop time and future asset start time should be equal for all Assets in all 7 days', 'Passed', f"Scheduled assets doesn't have any gaps"))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate Minutes attribute availability in all 7 days', f'Minutes attribute should be available for all Assets in all 7 days', 'Failed', f'Minutes attribute is missing', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Minutes attribute availability in all 7 days', f'Minutes attribute should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Minutes attribute availability in all 7 days', f'Minutes attribute should be available for all Assets in all 7 days', 'Not Tested', f'Schedule Length Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Minutes attribute availability in all 7 days', f'Minutes attribute should be available for all Assets in all 7 days', 'Passed', f'Minutes attribute is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate Minutes Value availability in all 7 days', f'Minutes Value should be available for all Assets in all 7 days', 'Failed', f'Minutes Value is missing', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Minutes Value availability in all 7 days', f'Minutes Value should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Minutes Value availability in all 7 days', f'Minutes Value should be available for all Assets in all 7 days', 'Not Tested', f'Schedule Length Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Minutes Value availability in all 7 days', f'Minutes Value should be available for all Assets in all 7 days', 'Not Tested', f'Minutes Attribute not available', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Minutes Value availability in all 7 days', f'Minutes Value should be available for all Assets in all 7 days', 'Passed', f'Minutes Value is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in minutes match with Minutes Value in all 7 days', f'Minutes Value and Asset Duration in minutes should be equal for all Assets in all 7 days', 'Failed', f'Minutes value and the asset duration (in minutes) are not matching', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in minutes match with Minutes Value in all 7 days', f'Minutes Value and Asset Duration in minutes should be equal for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in minutes match with Minutes Value in all 7 days', f'Minutes Value and Asset Duration in minutes should be equal for all Assets in all 7 days', 'Not Tested', f'Schedule Length Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in minutes match with Minutes Value in all 7 days', f'Minutes Value and Asset Duration in minutes should be equal for all Assets in all 7 days', 'Not Tested', f'Minutes Attribute not available', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in minutes match with Minutes Value in all 7 days', f'Minutes Value and Asset Duration in minutes should be equal for all Assets in all 7 days', 'Not Tested', f'Minutes Value not available', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in minutes match with Minutes Value in all 7 days', f'Minutes Value and Asset Duration in minutes should be equal for all Assets in all 7 days', 'Passed', f'Minutes Value and Asset Duration in minutes are equal for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate Seconds attribute availability in all 7 days', f'Seconds attribute should be available for all Assets in all 7 days', 'Failed', f'Seconds attribute is missing', ','.join(map(str, results[11]))) if results[11] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Seconds attribute availability in all 7 days', f'Seconds attribute should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Seconds attribute availability in all 7 days', f'Seconds attribute should be available for all Assets in all 7 days', 'Not Tested', f'Schedule Length Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Seconds attribute availability in all 7 days', f'Seconds attribute should be available for all Assets in all 7 days', 'Passed', f'Seconds attribute is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate Seconds Value availability in all 7 days', f'Seconds Value should be available for all Assets in all 7 days', 'Failed', f'Seconds value is missing', ','.join(map(str, results[10]))) if results[10] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Seconds Value availability in all 7 days', f'Seconds Value should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Seconds Value availability in all 7 days', f'Seconds Value should be available for all Assets in all 7 days', 'Not Tested', f'Schedule Length Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Seconds Value availability in all 7 days', f'Seconds Value should be available for all Assets in all 7 days', 'Not Tested', f'Seconds Attribute not available', ','.join(map(str, results[11]))) if results[11] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Seconds Value availability in all 7 days', f'Seconds Value should be available for all Assets in all 7 days', 'Passed', f'Seconds Value is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in seconds match with Seconds Value in all 7 days', f'Seconds Value and Asset Duration in seconds should be equal for all Assets in all 7 days', 'Failed', f'Seconds value and the asset duration (in seconds) are not matching', ','.join(map(str, results[9]))) if results[9] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in seconds match with Seconds Value in all 7 days', f'Seconds Value and Asset Duration in seconds should be equal for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in seconds match with Seconds Value in all 7 days', f'Seconds Value and Asset Duration in seconds should be equal for all Assets in all 7 days', 'Not Tested', f'Schedule Length Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in seconds match with Seconds Value in all 7 days', f'Seconds Value and Asset Duration in seconds should be equal for all Assets in all 7 days', 'Not Tested', f'Seconds Attribute not available', ','.join(map(str, results[11]))) if results[11] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in seconds match with Seconds Value in all 7 days', f'Seconds Value and Asset Duration in seconds should be equal for all Assets in all 7 days', 'Not Tested', f'Seconds Value not available', ','.join(map(str, results[10]))) if results[10] else
                                             helper_fuc(sequence_number, 'Schedule', f'Validate Asset Duration in seconds match with Seconds Value in all 7 days', f'Seconds Value and Asset Duration in seconds should be equal for all Assets in all 7 days', 'Passed', f'Seconds Value and Asset Duration in seconds are equal for all assets'))

                    sequence_number = sequence_number + 1

                    logger.info(f'Finished Schedule validation')

                    logger.info(f'{ticket_id} Started Asset Title validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'title', channel_level_language, content_type, 200)
                    logger.info(f'Results in title Master_template file: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Title availability in all 7 days', f'Asset Title should be available for all Assets in all 7 days', 'Failed', f'Asset title not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Title availability in all 7 days', f'Asset Title should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Title availability in all 7 days', f'Asset Title should be available for all Assets in all 7 days', 'Not Tested', f'Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Title availability in all 7 days', f'Asset Title should be available for all Assets in all 7 days', 'Passed', f'Asset Title is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate To Be Announced Assets in all 7 days', f'Asset Title field should not include To Be Announced for all Assets in all 7 days', 'Failed', f'Title field contains the value of "To Be Announced"', ','.join(map(str, results[9]))) if results[9] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate To Be Announced Assets in all 7 days', f'Asset Title field should not include To Be Announced for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate To Be Announced Assets in all 7 days', f'Asset Title field should not include To Be Announced for all Assets in all 7 days', 'Not Tested', f'Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate To Be Announced Assets in all 7 days', f'Asset Title field should not include To Be Announced for all Assets in all 7 days', 'Passed', f'Title field contains the value of "To Be Announced"'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Title and Description are matching in all 7 days', f'Asset Title and Description should not be same for all Assets in all 7 days', 'Failed', f'Asset Title and Description fields are matching"', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Title and Description are matching in all 7 days', f'Asset Title and Description should not be same for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Title and Description are matching in all 7 days', f'Asset Title and Description should not be same for all Assets in all 7 days', 'Not Tested', f'Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Title and Description are matching in all 7 days', f'Asset Title and Description should not be same for all Assets in all 7 days', 'Passed', f'Asset Title and Description fields are not matching'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Asset Title in all 7 days', f'Length of Asset Title should not exceed 200 characters for all Assets in all 7 days', 'Failed', f'Asset Title having in-correct-length (chars) which exceeds the maximum allowed length of 200 characters', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Asset Title in all 7 days', f'Length of Asset Title should not exceed 200 characters for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Asset Title in all 7 days', f'Length of Asset Title should not exceed 200 characters for all Assets in all 7 days', 'Not Tested', f'Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Asset Title in all 7 days', f'Length of Asset Title should not exceed 200 characters for all Assets in all 7 days', 'Passed', f'Asset Title length of all assets is within the expected limit of 200 characters'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Asset Title in all 7 days', f'Asset Title should not have any special characters for all Assets in all 7 days', 'Failed', f'Asset title contains special characters that are not permitted according to the platform standards', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Asset Title in all 7 days', f'Asset Title should not have any special characters for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Asset Title in all 7 days', f'Asset Title should not have any special characters for all Assets in all 7 days', 'Not Tested', f'Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Asset Title in all 7 days', f'Asset Title should not have any special characters for all Assets in all 7 days', 'Passed', f'Asset Title not having any special characters'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for title tag in all 7 days', f'Title tag should include language in all 7 days', 'Failed', f"Language node is missing from the title tag", ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for title tag in all 7 days', f'Title tag should include language in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for title tag in all 7 days', f'Title tag should include language in all 7 days', 'Not Tested', f'Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for title tag in all 7 days', f'Title tag should include language in all 7 days', 'Passed', f'Language Node is available in title tag'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Title_Language tag should be equal in all 7 days', 'Failed', f"Title_language_node having (lang value) and channel_level_language having channel_lang_value are not matching", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Title_Language tag should be equal in all 7 days', 'Not Tested', f'Title_language node not available', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Title_Language tag should be equal in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Title_Language tag should be equal in all 7 days', 'Not Tested', f'Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Title_Language tag should be equal in all 7 days', 'Passed', f'title_language value is same as channel_language'))

                    sequence_number = sequence_number + 1
                    logger.info(f'{ticket_id} Finished Asset Title validation')

                    logger.info(f'{ticket_id} Started Sub-Title validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'sub-title', channel_level_language, content_type, 200, content_type_list=content_type_list)
                    logger.info(f'{ticket_id} Sub-Title Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Sub-Title availability in all 7 days', f'Asset Sub-Title should be available for all Assets in all 7 days', 'Failed', f'Asset Sub-Title not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Sub-Title availability in all 7 days', f'Asset Sub-Title should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Sub-Title availability in all 7 days', f'Asset Sub-Title should be available for all Assets in all 7 days', 'Not Tested', f'Sub-Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Sub-Title availability in all 7 days', f'Asset Sub-Title should be available for all Assets in all 7 days', 'Passed', f'Asset Sub-Title is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title and Asset Title are matching in all 7 days', f'Sub-Title and Asset Title should not be same for all Assets in all 7 days', 'Failed', f'Sub-Title and Asset Title fields are matching"', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title and Asset Title are matching in all 7 days', f'Sub-Title and Asset Title should not be same for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title and Asset Title are matching in all 7 days', f'Sub-Title and Asset Title should not be same for all Assets in all 7 days', 'Not Tested', f'Sub-Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title and Asset Title are matching in all 7 days', f'Sub-Title and Asset Title should not be same for all Assets in all 7 days', 'Passed', f'Sub-Title and Asset Title fields are not matching'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title and Description are matching in all 7 days', f'Sub-Title and Description should not be same for all Assets in all 7 days', 'Failed', f'Sub-Title and Description fields are matching"', ','.join(map(str, results[10]))) if results[10] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title and Description are matching in all 7 days', f'Sub-Title and Description should not be same for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title and Description are matching in all 7 days', f'Sub-Title and Description should not be same for all Assets in all 7 days', 'Not Tested', f'Sub-Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title and Description are matching in all 7 days', f'Sub-Title and Description should not be same for all Assets in all 7 days', 'Passed', f'Sub-Title and Description fields are not matching'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Sub-Title in all 7 days', f'Length of Sub-Title should not exceed 200 characters for all Assets in all 7 days', 'Failed', f'Sub-Title having in-correct-length (chars) which exceeds the maximum allowed length of 200 characters', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Sub-Title in all 7 days', f'Length of Sub-Title should not exceed 200 characters for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Sub-Title in all 7 days', f'Length of Sub-Title should not exceed 200 characters for all Assets in all 7 days', 'Not Tested', f'Sub-Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Sub-Title in all 7 days', f'Length of Sub-Title should not exceed 200 characters for all Assets in all 7 days', 'Passed', f'Sub-Title length of all assets is within the expected limit of 200 characters'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Sub-Title in all 7 days', f'Sub-Title should not have any special characters for all Assets in all 7 days', 'Failed', f'Sub-Title contains special characters that are not permitted according to the platform standards', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Sub-Title in all 7 days', f'Sub-Title should not have any special characters for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Sub-Title in all 7 days', f'Sub-Title should not have any special characters for all Assets in all 7 days', 'Not Tested', f'Sub-Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Sub-Title in all 7 days', f'Sub-Title should not have any special characters for all Assets in all 7 days', 'Passed', f'Sub-Title not having any special characters'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Sub-Title tag in all 7 days', f'Sub-Title tag should include language in all 7 days', 'Failed', f"Language node is missing from the sub-title tag", ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Sub-Title tag in all 7 days', f'Sub-Title tag should include language in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Sub-Title tag in all 7 days', f'Sub-Title tag should include language in all 7 days', 'Not Tested', f'Sub-Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Sub-Title tag in all 7 days', f'Sub-Title tag should include language in all 7 days', 'Passed', f'Language Node is available in Sub-Title tag'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Sub-Title_Language tag should be equal in all 7 days', 'Failed', f"Sub-Title_language node having (lang value) and channel_level_language having channel_lang_value are not matching", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Sub-Title_Language tag should be equal in all 7 days', 'Not Tested', f'Sub-Title_language node not available', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Sub-Title_Language tag should be equal in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Sub-Title_Language tag should be equal in all 7 days', 'Not Tested', f'Sub-Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Sub-Title_Language node match with Channel_Language in all 7 days', f'Channel_Language and Sub-Title_Language tag should be equal in all 7 days', 'Passed', f'Sub-Title_language value is same as channel_language'))

                    sequence_number = sequence_number + 1
                    logger.info(f'{ticket_id} Finished Sub-Title validation')

                    logger.info(f'{ticket_id} Started Description validation')

                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'desc', channel_level_language, content_type, 4000)
                    logger.info(f'{ticket_id} Description Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Description availability in all 7 days', f'Asset Description should be available for all Assets in all 7 days', 'Failed', f'Asset Description not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Description availability in all 7 days', f'Asset Description should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Description availability in all 7 days', f'Asset Description should be available for all Assets in all 7 days', 'Not Tested', f'Description Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Description availability in all 7 days', f'Asset Description should be available for all Assets in all 7 days', 'Passed', f'Asset Description is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Description in all 7 days', f'Length of Description should not exceed 4000 characters for all Assets in all 7 days', 'Failed', f'Description having in-correct-length (chars) which exceeds the maximum allowed length of 4000 characters', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Description in all 7 days', f'Length of Description should not exceed 4000 characters for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Description in all 7 days', f'Length of Description should not exceed 4000 characters for all Assets in all 7 days', 'Not Tested', f'Sub-Title Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Length of Description in all 7 days', f'Length of Description should not exceed 4000 characters for all Assets in all 7 days', 'Passed', f'Description length of all assets is within the expected limit of 4000 characters'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Description in all 7 days', f'Description should not have any special characters for all Assets in all 7 days', 'Failed', f'Description contains special characters that are not permitted according to the platform standards', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Description in all 7 days', f'Description should not have any special characters for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Description in all 7 days', f'Description should not have any special characters for all Assets in all 7 days', 'Not Tested', f'Description Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Special Characters in Description in all 7 days', f'Description should not have any special characters for all Assets in all 7 days', 'Passed', f'Description not having any special characters'))

                    sequence_number = sequence_number + 1


                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Description tag in all 7 days', f'Description tag should include language in all 7 days', 'Failed', f"Language node is missing from the description tag", ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Description tag in all 7 days', f'Description tag should include language in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Description tag in all 7 days', f'Description tag should include language in all 7 days', 'Not Tested', f'Description Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Description tag in all 7 days', f'Description tag should include language in all 7 days', 'Passed', f'Language Node is available in Description tag'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Description_Language node match with Channel_Language in all 7 days', f'Channel_Language and Description_Language tag should be equal in all 7 days', 'Failed', f"Description_language having lang value and channel_level_language having channel_lang_value are not matching", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Description_Language node match with Channel_Language in all 7 days', f'Channel_Language and Description_Language tag should be equal in all 7 days', 'Not Tested', f'Description_language node not available', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Description_Language node match with Channel_Language in all 7 days', f'Channel_Language and Description_Language tag should be equal in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Description_Language node match with Channel_Language in all 7 days', f'Channel_Language and Description_Language tag should be equal in all 7 days', 'Not Tested', f'Description Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Description_Language node match with Channel_Language in all 7 days', f'Channel_Language and Description_Language tag should be equal in all 7 days', 'Passed', f'Description_language value is same as channel_language'))

                    sequence_number = sequence_number + 1
                    logger.info(f'{ticket_id} Finished Description validation')

                    logger.info(f'{ticket_id} Started Category validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'category', channel_level_language, content_type)
                    logger.info(f'{ticket_id} Category Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Category availability in all 7 days', f'Asset Category should be available for all Assets in all 7 days', 'Failed', f'Asset Category not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Category availability in all 7 days', f'Asset Category should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Category availability in all 7 days', f'Asset Category should be available for all Assets in all 7 days', 'Not Tested', f'Category Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Category availability in all 7 days', f'Asset Category should be available for all Assets in all 7 days', 'Passed', f'Asset Category is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Category tag in all 7 days', f'Category tag should include language in all 7 days', 'Failed', f"Language node is missing from the Category tag", ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Category tag in all 7 days', f'Category tag should include language in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Category tag in all 7 days', f'Category tag should include language in all 7 days', 'Not Tested', f'Category Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate language node availability for Category tag in all 7 days', f'Category tag should include language in all 7 days', 'Passed', f'Language Node is available in Category tag'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Category_Language node match with Channel_Language in all 7 days', f'Channel_Language and Category_Language tag should be equal in all 7 days', 'Failed', f"Category_language lang value and channel_level_language having channel_lang_value are not matching", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Category_Language node match with Channel_Language in all 7 days', f'Channel_Language and Category_Language tag should be equal in all 7 days', 'Not Tested', f'Category_language node not available', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Category_Language node match with Channel_Language in all 7 days', f'Channel_Language and Category_Language tag should be equal in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Category_Language node match with Channel_Language in all 7 days', f'Channel_Language and Category_Language tag should be equal in all 7 days', 'Not Tested', f'Category Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Category_Language node match with Channel_Language in all 7 days', f'Channel_Language and Category_Language tag should be equal in all 7 days', 'Passed', f'Category_language value is same as channel_language'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Category as per Samsung standard in all 7 days', f'Category should present in Samsung_Supported_Category_List in all 7 days', 'Failed', f"Some assets contain invalid categories that are not included in the Samsung_Supported_Category_List", ','.join(map(str, results[5]))) if results[5] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Category as per Samsung standard in all 7 days', f'Category should present in Samsung_Supported_Category_List in all 7 days', 'Not Tested', f'Category_language node not available', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Category as per Samsung standard in all 7 days', f'Category should present in Samsung_Supported_Category_List in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Category as per Samsung standard in all 7 days', f'Category should present in Samsung_Supported_Category_List in all 7 days', 'Not Tested', f'Category Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Category as per Samsung standard in all 7 days', f'Category should present in Samsung_Supported_Category_List in all 7 days', 'Passed', f'Categories are listed in the Samsung Expected Categories'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Category validation')

                    logger.info(f'{ticket_id} Started Language validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'language', channel_level_language, content_type)
                    logger.info(f'{ticket_id} Language Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset_Language availability in all 7 days', f'Asset Language should be available for all Assets in all 7 days', 'Failed', f'Asset Language not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset_Language availability in all 7 days', f'Asset Language should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset_Language availability in all 7 days', f'Asset Language should be available for all Assets in all 7 days', 'Not Tested', f'Language Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset_Language availability in all 7 days', f'Asset Language should be available for all Assets in all 7 days', 'Passed', f'Asset Language is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset_Language value match with Channel_Language in all 7 days', f'Channel_Language and Asset_Language should be equal in all 7 days', 'Failed', f"Asset_Language not same as channel_language", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset_Language value match with Channel_Language in all 7 days', f'Channel_Language and Asset_Language should be equal in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset_Language value match with Channel_Language in all 7 days', f'Channel_Language and Asset_Language should be equal in all 7 days', 'Not Tested', f'Asset_Language Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset_Language value match with Channel_Language in all 7 days', f'Channel_Language and Asset_Language should be equal in all 7 days', 'Passed', f'Asset_Language and channel_language are same'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Language validation')

                    logger.info(f'{ticket_id} Started Orig_Language validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'orig-language', channel_level_language, content_type)
                    logger.info(f'{ticket_id} Orig_Language Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Orig_Language availability in all 7 days', f'Asset Orig_Language should be available for all Assets in all 7 days', 'Failed', f'Asset Orig_Language not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Orig_Language availability in all 7 days', f'Asset Orig_Language should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Orig_Language availability in all 7 days', f'Asset Orig_Language should be available for all Assets in all 7 days', 'Not Tested', f'Orig_Language Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Orig_Language availability in all 7 days', f'Asset Orig_Language should be available for all Assets in all 7 days', 'Passed', f'Asset Orig_Language is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Orig-language Asset_Language value match with Channel_Language in all 7 days', f'Channel_Language and Asset Orig_Language should be equal in all 7 days', 'Failed', f"Asset Orig_Language not same as channel_language", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Orig-language Asset_Language value match with Channel_Language in all 7 days', f'Channel_Language and Asset Orig_Language should be equal in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Orig-language Asset_Language value match with Channel_Language in all 7 days', f'Channel_Language and Asset Orig_Language should be equal in all 7 days', 'Not Tested', f'Asset Orig_Language Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Orig-language Asset_Language value match with Channel_Language in all 7 days', f'Channel_Language and Asset Orig_Language should be equal in all 7 days', 'Passed', f'Asset Orig_Language and channel_language are same'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Orig_Language validation')

                    logger.info(f'{ticket_id} Started Thumbnail validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_thumbnail, 'icon', channel_level_language, content_type, expected_length = 2000)
                    logger.info(f'{ticket_id} Thumbnail Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail availability in all 7 days', f'Asset Thumbnail should be available for all Assets in all 7 days', 'Failed', f'Asset Thumbnail not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail availability in all 7 days', f'Asset Thumbnail should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail availability in all 7 days', f'Asset Thumbnail should be available for all Assets in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail availability in all 7 days', f'Asset Thumbnail should be available for all Assets in all 7 days', 'Passed', f'Asset Thumbnail is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Width availability in all 7 days', f'Asset Thumbnail_Width should be available for all Assets in all 7 days', 'Failed', f'Asset Thumbnail_Width not available', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Width availability in all 7 days', f'Asset Thumbnail_Width should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Width availability in all 7 days', f'Asset Thumbnail_Width should be available for all Assets in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Width availability in all 7 days', f'Asset Thumbnail_Width should be available for all Assets in all 7 days', 'Passed', f'Asset Thumbnail_Width is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Height availability in all 7 days', f'Asset Thumbnail_Height should be available for all Assets in all 7 days', 'Failed', f'Asset Thumbnail_Height not available', ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Height availability in all 7 days', f'Asset Thumbnail_Height should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Height availability in all 7 days', f'Asset Thumbnail_Height should be available for all Assets in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Height availability in all 7 days', f'Asset Thumbnail_Height should be available for all Assets in all 7 days', 'Passed', f'Asset Thumbnail_Height is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_URL Length in all 7 days', f'Length of Asset Thumbnail_URL should not exceed 2000 characters in all 7 days', 'Failed', f'Asset Thumbnail_URL length is in-correct-length which is more than expected limit of 2000 characters', ','.join(map(str, results[5]))) if results[5] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_URL Length in all 7 days', f'Length of Asset Thumbnail_URL should not exceed 2000 characters in all 7 days', 'Not Tested', f'Asset Thumbnail not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_URL Length in all 7 days', f'Length of Asset Thumbnail_URL should not exceed 2000 characters in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_URL Length in all 7 days', f'Length of Asset Thumbnail_URL should not exceed 2000 characters in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_URL Length in all 7 days', f'Length of Asset Thumbnail_URL should not exceed 2000 characters in all 7 days', 'Passed', f'Asset Thumbnail_URL length of all assets is within the expected limit of 2000 characters'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail status code in all 7 days', f'Asset Thumbnail should open with 200 OK Status Code in all 7 days', 'Failed', f'Asset Thumbnail request getting in-correct-thumbnail status code', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail status code in all 7 days', f'Asset Thumbnail should open with 200 OK Status Code in all 7 days', 'Not Tested', f'Asset Thumbnail not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail status code in all 7 days', f'Asset Thumbnail should open with 200 OK Status Code in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail status code in all 7 days', f'Asset Thumbnail should open with 200 OK Status Code in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail status code in all 7 days', f'Asset Thumbnail should open with 200 OK Status Code in all 7 days', 'Passed', f'Asset Thumbnail is being fetched successfully with an HTTP response status code of 200 Ok'))

                    if results[7]:
                        sequence_number = sequence_number + 1
                        Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail status code in all 7 days', f'Asset Thumbnail should open with 200 OK Status Code in all 7 days', 'Failed', f'Asset Thumbnail request getting re-directed with in-correct-thumbnail status code', ','.join(map(str, results[7]))))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Format in all 7 days', f'Asset Thumbnail Format should be JPEG/JPG in all 7 days', 'Failed', f'Asset Thumbnail are having in-correct-thumbnail format. But, expected should be JPEG/JPG format', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Format in all 7 days', f'Asset Thumbnail Format should be JPEG/JPG in all 7 days', 'Not Tested', f'Asset Thumbnail not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Format in all 7 days', f'Asset Thumbnail Format should be JPEG/JPG in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Format in all 7 days', f'Asset Thumbnail Format should be JPEG/JPG in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Format in all 7 days', f'Asset Thumbnail Format should be JPEG/JPG in all 7 days', 'Passed', f'Asset Thumbnail is in the expected JPEG/JPG format'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Resolution in all 7 days', f'Asset Thumbnail should be 1920X1080 resolution in all 7 days', 'Failed', f'Asset Thumbnail are having in-correct-thumbnail resolution. But, expected should be 1920X1080 resolution', ','.join(map(str, results[9]))) if results[9] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Resolution in all 7 days', f'Asset Thumbnail should be 1920X1080 resolution in all 7 days', 'Not Tested', f'Asset Thumbnail not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Resolution in all 7 days', f'Asset Thumbnail should be 1920X1080 resolution in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Resolution in all 7 days', f'Asset Thumbnail should be 1920X1080 resolution in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Resolution in all 7 days', f'Asset Thumbnail should be 1920X1080 resolution in all 7 days', 'Passed', f'Asset Thumbnail is in the expected 1920X1080 resolution'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Width XML_thumbnail_width in all 7 days', f'Asset Thumbnail_Width should match with XML_thumbnail_width for all Assets in all 7 days', 'Failed', f'Asset Thumbnail_Width having in-correct length and XML_thumbnail_width having proper-length are not matching', ','.join(map(str, results[10]))) if results[10] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Width XML_thumbnail_width in all 7 days', f'Asset Thumbnail_Width should match with XML_thumbnail_width for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Width XML_thumbnail_width in all 7 days', f'Asset Thumbnail_Width should match with XML_thumbnail_width for all Assets in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Width XML_thumbnail_width in all 7 days', f'Asset Thumbnail_Width should match with XML_thumbnail_width for all Assets in all 7 days', 'Passed', f'Asset Thumbnail_Width and XML_thumbnail_width are matching for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Height XML_thumbnail_height in all 7 days', f'Asset Thumbnail_Height should match with XML_thumbnail_height for all Assets in all 7 days', 'Failed', f'Asset Thumbnail_Height having in-correct length and XML_thumbnail_height having proper-length are not matching', ','.join(map(str, results[11]))) if results[11] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Height XML_thumbnail_height in all 7 days', f'Asset Thumbnail_Height should match with XML_thumbnail_height for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Height XML_thumbnail_height in all 7 days', f'Asset Thumbnail_Height should match with XML_thumbnail_height for all Assets in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail_Height XML_thumbnail_height in all 7 days', f'Asset Thumbnail_Height should match with XML_thumbnail_height for all Assets in all 7 days', 'Passed', f'Asset Thumbnail_Height and XML_thumbnail_height are matching for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append( helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Aspect Ratio in all 7 days', f'Asset Thumbnail should have 16:9 aspect aspect-ratio in all 7 days', 'Failed', f'Asset Thumbnail are having in-correct-thumbnail aspect ratio. But, expected should be 16:9 aspect-ratio', ','.join(map(str, results[12]))) if results[12] else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Aspect Ratio in all 7 days', f'Asset Thumbnail should have 16:9 aspect aspect-ratio in all 7 days', 'Not Tested', f'Asset Thumbnail not available', ','.join(map(str, results[2]))) if results[2] else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Aspect Ratio in all 7 days', f'Asset Thumbnail should have 16:9 aspect aspect-ratio in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Aspect Ratio in all 7 days', f'Asset Thumbnail should have 16:9 aspect aspect-ratio in all 7 days', 'Not Tested', f'Icon Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset Thumbnail Aspect Ratio in all 7 days', f'Asset Thumbnail should have 16:9 aspect aspect-ratio in all 7 days', 'Passed', f'Asset Thumbnail is in the expected 16:9 aspect_ratio'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Thumbnail validation')

                    logger.info(f'{ticket_id} Started Rating validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level',
                                                               validate_rating, 'rating', channel_level_language,
                                                               content_type)
                    logger.info(f'{ticket_id} Rating Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source availability in all 7 days', f'Rating Source should be available for all Assets in all 7 days', 'Failed', f'Rating Source not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source availability in all 7 days', f'Rating Source should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source availability in all 7 days', f'Rating Source should be available for all Assets in all 7 days', 'Not Tested', f'Rating Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source availability in all 7 days', f'Rating Source should be available for all Assets in all 7 days', 'Passed', f'Rating Source is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source as per Samsung standard in all 7 days', f'Rating Source should present in Samsung_Supported_Rating_Source_List in all 7 days', 'Failed', f'Assets are having (in-correct-rating) rating source', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source as per Samsung standard in all 7 days', f'Rating Source should present in Samsung_Supported_Rating_Source_List in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source as per Samsung standard in all 7 days', f'Rating Source should present in Samsung_Supported_Rating_Source_List in all 7 days', 'Not Tested', f'Rating Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source as per Samsung standard in all 7 days', f'Rating Source should present in Samsung_Supported_Rating_Source_List in all 7 days', 'Passed', f'Rating Source is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Value availability in all 7 days', f'Rating Value should be available for all Assets in all 7 days', 'Failed', f'Rating Value not available', ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Value availability in all 7 days', f'Rating Value should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Value availability in all 7 days', f'Rating Value should be available for all Assets in all 7 days', 'Not Tested', f'Rating Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Value availability in all 7 days', f'Rating Value should be available for all Assets in all 7 days', 'Passed', f'Rating Value is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Value as per Samsung standard in all 7 days', f'Rating Source Value present in Samsung_Supported_Rating_Value_List in all 7 days', 'Failed', f'Assets are having (in-correct-rating) rating value are not included in Samsung_Supported_Category_List', ','.join(map(str, results[5]))) if results[5] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Value as per Samsung standard in all 7 days', f'Rating Source Value present in Samsung_Supported_Rating_Value_List in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Value as per Samsung standard in all 7 days', f'Rating Source Value present in Samsung_Supported_Rating_Value_List in all 7 days', 'Not Tested', f'Rating Tag not available', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Value as per Samsung standard in all 7 days', f'Rating Source Value present in Samsung_Supported_Rating_Value_List in all 7 days', 'Passed', f'Rating Source is available for all assets'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Started Asset ID validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level',
                                                               validate_asset_title, 'episode-num', channel_level_language,
                                                               content_type, expected_length = 50, content_type_list=content_type_list)
                    logger.info(f'{ticket_id} Asset ID Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset ID availability in all 7 days', f'Asset ID should be available for all Assets in all 7 days', 'Failed', f'Asset ID not available', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset ID availability in all 7 days', f'Asset ID should be available for all Assets in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset ID availability in all 7 days', f'Asset ID should be available for all Assets in all 7 days', 'Not Tested', f'Asset ID Tag itself not available', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset ID availability in all 7 days', f'Asset ID should be available for all Assets in all 7 days', 'Passed', f'Asset ID is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset ID Length in all 7 days', f'Length of Asset ID should not exceed 50 characters in all 7 days', 'Failed', f'Asset ID length is in-correct-length which is more than expected limit of 50 characters', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset ID Length in all 7 days', f'Length of Asset ID should not exceed 50 characters in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset ID Length in all 7 days', f'Length of Asset ID should not exceed 50 characters in all 7 days', 'Not Tested', f'Asset ID Tag itself not available', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Asset ID Length in all 7 days', f'Length of Asset ID should not exceed 50 characters in all 7 days', 'Passed', f'Asset ID Length is within the expected limit of 50 characters'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Episode Number value availability in all 7 days', f'Episode Number Value should be available in all 7 days', 'Failed', f'Episode Number Value not available', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Episode Number value availability in all 7 days', f'Episode Number Value should be available in all 7 days', 'Not Tested', f'Main Programme Field itself not available', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Episode Number value availability in all 7 days', f'Episode Number Value should be available in all 7 days', 'Not Tested', f'Episode Number Tag itself not available', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Episode Number value availability in all 7 days', f'Episode Number Value should be available in all 7 days', 'Passed', f'Episode Number Value available for all assets'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Asset ID validation')




                    logger.info(f'{ticket_id} Validation Output: {Validation_Output}')
                    apply_priorities_to_validation_output(Validation_Output)
                    excel_path = xlsx_report(Validation_Output, report_path)
                    updated_summary_list = failed_cases_seperator()
                    logger.info(f"filtered_list: {updated_summary_list}")

                    html_path = summary_report_writer(
                        excel_path,
                        channel_name=channel_name,
                        content_partner_name=content_partner_name,
                        psd=ticket_id,
                        json_url=url,
                        updated_summary_list=updated_summary_list,
                    )

                    zip_file = zip_folder(report_path, report_path)
                    # drive_link: str = ""
                    # s3_html_url: str = ""
                    try:
                        drive_link = upload_to_drive(zip_file, DRIVE_FOLDER_ID)
                    except Exception as e:
                        logger.warning(f"Folder Upload to drive got failed: {e}")

                    try:
                        s3_result = upload_html_report(html_path)
                        s3_html_url = s3_result.get("report_url", "")
                    except Exception as exc:
                        logger.warning(f"S3 HTML upload failed: {exc}")
                    logger.info(f"S3_HTML URL: {s3_html_url}")
                    filtered_list = failed_cases_seperator()
                    logger.info(f"filtered_list: {filtered_list}")


            except Exception as e:
                 logger.error(f'{ticket_id} Exception: {e}')
                 return {"status":"FAILED",
                        "xml_url":url,
                        "drive_link":drive_link,
                        "s3_html_url":s3_html_url}

    elif url.endswith('.json'):
        logger.info(f'{ticket_id} JSON Template')
        Validation_Output.append(helper_fuc(sequence_number, 'URL', 'Validate URL format', 'URL format should be JSON', 'Passed','URL format is JSON'))
        sequence_number = sequence_number + 1
    else:
        Validation_Output.append(helper_fuc(sequence_number, 'URL', 'Validate URL format', 'URL format should be XML', 'Failed','Unknow URL format'))

    return {"status":"SUCCESS",
            "xml_url":url,
            "drive_link":drive_link,
            "s3_html_url":s3_html_url}
