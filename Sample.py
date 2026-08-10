"""
import re

urls = [
    "https:epg_deliveries/amgplt0002/amg35787c2/amg35787c2Today.xml",
    "https:epg_deliveries/amgplt0002/amg35787c2/amg35787c2YYYY-MM-DD.xml"
]

pattern = r"\d{4}-\d{2}-\d{2}\.xml$"

for url in urls:
    if re.search(pattern, url):
        print(f"Passed: {url}")
    else:
        print(f"Failed: {url}")


day = ['2026-08-04', '2026-08-05', '2026-08-06', '2026-08-07']
url = ['https:epg_deliveries/amgplt0002/amg35787c2/amg35787c22026-08-04.xml',
       'https:epg_deliveries/amgplt0002/amg35787c2/amg35787c22026-08-05.xml',
       'https:epg_deliveries/amgplt0002/amg35787c2/amg35787c22026-08-06.xml',
       'https:epg_deliveries/amgplt0002/amg35787c2/amg35787c22026-08-07.xml']

print(list(zip(day, url)))

import requests
import xml.etree.ElementTree as ET

import xmltodict

url = "https://d31l2nn7dlh4li.cloudfront.net/amg02134/epg_deliveries/amgplt0001/amg02134c2/Donut2026-08-06.xml"

response = requests.get(url)
root = ET.fromstring(response.content)
data = xmltodict.parse(response.content)
print(data)

print(root.tag)
channels = root.findall('channel')
for channel in channels:
       channel_id = channel.get('id')
       print(channel_id)
       display = channel.find('display-name')
       print(display.text)
       icon = channel.find('icon')
       print(icon.attrib)

for program in root.findall('programme'):
       program_id = program.find('title')
       if program_id is not None:
              print(program_id.text)
              print(program_id.attrib)
       #for t in program_id:
              #print(t.text)
       episode = program.findall('episode-num')
       if episode is not None:
              for epi in episode:
                     print(f'Episode Name: {epi.text}')
                     print(f'Episode Number: {epi.attrib}')

       categories = program.findall('title')
       if categories:
              for category in categories:
                     print(f'title: {category.text}')
                     print(f'title_lang_tag: {category.attrib}')



import pycountry

language = pycountry.languages.get(name="Portuguese")
print(language)
"""
import ast
from datetime import datetime

"""
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from services.gsheet_service import *


def check_drive_folder(service, folder_id):

    try:
        folder = service.files().get(
            fileId=folder_id,
            fields="id, name, mimeType, driveId",
            supportsAllDrives=True
        ).execute()

        print("Folder ID:", folder["id"])
        print("Folder Name:", folder["name"])
        print("MIME Type:", folder["mimeType"])
        print("Drive ID:", folder.get("driveId"))

        return True

    except Exception as e:
        print("Unable to access Drive folder:")
        print(e)
        return False



SCOPES = [
    "https://www.googleapis.com/auth/drive",
]


creds = Credentials.from_service_account_file(SA_JSON, scopes=SCOPES)

service = build(
    "drive",
    "v3",
    credentials=creds
)

DRIVE_FOLDER_ID = "1HKNF6C1wpfz6E4kw5AAFf4N08TSV_Q-p"

check_drive_folder(
    service,
    DRIVE_FOLDER_ID
)




print(datetime.today().strftime("%Y%m%d_%H-%M-%S"))



data = "{'2026-08-09': [{'2dd1a790-8abe-11f1-b133-0fcbf9ba3b3a': ['sub-title', 'episode-num-onscreen']}, {'850124a0-8abe-11f1-b133-0fcbf9ba3b3a': ['sub-title', 'episode-num-onscreen']}]},{'2026-08-10': [{'dad16220-8bb6-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}, {'e2fdf940-8bb6-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}]},{'2026-08-11': [{'1f529d60-8bb7-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}, {'257de640-8bb7-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}]},{'2026-08-12': [{'437652e0-8bb7-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}, {'4b4ba240-8bb7-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}]},{'2026-08-13': [{'73b035c0-8bb7-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}, {'7aeceea0-8bb7-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}]},{'2026-08-14': [{'93d19ce0-8bb7-11f1-82d5-bf92f3ef2427': ['sub-title', 'episode-num-onscreen']}]}"


for i in list(ast.literal_eval(f"[{data}]")):
    for date, ids in i.items():
        for asset_id in ids:
            print(list(asset_id.keys()))
            print(list(asset_id.values()))
"""



common_asset_ids = {'CFE_825_08062026_STAPLES_DELLENGER_GODFREY': {'2026-08-09': ['sports talk'], '2026-08-10': ['sports talk']},'080726_tds_duncan_jones_rev1': {'2026-08-09': ['sports talk']},'575162d0-86ff-11f1-ae0e-3d973648d331-Segmented-1': {'2026-08-09': ['football']},'9ade7a10-86ff-11f1-ae0e-3d973648d331-Segmented-1': {'2026-08-09': ['football']},'2dd1a790-8abe-11f1-b133-0fcbf9ba3b3a': {'2026-08-09': ['Football', 'Live']},'YSMW_025_20260731_VID_v01': {'2026-08-09': ['sports talk'], '2026-08-10': ['sports talk']},
'850124a0-8abe-11f1-b133-0fcbf9ba3b3a': {'2026-08-09': ['Football', 'Live']}, 'PPRMock_v1': {'2026-08-09': ['sports talk']}, 'FB301-222-20260806-TiceWinks-VID-v01': {'2026-08-09': ['sports talk']}, '344736e0-f8a5-11f0-91fb-31740536d0d4-Segmented-1': {'2026-08-10': ['sports talk'], '2026-08-11': ['sports talk'], '2026-08-12': ['sports talk'], '2026-08-13': ['sports talk']}, 'dad16220-8bb6-11f1-82d5-bf92f3ef2427': {'2026-08-10': ['sports talk', 'Live']}, '03_14_26_IFL_Quad_at_Fishers_Full': {'2026-08-10': ['sports talk'], '2026-08-15': ['sports talk']}, 'e2fdf940-8bb6-11f1-82d5-bf92f3ef2427': {'2026-08-10': ['sports talk', 'Live']}, 'cf70f4a0-f623-11f0-a515-1f71a0abfb8a-Segmented-1': {'2026-08-10': ['sports talk'], '2026-08-11': ['sports talk'], '2026-08-12': ['sports talk'], '2026-08-13': ['sports talk'], '2026-08-14': ['sports talk']}, 'AAA-623-20250910-StaplesWasserman-v01': {'2026-08-11': ['sports talk'], '2026-08-12': ['sports talk'], '2026-08-13': ['sports talk'], '2026-08-14': ['sports talk'], '2026-08-15': ['sports talk']}, 'af7e1e80-70ac-11f1-bf5d-ffd414aa4144-Segmented-1': {'2026-08-11': ['sports talk'], '2026-08-12': ['sports talk'], '2026-08-13': ['sports talk'], '2026-08-14': ['sports talk']}, '1f529d60-8bb7-11f1-82d5-bf92f3ef2427': {'2026-08-11': ['sports talk', 'Live']}, 'KOC-116-OConnorIkoBaneLevitan-VIDFULL-09232025': {'2026-08-11': ['sports talk'], '2026-08-12': ['sports talk'], '2026-08-13': ['sports talk'], '2026-08-14': ['sports talk']}, 'Baseball_Bar-B-Cast_placeholder_asset': {'2026-08-11': ['sports talk'], '2026-08-13': ['sports talk'], '2026-08-15': ['sports talk']}, '257de640-8bb7-11f1-82d5-bf92f3ef2427': {'2026-08-11': ['sports talk', 'Live']}, 'YSMW_060526_VID_01': {'2026-08-11': ['sports talk'], '2026-08-14': ['sports talk'], '2026-08-15': ['sports talk']}, '437652e0-8bb7-11f1-82d5-bf92f3ef2427': {'2026-08-12': ['sports talk', 'Live']}, 'TDS-411-20251014-DuncanJones-VID-01': {'2026-08-12': ['sports talk'], '2026-08-15': ['sports talk']}, '4b4ba240-8bb7-11f1-82d5-bf92f3ef2427': {'2026-08-12': ['sports talk', 'Live']}, 'CFE-723-093025-StaplesDellengerGodfrey-VID-v01': {'2026-08-12': ['sports talk'], '2026-08-13': ['sports talk'], '2026-08-14': ['sports talk']}, '73b035c0-8bb7-11f1-82d5-bf92f3ef2427': {'2026-08-13': ['sports talk', 'Live']}, 'TBN-045-HaberstrohDevine-VID-10012025v2': {'2026-08-13': ['sports talk']}, '7aeceea0-8bb7-11f1-82d5-bf92f3ef2427': {'2026-08-13': ['sports talk', 'Live']}, 'THC-435-20250917-PicKell-v01': {'2026-08-14': ['sports talk']}, '93d19ce0-8bb7-11f1-82d5-bf92f3ef2427': {'2026-08-14': ['sports talk', 'Live']}, '091225_Hoops360_YT_FINAL': {'2026-08-14': ['sports talk']}}

for key, Values in common_asset_ids.items():
    duplicate_values = []
    print(', '.join(list(Values.keys())))
    print(list(Values.values()))
    duplicate_values.extend(i for v in list(Values.values()) for i in v)
    print(duplicate_values)


