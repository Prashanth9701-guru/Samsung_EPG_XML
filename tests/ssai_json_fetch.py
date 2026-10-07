"""Fetch and persist a single day's delivered SSAI EPG JSON from a signed URL."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 60


def _empty_day_result(date: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "status_code": None,
        "date": date,
        "path": None,
        "data": None,
        "program": [],
        "schedule": [],
        "error": None,
    }


def parse_epg_payload(data: Any, ticket_id: str = "") -> Dict[str, List[Any]]:
    """
    Extract top-level program + schedule lists from delivered EPG JSON.

    Missing or non-list keys become empty lists (never raises).
    """
    prefix = f"{ticket_id} " if ticket_id else ""
    program: List[Any] = []
    schedule: List[Any] = []

    if not isinstance(data, dict):
        logger.warning("%sEPG payload is not a dict (type=%s)", prefix, type(data).__name__)
        return {"program": program, "schedule": schedule}

    raw_program = data.get("program")
    raw_schedule = data.get("schedule")

    if raw_program is None:
        logger.warning("%sEPG payload missing top-level 'program'", prefix)
    elif isinstance(raw_program, list):
        program = raw_program
    else:
        logger.warning(
            "%sEPG 'program' is not a list (type=%s)",
            prefix,
            type(raw_program).__name__,
        )

    if raw_schedule is None:
        logger.warning("%sEPG payload missing top-level 'schedule'", prefix)
    elif isinstance(raw_schedule, list):
        schedule = raw_schedule
    else:
        logger.warning(
            "%sEPG 'schedule' is not a list (type=%s)",
            prefix,
            type(raw_schedule).__name__,
        )

    return {"program": program, "schedule": schedule}


def save_epg_day_json(
    report_path: str,
    date: str,
    payload: Any,
    ticket_id: str = "",
) -> Optional[str]:
    """
    Write one day's EPG JSON under report_path as epg_{date}.json.
    Returns absolute file path on success, None on failure.
    """
    prefix = f"{ticket_id} " if ticket_id else ""
    try:
        os.makedirs(report_path, exist_ok=True)
        safe_date = str(date).replace("/", "-")
        path = os.path.join(report_path, f"epg_{safe_date}.json")
        with open(path, "w", encoding="utf-8") as fh:
            if isinstance(payload, (dict, list)):
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            else:
                fh.write(str(payload))
        logger.info("%sSaved EPG JSON date=%s path=%s", prefix, date, path)
        return path
    except OSError as exc:
        logger.error("%sFailed to save EPG JSON date=%s: %s", prefix, date, exc)
        return None


def fetch_epg_day_json(
    url: str,
    date: str,
    report_path: str,
    ticket_id: str = "",
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """
    GET a pre-signed day EPG URL, persist JSON, and parse program/schedule.

    Per-day isolation: never raises. Non-200 / invalid JSON → ok=False.

    Returns:
      {
        "ok": bool,
        "status_code": int | None,
        "date": str,
        "path": str | None,
        "data": dict | None,
        "program": list,
        "schedule": list,
        "error": str | None,
      }
    """
    prefix = f"{ticket_id} " if ticket_id else ""
    result = _empty_day_result(date)

    if not url:
        result["error"] = "empty_url"
        logger.error("%sEmpty EPG URL for date=%s", prefix, date)
        return result

    try:
        logger.info("%sFetching EPG JSON date=%s", prefix, date)
        response = requests.get(url, timeout=timeout)
        result["status_code"] = response.status_code

        if response.status_code != 200:
            result["error"] = f"http_{response.status_code}"
            logger.error(
                "%sEPG fetch failed date=%s status=%s body=%s",
                prefix,
                date,
                response.status_code,
                (response.text or "")[:300],
            )
            return result

        try:
            data = response.json()
        except ValueError as exc:
            result["error"] = f"invalid_json: {exc}"
            logger.error("%sEPG response not valid JSON date=%s: %s", prefix, date, exc)
            return result

        path = save_epg_day_json(report_path, date, data, ticket_id=ticket_id)
        if not path:
            result["error"] = "save_failed"
            result["data"] = data if isinstance(data, dict) else None
            parsed = parse_epg_payload(data, ticket_id=ticket_id)
            result["program"] = parsed["program"]
            result["schedule"] = parsed["schedule"]
            return result

        parsed = parse_epg_payload(data, ticket_id=ticket_id)
        result["ok"] = True
        result["path"] = path
        result["data"] = data if isinstance(data, dict) else {"_raw": data}
        result["program"] = parsed["program"]
        result["schedule"] = parsed["schedule"]
        logger.info(
            "%sEPG day OK date=%s programs=%s schedules=%s",
            prefix,
            date,
            len(result["program"]),
            len(result["schedule"]),
        )
        return result

    except requests.Timeout as exc:
        result["error"] = f"timeout: {exc}"
        logger.error("%sEPG fetch timeout date=%s: %s", prefix, date, exc)
        return result
    except requests.RequestException as exc:
        result["error"] = f"request_error: {exc}"
        logger.error("%sEPG fetch request failed date=%s: %s", prefix, date, exc)
        return result
    except Exception as exc:
        result["error"] = f"unexpected: {exc}"
        logger.error("%sEPG fetch unexpected error date=%s: %s", prefix, date, exc)
        return result
