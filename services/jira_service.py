import requests
import json

import yaml
from atlassian import Jira
import re

from requests.auth import HTTPBasicAuth


config = yaml.safe_load(open('config.yaml'))



def non_ssai_jira_fetch():

    jira = Jira(
        url=config["jira"]["base_url"],
        username=config["jira"]["username"],
        password=config["jira"]["api_token"]
    )

    default_jql = (
        f'project = {config["jira"]["project_key"]}'
        f' AND status IN ("QC BACKLOG", "QC RETEST")'#, "QC Retest", "QC Failed")'
        f' AND "Order Type[Short text]" !~ "VOD"'
    )
    jql = default_jql

    url = f'{config["jira"]["base_url"]}/rest/api/3/search/jql'

    headers = {
        "Accept": "application/json",
    }

    auth = HTTPBasicAuth(config["jira"]["username"], config["jira"]["api_token"])

    all_issues = []
    next_page_token = None

    ticket_data = []

    while True:

        query = {
            "jql": jql,
            "maxResults": 100,
            "fields": "*all"
        }

        if next_page_token:
            query["nextPageToken"] = next_page_token

        response = (requests.request("GET",
                                     url,
                                     headers=headers,
                                     params=query,
                                     auth=auth)).json()
        issues = response.get("issues", [])
        next_page_token = response.get("nextPageToken")
        if not issues:
            break

        for issue in issues:
            all_issues.append(issue.get('key'))

        if not next_page_token:
            break

        for issues in all_issues:

            issue = jira.issue(issues)
            fields = issue["fields"]
            if 'samsung' in (fields.get('customfield_11736', 'not_available')).lower():
                region_field = fields.get('customfield_12278')
                Delivery_region = ''
                for region in region_field:
                    Delivery_region = region.get('value', None)

                ticket_data.append({
                    "EPG_XML_URL": fields.get('customfield_11760', 'not_available'),
                    "Channel Name": fields.get('customfield_12211', 'not_available'),
                    "Content Partner Name": fields.get('customfield_11296', 'not_available'),
                    "PSD": f'https://amagiengg.atlassian.net/browse/{issues}',
                    "ASSET_TYPES_SUPPORTED": "Episode",
                    "RUN/STOP": "RUN"
                })



    return ticket_data