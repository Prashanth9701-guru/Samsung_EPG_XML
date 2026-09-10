"""Samsung SSAI AN3 EPG validation runner (control sheet → ssai_template → results/Slack)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from services import mongo_service
from services import slack_service
from services.amagi_api_service import get_oauth_token
from services.ssai_gsheet_service import ssai_appened_data
from services.jira_service import ssai_jira_fetch
from services.ssai_gsheet_service import (
    append_ssai_execution_result,
    build_number,
    build_url,
    slack_channel,
    ssai_validation_data,
    update_ssai_current_day_status,
)
from utilities.helper import Validation_Output
from utilities.logger_setup import set_up_log
from utilities.ssai_master_template import ssai_template

logger = logging.getLogger(__name__)


def _field(row: Dict[str, Any], *keys: str, default: str = "") -> str:
    """Return first non-empty value among preferred sheet header keys."""
    for key in keys:
        if key in row and row.get(key) is not None and str(row.get(key)).strip() != "":
            return str(row.get(key)).strip()
    return default


def _is_now3_stream_url(stream_url: str) -> bool:
    """True for now3 playout URLs (avoid matching substrings like 'no-now3')."""
    u = (stream_url or "").lower()
    return "playout.now3" in u or ".now3." in u


def _is_run_eligible(row: Dict[str, Any], today: str, today_format: str) -> bool:
    run_stop = _field(row, "RUN/STOP", "RUN_STOP")
    if run_stop.upper() != "RUN":
        return False
    if row.get(today_format) == "✔" or row.get(today) == "✔":
        return False
    return True


def _row_inputs(row: Dict[str, Any]) -> Dict[str, str]:
    return {
        "stream_url": _field(row, "Stream URL", "Stream_URL", "STREAM_URL"),
        "ticket_id": _field(row, "Ticket ID", "Ticket_ID", "PSD", "Ticket Id"),
        "channel_name": _field(row, "Channel Name", "Channel_Name"),
        "content_partner_name": _field(
            row, "Content Partner Name", "Content_Partner_Name", "Content Partner"
        ),
        "epg_delivery": _field(
            row, "EPG Delivery Status", "EPG_Delivery_Status", "EPG Delivery"
        ),
        "run_stop": _field(row, "RUN/STOP", "RUN_STOP"),
    }


def _is_ssai_executable(row: Dict[str, Any], today: str, today_format: str) -> bool:
    """True when the row would enter the AN3/now3 execution path (incl. missing-field FAIL)."""
    if not _is_run_eligible(row, today, today_format):
        return False
    fields = _row_inputs(row)
    if fields["epg_delivery"].strip().upper() != "AN3":
        return False
    if not _is_now3_stream_url(fields["stream_url"]):
        return False
    return True


def _store_ssai_mongo_result(
    *,
    execution_date: str,
    input_name: str,
    pipeline_status: str,
    input_start: datetime,
    input_end: datetime,
    ticket_id: str = "",
    row_index: int = 0,
    input_url: str = "",
    partner: str = "",
    html_link: str = "",
    drive_link: str = "",
) -> None:
    try:
        validation_snapshot = list(Validation_Output)
        mongo_status = mongo_service.normalize_input_status(
            pipeline_status, validation_snapshot
        )
        resolved_ticket = (ticket_id or "").strip() or f"row_{row_index}"
        payload = mongo_service.build_input_payload(
            input_name=input_name,
            status=mongo_status,
            execution_start_time=input_start,
            execution_end_time=input_end,
            result=validation_snapshot,
            ticket_id=resolved_ticket,
            input_url=input_url,
            partner=partner,
            html_link=html_link,
            drive_link=drive_link,
        )
        mongo_service.store_input_result(
            mongo_service.PIPELINE_SSAI,
            payload,
            execution_date=execution_date,
        )
        try:
            mongo_service.fetch_and_log_today_input(
                mongo_service.PIPELINE_SSAI,
                resolved_ticket,
                execution_date=execution_date,
            )
        except Exception as fetch_exc:
            logger.error(
                "Mongo fetch_and_log_today_input failed (non-fatal): %s",
                fetch_exc,
            )
    except Exception as exc:
        logger.error("Mongo store_input_result failed (non-fatal): %s", exc)


def main() -> None:
    execution_results: List[Dict[str, Any]] = []
    session_start = datetime.today()
    execution_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ticket_data = ssai_jira_fetch()
    ssai_appened_data(ticket_data)
    token = get_oauth_token()
    if not token:
        logger.warning("Initial OAuth token is missing; ssai_template may refresh per channel")

    try:
        sheet_data, worksheet, new_column_number, spreadsheet, today, today_format = (
            ssai_validation_data()
        )
    except Exception as exc:
        logger.error("SSAI control sheet unavailable — aborting run: %s", exc)
        return

    eligible_count = sum(
        1 for row in sheet_data if _is_ssai_executable(row, today, today_format)
    )
    try:
        mongo_service.init_daily_execution(
            mongo_service.PIPELINE_SSAI,
            eligible_count,
            execution_date=execution_date,
            build_number=build_number,
            build_url=build_url,
        )
    except Exception as exc:
        logger.error("Mongo init failed (non-fatal): %s", exc)

    for inx, data in enumerate(sheet_data):
        try:
            if not _is_run_eligible(data, today, today_format):
                logger.info(
                    "Skipping row index=%s (not RUN or already ✔ for today)",
                    inx,
                )
                continue

            fields = _row_inputs(data)
            stream_url = fields["stream_url"]
            ticket_id = fields["ticket_id"]
            channel_name = fields["channel_name"]
            partner = fields["content_partner_name"]
            epg_delivery = fields["epg_delivery"]
            run_stop = fields["run_stop"]

            logger.info(
                "Eligible row index=%s ticket=%s channel=%s delivery=%s",
                inx,
                ticket_id,
                channel_name,
                epg_delivery,
            )

            # Branch: AN3 only
            if epg_delivery.strip().upper() != "AN3":
                logger.info(
                    "Stub skip (non-AN3) ticket=%s delivery=%s",
                    ticket_id,
                    epg_delivery,
                )
                continue

            # Branch: now3 Stream URL only
            if not _is_now3_stream_url(stream_url):
                logger.info(
                    "Stub skip (non-now3 Stream URL) ticket=%s url=%s",
                    ticket_id,
                    stream_url,
                )
                continue

            if not stream_url or not ticket_id:
                logger.error(
                    "Missing Stream URL or Ticket ID at row index=%s — marking FAILED",
                    inx,
                )
                input_start = datetime.now(timezone.utc)
                append_ssai_execution_result(
                    spreadsheet,
                    [
                        stream_url,
                        channel_name,
                        partner,
                        ticket_id,
                        epg_delivery,
                        datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
                        "FAILED",
                        "",
                        "",
                        run_stop,
                        build_number,
                        build_url,
                    ],
                )
                update_ssai_current_day_status(
                    worksheet, inx, new_column_number, "❌", today_header=today_format
                )
                execution_results.append(
                    {
                        "status": "FAILED",
                        "channel": channel_name or f"row_{inx}",
                        "html_link": "",
                        "json_link": "",
                    }
                )
                input_end = datetime.now(timezone.utc)
                _store_ssai_mongo_result(
                    execution_date=execution_date,
                    input_name=channel_name or f"row_{inx}",
                    pipeline_status="FAILED",
                    input_start=input_start,
                    input_end=input_end,
                    ticket_id=ticket_id,
                    row_index=inx,
                    input_url=stream_url,
                    partner=partner,
                )
                continue

            input_start = datetime.now(timezone.utc)
            results = ssai_template(
                stream_url=stream_url,
                ticket_id=ticket_id,
                channel_name=channel_name,
                content_partner_name=partner,
                token=token,
            )
            input_end = datetime.now(timezone.utc)

            status = (results or {}).get("status") or "FAILED"
            drive_link = (results or {}).get("drive_link") or ""
            s3_html_url = (results or {}).get("s3_html_url") or ""

            # Reuse refreshed token if master returned one in future; keep current for now
            append_ssai_execution_result(
                spreadsheet,
                [
                    stream_url,
                    channel_name,
                    partner,
                    ticket_id,
                    epg_delivery,
                    datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
                    status,
                    drive_link,
                    s3_html_url,
                    run_stop,
                    build_number,
                    build_url,
                ],
            )

            mark = "✔" if status == "PASSED" else "❌"
            update_ssai_current_day_status(
                worksheet, inx, new_column_number, mark, today_header=today_format
            )

            slack_status = "SUCCESS" if status == "PASSED" else status
            execution_results.append(
                {
                    "status": slack_status,
                    "channel": channel_name,
                    "html_link": s3_html_url,
                    "json_link": drive_link,
                }
            )
            logger.info(
                "Finished ticket=%s channel=%s status=%s",
                ticket_id,
                channel_name,
                status,
            )
            _store_ssai_mongo_result(
                execution_date=execution_date,
                input_name=channel_name or f"row_{inx}",
                pipeline_status=status,
                input_start=input_start,
                input_end=input_end,
                ticket_id=ticket_id,
                row_index=inx,
                input_url=stream_url,
                partner=partner,
                html_link=s3_html_url,
                drive_link=drive_link,
            )

        except Exception as exc:
            logger.error(
                "SSAI row index=%s failed (continuing): %s",
                inx,
                exc,
                exc_info=True,
            )
            try:
                fields = _row_inputs(data) if isinstance(data, dict) else {}
                append_ssai_execution_result(
                    spreadsheet,
                    [
                        fields.get("stream_url", ""),
                        fields.get("channel_name", ""),
                        fields.get("content_partner_name", ""),
                        fields.get("ticket_id", ""),
                        fields.get("epg_delivery", ""),
                        datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
                        "FAILED",
                        "",
                        "",
                        fields.get("run_stop", ""),
                        build_number,
                        build_url,
                    ],
                )
                update_ssai_current_day_status(
                    worksheet, inx, new_column_number, "❌", today_header=today_format
                )
                execution_results.append(
                    {
                        "status": "FAILED",
                        "channel": fields.get("channel_name") or f"row_{inx}",
                        "html_link": "",
                        "json_link": "",
                    }
                )
                fail_end = datetime.now(timezone.utc)
                _store_ssai_mongo_result(
                    execution_date=execution_date,
                    input_name=fields.get("channel_name") or f"row_{inx}",
                    pipeline_status="FAILED",
                    input_start=fail_end,
                    input_end=fail_end,
                    ticket_id=fields.get("ticket_id", ""),
                    row_index=inx,
                    input_url=fields.get("stream_url", ""),
                    partner=fields.get("content_partner_name", ""),
                )
            except Exception as inner:
                logger.error("SSAI failure bookkeeping also failed: %s", inner)
            continue

    logger.info("SSAI Execution Results: %s", execution_results)
    try:
        slack_service.send_execution_summary(
            channel=slack_channel,
            execution_results=execution_results,
            build_number=build_number or None,
            build_url=build_url or None,
            build_start_time=session_start.strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as exc:
        logger.error("Slack summary failed (non-fatal): %s", exc)

    try:
        mongo_service.mark_daily_execution_completed(
            mongo_service.PIPELINE_SSAI,
            execution_date=execution_date,
        )
    except Exception as exc:
        logger.error("Mongo mark completed failed (non-fatal): %s", exc)


if __name__ == "__main__":
    set_up_log()
    main()
