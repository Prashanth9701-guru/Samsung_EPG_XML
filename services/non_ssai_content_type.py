"""NON-SSAI content_type lookup via Amagi EPG customerschedules API.

Used when the input XML URL does not contain ``amgplt``. Existing amgplt /
Now3 lookup in ``amagi_api_service.collect_asset_content_types`` is unchanged.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from typing import Any, Optional

import requests
import yaml

from services.amagi_api_service import (
    _asset_id_from_programme,
    _iter_programmes,
    _title_from_programme,
    normalize_api_content_type,
)

logger = logging.getLogger(__name__)

config = yaml.safe_load(open("config.yaml"))

BASE_URL = "https://amgepg.amagi.tv/v1/"
TOKEN_URL = f"{BASE_URL}users/login"
DEFAULT_TIMEOUT_SEC = 60



def _prefix(ticket_id: str = "") -> str:
    return f"{ticket_id} " if ticket_id else ""


def _url_has_amgplt(url: str) -> bool:
    return "amgplt" in (url or "")


def extract_channel_id_from_xml(date_xml_data: list, ticket_id: str = "") -> Optional[str]:
    """Return the first ``<channel>`` id from fetched XML (attribute or child tag)."""
    prefix = _prefix(ticket_id)
    for single_date_xml_data in date_xml_data or []:
        if not isinstance(single_date_xml_data, dict):
            continue
        for date, xml_data in single_date_xml_data.items():
            if not xml_data:
                continue
            try:
                root = ET.fromstring(xml_data)
            except Exception as exc:
                logger.error(
                    "%sFailed to parse XML for channel id (date=%s): %s",
                    prefix,
                    date,
                    exc,
                )
                continue
            for channel in root.findall("channel"):
                attr_id = (channel.get("id") or "").strip()
                if attr_id:
                    logger.info(
                        "%sExtracted channel id=%s from XML channel attribute (date=%s)",
                        prefix,
                        attr_id,
                        date,
                    )
                    return attr_id
                id_tag = channel.find("id")
                if id_tag is not None and (id_tag.text or "").strip():
                    tag_id = id_tag.text.strip()
                    logger.info(
                        "%sExtracted channel id=%s from XML channel <id> tag (date=%s)",
                        prefix,
                        tag_id,
                        date,
                    )
                    return tag_id
    logger.warning("%sNo channel id found in XML response", prefix)
    return None


def _get_amgepg_credentials() -> tuple[Optional[str], Optional[str]]:
    amgepg = config.get("amgepg") or {}
    username = str(amgepg.get("username") or "").strip()
    password = str(amgepg.get("password") or "")
    if not username or not password:
        return None, None
    return username, password


def get_amgepg_token(ticket_id: str = "") -> Optional[str]:
    """Authenticate with Amagi EPG. Returns access_token or None. Never logs secrets."""
    prefix = _prefix(ticket_id)
    username, password = _get_amgepg_credentials()
    if not username or not password:
        logger.error(
            "%sAmagi EPG credentials missing; set amgepg.username and amgepg.password in config.yaml",
            prefix,
        )
        return None
    try:
        logger.info("%sRequesting Amagi EPG access token from %s", prefix, TOKEN_URL)
        response = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/json"},
            json={"username": username, "password": password},
            timeout=DEFAULT_TIMEOUT_SEC,
        )
        response.raise_for_status()
        token = ((response.json() or {}).get("token") or {}).get("access_token")
        if token:
            logger.info("%sAmagi EPG authentication succeeded", prefix)
            return token
        logger.error("%sAmagi EPG authentication failed: access_token missing in response", prefix)
        return None
    except Exception as exc:
        logger.error("%sAmagi EPG authentication failed: %s", prefix, exc)
        return None


def fetch_customer_schedules(
    token: str,
    channel_id: str,
    ticket_id: str = "",
) -> Optional[Any]:
    """GET customerschedules for the XML channel id. Returns JSON or None."""
    prefix = _prefix(ticket_id)
    content_type_url = f"{BASE_URL}schedules/customerschedules/{channel_id}?days=7"
    try:
        logger.info("%sFetching Amagi EPG schedules from %s", prefix, content_type_url)
        response = requests.get(
            content_type_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=DEFAULT_TIMEOUT_SEC,
        )
        logger.info(
            "%sAmagi EPG schedules HTTP status=%s",
            prefix,
            response.status_code,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            logger.info(
                "%sAmagi EPG schedules response keys=%s",
                prefix,
                list(data.keys()),
            )
        else:
            logger.info(
                "%sAmagi EPG schedules response type=%s",
                prefix,
                type(data).__name__,
            )
        return data
    except Exception as exc:
        logger.error("%sAmagi EPG schedules fetch failed: %s", prefix, exc)
        return None


def _parse_program_details(details: Any) -> Optional[dict]:
    """Parse program.details (JSON string or dict) into a dict."""
    if isinstance(details, dict):
        return details
    if not isinstance(details, str) or not details.strip():
        return None
    try:
        parsed = json.loads(details)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _content_type_from_details(details: Any) -> Optional[str]:
    """Read meta.episode.content_type (not season/series)."""
    parsed = _parse_program_details(details)
    if not parsed:
        return None
    meta = parsed.get("meta") if isinstance(parsed.get("meta"), dict) else {}
    episode = meta.get("episode") if isinstance(meta.get("episode"), dict) else {}
    content_type = (
        episode.get("content_type")
        or episode.get("contentType")
        or episode.get("program_type")
    )
    if content_type is not None and str(content_type).strip():
        return str(content_type).strip()
    return None


def _iter_schedule_days(data: Any):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "schedules", "result"):
            nested = data.get(key)
            if isinstance(nested, list):
                return nested
        return [data]
    return []


def build_epg_content_type_map(data: Any) -> dict:
    """Map program.asset_id -> meta.episode.content_type from customerschedules JSON."""
    mapping: dict = {}
    for day in _iter_schedule_days(data):
        if not isinstance(day, dict):
            continue
        programs = day.get("programs")
        if not isinstance(programs, list):
            continue
        for program in programs:
            if not isinstance(program, dict):
                continue
            asset_id = str(program.get("asset_id") or "").strip()
            if not asset_id:
                continue
            content_type = _content_type_from_details(program.get("details"))
            if content_type:
                mapping[asset_id] = content_type
    return mapping


def collect_non_ssai_asset_content_types(
    url: str,
    date_xml_data: list,
    default_content_type: str = "others",
    ticket_id: str = "",
) -> list:
    """
    For input XML URLs without amgplt, collect [{asset_id: content_type}, ...]
    from Amagi EPG. Missing assets keep default_content_type. Never raises.
    """
    prefix = _prefix(ticket_id)
    amgplt_detected = _url_has_amgplt(url)
    logger.info(
        "%sNON-SSAI content_type: input XML URL=%s amgplt_detected=%s",
        prefix,
        url,
        amgplt_detected,
    )
    if amgplt_detected:
        logger.info(
            "%sInput XML URL contains amgplt; skipping NON-SSAI EPG content_type lookup",
            prefix,
        )
        return []

    channel_id = extract_channel_id_from_xml(date_xml_data, ticket_id=ticket_id)
    if not channel_id:
        logger.warning(
            "%sCannot call Amagi EPG schedules without XML channel id; skipping",
            prefix,
        )
        return []

    token = get_amgepg_token(ticket_id=ticket_id)
    if not token:
        return []

    epg_data = fetch_customer_schedules(token, channel_id, ticket_id=ticket_id)
    if epg_data is None:
        return []

    epg_map = build_epg_content_type_map(epg_data)
    logger.info(
        "%sAmagi EPG content_type map size=%s",
        prefix,
        len(epg_map),
    )

    asset_ids = []
    seen_asset_ids = set()
    missing_asset_keys = []
    seen_missing = set()

    for program in _iter_programmes(date_xml_data):
        asset_id = _asset_id_from_programme(program)
        if asset_id and asset_id != "Asset_ID not available":
            if asset_id not in seen_asset_ids:
                seen_asset_ids.add(asset_id)
                asset_ids.append(asset_id)
            continue
        key = _title_from_programme(program) or "Asset_ID not available"
        if key not in seen_missing:
            seen_missing.add(key)
            missing_asset_keys.append(key)

    matched = []
    missing_from_epg = []
    defaulted = []
    content_type_list = []

    for asset_id in asset_ids:
        epg_content_type = epg_map.get(asset_id)
        if epg_content_type:
            normalized = normalize_api_content_type(epg_content_type)
            logger.info(
                "%sasset_id=%s matched EPG content_type=%s normalized=%s",
                prefix,
                asset_id,
                epg_content_type,
                normalized,
            )
            content_type_list.append({asset_id: normalized})
            matched.append(asset_id)
        else:
            logger.info(
                "%sasset_id=%s missing from EPG; using default content_type=%s",
                prefix,
                asset_id,
                default_content_type,
            )
            content_type_list.append({asset_id: default_content_type})
            missing_from_epg.append(asset_id)
            defaulted.append(asset_id)

    for key in missing_asset_keys:
        logger.info(
            "%sNo asset_id for programme key=%s; using default content_type=%s",
            prefix,
            key,
            default_content_type,
        )
        content_type_list.append({key: default_content_type})
        defaulted.append(key)

    logger.info(
        "%sNON-SSAI content_type summary: processed=%s matched=%s missing_from_epg=%s "
        "defaulted=%s matched_ids=%s missing_ids=%s defaulted_ids=%s",
        prefix,
        len(asset_ids) + len(missing_asset_keys),
        len(matched),
        len(missing_from_epg),
        len(defaulted),
        matched,
        missing_from_epg,
        defaulted,
    )
    return content_type_list
