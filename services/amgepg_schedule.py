"""AMGEPG schedule capture: dates, fetch via AMGEPGClient, normalize to AN3 by_date."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.amgepg_api import AMGEPGAPIError, AMGEPGClient

logger = logging.getLogger(__name__)

# Match AN3 build_schedule_window(days=7): today through today+6
_SCHEDULE_DAYS = 7


def schedule_date_strings(
    start: Optional[datetime] = None,
    days: int = _SCHEDULE_DAYS,
) -> List[str]:
    """Return YYYY-MM-DD strings for today .. today+(days-1) in UTC."""
    day = (start or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    n = max(int(days), 1)
    return [(day + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def _flatten_program_entry(entry: Any) -> Optional[dict]:
    """
    Normalize one AMGEPG program list item to AN3-style top-level program dict.

    AMGEPG often returns ``{asset_id, program: {...}}``; AN3 validators expect
    ``id`` / ``title`` / etc. on the program object itself.
    """
    if not isinstance(entry, dict):
        return None
    nested = entry.get("program")
    if isinstance(nested, dict):
        out = dict(nested)
        if entry.get("asset_id") is not None and out.get("asset_id") is None:
            out["asset_id"] = entry.get("asset_id")
        return out
    # Already flat (or program-shaped)
    if entry.get("id") is not None or entry.get("title") is not None:
        return dict(entry)
    return dict(entry)


def normalize_amgepg_day_payload(payload: Any) -> Dict[str, List[Any]]:
    """
    Map AMGEPG day JSON to AN3 keys ``program`` / ``schedule``.

    Accepts ``programs``/``schedules`` (AMGEPG) or ``program``/``schedule`` (AN3).
    """
    if not isinstance(payload, dict):
        return {"program": [], "schedule": []}

    raw_programs = payload.get("programs")
    if raw_programs is None:
        raw_programs = payload.get("program")
    raw_schedules = payload.get("schedules")
    if raw_schedules is None:
        raw_schedules = payload.get("schedule")

    programs: List[Any] = []
    if isinstance(raw_programs, list):
        for item in raw_programs:
            flat = _flatten_program_entry(item)
            if flat is not None:
                programs.append(flat)

    schedules: List[Any] = []
    if isinstance(raw_schedules, list):
        schedules = [s for s in raw_schedules if isinstance(s, dict)]

    return {"program": programs, "schedule": schedules}


def _save_day_json(
    report_path: str,
    schedule_date: str,
    payload: dict,
    ticket_id: str = "",
) -> Optional[str]:
    if not report_path:
        return None
    try:
        os.makedirs(report_path, exist_ok=True)
        path = os.path.join(report_path, f"amgepg_epg_{schedule_date}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return path
    except Exception as exc:
        prefix = f"{ticket_id} " if ticket_id else ""
        logger.warning("%sAMGEPG failed to save day JSON date=%s: %s", prefix, schedule_date, exc)
        return None


def fetch_amgepg_schedules(
    customer_id: Any,
    delivery_region: str,
    report_path: str = "",
    ticket_id: str = "",
    client: Optional[AMGEPGClient] = None,
    days: int = _SCHEDULE_DAYS,
) -> Dict[str, Any]:
    """
    Fetch AMGEPG EPG for today..(today+days-1) and build AN3-compatible by_date.

    Returns (same shape as fetch_all_epg_days):
      {ok, by_date, failed_days, dates_ok, dates_failed,
       channel_code, platform_id, error}
    """
    prefix = f"{ticket_id} " if ticket_id else ""
    result: Dict[str, Any] = {
        "ok": False,
        "by_date": {},
        "failed_days": [],
        "dates_ok": [],
        "dates_failed": [],
        "channel_code": None,
        "platform_id": None,
        "error": None,
    }

    api = client or AMGEPGClient()
    try:
        channel_code, platform_id = api.resolve_channel_and_platform(
            customer_id, delivery_region
        )
    except AMGEPGAPIError as exc:
        logger.error("%sAMGEPG resolve channel/platform failed: %s", prefix, exc)
        result["error"] = str(exc)
        result["failed_days"].append(
            {"date": None, "status_code": None, "error": str(exc)}
        )
        return result

    result["channel_code"] = channel_code
    result["platform_id"] = platform_id

    by_date: Dict[str, Dict[str, Any]] = {}
    failed_days: List[Dict[str, Any]] = []

    for schedule_date in schedule_date_strings(days=days):
        try:
            payload = api.get_schedule(channel_code, platform_id, schedule_date)
            normalized = normalize_amgepg_day_payload(payload)
            path = _save_day_json(report_path, schedule_date, payload, ticket_id=ticket_id)
            by_date[schedule_date] = {
                "program": normalized["program"],
                "schedule": normalized["schedule"],
                "path": path,
            }
            logger.info(
                "%sAMGEPG day OK date=%s programs=%s schedules=%s",
                prefix,
                schedule_date,
                len(normalized["program"]),
                len(normalized["schedule"]),
            )
        except AMGEPGAPIError as exc:
            logger.warning("%sAMGEPG day fetch failed date=%s: %s", prefix, schedule_date, exc)
            failed_days.append(
                {"date": schedule_date, "status_code": None, "error": str(exc)}
            )
        except Exception as exc:
            logger.error(
                "%sAMGEPG unexpected day error date=%s: %s",
                prefix,
                schedule_date,
                exc,
            )
            failed_days.append(
                {
                    "date": schedule_date,
                    "status_code": None,
                    "error": f"unexpected: {exc}",
                }
            )

    dates_ok = list(by_date.keys())
    dates_failed = [item["date"] for item in failed_days if item.get("date")]
    result["by_date"] = by_date
    result["failed_days"] = failed_days
    result["dates_ok"] = dates_ok
    result["dates_failed"] = dates_failed
    result["ok"] = bool(by_date)
    logger.info(
        "%sAMGEPG fetch summary ok_days=%s failed_days=%s",
        prefix,
        dates_ok,
        dates_failed,
    )
    return result
