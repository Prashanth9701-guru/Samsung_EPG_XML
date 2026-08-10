import gspread
import logging
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

#from dotenv import load_dotenv
import os

#load_dotenv(".env.local")

logger = logging.getLogger("__name__")


SPREADSHEET_ID = os.environ.get("GOOGLE_DATA_SPREADSHEET_ID",
    "1tYuX0SLiNPl6Eg_fK9NwExsn2OIh1dNQCShCD9vdhxM")
#SHEET_GID = os.environ.get("GOOGLE_DATA_GID", "1693805805")
SHEET_GID = os.environ.get("GOOGLE_DATA_GID", "2021280443")
#SA_JSON = os.environ.get("GDRIVE_SA_JSON") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
SA_JSON = os.environ.get("GDRIVE_SA_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID")


print(f'Service JSON: {SA_JSON}')

def validation_data():

    scope =["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"]


    creds = Credentials.from_service_account_file(SA_JSON, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID)

    worksheet = sheet.get_worksheet_by_id(0)
    sheet_data = worksheet.get_all_records()
    logger.info(f'Sheet_Data: {sheet_data}')
    # result = sheet.spreadsheets().values().get(
    #     spreadsheetId=0,
    #     range="Sheet1!1:1"
    # ).execute()

    headers = worksheet.row_values(1)
    logger.info(f'Headers: {headers}')
    today = datetime.now().strftime("%d-%b-%Y")
    new_column_number = len(headers) + 1
    # today_date = datetime.today().strftime('%Y-%m-%d')
    # worksheet.update_cell(1, new_column_number, today)


    return sheet_data, worksheet, new_column_number, sheet, today


