import logging
import ast
from collections import defaultdict
from datetime import datetime, timedelta
from utilities.helper import *

logger = logging.getLogger(__name__)

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
                                  'Asset IDs': Asset_ID})
            i+= 1


    for data in filtered_list:
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
                    updated_summary_list.append({'Asset ID': key,
                                                 'Module': data.get('Module'),
                                                 'Issue Summary': data.get('Issue Summary').replace('Mandatory', f'In {', '.join(list(Values.keys()))} days, {', '.join(duplicate_values)}')})

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
                    updated_summary_list.append({'Asset ID': key,
                                                 'Module': data.get('Module'),
                                                 'Issue Summary': f'In {', '.join(list(Values.keys()))} days are having, wrong date format (Ex:{duplicate_values[0]}) which is not expected as per platform standard'})

            elif 'in-correct-thumbnail' in data.get('Issue Summary') or 'in-correct-length' in data.get('Issue Summary'):
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
                    updated_summary_list.append({'Asset ID': key,
                                                 'Module': data.get('Module'),
                                                 'Issue Summary': data.get('Issue Summary').replace('in-correct-thumbnail', f'{duplicate_values[0]}')})

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
                    updated_summary_list.append({'Asset ID': key,
                                                 'Module': data.get('Module'),
                                                 'Issue Summary': data.get('Issue Summary').replace('in-correct length', f'{duplicate_values[1]}').replace('proper-length', f'{duplicate_values[0]}')})

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
                    updated_summary_list.append({'Asset ID': key,
                                                 'Module': data.get('Module'),
                                                 'Issue Summary': data.get('Issue Summary').replace('lang value', f'{duplicate_values[0]}').replace('channel_lang_value', f'{duplicate_values[1]}')})

            elif 'in-correct-cat' in data.get('Issue Summary'):
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
                    updated_summary_list.append({'Asset ID': key,
                                                 'Module': data.get('Module'),
                                                 'Issue Summary': f"In {', '.join(list(Values.keys()))} days, {data.get('Issue Summary').replace('in-correct-cat', ', '.join(set(duplicate_values)))}"})

            elif data.get('Scenario').strip() == 'Validate less than 20 minutes (1200 seconds) of Assets are not scheduled in all 7 days':
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, start_time, dur = value
                        updated_summary_list.append({'Asset ID': key,
                                                     'Module': data.get('Module'),
                                                     'Issue Summary': f"In {date} day, Scheduled asset duration is {dur} sec which is less than 20 minutes (1200 seconds) (Asset Scheduled Time: {start_time})"})

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
                    updated_summary_list.append({'Asset ID': key,
                                                 'Module': data.get('Module'),
                                                 'Issue Summary': data.get('Issue Summary')})

        else:
            updated_summary_list.append({'Asset ID' : '',
                                         'Module' : data.get('Module'),
                                         'Issue Summary' : data.get('Issue Summary')})

    logger.info(f'Updated_Summary_List: {updated_summary_list}')
    logger.info(f'Failed Cases Filtering is completed successfully')

    return updated_summary_list




