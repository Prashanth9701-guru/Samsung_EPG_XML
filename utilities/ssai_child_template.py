"""SSAI AN3 child helpers: report folder, multi-day EPG fetch, fetch-status rows."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from tests.ssai_json_fetch import fetch_epg_day_json
from utilities.helper import Validation_Output, helper_fuc

logger = logging.getLogger(__name__)


def create_ssai_report_dir(ticket_id: str, base_dir: Optional[str] = None) -> str:
    """Create reports/{ticket}_{timestamp}/ under the project root (or base_dir)."""
    ticket = str(ticket_id or "unknown").rstrip("/").split("/")[-1] or "unknown"
    timestamp = datetime.today().strftime("%Y%m%d_%H%M%S")
    if base_dir is None:
        base_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reports",
        )
    report_path = os.path.join(base_dir, f"{ticket}_{timestamp}")
    os.makedirs(report_path, exist_ok=True)
    logger.info("%s SSAI report_path=%s", ticket_id, report_path)
    return report_path


def fetch_all_epg_days(
    epg_urls: Dict[str, str],
    report_path: str,
    ticket_id: str = "",
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Fetch each delivery_details.epg URL; isolate failures per day.

    Returns:
      {
        "ok": bool,
        "by_date": {date: {"program": [...], "schedule": [...], "path": str}},
        "failed_days": [{"date", "status_code", "error"}, ...],
        "dates_ok": [...],
        "dates_failed": [...],
      }
    """
    prefix = f"{ticket_id} " if ticket_id else ""
    by_date: Dict[str, Dict[str, Any]] = {}
    failed_days: List[Dict[str, Any]] = []

    if not epg_urls:
        logger.warning("%sNo EPG URLs to fetch", prefix)
        return {
            "ok": False,
            "by_date": {},
            "failed_days": [{"date": None, "status_code": None, "error": "empty_epg_urls"}],
            "dates_ok": [],
            "dates_failed": [],
        }

    for date in sorted(epg_urls.keys()):
        url = epg_urls[date]
        try:
            day = fetch_epg_day_json(
                url=url,
                date=str(date),
                report_path=report_path,
                ticket_id=ticket_id,
                timeout=timeout,
            )
        except Exception as exc:
            logger.error("%sUnhandled fetch error date=%s: %s", prefix, date, exc)
            failed_days.append(
                {"date": str(date), "status_code": None, "error": f"unexpected: {exc}"}
            )
            continue

        if day.get("ok"):
            by_date[str(date)] = {
                "program": day.get("program") or [],
                "schedule": day.get("schedule") or [],
                "path": day.get("path"),
            }
        else:
            failed_days.append(
                {
                    "date": str(date),
                    "status_code": day.get("status_code"),
                    "error": day.get("error") or "unknown",
                }
            )
            logger.warning(
                "%sDay fetch failed date=%s error=%s status=%s",
                prefix,
                date,
                day.get("error"),
                day.get("status_code"),
            )

    dates_ok = list(by_date.keys())
    dates_failed = [item["date"] for item in failed_days if item.get("date")]
    result = {
        "ok": bool(by_date),
        "by_date": by_date,
        "failed_days": failed_days,
        "dates_ok": dates_ok,
        "dates_failed": dates_failed,
    }
    logger.info(
        "%sEPG fetch summary ok_days=%s failed_days=%s",
        prefix,
        dates_ok,
        dates_failed,
    )
    return result


def record_epg_fetch_status(
    num: int,
    fetch_result: Dict[str, Any],
    ticket_id: str = "",
    epg_urls_empty: bool = False,
) -> int:
    """
    Append helper_fuc rows for EPG URL availability / day-load status.
    Returns next sequence number.
    """
    prefix = f"{ticket_id} " if ticket_id else ""

    if epg_urls_empty:
        Validation_Output.append(
            helper_fuc(
                num,
                "URL",
                "Validate EPG delivery URLs availability",
                "delivery_details.epg should provide date/url entries",
                "Failed",
                "Data not available",
                "",
            )
        )
        logger.warning("%sNo EPG delivery URLs — Data not available", prefix)
        return num + 1

    failed_days = fetch_result.get("failed_days") or []
    dates_ok = fetch_result.get("dates_ok") or []
    # Exclude synthetic empty_epg_urls failure from day-load row when already handled
    real_failures = [f for f in failed_days if f.get("date")]

    if real_failures:
        asset_ids = ",".join(
            str({f["date"]: [{"fetch": [f.get("error"), f.get("status_code")]}]})
            for f in real_failures
        )
        Validation_Output.append(
            helper_fuc(
                num,
                "URL",
                "Validate EPG day JSON load status for all returned days",
                "Each delivery EPG URL should load successfully with 200 OK",
                "Failed",
                "One or more EPG day URLs failed to load",
                asset_ids,
            )
        )
    elif dates_ok:
        Validation_Output.append(
            helper_fuc(
                num,
                "URL",
                "Validate EPG day JSON load status for all returned days",
                "Each delivery EPG URL should load successfully with 200 OK",
                "Passed",
                f"EPG JSON loaded successfully for days: {', '.join(dates_ok)}",
                "",
            )
        )
    else:
        Validation_Output.append(
            helper_fuc(
                num,
                "URL",
                "Validate EPG day JSON load status for all returned days",
                "Each delivery EPG URL should load successfully with 200 OK",
                "Failed",
                "Data not available",
                "",
            )
        )

    return num + 1
