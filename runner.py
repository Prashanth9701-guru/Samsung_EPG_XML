from datetime import datetime

from services import slack_service
from services.gsheet_service import validation_data
from utilities.helper import *
from utilities.logger_setup import *
from input import *
from utilities.master_template import *

Validation_Output = []



def main():
    execution_results = []
    sheet_data, work_sheet, new_column_number, sheet_service, today = validation_data()
    session_start = datetime.today()
    for inx, data in enumerate(sheet_data):
        if data.get('RUN/STOP') == 'RUN' and data.get(today) != '✔':
            content_type = data.get('ASSET_TYPES_SUPPORTED').lower() if data.get('ASSET_TYPES_SUPPORTED') == 'Episode' else 'others'
            results = template(data.get('EPG_XML_URL'),
                               content_type,
                               data.get('PSD'),
                               data.get('Channel Name'),
                               data.get('Content Partner Name'))
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



if __name__ == '__main__':
    set_up_log()
    main()
