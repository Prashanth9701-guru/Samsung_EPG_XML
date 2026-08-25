"""Samsung SSAI AN3 EPG validation runner (control sheet → ssai_template → results/Slack)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from services import slack_service
from services.amagi_api_service import get_oauth_token
from services.ssai_gsheet_service import (
    append_ssai_execution_result,
    build_number,
    build_url,
    slack_channel,
    ssai_validation_data,
    update_ssai_current_day_status,
)
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


def main() -> None:
    execution_results: List[Dict[str, Any]] = []
    session_start = datetime.today()

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
                continue

            results = ssai_template(
                stream_url=stream_url,
                ticket_id=ticket_id,
                channel_name=channel_name,
                content_partner_name=partner,
                token=token,
            )

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


if __name__ == "__main__":
    set_up_log()
    main()
