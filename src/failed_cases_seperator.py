import logging
import ast
from collections import defaultdict
from datetime import datetime, timedelta
from utilities.helper import *

logger = logging.getLogger(__name__)

def _failure_summary_entry(asset_id, module, issue_summary, priority=''):
    return {
        'Asset ID': asset_id,
        'Module': module,
        'Issue Summary': issue_summary,
        'Priority': priority or '',
    }


def failed_cases_seperator():

    filtered_list = []
    updated_summary_list = []
    i = 1
    logger.info(f'Started Filtering of Failed Cases')
    for data in Validation_Output:
        module = data.get('Module')
        scenario = data.get('Scenario')
        status = data.get('Status')
        issue_summary = data.get('Issue Summary')
        Asset_ID = data.get('Asset IDs')

        if status == 'Failed':
            filtered_list.append({'S.No': i,
                                  'Module': module,
                                  'Scenario': scenario,
                                  'Issue Summary': issue_summary,
                                  'Asset IDs': Asset_ID,
                                  'Priority': data.get('Priority', '')})
            i+= 1


    for data in filtered_list:
        priority = data.get('Priority', '')
        if data.get('Module') not in ['URL', 'Channel_Level']:
            if 'Mandatory' in data.get('Issue Summary'):
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), data.get('Issue Summary').replace('Mandatory', f'In {', '.join(list(Values.keys()))} days, {', '.join(set(duplicate_values))}'), priority))

            elif 'Some assets are having wrong datetime format' in data.get('Issue Summary'):
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f'In {', '.join(list(Values.keys()))} days are having, wrong date format (Ex:{duplicate_values[0]}) which is not expected as per platform standard', priority))

            elif 'in-correct-thumbnail' in data.get('Issue Summary') or 'in-correct-length' in data.get('Issue Summary') or 'in-correct_content_type' in data.get('Issue Summary'):
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), data.get('Issue Summary').replace('in-correct-thumbnail', f'{duplicate_values[0]}') if 'in-correct-thumbnail' in data.get('Issue Summary') else data.get('Issue Summary').replace('in-correct-length', f'{duplicate_values[0]}'), priority))


            elif 'in-correct_content_type' in data.get('Issue Summary'):
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), data.get('Issue Summary').replace('in-correct_content_type', f'{duplicate_values[0]}'), priority))



            elif 'in-correct length' in data.get('Issue Summary') and 'proper-length' in data.get('Issue Summary'):
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), data.get('Issue Summary').replace('in-correct length', f'{duplicate_values[1]}').replace('proper-length', f'{duplicate_values[0]}'), priority))

            elif 'lang value' in data.get('Issue Summary') and 'channel_lang_value' in data.get('Issue Summary'):
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), data.get('Issue Summary').replace('lang value', f'{duplicate_values[0]}').replace('channel_lang_value', f'{duplicate_values[1]}'), priority))

            elif 'invalid' in data.get('Issue Summary'):
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} days, {data.get('Issue Summary').replace('invalid', ', '.join(set(duplicate_values)))}", priority))

            
            elif 'in-correct-rating' in data.get('Issue Summary'):
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} days, {data.get('Issue Summary').replace('in-correct-rating', ', '.join(set(duplicate_values)))}", priority))


                    

            elif data.get('Scenario').strip() == 'Validate less than 20 minutes (1200 seconds) of Assets are not scheduled in all 7 days':
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, start_time, dur = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day, Scheduled asset duration is {dur} sec which is less than 20 minutes (1200 seconds) (Asset Scheduled Time: {start_time})", priority))


            elif data.get('Scenario').strip() == 'Validate greater than 6 hours (21600 seconds) of Assets are not scheduled in all 7 days':
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, start_time, dur = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day, Scheduled asset duration is {dur} sec which is greater than 6 hours (21600 seconds) (Asset Scheduled Time: {start_time})", priority))


            elif data.get('Scenario').strip() == 'Validate schedule gap between Assets in all 7 days':
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, start_time, next_asset_end_time = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day, Current asset start time is {start_time} and Previous Asset End Time {next_asset_end_time} are not matching", priority))

            elif data.get('Scenario').strip() == 'Validate Asset Duration in minutes match with Minutes Value in all 7 days':
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, xml_min, actual_dur_min = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day,Actual asset duration {actual_dur_min} minutes and Duration in XML {xml_min} minutes are not matching", priority))


            elif data.get('Scenario').strip() == 'Validate Asset Duration in seconds match with Seconds Value in all 7 days':
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, xml_sec, actual_dur_sec = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day,Actual asset duration {actual_dur_sec} seconds and Duration in XML {xml_sec} seconds are not matching", priority))

            else:
                common_asset_ids = {}
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for date, ids in asset_ids_data.items():
                        for asset_ids in ids:
                            for asset_id, value in asset_ids.items():
                                if asset_id not in common_asset_ids:
                                    common_asset_ids[asset_id] = {}

                                if date not in common_asset_ids[asset_id]:
                                    common_asset_ids[asset_id][date] = []

                                common_asset_ids[asset_id][date].extend(v for v in value if v not in common_asset_ids[asset_id][date])

                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), data.get('Issue Summary'), priority))

        else:
            updated_summary_list.append(_failure_summary_entry('', data.get('Module'), data.get('Issue Summary'), priority))

    logger.info(f'Updated_Summary_List: {updated_summary_list}')
    logger.info(f'Failed Cases Filtering is completed successfully')

    return updated_summary_list




