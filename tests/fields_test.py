import logging
import yaml


logger = logging.getLogger(__name__)

config = yaml.safe_load(open('config.yaml'))

def validate_fields_availability(data, man_fields) -> tuple[bool, list]:

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


def _content_type_map(content_type_list) -> dict:
    """Flatten [{asset_id: content_type}, ...] into a single lookup dict."""
    mapping = {}
    for item in content_type_list or []:
        if isinstance(item, dict):
            mapping.update(item)
    return mapping


def validate_asset_fields_availability(programs, man_fields, mand_child_values, content_type, content_type_list=None) -> tuple[bool, list, list, list]:
    status_pass = []
    status_fail = []
    incorrect_content_type_pass = []
    incorrect_content_type_fail = []
    type_map = _content_type_map(content_type_list)

    programs_data = programs if isinstance(programs, list) else [programs]

    if programs_data:
        for program in programs_data:
            logger.info(f'Entered program validation')
            asset_id = ''
            if isinstance(program.get('episode-num'), list):
                asset_id = next((episode.get('#text') for episode in program.get('episode-num') if episode.get('@system') == 'assetID'), 'Asset_ID not available')
            elif isinstance(program.get('episode-num'), dict):
                asset_id = (program.get('episode-num')).get('#text') if (program.get('episode-num')).get('@system') == 'assetID' else 'Asset_ID not available'

            logger.info(f'Asset ID: {asset_id}')
            effective_ct = type_map.get(asset_id, content_type)
            config_key = 'episode' if 'episode' in str(effective_ct).lower() else 'others'
            logger.info(f'Asset ID: {asset_id} effective_content_type={effective_ct} config_key={config_key}')

            if 'episode' in str(effective_ct).lower():
                asset_keys = list(program.keys())
                episode_num = next(True for episode in program.get('episode-num') if episode.get('@system') in mand_child_values) if isinstance(program.get('episode-num'), list) else 'episode-num-onscreen'

                not_available_keys = [key for key in config.get(config_key) if key not in asset_keys]
                if not isinstance(episode_num, bool):
                    not_available_keys.append(episode_num)

                if not_available_keys:
                    status_fail.append({asset_id: not_available_keys})

                else:
                    status_pass.append(asset_id)

                # Separate incorrect-content-type check (episode from list missing sub-title/onscreen)
                if type_map and asset_id in type_map:
                    incorrect_keys = []
                    if 'sub-title' not in asset_keys:
                        incorrect_keys.append('sub-title')
                    if not isinstance(episode_num, bool):
                        incorrect_keys.append('onscreen')
                    if incorrect_keys:
                        incorrect_content_type_fail.append({asset_id: [type_map.get(asset_id)]})
                    else:
                        incorrect_content_type_pass.append(asset_id)

            else:
                asset_keys = list(program.keys())
                not_available_keys = [key for key in config.get(config_key) if key not in asset_keys]
                if not_available_keys:
                    status_fail.append({asset_id: not_available_keys})

                else:
                    status_pass.append(asset_id)


    if status_fail:
        return False, status_fail, incorrect_content_type_pass, incorrect_content_type_fail
    elif status_pass:
        return True, status_pass, incorrect_content_type_pass, incorrect_content_type_fail

    return False, [], incorrect_content_type_pass, incorrect_content_type_fail
