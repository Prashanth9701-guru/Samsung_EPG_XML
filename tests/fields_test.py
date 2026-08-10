import logging
import yaml


logger = logging.getLogger(__name__)

config = yaml.safe_load(open('config.yaml'))

def validate_fields_availability(data, man_fields):

    status_pass = []
    status_fail = []
    for key in data.keys():
        if key in man_fields:
            status_pass.append(key)
        else:
            status_fail.append(key)

    if status_fail:
        return False, status_fail
    else:
        return True, status_pass



def validate_asset_fields_availability(programs, man_fields, mand_child_values, content_type):
    status_pass = []
    status_fail = []

    #programs_data = []

    programs_data = programs if isinstance(programs, list) else [programs]

    if programs_data:
        for program in programs_data:
            logger.info(f'Entered program validation')
            asset_id = ''
            if isinstance(program.get('episode-num'), list):
                asset_id = next(episode.get('#text') for episode in program.get('episode-num') if episode.get('@system') == 'assetID')
            elif isinstance(program.get('episode-num'), dict):
                asset_id = (program.get('episode-num')).get('#text') if (program.get('episode-num')).get('@system') == 'assetID' else 'Asset_ID not available'

            logger.info(f'Asset ID: {asset_id}')
            if content_type.lower() == 'episode':
                asset_keys = list(program.keys())
                episode_num = next(True for episode in program.get('episode-num') if episode.get('@system') in mand_child_values) if isinstance(program.get('episode-num'), list) else 'episode-num-onscreen'

                not_available_keys = [key for key in config.get(content_type.lower()) if key not in asset_keys]
                if not isinstance(episode_num, bool):
                    not_available_keys.append(episode_num)

                if not_available_keys:
                    status_fail.append({asset_id: not_available_keys})

                else:
                    status_pass.append(asset_id)

            else:
                asset_keys = list(program.keys())
                not_available_keys = [key for key in config.get(content_type.lower()) if key not in asset_keys]
                if not_available_keys:
                    status_fail.append({asset_id: not_available_keys})

                else:
                    status_pass.append(asset_id)

        # elif isinstance(programs, dict):
        #     asset_id = ''
        #     if isinstance(programs.get('episode-num'), list):
        #         asset_id = next(episode.get('#text') for episode in programs.get('episode-num') if episode.get('@system') == 'assetID')
        #     elif isinstance(programs.get('episode-num'), dict):
        #         asset_id = (programs.get('episode-num')).get('#text') if (programs.get('episode-num')).get('@system') == 'assetID' else 'Asset_ID not available'
        #
        #     logger.info(f'Asset ID: {asset_id}')
        #     if content_type.lower() == 'episode':
        #         asset_keys = list(programs.keys())
        #         episode_num = next(True for episode in programs.get('episode-num') if episode.get('@system') in mand_child_values) if isinstance(programs.get('episode-num'), list) else 'episode-num-onscreen'
        #
        #         not_available_keys = [key for key in config.get(content_type.lower()) if key not in asset_keys]
        #         if not isinstance(episode_num, bool):
        #             not_available_keys.append(episode_num)
        #
        #         if not_available_keys:
        #             status_fail.append({asset_id: not_available_keys})
        #
        #         else:
        #             status_pass.append(asset_id)
        #
        #     else:
        #         asset_keys = list(programs.keys())
        #         not_available_keys = [key for key in config.get(content_type.lower()) if key not in asset_keys]
        #         if not_available_keys:
        #             status_fail.append({asset_id: not_available_keys})
        #
        #         else:
        #             status_pass.append(asset_id)


    if status_fail:
        return False, status_fail
    elif status_pass:
        return True, status_pass

    return False, None
