"""AN3 scheduling / EPG delivery API for Samsung SSAI."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import requests

from services.amagi_api_service import get_oauth_token

logger = logging.getLogger(__name__)

PROGRAMS_URL = "https://api-now3.secure.amagi.tv/api/programs"
DEFAULT_TIMEOUT_SEC = 60


def build_schedule_window(
    day: Optional[datetime] = None,
    days: int = 7,
) -> Tuple[str, str]:
    """
    Build UTC start/end window for scheduling API.

    start_time: current day 00:00:00Z
    end_time:   (current day + days-1) 23:59:59Z
    """
    day = (day or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = day.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (day + timedelta(days=max(days, 1) - 1)).replace(
        hour=23, minute=59, second=59, microsecond=0
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return start, end


def extract_epg_delivery_urls(
    data: Any,
    ticket_id: str = "",
) -> Dict[str, str]:
    """Build {date: url} from delivery_details.epg list."""
    prefix = f"{ticket_id} " if ticket_id else ""
    epg_urls: Dict[str, str] = {}

    if not isinstance(data, dict):
        logger.warning("%sextract_epg_delivery_urls: data is not a dict", prefix)
        return epg_urls

    delivery = data.get("delivery_details") or {}
    if not isinstance(delivery, dict):
        logger.warning("%sdelivery_details missing or not a dict", prefix)
        return epg_urls

    epg_list = delivery.get("epg")
    if epg_list is None:
        logger.warning("%sdelivery_details.epg missing", prefix)
        return epg_urls

    if isinstance(epg_list, dict):
        date = epg_list.get("date")
        url = epg_list.get("url")
        if date and url:
            epg_urls[str(date)] = str(url)
        return epg_urls

    if not isinstance(epg_list, list):
        logger.warning(
            "%sdelivery_details.epg unexpected type=%s",
            prefix,
            type(epg_list).__name__,
        )
        return epg_urls

    for item in epg_list:
        if not isinstance(item, dict):
            continue
        date = item.get("date")
        url = item.get("url")
        if date and url:
            epg_urls[str(date)] = str(url)
        else:
            logger.warning(
                "%sSkipping epg entry with missing date/url: keys=%s",
                prefix,
                list(item.keys()) if isinstance(item, dict) else type(item),
            )

    return epg_urls


def fetch_schedule_programs(
    amg_id: str,
    channel_id: str,
    platform_id: str,
    token: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    ticket_id: str = "",
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> Dict[str, Any]:
    """
    GET /api/programs for the given IDs and time window.

    Returns normalized result dict (never raises):
      {ok, status_code, data, epg_urls, error}
    """
    prefix = f"{ticket_id} " if ticket_id else ""
    result: Dict[str, Any] = {
        "ok": False,
        "status_code": None,
        "data": None,
        "epg_urls": {},
        "error": None,
    }

    if not token:
        result["error"] = "missing_token"
        logger.error("%sJWT/token missing for schedule API", prefix)
        return result

    if not amg_id or not channel_id or not platform_id:
        result["error"] = "missing_ids"
        logger.error("%sMissing amg_id/channel_id/platform_id for schedule API", prefix)
        return result

    if not start_time or not end_time:
        start_time, end_time = build_schedule_window()

    params = {
        "amg_id": amg_id,
        "channel_id": channel_id,
        "platform_id": platform_id,
        "start_time": start_time,
        "end_time": end_time,
    }
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": f"Bearer {token}",
        "origin": "https://amagi.amaginow.com",
        "referer": "https://amagi.amaginow.com/",
        "x-service-id": "epg",
        "x-account-id": amg_id,
    }

    try:
        logger.info(
            "%sFetching schedule API amg_id=%s channel_id=%s platform_id=%s start=%s end=%s",
            prefix,
            amg_id,
            channel_id,
            platform_id,
            start_time,
            end_time,
        )
        response = requests.get(
            PROGRAMS_URL,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        result["status_code"] = response.status_code

        if response.status_code == 401:
            result["error"] = "jwt_expired_or_invalid"
            logger.error("%sSchedule API JWT expired/invalid (401)", prefix)
            return result

        if response.status_code >= 500:
            result["error"] = f"api_5xx_{response.status_code}"
            logger.error("%sSchedule API 5xx: %s", prefix, response.status_code)
            return result

        if response.status_code >= 400:
            result["error"] = f"api_4xx_{response.status_code}"
            logger.error(
                "%sSchedule API 4xx: %s body=%s",
                prefix,
                response.status_code,
                (response.text or "")[:500],
            )
            return result

        if response.status_code != 200:
            result["error"] = f"unexpected_status_{response.status_code}"
            logger.error("%sSchedule API unexpected status %s", prefix, response.status_code)
            return result

        try:
            data = response.json()
        except ValueError as exc:
            result["error"] = f"invalid_json: {exc}"
            logger.error("%sSchedule API response is not valid JSON: %s", prefix, exc)
            return result

        result["data"] = data
        epg_urls = extract_epg_delivery_urls(data, ticket_id=ticket_id)
        result["epg_urls"] = epg_urls

        if not epg_urls:
            result["error"] = "delivery_details_epg_missing_or_empty"
            logger.warning("%sSchedule API 200 but delivery_details.epg empty/missing", prefix)
            return result

        result["ok"] = True
        logger.info("%sSchedule API OK; epg dates=%s", prefix, list(epg_urls.keys()))
        return result

    except requests.Timeout as exc:
        result["error"] = f"timeout: {exc}"
        logger.error("%sSchedule API timeout: %s", prefix, exc)
        return result
    except requests.RequestException as exc:
        result["error"] = f"request_error: {exc}"
        logger.error("%sSchedule API request failed: %s", prefix, exc)
        return result
    except Exception as exc:
        result["error"] = f"unexpected: {exc}"
        logger.error("%sSchedule API unexpected error: %s", prefix, exc)
        return result


def fetch_schedule_with_token_retry(
    amg_id: str,
    channel_id: str,
    platform_id: str,
    token: Optional[str],
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    ticket_id: str = "",
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Call schedule API; on JWT expiry (401), refresh token once and retry.

    Returns (token_to_reuse, result_dict).
    """
    active_token = token or get_oauth_token(ticket_id=ticket_id)
    result = fetch_schedule_programs(
        amg_id=amg_id,
        channel_id=channel_id,
        platform_id=platform_id,
        token=active_token or "",
        start_time=start_time,
        end_time=end_time,
        ticket_id=ticket_id,
    )

    if result.get("error") == "jwt_expired_or_invalid":
        logger.info("%sRefreshing JWT after 401 and retrying schedule API", ticket_id)
        active_token = get_oauth_token(ticket_id=ticket_id)
        result = fetch_schedule_programs(
            amg_id=amg_id,
            channel_id=channel_id,
            platform_id=platform_id,
            token=active_token or "",
            start_time=start_time,
            end_time=end_time,
            ticket_id=ticket_id,
        )

    return active_token, result
