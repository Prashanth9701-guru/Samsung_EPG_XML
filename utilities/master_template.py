import os.path
from datetime import datetime, timezone

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
from services import mongo_service

logger = logging.getLogger(__name__)


def _store_and_fetch_mongo_non_ssai(
    *,
    ticket_id: str,
    channel_name: str,
    content_partner_name: str,
    url: str,
    pipeline_status: str,
    input_start: datetime,
    drive_link: str = "",
    s3_html_url: str = "",
):
    """
    Push Validation_Output to Mongo for today, then fetch and log.

    Returns the fetched Mongo input document (including ``result``), or None.
    Non-fatal on errors.
    """
    try:
        input_end = datetime.now(timezone.utc)
        execution_date = input_end.strftime("%Y-%m-%d")
        tid = (ticket_id or "").strip() or "unknown"
        validation_snapshot = list(Validation_Output)
        mongo_status = mongo_service.normalize_input_status(
            pipeline_status, validation_snapshot
        )
        payload = mongo_service.build_input_payload(
            input_name=channel_name or tid,
            status=mongo_status,
            execution_start_time=input_start,
            execution_end_time=input_end,
            result=validation_snapshot,
            ticket_id=tid,
            input_url=url or "",
            partner=content_partner_name or "",
            html_link=s3_html_url or "",
            drive_link=drive_link or "",
        )
        mongo_service.store_input_result(
            mongo_service.PIPELINE_NON_SSAI,
            payload,
            execution_date=execution_date,
        )
        return mongo_service.fetch_and_log_today_input(
            mongo_service.PIPELINE_NON_SSAI,
            tid,
            execution_date=execution_date,
        )
    except Exception as exc:
        logger.error(
            "Mongo store/fetch failed for ticket_id=%s (non-fatal): %s",
            ticket_id,
            exc,
        )
        return None


def template(url,
             content_type,
             ticket_id,
             channel_name,
             content_partner_name,
             sequence_number = 1,
             token=None) -> dict:

    drive_link: str = ""
    s3_html_url: str = ""
    status: str = ""
    input_start = datetime.now(timezone.utc)
    mongo_fetched = None

    if url.endswith('.xml'):
        logger.info(f'{ticket_id} XML Template')
        Validation_Output.append(helper_fuc(sequence_number, 'URL', 'Verify the URL content format', 'The URL should point to content in XML format.', 'Passed', 'The URL points to content in XML format.'))
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
                    episode = [True if 'others' not in i.values() else False for i in content_type_list]
                    others = [True if 'others' in i.values() else False for i in content_type_list]

                    logger.info(f'{ticket_id} - Started Channel Level Fields')
                    sequence_number, channel_level_language = validate_seven_days_channel_level_data(date_xml_data, sequence_number, 'Channel_Level')
                    logger.info(f'{ticket_id} - Channel Level Language: {channel_level_language}')
                    sequence_number = validate_asset_fields_availability_seven_days(
                        date_json_data, date_xml_data, sequence_number, channel_level_language,
                        'Asset_Level', content_type, content_type_list=content_type_list
                    )

                    logger.info(f'{ticket_id} - Started Asset Start time format validation')
                    failed_cases, not_available_cases, no_value = validate_programs_seven_days_json(date_json_data, sequence_number, 'Asset_Level', validate_time, '@start', channel_level_language)

                    Validation_Output.append( helper_fuc(sequence_number, 'Asset_Level', f'Verify the start-time format for all assets across the seven-day schedule', f'The start time of every asset should use the expected date-time format throughout the seven-day schedule.', 'Failed', f'One or more assets have a start time in an invalid date-time format.', ','.join(map(str, failed_cases))) if failed_cases else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Verify the start-time format for all assets across the seven-day schedule', f'The start time of every asset should use the expected date-time format throughout the seven-day schedule.', 'Not Tested', f'Start Time filed not available. Hence, skipping the validation of related test cases', ','.join(map(str, not_available_cases))) if not_available_cases else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Verify the start-time format for all assets across the seven-day schedule', f'The start time of every asset should use the expected date-time format throughout the seven-day schedule.', 'Not Tested', f'The start-time value is unavailable; therefore, the related test cases were not run.', ','.join(map(str, no_value))) if no_value else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Verify the start-time format for all assets across the seven-day schedule', f'The start time of every asset should use the expected date-time format throughout the seven-day schedule.', 'Passed', f'All assets use the expected date-time format.'))
                    logger.info(f'{ticket_id} - Finished Asset Start time format validation')

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} - Started Asset End time format validation')
                    failed_cases, not_available_cases, no_value = validate_programs_seven_days_json(date_json_data, sequence_number, 'Asset_Level', validate_time, '@stop', channel_level_language)

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the end-time format for all assets across the seven-day schedule', f'The end time of every asset should use the expected date-time format throughout the seven-day schedule.', 'Failed', f'One or more assets have a end time in an invalid date-time format.', ','.join(map(str, failed_cases))) if failed_cases else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the end-time format for all assets across the seven-day schedule', f'The end time of every asset should use the expected date-time format throughout the seven-day schedule.', 'Not Tested', f'End Time not available. Hence, skipping the validation of related test cases', ','.join(map(str, not_available_cases))) if not_available_cases else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the end-time format for all assets across the seven-day schedule', f'The end time of every asset should use the expected date-time format throughout the seven-day schedule.', 'Not Tested', 'The end-time value is unavailable; therefore, the related test cases were not run.', ','.join(map(str, no_value))) if no_value else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the end-time format for all assets across the seven-day schedule', f'The end time of every asset should use the expected date-time format throughout the seven-day schedule.', 'Passed', f'All assets use the expected date-time format.'))
                    logger.info(f'{ticket_id} Finished Asset End time format validation')

                    sequence_number = sequence_number + 1

                    logger.info(f'Started Schedule validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Schedule',
                                                               validate_asset_title, 'title', channel_level_language,
                                                               content_type, 200, [1200, 21600])
                    logger.info(f'Schedule Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify that no asset shorter than 20 minutes (1,200 seconds) is scheduled across the seven-day schedule', f'Every scheduled asset should have a duration of at least 20 minutes (1,200 seconds) throughout the seven-day schedule.', 'Failed', f'One or more scheduled assets have a duration of less than the required 20 minutes (1,200 seconds).', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that no asset shorter than 20 minutes (1,200 seconds) is scheduled across the seven-day schedule', f'Every scheduled asset should have a duration of at least 20 minutes (1,200 seconds) throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that no asset shorter than 20 minutes (1,200 seconds) is scheduled across the seven-day schedule', f'Every scheduled asset should have a duration of at least 20 minutes (1,200 seconds) throughout the seven-day schedule.', 'Not Tested', 'The start and stop tags are unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that no asset shorter than 20 minutes (1,200 seconds) is scheduled across the seven-day schedule', f'Every scheduled asset should have a duration of at least 20 minutes (1,200 seconds) throughout the seven-day schedule.', 'Passed', f'All scheduled assets have a duration of at least 20 minutes.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify that no asset longer than 6 hours (21,600 seconds) is scheduled across the seven-day schedule', f'Every scheduled asset should have a duration of no more than 6 hours (21,600 seconds) throughout the seven-day schedule.', 'Failed', f'One or more scheduled assets exceed the maximum permitted duration of 6 hours (21,600 seconds).', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that no asset longer than 6 hours (21,600 seconds) is scheduled across the seven-day schedule', f'Every scheduled asset should have a duration of no more than 6 hours (21,600 seconds) throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that no asset longer than 6 hours (21,600 seconds) is scheduled across the seven-day schedule', f'Every scheduled asset should have a duration of no more than 6 hours (21,600 seconds) throughout the seven-day schedule.', 'Not Tested', 'The start and stop tags are unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that no asset longer than 6 hours (21,600 seconds) is scheduled across the seven-day schedule', f'Every scheduled asset should have a duration of no more than 6 hours (21,600 seconds) throughout the seven-day schedule.', 'Passed', f'All scheduled assets have a duration of no more than 6 hours.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify that there are no scheduling gaps between assets across the seven-day schedule', f"Each asset's stop time should match the next asset's start time throughout the seven-day schedule.", 'Failed', f"A scheduling gap exists because an asset's stop time does not match the next asset's start time.", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that there are no scheduling gaps between assets across the seven-day schedule', f"Each asset's stop time should match the next asset's start time throughout the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that there are no scheduling gaps between assets across the seven-day schedule', f"Each asset's stop time should match the next asset's start time throughout the seven-day schedule.", 'Not Tested', 'The start and stop tags are unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that there are no scheduling gaps between assets across the seven-day schedule', f"Each asset's stop time should match the next asset's start time throughout the seven-day schedule.", 'Passed', f"There are no gaps between scheduled assets."))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify the presence of the minutes attribute for all assets across the seven-day schedule', f'The minutes attribute should be present for every asset in the seven-day schedule.', 'Failed', f'The minutes attribute is missing.', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of the minutes attribute for all assets across the seven-day schedule', f'The minutes attribute should be present for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of the minutes attribute for all assets across the seven-day schedule', f'The minutes attribute should be present for every asset in the seven-day schedule.', 'Not Tested', f'The schedule-length tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of the minutes attribute for all assets across the seven-day schedule', f'The minutes attribute should be present for every asset in the seven-day schedule.', 'Passed', f'The minutes attribute is present for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a minutes value for all assets across the seven-day schedule', f'A minutes value should be specified for every asset in the seven-day schedule.', 'Failed', f'The minutes value is missing.', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a minutes value for all assets across the seven-day schedule', f'A minutes value should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a minutes value for all assets across the seven-day schedule', f'A minutes value should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The schedule-length tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a minutes value for all assets across the seven-day schedule', f'A minutes value should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The minutes attribute is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a minutes value for all assets across the seven-day schedule', f'A minutes value should be specified for every asset in the seven-day schedule.', 'Passed', f'A minutes value is specified for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in minutes matches its minutes value across the seven-day schedule', f"Each asset's duration in minutes should match its minutes value throughout the seven-day schedule.", 'Failed', f"One or more assets have a minutes value that does not match the asset's duration in minutes.", ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in minutes matches its minutes value across the seven-day schedule', f"Each asset's duration in minutes should match its minutes value throughout the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in minutes matches its minutes value across the seven-day schedule', f"Each asset's duration in minutes should match its minutes value throughout the seven-day schedule.", 'Not Tested', f'The schedule-length tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in minutes matches its minutes value across the seven-day schedule', f"Each asset's duration in minutes should match its minutes value throughout the seven-day schedule.", 'Not Tested', f'The minutes attribute is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in minutes matches its minutes value across the seven-day schedule', f"Each asset's duration in minutes should match its minutes value throughout the seven-day schedule.", 'Not Tested', f'Minutes Value not available. Hence, skipping the validation of related test cases', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in minutes matches its minutes value across the seven-day schedule', f"Each asset's duration in minutes should match its minutes value throughout the seven-day schedule.", 'Passed', f"Each asset's minutes value matches its duration in minutes."))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify the presence of the seconds attribute for all assets across the seven-day schedule', f'The seconds attribute should be present for every asset in the seven-day schedule.', 'Failed', f'The seconds attribute is missing.', ','.join(map(str, results[11]))) if results[11] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of the seconds attribute for all assets across the seven-day schedule', f'The seconds attribute should be present for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of the seconds attribute for all assets across the seven-day schedule', f'The seconds attribute should be present for every asset in the seven-day schedule.', 'Not Tested', f'The schedule-length tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of the seconds attribute for all assets across the seven-day schedule', f'The seconds attribute should be present for every asset in the seven-day schedule.', 'Passed', f'The seconds attribute is present for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a seconds value for all assets across the seven-day schedule', f'A seconds value should be specified for every asset in the seven-day schedule.', 'Failed', f'The seconds value is missing.', ','.join(map(str, results[10]))) if results[10] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a seconds value for all assets across the seven-day schedule', f'A seconds value should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a seconds value for all assets across the seven-day schedule', f'A seconds value should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The schedule-length tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a seconds value for all assets across the seven-day schedule', f'A seconds value should be specified for every asset in the seven-day schedule.', 'Not Tested', f'Seconds Attribute not available. Hence, skipping the validation of related test cases', ','.join(map(str, results[11]))) if results[11] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify the presence of a seconds value for all assets across the seven-day schedule', f'A seconds value should be specified for every asset in the seven-day schedule.', 'Passed', f'A seconds value is specified for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in seconds matches its seconds value across the seven-day schedule', f"Each asset's duration in seconds should match its seconds value throughout the seven-day schedule.", 'Failed', f"One or more assets have a seconds value that does not match the asset's duration in seconds.", ','.join(map(str, results[9]))) if results[9] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in seconds matches its seconds value across the seven-day schedule', f"Each asset's duration in seconds should match its seconds value throughout the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in seconds matches its seconds value across the seven-day schedule', f"Each asset's duration in seconds should match its seconds value throughout the seven-day schedule.", 'Not Tested', f'The schedule-length tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in seconds matches its seconds value across the seven-day schedule', f"Each asset's duration in seconds should match its seconds value throughout the seven-day schedule.", 'Not Tested', f'Seconds Attribute not available. Hence, skipping the validation of related test cases', ','.join(map(str, results[11]))) if results[11] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in seconds matches its seconds value across the seven-day schedule', f"Each asset's duration in seconds should match its seconds value throughout the seven-day schedule.", 'Not Tested', f'The seconds value is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[10]))) if results[10] else
                                             helper_fuc(sequence_number, 'Schedule', f'Verify that each asset duration in seconds matches its seconds value across the seven-day schedule', f"Each asset's duration in seconds should match its seconds value throughout the seven-day schedule.", 'Passed', f"Each asset's seconds value matches its duration in seconds."))

                    sequence_number = sequence_number + 1

                    logger.info(f'Finished Schedule validation')

                    logger.info(f'{ticket_id} Started Asset Title validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'title', channel_level_language, content_type, 200)
                    logger.info(f'Results in title Master_template file: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a title for all assets across the seven-day schedule', f'A title should be present for every asset in the seven-day schedule.', 'Failed', f'The asset title is missing.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a title for all assets across the seven-day schedule', f'A title should be present for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a title for all assets across the seven-day schedule', f'A title should be present for every asset in the seven-day schedule.', 'Not Tested', f"The title tag is unavailable; therefore, the related test cases were not run.", ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a title for all assets across the seven-day schedule', f'A title should be present for every asset in the seven-day schedule.', 'Passed', f'A title is present for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f"Verify that no asset title contains 'To Be Announced' across the seven-day schedule", f"No asset title should contain 'To Be Announced' in the seven-day schedule.", 'Failed', f"One or more asset titles contain 'To Be Announced'.", ','.join(map(str, results[9]))) if results[9] else
                                             helper_fuc(sequence_number, 'Asset_Level', f"Verify that no asset title contains 'To Be Announced' across the seven-day schedule", f"No asset title should contain 'To Be Announced' in the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f"Verify that no asset title contains 'To Be Announced' across the seven-day schedule", f"No asset title should contain 'To Be Announced' in the seven-day schedule.", 'Not Tested', f"The title tag is unavailable; therefore, the related test cases were not run.", ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f"Verify that no asset title contains 'To Be Announced' across the seven-day schedule", f"No asset title should contain 'To Be Announced' in the seven-day schedule.", 'Passed', f"No asset title contains 'To Be Announced'."))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset titles and descriptions are not identical across the seven-day schedule', f"An asset's title and description should not be identical anywhere in the seven-day schedule.", 'Failed', f'The title and description are identical for one or more assets.', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset titles and descriptions are not identical across the seven-day schedule', f"An asset's title and description should not be identical anywhere in the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset titles and descriptions are not identical across the seven-day schedule', f"An asset's title and description should not be identical anywhere in the seven-day schedule.", 'Not Tested', f"The title tag is unavailable; therefore, the related test cases were not run.", ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset titles and descriptions are not identical across the seven-day schedule', f"An asset's title and description should not be identical anywhere in the seven-day schedule.", 'Passed', f'The title and description are different for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the title length for all assets across the seven-day schedule', f'No asset title should exceed 200 characters in the seven-day schedule.', 'Failed', f'One or more asset titles exceed the maximum permitted length of 200 characters.', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the title length for all assets across the seven-day schedule', f'No asset title should exceed 200 characters in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the title length for all assets across the seven-day schedule', f'No asset title should exceed 200 characters in the seven-day schedule.', 'Not Tested', f"The title tag is unavailable; therefore, the related test cases were not run.", ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the title length for all assets across the seven-day schedule', f'No asset title should exceed 200 characters in the seven-day schedule.', 'Passed', f"Every asset title is within the permitted limit of 200 characters."))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset titles do not contain prohibited special characters across the seven-day schedule', f'Asset titles should not contain special characters prohibited by the platform standards.', 'Failed', f'One or more asset titles contain special characters prohibited by the platform standards.', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset titles do not contain prohibited special characters across the seven-day schedule', f'Asset titles should not contain special characters prohibited by the platform standards.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset titles do not contain prohibited special characters across the seven-day schedule', f'Asset titles should not contain special characters prohibited by the platform standards.', 'Not Tested', f"The title tag is unavailable; therefore, the related test cases were not run.", ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset titles do not contain prohibited special characters across the seven-day schedule', f'Asset titles should not contain special characters prohibited by the platform standards.', 'Passed', f'No asset title contains prohibited special characters.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all title tags across the seven-day schedule', f'Every title tag should include a language attribute throughout the seven-day schedule.', 'Failed', f"The language attribute is missing from one or more title tags.", ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all title tags across the seven-day schedule', f'Every title tag should include a language attribute throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all title tags across the seven-day schedule', f'Every title tag should include a language attribute throughout the seven-day schedule.', 'Not Tested', f"The title tag is unavailable; therefore, the related test cases were not run.", ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all title tags across the seven-day schedule', f'Every title tag should include a language attribute throughout the seven-day schedule.', 'Passed', f'The language attribute is present in every title tag.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that title_language matches channel_language across the seven-day schedule', f'The title_language value should match the channel_language value throughout the seven-day schedule.', 'Failed', f"The title_language and channel_language values do not match for one or more assets.", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that title_language matches channel_language across the seven-day schedule', f'The title_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'Title_language node not available. Hence, skipping the validation of related test cases', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that title_language matches channel_language across the seven-day schedule', f'The title_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that title_language matches channel_language across the seven-day schedule', f'The title_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f"The title tag is unavailable; therefore, the related test cases were not run.", ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that title_language matches channel_language across the seven-day schedule', f'The title_language value should match the channel_language value throughout the seven-day schedule.', 'Passed', f'The title_language value matches the channel_language value for every asset.'))

                    sequence_number = sequence_number + 1
                    logger.info(f'{ticket_id} Finished Asset Title validation')

                    logger.info(f'{ticket_id} Started Sub-Title validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'sub-title', channel_level_language, content_type, 200, content_type_list=content_type_list)
                    logger.info(f'{ticket_id} Sub-Title Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a subtitle for all applicable assets across the seven-day schedule', f'A subtitle should be present for every applicable asset in the seven-day schedule.', 'Failed', f'The asset subtitle is missing.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a subtitle for all applicable assets across the seven-day schedule', f'A subtitle should be present for every applicable asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a subtitle for all applicable assets across the seven-day schedule', f'A subtitle should be present for every applicable asset in the seven-day schedule.', 'Not Tested', 'The subtitle test case was not run because its prerequisite test cases failed.', ','.join(map(str, results[1]))) if results[1] and any(episode) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a subtitle for all applicable assets across the seven-day schedule', f'A subtitle should be present for every applicable asset in the seven-day schedule.', 'Not Applicable', 'The subtitle test case does not apply to non-episodic assets.', ','.join(map(str, results[1]))) if results[1] and all(others) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a subtitle for all applicable assets across the seven-day schedule', f'A subtitle should be present for every applicable asset in the seven-day schedule.', 'Passed', f'A subtitle is present for every applicable asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and titles are not identical across the seven-day schedule', f"An asset's subtitle and title should not be identical anywhere in the seven-day schedule.", 'Failed', f'The subtitle and title are identical for one or more assets.', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and titles are not identical across the seven-day schedule', f"An asset's subtitle and title should not be identical anywhere in the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and titles are not identical across the seven-day schedule', f"An asset's subtitle and title should not be identical anywhere in the seven-day schedule.", 'Not Tested', 'The subtitle test case was not run because its prerequisite test cases failed.', ','.join(map(str, results[1]))) if results[1] and any(episode) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and titles are not identical across the seven-day schedule', f"An asset's subtitle and title should not be identical anywhere in the seven-day schedule.", 'Not Applicable', 'The subtitle test case does not apply to non-episodic assets.', ','.join(map(str, results[1]))) if results[1] and all(others) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and titles are not identical across the seven-day schedule', f"An asset's subtitle and title should not be identical anywhere in the seven-day schedule.", 'Passed', f'The subtitle and title are different for every applicable asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and descriptions are not identical across the seven-day schedule', f"An asset's subtitle and description should not be identical anywhere in the seven-day schedule.", 'Failed', f'The subtitle and description are identical for one or more assets.', ','.join(map(str, results[10]))) if results[10] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and descriptions are not identical across the seven-day schedule', f"An asset's subtitle and description should not be identical anywhere in the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and descriptions are not identical across the seven-day schedule', f"An asset's subtitle and description should not be identical anywhere in the seven-day schedule.", 'Not Tested', f'The subtitle test case was not run because its prerequisite test cases failed.', ','.join(map(str, results[1]))) if results[1] and any(episode) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and descriptions are not identical across the seven-day schedule', f"An asset's subtitle and description should not be identical anywhere in the seven-day schedule.", 'Not Applicable', 'The subtitle test case does not apply to non-episodic assets.', ','.join(map(str, results[1]))) if results[1] and all(others) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles and descriptions are not identical across the seven-day schedule', f"An asset's subtitle and description should not be identical anywhere in the seven-day schedule.", 'Passed', f'The subtitle and description are different for every applicable asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the subtitle length for all assets across the seven-day schedule', f'No asset subtitle should exceed 200 characters in the seven-day schedule.', 'Failed', f'One or more asset subtitles exceed the maximum permitted length of 200 characters.', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the subtitle length for all assets across the seven-day schedule', f'No asset subtitle should exceed 200 characters in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the subtitle length for all assets across the seven-day schedule', f'No asset subtitle should exceed 200 characters in the seven-day schedule.', 'Not Tested', f'The subtitle test case was not run because its prerequisite test cases failed.', ','.join(map(str, results[1]))) if results[1] and any(episode) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the subtitle length for all assets across the seven-day schedule', f'No asset subtitle should exceed 200 characters in the seven-day schedule.', 'Not Applicable', 'The subtitle test case does not apply to non-episodic assets.', ','.join(map(str, results[1]))) if results[1] and all(others) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the subtitle length for all assets across the seven-day schedule', f'No asset subtitle should exceed 200 characters in the seven-day schedule.', 'Passed', f'Every asset subtitle is within the permitted limit of 200 characters.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles do not contain prohibited special characters across the seven-day schedule', f'Asset subtitles should not contain special characters prohibited by the platform standards.', 'Failed', f'One or more asset subtitles contain special characters prohibited by the platform standards.', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles do not contain prohibited special characters across the seven-day schedule', f'Asset subtitles should not contain special characters prohibited by the platform standards.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles do not contain prohibited special characters across the seven-day schedule', f'Asset subtitles should not contain special characters prohibited by the platform standards.', 'Not Tested', f'The subtitle test case was not run because its prerequisite test cases failed.', ','.join(map(str, results[1]))) if results[1] and any(episode) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles do not contain prohibited special characters across the seven-day schedule', f'Asset subtitles should not contain special characters prohibited by the platform standards.', 'Not Applicable', 'The subtitle test case does not apply to non-episodic assets.', ','.join(map(str, results[1]))) if results[1] and all(others) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset subtitles do not contain prohibited special characters across the seven-day schedule', f'Asset subtitles should not contain special characters prohibited by the platform standards.', 'Passed', f'No asset subtitle contains prohibited special characters.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all subtitle tags across the seven-day schedule', f'Every subtitle tag should include a language attribute throughout the seven-day schedule.', 'Failed', f"The language attribute is missing from one or more subtitle tags.", ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all subtitle tags across the seven-day schedule', f'Every subtitle tag should include a language attribute throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all subtitle tags across the seven-day schedule', f'Every subtitle tag should include a language attribute throughout the seven-day schedule.', 'Not Tested', f'The subtitle test case was not run because its prerequisite test cases failed.', ','.join(map(str, results[1]))) if results[1] and any(episode) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all subtitle tags across the seven-day schedule', f'Every subtitle tag should include a language attribute throughout the seven-day schedule.', 'Not Applicable', 'The subtitle test case does not apply to non-episodic assets.', ','.join(map(str, results[1]))) if results[1] and all(others) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all subtitle tags across the seven-day schedule', f'Every subtitle tag should include a language attribute throughout the seven-day schedule.', 'Passed', f'The language attribute is present in every subtitle tag.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that subtitle_language matches channel_language across the seven-day schedule', f'The subtitle_language value should match the channel_language value throughout the seven-day schedule.', 'Failed', f"The subtitle_language and channel_language values do not match for one or more assets.", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that subtitle_language matches channel_language across the seven-day schedule', f'The subtitle_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The subtitle_language value is unavailable; therefore, this test case was not run.', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that subtitle_language matches channel_language across the seven-day schedule', f'The subtitle_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that subtitle_language matches channel_language across the seven-day schedule', f'The subtitle_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The subtitle test case was not run because its prerequisite test cases failed.', ','.join(map(str, results[1]))) if results[1] and any(episode) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that subtitle_language matches channel_language across the seven-day schedule', f'The subtitle_language value should match the channel_language value throughout the seven-day schedule.', 'Not Applicable', 'The subtitle test case does not apply to non-episodic assets.', ','.join(map(str, results[1]))) if results[1] and all(others) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that subtitle_language matches channel_language across the seven-day schedule', f'The subtitle_language value should match the channel_language value throughout the seven-day schedule.', 'Passed', f'The subtitle_language value matches the channel_language value for every applicable asset.'))

                    sequence_number = sequence_number + 1
                    logger.info(f'{ticket_id} Finished Sub-Title validation')

                    logger.info(f'{ticket_id} Started Description validation')

                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'desc', channel_level_language, content_type, 4000)
                    logger.info(f'{ticket_id} Description Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a description for all assets across the seven-day schedule', f'A description should be present for every asset in the seven-day schedule.', 'Failed', f'The asset description is missing.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a description for all assets across the seven-day schedule', f'A description should be present for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a description for all assets across the seven-day schedule', f'A description should be present for every asset in the seven-day schedule.', 'Not Tested', f'The description tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a description for all assets across the seven-day schedule', f'A description should be present for every asset in the seven-day schedule.', 'Passed', f'A description is present for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the description length for all assets across the seven-day schedule', f'No asset description should exceed 4,000 characters in the seven-day schedule.', 'Failed', f'One or more asset descriptions exceed the maximum permitted length of 4,000 characters.', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the description length for all assets across the seven-day schedule', f'No asset description should exceed 4,000 characters in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the description length for all assets across the seven-day schedule', f'No asset description should exceed 4,000 characters in the seven-day schedule.', 'Not Tested', f'The description tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the description length for all assets across the seven-day schedule', f'No asset description should exceed 4,000 characters in the seven-day schedule.', 'Passed', f'Every asset description is within the permitted limit of 4,000 characters.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset descriptions do not contain prohibited special characters across the seven-day schedule', f'Asset descriptions should not contain special characters prohibited by the platform standards.', 'Failed', f'One or more asset descriptions contain special characters prohibited by the platform standards.', ','.join(map(str, results[7]))) if results[7] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset descriptions do not contain prohibited special characters across the seven-day schedule', f'Asset descriptions should not contain special characters prohibited by the platform standards.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset descriptions do not contain prohibited special characters across the seven-day schedule', f'Asset descriptions should not contain special characters prohibited by the platform standards.', 'Not Tested', f'The description tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset descriptions do not contain prohibited special characters across the seven-day schedule', f'Asset descriptions should not contain special characters prohibited by the platform standards.', 'Passed', f'No asset description contains prohibited special characters.'))

                    sequence_number = sequence_number + 1


                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all description tags across the seven-day schedule', f'Every description tag should include a language attribute throughout the seven-day schedule.', 'Failed', f"The language attribute is missing from one or more description tags.", ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all description tags across the seven-day schedule', f'Every description tag should include a language attribute throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all description tags across the seven-day schedule', f'Every description tag should include a language attribute throughout the seven-day schedule.', 'Not Tested', f'The description tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all description tags across the seven-day schedule', f'Every description tag should include a language attribute throughout the seven-day schedule.', 'Passed', f'The language attribute is present in every description tag.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that description_language matches channel_language across the seven-day schedule', f'The description_language value should match the channel_language value throughout the seven-day schedule.', 'Failed', f"The description_language and channel_language values do not match for one or more assets.", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that description_language matches channel_language across the seven-day schedule', f'The description_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The description_language value is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that description_language matches channel_language across the seven-day schedule', f'The description_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that description_language matches channel_language across the seven-day schedule', f'The description_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The description tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that description_language matches channel_language across the seven-day schedule', f'The description_language value should match the channel_language value throughout the seven-day schedule.', 'Passed', f'The description_language value matches the channel_language value for every asset.'))

                    sequence_number = sequence_number + 1
                    logger.info(f'{ticket_id} Finished Description validation')

                    logger.info(f'{ticket_id} Started Category validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'category', channel_level_language, content_type)
                    logger.info(f'{ticket_id} Category Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a category for all assets across the seven-day schedule', f'A category should be present for every asset in the seven-day schedule.', 'Failed', f'The asset category is missing.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a category for all assets across the seven-day schedule', f'A category should be present for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a category for all assets across the seven-day schedule', f'A category should be present for every asset in the seven-day schedule.', 'Not Tested', f'The category tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a category for all assets across the seven-day schedule', f'A category should be present for every asset in the seven-day schedule.', 'Passed', f'A category is present for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all category tags across the seven-day schedule', f'Every category tag should include a language attribute throughout the seven-day schedule.', 'Failed', f"The language attribute is missing from one or more category tags.", ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all category tags across the seven-day schedule', f'Every category tag should include a language attribute throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all category tags across the seven-day schedule', f'Every category tag should include a language attribute throughout the seven-day schedule.', 'Not Tested', f'The category tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a language attribute in all category tags across the seven-day schedule', f'Every category tag should include a language attribute throughout the seven-day schedule.', 'Passed', f'The language attribute is present in every category tag.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that category_language matches channel_language across the seven-day schedule', f'The category_language value should match the channel_language value throughout the seven-day schedule.', 'Failed', f"The category_language and channel_language values do not match for one or more assets.", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that category_language matches channel_language across the seven-day schedule', f'The category_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The category_language value is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that category_language matches channel_language across the seven-day schedule', f'The category_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that category_language matches channel_language across the seven-day schedule', f'The category_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The category tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that category_language matches channel_language across the seven-day schedule', f'The category_language value should match the channel_language value throughout the seven-day schedule.', 'Passed', f'The category_language value matches the channel_language value for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that all categories comply with Samsung standards across the seven-day schedule', f'Every category should be included in the Samsung_Supported_Category_List throughout the seven-day schedule.', 'Failed', f"One or more assets contain categories that are not included in the Samsung_Supported_Category_List.", ','.join(map(str, results[5]))) if results[5] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that all categories comply with Samsung standards across the seven-day schedule', f'Every category should be included in the Samsung_Supported_Category_List throughout the seven-day schedule.', 'Not Tested', f'The category_language value is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that all categories comply with Samsung standards across the seven-day schedule', f'Every category should be included in the Samsung_Supported_Category_List throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that all categories comply with Samsung standards across the seven-day schedule', f'Every category should be included in the Samsung_Supported_Category_List throughout the seven-day schedule.', 'Not Tested', f'The category tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that all categories comply with Samsung standards across the seven-day schedule', f'Every category should be included in the Samsung_Supported_Category_List throughout the seven-day schedule.', 'Passed', f'All asset categories are included in the Samsung-supported category list.'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Category validation')

                    logger.info(f'{ticket_id} Started Language validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'language', channel_level_language, content_type)
                    logger.info(f'{ticket_id} Language Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the asset language for all assets across the seven-day schedule', f'The asset language should be specified for every asset in the seven-day schedule.', 'Failed', f'The asset language is missing.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the asset language for all assets across the seven-day schedule', f'The asset language should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the asset language for all assets across the seven-day schedule', f'The asset language should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The language tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the asset language for all assets across the seven-day schedule', f'The asset language should be specified for every asset in the seven-day schedule.', 'Passed', f'The asset language is specified for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset_language matches channel_language across the seven-day schedule', f'The asset_language value should match the channel_language value throughout the seven-day schedule.', 'Failed', f"The asset_language and channel_language values do not match for one or more assets.", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset_language matches channel_language across the seven-day schedule', f'The asset_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset_language matches channel_language across the seven-day schedule', f'The asset_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The asset_language tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset_language matches channel_language across the seven-day schedule', f'The asset_language value should match the channel_language value throughout the seven-day schedule.', 'Passed', f'The asset_language value matches the channel_language value for every asset.'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Language validation')

                    logger.info(f'{ticket_id} Started Orig_Language validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_asset_title, 'orig-language', channel_level_language, content_type)
                    logger.info(f'{ticket_id} Orig_Language Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the original language for all assets across the seven-day schedule', f'The original language should be specified for every asset in the seven-day schedule.', 'Failed', f'The original language is missing for one or more assets.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the original language for all assets across the seven-day schedule', f'The original language should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the original language for all assets across the seven-day schedule', f'The original language should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The orig_language tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the original language for all assets across the seven-day schedule', f'The original language should be specified for every asset in the seven-day schedule.', 'Passed', f'The original language is specified for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset orig_language matches channel_language across the seven-day schedule', f'The asset orig_language value should match the channel_language value throughout the seven-day schedule.', 'Failed', f"The asset orig_language and channel_language values do not match for one or more assets.", ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset orig_language matches channel_language across the seven-day schedule', f'The asset orig_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset orig_language matches channel_language across the seven-day schedule', f'The asset orig_language value should match the channel_language value throughout the seven-day schedule.', 'Not Tested', f'The asset orig_language tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that asset orig_language matches channel_language across the seven-day schedule', f'The asset orig_language value should match the channel_language value throughout the seven-day schedule.', 'Passed', f'The asset orig_language value matches the channel_language value for every asset.'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Orig_Language validation')

                    logger.info(f'{ticket_id} Started Thumbnail validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level', validate_thumbnail, 'icon', channel_level_language, content_type, expected_length = 2000)
                    logger.info(f'{ticket_id} Thumbnail Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the availability of thumbnails for all assets across the seven-day schedule', f'A thumbnail should be available for every asset in the seven-day schedule.', 'Failed', f'The asset thumbnail is missing.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the availability of thumbnails for all assets across the seven-day schedule', f'A thumbnail should be available for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the availability of thumbnails for all assets across the seven-day schedule', f'A thumbnail should be available for every asset in the seven-day schedule.', 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the availability of thumbnails for all assets across the seven-day schedule', f'A thumbnail should be available for every asset in the seven-day schedule.', 'Passed', f'A thumbnail is available for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the thumbnail width for all assets across the seven-day schedule', f'The thumbnail width should be specified for every asset in the seven-day schedule.', 'Failed', f'The thumbnail width is missing for one or more assets.', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the thumbnail width for all assets across the seven-day schedule', f'The thumbnail width should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the thumbnail width for all assets across the seven-day schedule', f'The thumbnail width should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the thumbnail width for all assets across the seven-day schedule', f'The thumbnail width should be specified for every asset in the seven-day schedule.', 'Passed', f'The thumbnail width is specified for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the thumbnail height for all assets across the seven-day schedule', f'The thumbnail height should be specified for every asset in the seven-day schedule.', 'Failed', f'The thumbnail height is missing for one or more assets.', ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the thumbnail height for all assets across the seven-day schedule', f'The thumbnail height should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the thumbnail height for all assets across the seven-day schedule', f'The thumbnail height should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of the thumbnail height for all assets across the seven-day schedule', f'The thumbnail height should be specified for every asset in the seven-day schedule.', 'Passed', f'The thumbnail height is specified for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail URL length for all assets across the seven-day schedule', f'No asset thumbnail URL should exceed 2,000 characters in the seven-day schedule.', 'Failed', f'One or more asset thumbnail URLs exceed the maximum permitted length of 2,000 characters.', ','.join(map(str, results[5]))) if results[5] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail URL length for all assets across the seven-day schedule', f'No asset thumbnail URL should exceed 2,000 characters in the seven-day schedule.', 'Not Tested', f'The asset thumbnail is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail URL length for all assets across the seven-day schedule', f'No asset thumbnail URL should exceed 2,000 characters in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail URL length for all assets across the seven-day schedule', f'No asset thumbnail URL should exceed 2,000 characters in the seven-day schedule.', 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail URL length for all assets across the seven-day schedule', f'No asset thumbnail URL should exceed 2,000 characters in the seven-day schedule.', 'Passed', f'Every asset thumbnail URL is within the permitted limit of 2,000 characters.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the HTTP response status of all asset thumbnails across the seven-day schedule', f'Every asset thumbnail URL should return an HTTP 200 OK response throughout the seven-day schedule.', 'Failed', f'One or more asset thumbnail requests return an unexpected HTTP status code.', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the HTTP response status of all asset thumbnails across the seven-day schedule', f'Every asset thumbnail URL should return an HTTP 200 OK response throughout the seven-day schedule.', 'Not Tested', f'The asset thumbnail is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the HTTP response status of all asset thumbnails across the seven-day schedule', f'Every asset thumbnail URL should return an HTTP 200 OK response throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the HTTP response status of all asset thumbnails across the seven-day schedule', f'Every asset thumbnail URL should return an HTTP 200 OK response throughout the seven-day schedule.', 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the HTTP response status of all asset thumbnails across the seven-day schedule', f'Every asset thumbnail URL should return an HTTP 200 OK response throughout the seven-day schedule.', 'Passed', f'Every asset thumbnail is retrieved successfully with an HTTP 200 OK response.'))

                    if results[7]:
                        sequence_number = sequence_number + 1
                        Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the HTTP response status of all asset thumbnails across the seven-day schedule', f'Every asset thumbnail URL should return an HTTP 200 OK response throughout the seven-day schedule.', 'Failed', f'One or more asset thumbnail requests are redirected and return an unexpected HTTP status code.', ','.join(map(str, results[7]))))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail format for all assets across the seven-day schedule', f'Every asset thumbnail should be in JPEG or JPG or PNG format throughout the seven-day schedule.', 'Failed', f'One or more asset thumbnails are not in the required JPEG or JPG or PNG format.', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail format for all assets across the seven-day schedule', f'Every asset thumbnail should be in JPEG or JPG or PNG format throughout the seven-day schedule.', 'Not Tested', f'The asset thumbnail is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail format for all assets across the seven-day schedule', f'Every asset thumbnail should be in JPEG or JPG or PNG format throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail format for all assets across the seven-day schedule', f'Every asset thumbnail should be in JPEG or JPG or PNG format throughout the seven-day schedule.', 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail format for all assets across the seven-day schedule', f'Every asset thumbnail should be in JPEG or JPG or PNG format throughout the seven-day schedule.', 'Passed', f'Every asset thumbnail is in the required JPEG or JPG or PNG format.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail resolution for all assets across the seven-day schedule', f'Every asset thumbnail should have a resolution of 1920 × 1080 pixels throughout the seven-day schedule.', 'Failed', f'One or more asset thumbnails do not have the required resolution of 1920 × 1080 pixels.', ','.join(map(str, results[9]))) if results[9] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail resolution for all assets across the seven-day schedule', f'Every asset thumbnail should have a resolution of 1920 × 1080 pixels throughout the seven-day schedule.', 'Not Tested', f'The asset thumbnail is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail resolution for all assets across the seven-day schedule', f'Every asset thumbnail should have a resolution of 1920 × 1080 pixels throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail resolution for all assets across the seven-day schedule', f'Every asset thumbnail should have a resolution of 1920 × 1080 pixels throughout the seven-day schedule.', 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail resolution for all assets across the seven-day schedule', f'Every asset thumbnail should have a resolution of 1920 × 1080 pixels throughout the seven-day schedule.', 'Passed', f'Every asset thumbnail has the required resolution of 1920 × 1080 pixels.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that each actual thumbnail width matches its XML_thumbnail_width value across the seven-day schedule', f"Each asset thumbnail's actual width should match the XML_thumbnail_width value throughout the seven-day schedule.", 'Failed', f'The actual thumbnail width does not match the XML_thumbnail_width value for one or more assets.', ','.join(map(str, results[10]))) if results[10] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that each actual thumbnail width matches its XML_thumbnail_width value across the seven-day schedule', f"Each asset thumbnail's actual width should match the XML_thumbnail_width value throughout the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that each actual thumbnail width matches its XML_thumbnail_width value across the seven-day schedule', f"Each asset thumbnail's actual width should match the XML_thumbnail_width value throughout the seven-day schedule.", 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that each actual thumbnail width matches its XML_thumbnail_width value across the seven-day schedule', f"Each asset thumbnail's actual width should match the XML_thumbnail_width value throughout the seven-day schedule.", 'Passed', f'The actual thumbnail width matches the XML_thumbnail_width value for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that each actual thumbnail height matches its XML_thumbnail_height value across the seven-day schedule', f"Each asset thumbnail's actual height should match the XML_thumbnail_height value throughout the seven-day schedule.", 'Failed', f'The actual thumbnail height does not match the XML_thumbnail_height value for one or more assets.', ','.join(map(str, results[11]))) if results[11] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that each actual thumbnail height matches its XML_thumbnail_height value across the seven-day schedule', f"Each asset thumbnail's actual height should match the XML_thumbnail_height value throughout the seven-day schedule.", 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that each actual thumbnail height matches its XML_thumbnail_height value across the seven-day schedule', f"Each asset thumbnail's actual height should match the XML_thumbnail_height value throughout the seven-day schedule.", 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that each actual thumbnail height matches its XML_thumbnail_height value across the seven-day schedule', f"Each asset thumbnail's actual height should match the XML_thumbnail_height value throughout the seven-day schedule.", 'Passed', f'The actual thumbnail height matches the XML_thumbnail_height value for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append( helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail aspect ratio for all assets across the seven-day schedule', f'Every asset thumbnail should have a 16:9 aspect ratio throughout the seven-day schedule.', 'Failed', f'One or more asset thumbnails do not have the required 16:9 aspect ratio.', ','.join(map(str, results[12]))) if results[12] else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail aspect ratio for all assets across the seven-day schedule', f'Every asset thumbnail should have a 16:9 aspect ratio throughout the seven-day schedule.', 'Not Tested', f'The asset thumbnail is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[2]))) if results[2] else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail aspect ratio for all assets across the seven-day schedule', f'Every asset thumbnail should have a 16:9 aspect ratio throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail aspect ratio for all assets across the seven-day schedule', f'Every asset thumbnail should have a 16:9 aspect ratio throughout the seven-day schedule.', 'Not Tested', f'The icon tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                              helper_fuc(sequence_number, 'Asset_Level', f'Verify the thumbnail aspect ratio for all assets across the seven-day schedule', f'Every asset thumbnail should have a 16:9 aspect ratio throughout the seven-day schedule.', 'Passed', f'Every asset thumbnail has the required 16:9 aspect ratio.'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Thumbnail validation')

                    logger.info(f'{ticket_id} Started Rating validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level',
                                                               validate_rating, 'rating', channel_level_language,
                                                               content_type)
                    logger.info(f'{ticket_id} Rating Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a rating source for all assets across the seven-day schedule', f'A rating source should be specified for every asset in the seven-day schedule.', 'Failed', f'A rating source is specified for every asset.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a rating source for all assets across the seven-day schedule', f'A rating source should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a rating source for all assets across the seven-day schedule', f'A rating source should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The rating tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a rating source for all assets across the seven-day schedule', f'A rating source should be specified for every asset in the seven-day schedule.', 'Passed', f'A rating source is specified for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source as per Samsung standard in all 7 days', f'Rating Source should present in Samsung_Supported_Rating_Source_List in all 7 days', 'Failed', f'One or more assets contain a rating source that is not permitted by the platform standards.', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source as per Samsung standard in all 7 days', f'Rating Source should present in Samsung_Supported_Rating_Source_List in all 7 days', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source as per Samsung standard in all 7 days', f'Rating Source should present in Samsung_Supported_Rating_Source_List in all 7 days', 'Not Tested', f'The rating tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Validate Rating Source as per Samsung standard in all 7 days', f'Rating Source should present in Samsung_Supported_Rating_Source_List in all 7 days', 'Passed', f'Every rating source is included in the Samsung-supported rating source list.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a rating value for all assets across the seven-day schedule', f'A rating value should be specified for every asset in the seven-day schedule.', 'Failed', f'The rating value is missing for one or more assets.', ','.join(map(str, results[4]))) if results[4] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a rating value for all assets across the seven-day schedule', f'A rating value should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a rating value for all assets across the seven-day schedule', f'A rating value should be specified for every asset in the seven-day schedule.', 'Not Tested', f'The rating tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of a rating value for all assets across the seven-day schedule', f'A rating value should be specified for every asset in the seven-day schedule.', 'Passed', f'A rating value is specified for every asset.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify that all rating values comply with Samsung standards across the seven-day schedule', f'Every rating value should be included in the Samsung_Supported_Rating_Value_List throughout the seven-day schedule.', 'Failed', f'One or more assets contain a rating value that is not permitted by the platform standard.', ','.join(map(str, results[5]))) if results[5] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that all rating values comply with Samsung standards across the seven-day schedule', f'Every rating value should be included in the Samsung_Supported_Rating_Value_List throughout the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that all rating values comply with Samsung standards across the seven-day schedule', f'Every rating value should be included in the Samsung_Supported_Rating_Value_List throughout the seven-day schedule.', 'Not Tested', f'The rating tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[1]))) if results[1] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify that all rating values comply with Samsung standards across the seven-day schedule', f'Every rating value should be included in the Samsung_Supported_Rating_Value_List throughout the seven-day schedule.', 'Passed', f'Every rating value is included in the Samsung-supported rating value list.'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Started Asset ID validation')
                    results = validate_programs_seven_days_xml(date_xml_data, sequence_number, 'Asset_Level',
                                                               validate_asset_title, 'episode-num', channel_level_language,
                                                               content_type, expected_length = 50, content_type_list=content_type_list)
                    logger.info(f'{ticket_id} Asset ID Results: {results}')

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an asset ID for all assets across the seven-day schedule', f'An asset ID should be present for every asset in the seven-day schedule.', 'Failed', f'The asset ID is missing for one or more assets.', ','.join(map(str, results[2]))) if results[2] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an asset ID for all assets across the seven-day schedule', f'An asset ID should be present for every asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an asset ID for all assets across the seven-day schedule', f'An asset ID should be present for every asset in the seven-day schedule.', 'Not Tested', f'The asset ID tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an asset ID for all assets across the seven-day schedule', f'An asset ID should be present for every asset in the seven-day schedule.', 'Passed', f'Asset ID is available for all assets'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the asset ID length across the seven-day schedule', f'No asset ID should exceed 50 characters in the seven-day schedule.', 'Failed', f'One or more asset IDs exceed the maximum permitted length of 50 characters.', ','.join(map(str, results[6]))) if results[6] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the asset ID length across the seven-day schedule', f'No asset ID should exceed 50 characters in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the asset ID length across the seven-day schedule', f'No asset ID should exceed 50 characters in the seven-day schedule.', 'Not Tested', f'The asset ID tag is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[8]))) if results[8] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the asset ID length across the seven-day schedule', f'No asset ID should exceed 50 characters in the seven-day schedule.', 'Passed', f'Every asset ID is within the permitted limit of 50 characters.'))

                    sequence_number = sequence_number + 1

                    Validation_Output.append(helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an episode number for all applicable assets across the seven-day schedule', f'An episode number should be specified for every applicable asset in the seven-day schedule.', 'Failed', f'The episode number is missing for one or more applicable assets.', ','.join(map(str, results[3]))) if results[3] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an episode number for all applicable assets across the seven-day schedule', f'An episode number should be specified for every applicable asset in the seven-day schedule.', 'Not Tested', f'The main programme field is unavailable; therefore, the related test cases were not run.', ','.join(map(str, results[0]))) if results[0] else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an episode number for all applicable assets across the seven-day schedule', f'An episode number should be specified for every applicable asset in the seven-day schedule.', 'Not Tested', f'The episode-number test case was not run because its prerequisite test cases failed.', ','.join(map(str, results[7]))) if results[7] and any(episode) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an episode number for all applicable assets across the seven-day schedule', f'An episode number should be specified for every applicable asset in the seven-day schedule.', 'Not Applicable', 'The episode-number test case does not apply to non-episodic assets.', ','.join(map(str, results[7]))) if results[7] and all(others) else
                                             helper_fuc(sequence_number, 'Asset_Level', f'Verify the presence of an episode number for all applicable assets across the seven-day schedule', f'An episode number should be specified for every applicable asset in the seven-day schedule.', 'Passed', f'An episode number is specified for every applicable asset.'))

                    sequence_number = sequence_number + 1

                    logger.info(f'{ticket_id} Finished Asset ID validation')




                    logger.info(f'{ticket_id} Validation Output: {Validation_Output}')
                    apply_priorities_to_validation_output(Validation_Output)
                    excel_path = xlsx_report(Validation_Output, report_path)

                    # Push to DB and fetch today's result after Excel, before failed-case separator
                    mongo_fetched = _store_and_fetch_mongo_non_ssai(
                        ticket_id=ticket_id,
                        channel_name=channel_name,
                        content_partner_name=content_partner_name,
                        url=url,
                        pipeline_status="SUCCESS",
                        input_start=input_start,
                        drive_link=drive_link,
                        s3_html_url=s3_html_url,
                    )
                    logger.info(
                        "%s Mongo fetched result returned: %s",
                        ticket_id,
                        mongo_fetched,
                    )

                    updated_summary_list = failed_cases_seperator(mongo_fetched)
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
                    status = "FAILED" if 'Failed' in str(Validation_Output) else "SUCCESS"
                    #filtered_list = failed_cases_seperator()
                    #logger.info(f"filtered_list: {filtered_list}")
                else:
                    logger.info(f'{ticket_id} Validation Output when there is no xml data: {Validation_Output}')
                    apply_priorities_to_validation_output(Validation_Output)
                    excel_path = xlsx_report(Validation_Output, report_path)

                    # Push to DB and fetch today's result after Excel, before failed-case separator
                    mongo_fetched = _store_and_fetch_mongo_non_ssai(
                        ticket_id=ticket_id,
                        channel_name=channel_name,
                        content_partner_name=content_partner_name,
                        url=url,
                        pipeline_status="SUCCESS",
                        input_start=input_start,
                        drive_link=drive_link,
                        s3_html_url=s3_html_url,
                    )
                    logger.info(
                        "%s Mongo fetched result returned: %s",
                        ticket_id,
                        mongo_fetched,
                    )

                    updated_summary_list = failed_cases_seperator(mongo_fetched)
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
                    status = "FAILED" if 'Failed' in str(Validation_Output) else "SUCCESS"
                    # filtered_list = failed_cases_seperator()
                    # logger.info(f"filtered_list: {filtered_list}")

            except Exception as e:
                 logger.error(f'{ticket_id} Exception: {e}')
                 _store_and_fetch_mongo_non_ssai(
                     ticket_id=ticket_id,
                     channel_name=channel_name,
                     content_partner_name=content_partner_name,
                     url=url,
                     pipeline_status="FAILED",
                     input_start=input_start,
                     drive_link=drive_link,
                     s3_html_url=s3_html_url,
                 )
                 return {"status":"FAILED",
                        "xml_url":url,
                        "drive_link":drive_link,
                        "s3_html_url":s3_html_url}
        else:
            logger.info(f'{ticket_id} Validation Output when there is no xml data: {Validation_Output}')
            apply_priorities_to_validation_output(Validation_Output)
            excel_path = xlsx_report(Validation_Output, report_path)

            # Push to DB and fetch today's result after Excel, before failed-case separator
            mongo_fetched = _store_and_fetch_mongo_non_ssai(
                ticket_id=ticket_id,
                channel_name=channel_name,
                content_partner_name=content_partner_name,
                url=url,
                pipeline_status="SUCCESS",
                input_start=input_start,
                drive_link=drive_link,
                s3_html_url=s3_html_url,
            )
            logger.info(
                "%s Mongo fetched result returned: %s",
                ticket_id,
                mongo_fetched,
            )

            updated_summary_list = failed_cases_seperator(mongo_fetched)
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
            status = "FAILED" if 'Failed' in str(Validation_Output) else "SUCCESS"
            # filtered_list = failed_cases_seperator()
            # logger.info(f"filtered_list: {filtered_list}")
    elif url.endswith('.json'):
        logger.info(f'{ticket_id} JSON Template')
        Validation_Output.append(helper_fuc(sequence_number, 'URL', 'Verify the URL content format', 'The URL should point to content in XML format.', 'Passed','The URL points to content in XML format.'))
        sequence_number = sequence_number + 1
    else:
        Validation_Output.append(helper_fuc(sequence_number, 'URL', 'Verify the URL content format', 'The URL should point to content in XML format.', 'Failed','The URL points to content not in XML format.'))

    return {"status": status,
            "xml_url":url,
            "drive_link":drive_link,
            "s3_html_url":s3_html_url}
