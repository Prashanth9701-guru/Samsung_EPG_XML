"""SSAI AN3 channel orchestration: schedule API → fetch days → validate → reports."""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any, Dict, Optional

from services.ssai_gsheet_service import SSAI_DRIVE_FOLDER_ID
from services.ssai_schedule_api import fetch_schedule_with_token_retry
from services.xlsx_service import xlsx_report
from src.ssai_failed_cases_seperator import ssai_failed_cases_seperator
from tests.ssai_asset_validation import run_ssai_day_validations
from utilities.helper import Validation_Output, helper_fuc
from utilities.ssai_child_template import (
    create_ssai_report_dir,
    fetch_all_epg_days,
    record_epg_fetch_status,
)
from utilities.ssai_url_parser import parse_now3_stream_url

logger = logging.getLogger(__name__)


def _zip_report_folder(report_path: str) -> Optional[str]:
    """Zip report folder using shutil (avoids import-time Drive SA load)."""
    try:
        zip_file = shutil.make_archive(report_path, "zip", report_path)
        logger.info("SSAI ZIP created: %s", zip_file)
        return zip_file
    except Exception as exc:
        logger.warning("SSAI zip failed: %s", exc)
        return None


def _upload_drive(zip_file: str) -> str:
    if not zip_file:
        return ""
    try:
        from services.upload_drive_service import upload_to_drive

        return upload_to_drive(zip_file, SSAI_DRIVE_FOLDER_ID) or ""
    except Exception as exc:
        logger.warning("SSAI Drive upload failed (non-fatal): %s", exc)
        return ""


def _upload_s3_html(html_path: Optional[str]) -> str:
    if not html_path:
        return ""
    try:
        from services.S3_html_local import upload_html_report

        result = upload_html_report(html_path) or {}
        return result.get("report_url", "") or ""
    except Exception as exc:
        logger.warning("SSAI S3 HTML upload failed (non-fatal): %s", exc)
        return ""


def _has_failed_rows() -> bool:
    return any(row.get("Status") == "Failed" for row in Validation_Output)


def ssai_template(
    stream_url: str,
    ticket_id: str,
    channel_name: str,
    content_partner_name: str,
    token: Optional[str] = None,
    sequence_number: int = 1,
) -> Dict[str, Any]:
    """
    Run SSAI AN3 validation + reporting for one channel.

    Returns:
      {"status": "PASSED"|"FAILED", "stream_url", "drive_link", "s3_html_url", "report_path"}
    """
    drive_link = ""
    s3_html_url = ""
    report_path = ""

    try:
        Validation_Output.clear()
        num = sequence_number

        parsed = parse_now3_stream_url(stream_url)
        if not parsed.get("ok"):
            Validation_Output.append(
                helper_fuc(
                    num,
                    "URL",
                    "Validate now3 Stream URL ID parse",
                    "Stream URL should contain amg/channel/platform IDs",
                    "Failed",
                    parsed.get("error") or "parse failed",
                    "",
                )
            )
            report_path = create_ssai_report_dir(ticket_id)
            try:
                excel_path = xlsx_report(Validation_Output, report_path) if Validation_Output else None
                if excel_path:
                    from services.summary_report import summary_report_writer

                    summary_report_writer(
                        excel_path,
                        channel_name=channel_name,
                        content_partner_name=content_partner_name,
                        psd=ticket_id,
                        json_url=stream_url,
                        updated_summary_list=ssai_failed_cases_seperator(),
                    )
            except Exception as exc:
                logger.warning("%s Early report write failed: %s", ticket_id, exc)
            return {
                "status": "FAILED",
                "stream_url": stream_url,
                "drive_link": "",
                "s3_html_url": "",
                "report_path": report_path,
            }

        Validation_Output.append(
            helper_fuc(
                num,
                "URL",
                "Validate now3 Stream URL ID parse",
                "Stream URL should contain amg/channel/platform IDs",
                "Passed",
                f"Parsed amg_id={parsed['amg_id']} channel_id={parsed['channel_id']} "
                f"platform_id={parsed['platform_id']}",
                "",
            )
        )
        num += 1

        token, schedule_result = fetch_schedule_with_token_retry(
            amg_id=parsed["amg_id"],
            channel_id=parsed["channel_id"],
            platform_id=parsed["platform_id"],
            token=token,
            ticket_id=ticket_id,
        )

        report_path = create_ssai_report_dir(ticket_id)
        epg_urls = (schedule_result or {}).get("epg_urls") or {}

        if not schedule_result.get("ok"):
            Validation_Output.append(
                helper_fuc(
                    num,
                    "URL",
                    "Validate scheduling API / EPG delivery availability",
                    "GET /api/programs should return delivery_details.epg",
                    "Failed",
                    schedule_result.get("error") or "Data not available",
                    "",
                )
            )
            num += 1
            record_epg_fetch_status(num, {"ok": False, "by_date": {}, "failed_days": [], "dates_ok": []},
                                    ticket_id=ticket_id, epg_urls_empty=True)
        else:
            Validation_Output.append(
                helper_fuc(
                    num,
                    "URL",
                    "Validate scheduling API / EPG delivery availability",
                    "GET /api/programs should return delivery_details.epg",
                    "Passed",
                    f"EPG delivery URLs for dates: {', '.join(sorted(epg_urls.keys()))}",
                    "",
                )
            )
            num += 1

            if not epg_urls:
                num = record_epg_fetch_status(
                    num, {"ok": False, "by_date": {}, "failed_days": [], "dates_ok": []},
                    ticket_id=ticket_id, epg_urls_empty=True,
                )
            else:
                fetch_result = fetch_all_epg_days(
                    epg_urls=epg_urls,
                    report_path=report_path,
                    ticket_id=ticket_id,
                )
                num = record_epg_fetch_status(num, fetch_result, ticket_id=ticket_id)
                by_date = fetch_result.get("by_date") or {}
                if by_date:
                    num = run_ssai_day_validations(
                        by_date=by_date,
                        stream_url=stream_url,
                        sequence_number=num,
                        ticket_id=ticket_id,
                    )
                else:
                    logger.warning("%s No successful EPG days to validate", ticket_id)

        # --- Reporting ---
        excel_path = None
        html_path = None
        try:
            if Validation_Output:
                excel_path = xlsx_report(Validation_Output, report_path)
                logger.info("%s Excel report: %s", ticket_id, excel_path)
        except Exception as exc:
            logger.warning("%s Excel report failed: %s", ticket_id, exc)

        try:
            updated_summary_list = ssai_failed_cases_seperator()
            if excel_path:
                from services.summary_report import summary_report_writer

                html_path = summary_report_writer(
                    excel_path,
                    channel_name=channel_name,
                    content_partner_name=content_partner_name,
                    psd=ticket_id,
                    json_url=stream_url,
                    updated_summary_list=updated_summary_list,
                )
                logger.info("%s HTML report: %s", ticket_id, html_path)
        except Exception as exc:
            logger.warning("%s HTML report failed: %s", ticket_id, exc)

        zip_file = _zip_report_folder(report_path) if report_path else None
        drive_link = _upload_drive(zip_file) if zip_file else ""
        s3_html_url = _upload_s3_html(html_path)

        status = "FAILED" if _has_failed_rows() else "PASSED"

        logger.info(
            "%s ssai_template done status=%s drive=%s s3=%s path=%s",
            ticket_id,
            status,
            bool(drive_link),
            bool(s3_html_url),
            report_path,
        )
        return {
            "status": status,
            "stream_url": stream_url,
            "drive_link": drive_link,
            "s3_html_url": s3_html_url,
            "report_path": report_path,
        }

    except Exception as exc:
        logger.error("%s ssai_template unexpected error: %s", ticket_id, exc)
        return {
            "status": "FAILED",
            "stream_url": stream_url,
            "drive_link": drive_link,
            "s3_html_url": s3_html_url,
            "report_path": report_path,
        }
