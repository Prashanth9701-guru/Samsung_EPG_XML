"""Google Sheet helpers / constants for Samsung SSAI AN3.

Phase 2 uses Drive folder constant. Full sheet I/O is used in Phase 3.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

SPREADSHEET_ID = os.environ.get(
    "CONTROL_SHEET_URL",
    os.environ.get(
        "CONTROL_SHEET_URL",
        "1tYuX0SLiNPl6Eg_fK9NwExsn2OIh1dNQCShCD9vdhxM",
    ),
)
SSAI_INPUT_SHEET_GID = int(os.environ.get("CONTROL_SHEET_GID", "1350788501"))
SSAI_RESULTS_SHEET_GID = int(os.environ.get("HISTORY_SHEET_GID", "852742931"))
SSAI_DRIVE_FOLDER_ID = os.environ.get(
    "DRIVE_PARENT_FOLDER_ID",
    "1HKNF6C1wpfz6E4kw5AAFf4N08TSV_Q-p",
)
SA_JSON = os.environ.get("GDRIVE_SA_JSON") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

slack_channel = os.environ.get("SLACK_CHANNEL")
build_number = os.environ.get("BUILD_NUMBER")
build_url = os.environ.get("BUILD_URL")

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _authorize_client():
    import gspread
    from google.oauth2.service_account import Credentials

    if not SA_JSON:
        raise RuntimeError(
            "Google service account JSON path not set "
            "(GDRIVE_SA_JSON or GOOGLE_SERVICE_ACCOUNT_JSON)"
        )
    creds = Credentials.from_service_account_file(SA_JSON, scopes=_SCOPES)
    return gspread.authorize(creds)


def ssai_validation_data() -> Tuple[List[dict], Any, int, Any, str, str]:
    """Read SSAI input sheet (gid 1350788501). Used by Phase 3 runner."""
    try:
        client = _authorize_client()
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.get_worksheet_by_id(SSAI_INPUT_SHEET_GID)
        sheet_data = worksheet.get_all_records()
        logger.info(
            "SSAI input sheet loaded gid=%s rows=%s",
            SSAI_INPUT_SHEET_GID,
            len(sheet_data),
        )

        headers = worksheet.row_values(1)
        today = datetime.now().strftime("%Y-%m-%d")
        today_format = datetime.now().strftime("%d-%b-%Y")
        new_column_number = (
            len(headers) + 1
            if str(today) not in headers and str(today_format) not in headers
            else len(headers)
        )
        return sheet_data, worksheet, new_column_number, spreadsheet, today, today_format
    except Exception as exc:
        logger.error("SSAI Google Sheet unavailable / read failed: %s", exc)
        raise


def get_ssai_results_worksheet(spreadsheet) -> Any:
    return spreadsheet.get_worksheet_by_id(SSAI_RESULTS_SHEET_GID)


def append_ssai_execution_result(spreadsheet, row_values: List[Any]) -> bool:
    try:
        results_ws = get_ssai_results_worksheet(spreadsheet)
        results_ws.append_row(row_values, value_input_option="USER_ENTERED")
        logger.info("SSAI results sheet row appended values_count=%s", len(row_values))
        return True
    except Exception as exc:
        logger.error("SSAI results sheet update failed (non-fatal): %s", exc)
        return False


def update_ssai_current_day_status(
    worksheet,
    row_index: int,
    column_number: int,
    status: str,
    today_header: Optional[str] = None,
) -> bool:
    try:
        header = today_header or datetime.now().strftime("%d-%b-%Y")
        worksheet.update_cell(1, column_number, header)
        worksheet.update_cell(row_index + 2, column_number, status)
        logger.info(
            "SSAI current-day status updated row=%s col=%s status=%s",
            row_index + 2,
            column_number,
            status,
        )
        return True
    except Exception as exc:
        logger.error("SSAI current-day status update failed (non-fatal): %s", exc)
        return False
