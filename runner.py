from datetime import datetime, timezone

from services import slack_service
from services import mongo_service
from services.amagi_api_service import get_oauth_token
from services.gsheet_service import validation_data
from services.jira_service import non_ssai_jira_fetch
from utilities.helper import *
from utilities.logger_setup import *
from utilities.master_template import *


def _is_non_ssai_eligible(data, today, today_format):
    return data.get('RUN/STOP') == 'RUN' and (
        data.get(today_format) != '✔' and data.get(today) != '✔'
    )


def main():
    execution_results = []
    ticket_data = non_ssai_jira_fetch()
    non_ssai_appened_data(ticket_data)
    token = get_oauth_token()
    sheet_data, work_sheet, new_column_number, sheet_service, today, today_format = validation_data()
    session_start = datetime.today()
    execution_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    eligible_count = sum(
        1 for data in sheet_data if _is_non_ssai_eligible(data, today, today_format)
    )
    try:
        mongo_service.init_daily_execution(
            mongo_service.PIPELINE_NON_SSAI,
            eligible_count,
            execution_date=execution_date,
            build_number=build_number,
            build_url=build_url,
        )
    except Exception as exc:
        logger.error("Mongo init failed (non-fatal): %s", exc)

    for inx, data in enumerate(sheet_data):
        Validation_Output.clear()
        if _is_non_ssai_eligible(data, today, today_format):
            content_type = (data.get('ASSET_TYPES_SUPPORTED')).lower() if (data.get('ASSET_TYPES_SUPPORTED')).lower() == 'episode' else 'others'
            input_start = datetime.now(timezone.utc)
            results = template(data.get('EPG_XML_URL'),
                               content_type,
                               data.get('PSD'),
                               data.get('Channel Name'),
                               data.get('Content Partner Name'),
                               token=token)
            input_end = datetime.now(timezone.utc)
            output = [data.get('EPG_XML_URL'),
                      data.get('Channel Name'),
                      data.get('Content Partner Name'),
                      data.get('PSD'),
                      data.get('ASSET_TYPES_SUPPORTED'),
                      datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
                      results.get('status'),
                      results.get('drive_link'),
                      results.get('s3_html_url'),
                      data.get('RUN/STOP'),
                      build_number,
                      build_url]

            execution_results.append({'status':results.get('status'),
                                     'channel':data.get('Channel Name'),
                                     'html_link':results.get('s3_html_url'),
                                     'json_link':results.get('drive_link')})

            for i in range(10):
                try:
                    work_sheet_2 = sheet_service.get_worksheet_by_id('653083829')
                    print(work_sheet_2.get_all_records())
                    row = len(work_sheet_2.get_all_records())+2
                    work_sheet_2.update(
                        range_name=f"A{row}:N{row}",
                        values=[output]
                    )
        
                    today_date = datetime.today().strftime("%d-%b-%Y")
                    if results.get('status') == 'SUCCESS':
                        work_sheet.update_cell(1, new_column_number, today_date)
                        work_sheet.update_cell(inx+2, new_column_number, "✔")
                    else:
                        work_sheet.update_cell(1, new_column_number, today_date)
                        work_sheet.update_cell(inx + 2, new_column_number, "❌")
                    break
                except requests.exceptions.ConnectionError as e:
                    logger.info(f"Connection error while accessing Google Sheets: {e}")

            try:
                validation_snapshot = list(Validation_Output)
                mongo_status = mongo_service.normalize_input_status(
                    results.get('status'), validation_snapshot
                )
                payload = mongo_service.build_input_payload(
                    input_name=data.get('Channel Name') or f"row_{inx}",
                    status=mongo_status,
                    execution_start_time=input_start,
                    execution_end_time=input_end,
                    result=validation_snapshot,
                    ticket_id=data.get('PSD') or "",
                    input_url=data.get('EPG_XML_URL') or "",
                    partner=data.get('Content Partner Name') or "",
                    html_link=results.get('s3_html_url') or "",
                    drive_link=results.get('drive_link') or "",
                )
                mongo_service.store_input_result(
                    mongo_service.PIPELINE_NON_SSAI,
                    payload,
                    execution_date=execution_date,
                )
            except Exception as exc:
                logger.error("Mongo store_input_result failed (non-fatal): %s", exc)
        else:
            logger.info(f'There is no Data to run for this day')

    logger.info(f'Execution Results: {execution_results}')
    try:
        slack_service.send_execution_summary(channel=slack_channel,
                                             execution_results=execution_results,
                                             build_number=build_number or None,
                                             build_url=build_url or None,
                                             build_start_time=session_start.strftime("%Y-%m-%d %H:%M:%S"),
                                            )
    except Exception as exc:
        logger.error("Slack summary failed (non-fatal): %s", exc)

    try:
        mongo_service.mark_daily_execution_completed(
            mongo_service.PIPELINE_NON_SSAI,
            execution_date=execution_date,
        )
    except Exception as exc:
        logger.error("Mongo mark completed failed (non-fatal): %s", exc)



if __name__ == '__main__':
    set_up_log()
    main()
