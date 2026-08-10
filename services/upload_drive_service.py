import os
import shutil

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from services.gsheet_service import *

#SA_JSON = "service_account.json"

# SCOPES = [
#     "https://www.googleapis.com/auth/drive"
# ]
#
# creds = Credentials.from_service_account_file(
#     SA_JSON,
#     scopes=SCOPES
# )

print(f'SA_JSON: {SA_JSON}')

SCOPES = [
    "https://www.googleapis.com/auth/drive",
]


creds = Credentials.from_service_account_file(SA_JSON, scopes=SCOPES)

service = build(
    "drive",
    "v3",
    credentials=creds
)


def zip_folder(folder_path, output_path):
    zip_file = shutil.make_archive(
        output_path,
        "zip",
        folder_path
    )

    print(f"ZIP created: {zip_file}")

    return zip_file


def upload_to_drive(zip_file, drive_folder_id):

    file_metadata = {
        "name": os.path.basename(zip_file),
        "parents": [drive_folder_id]
    }
    print(f'File_Metadata completed')
    media = MediaFileUpload(
        zip_file,
        mimetype="application/octet-stream",
        resumable=True
    )

    print(f'Media also completed')

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True
    ).execute()

    print(f"Uploaded: {uploaded_file['name']}")
    print(f"File ID: {uploaded_file['id']}")
    print(f"Link: {uploaded_file['webViewLink']}")

    return uploaded_file['webViewLink']