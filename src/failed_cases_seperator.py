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


def failed_cases_seperator(mongo_fetched):

    filtered_list = []
    updated_summary_list = []
    i = 1
    logger.info(f'Started Filtering of Failed Cases')
    for data in mongo_fetched:
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
            if 'One or more mandatory' in data.get('Issue Summary'):
                logger.info(f'Started Failed Case Separator 1')
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

                logger.info(f'completed common asset ids in Failed Case separator 1')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), data.get('Issue Summary').replace('One or more mandatory', f'In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, {', '.join(set(duplicate_values))}'), priority))
                logger.info(f'Completed Failed Case Separator 1')
                
            elif data.get('Issue Summary') == 'One or more assets have a start time in an invalid date-time format.' or data.get('Issue Summary') == 'One or more assets have a end time in an invalid date-time format.':
                logger.info(f'Started Failed Case Separator 2')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 2')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f'In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'} are having, invalid date-time format (Ex:{duplicate_values[0]}) which is not expected as per platform standard', priority))
                logger.info(f'Completed Failed Case Separator 2')
                
            elif 'in-correct-thumbnail' in data.get('Issue Summary') or 'in-correct-length' in data.get('Issue Summary'):
                logger.info(f'Started Failed Case Separator 3')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 3')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, {data.get('Issue Summary').replace('in-correct-thumbnail', f'{duplicate_values[0]}')}" if 'in-correct-thumbnail' in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, {data.get('Issue Summary').replace('in-correct-length', f'{duplicate_values[0]}')}", priority))
                logger.info(f'Completed Failed Case Separator 3')

            elif data.get('Issue Summary') == 'One or more asset thumbnails do not have the required 16:9 aspect ratio.':
                logger.info(f'Started Failed Case Separator 4')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 4')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, asset thumbnail having {duplicate_values[0]} aspect ratio. But, expected should be 16:9 aspect-ratio", priority))
                logger.info(f'Completed Failed Case Separator 4')


            elif data.get('Issue Summary') == 'One or more asset thumbnails are not in the required JPEG or JPG format.' or data.get('Issue Summary') == 'One or more asset thumbnails do not have the required resolution of 1920 × 1080 pixels.':
                logger.info(f'Started Failed Case Separator 5')
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
                logger.info(f'Completed common asset ids in Failed Case Separator 5')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset thumbnail is in {duplicate_values[0]} format. But, expected should be JPEG/JPG" if 'resolution' not in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset thumbnail having {duplicate_values[0]}. But, expected should be 1920 × 1080 pixels", priority))
                logger.info(f'Completed Failed Case Separator 5')






            elif data.get('Issue Summary') == 'One or more asset thumbnail URLs exceed the maximum permitted length of 2,000 characters.' or data.get('Issue Summary') == 'One or more asset IDs exceed the maximum permitted length of 50 characters.':
                logger.info(f'Started Failed Case Separator 6')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 6')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset thumbnail url length is {duplicate_values[0]} characters were exceed the permitted length of 2,000 characters" if 'thumbnail' in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset ID length is {duplicate_values[0]} characters were exceed the permitted length of 50 characters", priority))
                logger.info(f'Completed Failed Case Separator 6')

            elif data.get('Issue Summary') == 'One or more asset thumbnail requests return an unexpected HTTP status code.' or data.get('Issue Summary') == 'One or more asset thumbnail requests are redirected and return an unexpected HTTP status code.':
                logger.info(f'Started Failed Case Separator 7')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 7')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset thumbnail request getting {duplicate_values[0]} status code" if 'redirected' not in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset thumbnail request getting re-directed with {duplicate_values[0]} status code", priority))
                logger.info(f'Completed Failed Case Separator 7')






            elif data.get('Issue Summary') == "One or more asset titles exceed the maximum permitted length of 200 characters." or data.get('Issue Summary') == "One or more asset subtitles exceed the maximum permitted length of 200 characters." or data.get('Issue Summary') == 'One or more asset descriptions exceed the maximum permitted length of 4,000 characters.':
                logger.info(f'Started Failed Case Separator 8')
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

                loger.info(f'Completed common asset ids in Failed Case Separator 8')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset title having {duplicate_values[0]} chars exceed the maximum permitted length of 200 characters" if 'subtitles' not in data.get('Issue Summary') and 'descriptions' not in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Description having {duplicate_values[0]} chars exceed the maximum permitted length of 4,000 characters" if 'descriptions' in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset sub-title having {duplicate_values[0]} chars exceed the maximum permitted length of 200 characters", priority))
                logger.info(f'Completed Failed Case Separator 8')




            elif 'invalid content_type' in data.get('Issue Summary'):
                logger.info(f'Started Failed Case Separator 9')
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

                logger.info(f'Completed common asset ids in Failed Case Separator in 9')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, {data.get('Issue Summary').replace('invalid content_type', f'{duplicate_values[0]}')}", priority))
                logger.info(f'Completed Failed Case Separator 9')


            elif 'in-correct length' in data.get('Issue Summary') and 'proper-length' in data.get('Issue Summary'):
                logger.info(f'Started Failed Case Separator 10')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 10')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, {data.get('Issue Summary').replace('in-correct length', f'{duplicate_values[1]}').replace('proper-length', f'{duplicate_values[0]}')}", priority))
                logger.info(f'Completed Failed Case Separator 10')

            elif data.get('Issue Summary') == 'The actual thumbnail width does not match the XML_thumbnail_width value for one or more assets.' or data.get('Issue Summary') == 'The actual thumbnail height does not match the XML_thumbnail_height value for one or more assets.':
                logger.info(f'Started Failed Case Separator 11')
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

                logger.info(f'Completed common asset ids in Failed Case separator 11')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, actual asset thumbnail width {duplicate_values[1]} does not match with the XML_thumbnail width {duplicate_values[0]}" if 'width' in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, actual asset thumbnail height {duplicate_values[1]} does not match with the XML_thumbnail height {duplicate_values[0]}", priority))
                logger.info(f'Completed Failed Case Separator 11')



            elif data.get('Issue Summary') == 'The title_language and channel_language values do not match for one or more assets.' or data.get('Issue Summary') == 'The subtitle_language and channel_language values do not match for one or more assets.' or data.get('Issue Summary') == 'The description_language and channel_language values do not match for one or more assets.' or data.get('Issue Summary') == 'The category_language and channel_language values do not match for one or more assets.':
                logger.info(f'Started Failed Case Separator 12')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 12')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Title_language node having {duplicate_values[0]} does not match with the channel_level_language having {duplicate_values[1]}" if 'subtitle' not in data.get('Issue Summary') and 'description' not in data.get('Issue Summary') and 'category' not in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, description_language node having {duplicate_values[0]} does not match with the channel_level_language having {duplicate_values[1]}" if 'description' in data.get('Issue Summary') and 'category' not in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Category_language node having {duplicate_values[0]} does not match with the channel_level_language having {duplicate_values[1]}" if 'category' in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Subtitle_language node having {duplicate_values[0]} does not match with the channel_level_language having {duplicate_values[1]}", priority))
                logger.info(f'Completed Failed Case Separator 12')
            
            elif 'invalid' in data.get('Issue Summary'):
                logger.info(f'Started Failed Case Separator 13')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 13')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, {data.get('Issue Summary').replace('invalid', ', '.join(set(duplicate_values)))}", priority))
                logger.info(f'Completed Failed Case Separator 13')

            elif data.get('Issue Summary') == 'One or more assets contain categories that are not included in the Samsung_Supported_Category_List.':
                logger.info(f'Started Failed Case Separator 14')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 14')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, asset contain {', '.join(set(duplicate_values))} categories that are not included in Samsung_Supported_Category_List", priority))
                logger.info(f'Completed Failed Case Separator 14')


            
            elif 'in-correct-rating' in data.get('Issue Summary'):
                logger.info(f'Started Failed Case Separator 15')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 15')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, {data.get('Issue Summary').replace('in-correct-rating', ', '.join(set(duplicate_values)))}", priority))
                logger.info(f'Completed Failed Case Separator 15')

            elif data.get('Issue Summary') == 'One or more assets contain a rating source that is not permitted by the platform standards.' or data.get('Issue Summary') == 'One or more assets contain a rating value that is not included in the Samsung_Supported_Rating_Value_List.':
                logger.info(f'Started Failed Case Separator 16')
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

                logger.info(f'Completed common asset ids in Failed Case Separator 16')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset having (f{', '.join(set(duplicate_values))}) rating source that is not permitted by the platform standard" if 'rating source' in data.get('Issue Summary') else f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, Asset having (f{', '.join(set(duplicate_values))}) rating value that is not permitted by the platform standard", priority))
                logger.info(f'Completed Failed Case Separator 16')




                    

            elif data.get('Scenario').strip() == 'Verify that no asset shorter than 20 minutes (1,200 seconds) is scheduled across the seven-day schedule':
                logger.info(f'Started Failed Case Separator 17')
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, start_time, dur = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day, Scheduled asset duration is {dur} sec is less than expected limit of 20 minutes (1200 seconds) (Asset Scheduled Time: {start_time})", priority))
                logger.info(f'Completed Failed Case Separator 17')

            elif data.get('Scenario').strip() == 'Verify that no asset longer than 6 hours (21,600 seconds) is scheduled across the seven-day schedule':
                logger.info(f'Started Failed Case Separator 18')
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, start_time, dur = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day, Scheduled asset duration is {dur} sec is greater than expected limit of 6 hours (21600 seconds) (Asset Scheduled Time: {start_time})", priority))
                logger.info(f'Completed Failed Case Separator 18')

            elif data.get('Scenario').strip() == 'Verify that there are no scheduling gaps between assets across the seven-day schedule':
                logger.info(f'Started Failed Case Separator 19')
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, start_time, next_asset_end_time = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day, A scheduling gap is exists because an asset's start time({start_time}) does not match the previous asset's end time({next_asset_end_time})", priority))
                logger.info(f'Completed Failed Case Separator 19')
            
            elif data.get('Scenario').strip() == 'Verify that each asset duration in minutes matches its minutes value across the seven-day schedule':
                logger.info(f'Started Failed Case Separator 20')
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, xml_min, actual_dur_min = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day, asset having {xml_min} minutes that does not match the asset duration {actual_dur_min} minutes", priority))
                logger.info(f'Completed Failed Case Separator 20')

            elif data.get('Scenario').strip() == 'Validate Asset Duration in seconds match with Seconds Value in all 7 days':
                logger.info(f'Started Failed Case Separator 21')
                for asset_ids_data in list(ast.literal_eval(f"[{data.get('Asset IDs')}]")):
                    for key, value in asset_ids_data.items():
                        date, xml_sec, actual_dur_sec = value
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {date} day, asset having {xml_sec} seconds that does not match the asset duration {actual_dur_sec} seconds", priority))
                logger.info(f'Completed Failed Case Separator 21')
            
            else:
                logger.info(f'Started Failed Case Separator 22')
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
                logger.info(f'Completed common asset ids in Failed Case Separator 22')
                for key, Values in common_asset_ids.items():
                    duplicate_values = []
                    duplicate_values.extend(i for v in list(Values.values()) for i in v)
                    updated_summary_list.append(_failure_summary_entry(key, data.get('Module'), f"In {', '.join(list(Values.keys()))} {'days' if len(list(Values.keys())) > 1 else 'day'}, {data.get('Issue Summary')}", priority))
                logger.info(f'Completed Failed Case Separator 22')
        else:
            updated_summary_list.append(_failure_summary_entry('', data.get('Module'), data.get('Issue Summary'), priority))

    logger.info(f'Updated_Summary_List: {updated_summary_list}')
    logger.info(f'Failed Cases Filtering is completed successfully')

    return updated_summary_list




