import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = "https://authserver.nandi.amagi.tv/oauth/token"
PROGRAMS_URL = "https://api-now3.secure.amagi.tv/api/programs"
CONTENT_TYPE_MAX_RETRIES = 10
CONTENT_TYPE_RETRY_DELAY_SEC = 2

DEFAULT_CLIENT_ID = "jv9vf3iG7fbkn8wUvwoVK67aux8etZKY"
DEFAULT_CLIENT_SECRET = "03IyzeSy6koLdg99_ldbI-qKaupE2Vulcz12l-zXdhZw7ni_gGHE-jnijBCjLaF9"
DEFAULT_AUDIENCE = "https://amagi.amaginow.com"


def get_oauth_token(ticket_id: str = "") -> Optional[str]:
    """Fetch OAuth access token. Returns None on failure (never raises)."""
    prefix = f"{ticket_id} " if ticket_id else ""
    try:
        payload = {
            "client_id": DEFAULT_CLIENT_ID,
            "client_secret": DEFAULT_CLIENT_SECRET,
            "audience": DEFAULT_AUDIENCE,
            # "client_id": os.environ.get("AMAGI_CLIENT_ID", DEFAULT_CLIENT_ID),
            # "client_secret": os.environ.get("AMAGI_CLIENT_SECRET", DEFAULT_CLIENT_SECRET),
            # "audience": os.environ.get("AMAGI_AUDIENCE", DEFAULT_AUDIENCE),
            "grant_type": "client_credentials",
        }
        logger.info(f"{prefix}Requesting OAuth token from {TOKEN_URL}")
        response = requests.post(
            TOKEN_URL,
            json=payload,
            headers={"content-type": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if token:
            logger.info(f"{prefix}OAuth token obtained successfully")
            return token
        logger.error(f"{prefix}OAuth response missing access_token")
        return None
    except Exception as exc:
        logger.error(f"{prefix}Failed to obtain OAuth token: {exc}")
        return None


def parse_amagi_ids_from_url(url: str) -> Optional[dict]:
    """Parse amg_id, platform_id, channel_id from epg_deliveries URL path."""
    try:
        path = urlparse(url).path
        match = re.search(
            r"/(?P<amg_id>amg\d+)/epg_deliveries/(?P<platform_id>amgplt\w+)/(?P<channel_id>amg\w+)/",
            path,
        )
        if not match:
            return None
        return {
            "amg_id": match.group("amg_id"),
            "platform_id": match.group("platform_id"),
            "channel_id": match.group("channel_id"),
        }
    except Exception as exc:
        logger.error(f"Failed to parse Amagi IDs from URL {url}: {exc}")
        return None


def _asset_id_from_programme(program) -> Optional[str]:
    """Extract assetID from a programme ElementTree node."""
    for epi in program.findall("episode-num"):
        if "assetID" in str(epi.attrib) and epi.text:
            return epi.text
    return None


def _title_from_programme(program) -> Optional[str]:
    """Extract first title text from a programme ElementTree node."""
    title = program.find("title")
    if title is not None and title.text:
        return title.text.strip()
    return None


def _iter_programmes(date_xml_data: list):
    """Yield programme elements from 7-day EPG XML data."""
    for single_date_xml_data in date_xml_data or []:
        for _date, xml_data in single_date_xml_data.items():
            try:
                root = ET.fromstring(xml_data)
            except Exception as exc:
                logger.error(f"Failed to parse XML for asset_id extraction: {exc}")
                continue
            for program in root.findall("programme"):
                yield program


def extract_unique_asset_ids(date_xml_data: list) -> list:
    """Extract unique asset IDs from 7-day EPG XML data."""
    asset_ids = []
    seen = set()
    for program in _iter_programmes(date_xml_data):
        asset_id = _asset_id_from_programme(program)
        if not asset_id or asset_id == "Asset_ID not available":
            continue
        if asset_id not in seen:
            seen.add(asset_id)
            asset_ids.append(asset_id)
    return asset_ids


def _extract_content_type_from_response(data, asset_id: str = "") -> Optional[str]:
    """Pull program type from /api/programs response (meta.program.type)."""
    if not isinstance(data, dict):
        if isinstance(data, list) and data:
            return _extract_content_type_from_response(data[0], asset_id)
        return None

    # Preferred path from Amagi Now API:
    # channels[].epg[].meta.program.type  (matched by asset_id when possible)
    for channel in data.get("channels") or []:
        if not isinstance(channel, dict):
            continue
        for epg_item in channel.get("epg") or []:
            if not isinstance(epg_item, dict):
                continue
            if asset_id and epg_item.get("asset_id") and epg_item.get("asset_id") != asset_id:
                continue
            program = ((epg_item.get("meta") or {}).get("program") or {})
            program_type = program.get("type") or program.get("content_type") or program.get("program_type")
            if program_type:
                return program_type

    # Fallbacks for other shapes
    if data.get("content_type"):
        return data.get("content_type")
    for key in ("data", "program", "result"):
        nested = data.get(key)
        found = _extract_content_type_from_response(nested, asset_id)
        if found:
            return found
    return None


def fetch_content_type_for_asset(
    token: str,
    amg_id: str,
    channel_id: str,
    platform_id: str,
    asset_id: str,
    ticket_id: str = "",
) -> Optional[str]:
    """GET program details and return content_type. Retries on error up to 10 times."""
    prefix = f"{ticket_id} " if ticket_id else ""
    params = {
        "amg_id": amg_id,
        "channel_id": channel_id,
        "platform_id": platform_id,
        "asset_id": asset_id,
        #"language_code": "en",
        "expanded": "true",
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

    last_error = None
    for attempt in range(1, CONTENT_TYPE_MAX_RETRIES + 1):
        try:
            logger.info(
                f"{prefix}Fetching content_type for asset_id={asset_id} "
                f"(attempt {attempt}/{CONTENT_TYPE_MAX_RETRIES})"
            )
            response = requests.get(PROGRAMS_URL, params=params, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            content_type = _extract_content_type_from_response(data, asset_id=asset_id)
            if content_type:
                logger.info(f"{prefix}asset_id={asset_id} content_type={content_type}")
                return content_type
            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            logger.warning(
                f"{prefix}content_type missing for asset_id={asset_id}; "
                f"response shape keys/type={keys}"
            )
            return None
        except Exception as exc:
            last_error = exc
            logger.error(
                f"{prefix}Failed to fetch content_type for asset_id={asset_id} "
                f"(attempt {attempt}/{CONTENT_TYPE_MAX_RETRIES}): {exc}"
            )
            if attempt < CONTENT_TYPE_MAX_RETRIES:
                time.sleep(CONTENT_TYPE_RETRY_DELAY_SEC)

    logger.error(
        f"{prefix}Exhausted {CONTENT_TYPE_MAX_RETRIES} retries for asset_id={asset_id}: {last_error}"
    )
    return None


def normalize_api_content_type(content_type: str) -> str:
    """Keep API content_type if it contains 'episode'; otherwise map to 'others'."""
    if content_type and "episode" in str(content_type).lower():
        return content_type
    return "others"


def collect_asset_content_types(
    token: Optional[str],
    url: str,
    date_xml_data: list,
    ticket_id: str = "",
    default_content_type: str = "others",
) -> list:
    """
    For amgplt EPG URLs only, collect [{asset_id: content_type}, ...] via API.
    Asset IDs are read from date_xml_data (raw EPG XML).
    Programmes with no asset_id use default_content_type from the Google Sheet.
    Non-amgplt / missing token / errors return [] without raising.
    """
    prefix = f"{ticket_id} " if ticket_id else ""

    if "amgplt" not in (url or ""):
        logger.info(f"{prefix}URL has no amgplt; skipping content_type API collection")
        return []

    if not token:
        logger.warning(f"{prefix}No OAuth token available; skipping content_type API collection")
        return []

    ids = parse_amagi_ids_from_url(url)
    if not ids:
        logger.warning(f"{prefix}Could not parse amg_id/platform_id/channel_id from URL; skipping")
        return []

    logger.info(
        f"{prefix}Parsed Amagi IDs: amg_id={ids['amg_id']}, "
        f"platform_id={ids['platform_id']}, channel_id={ids['channel_id']}"
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

        # No asset_id → use Google Sheet default content_type
        key = _title_from_programme(program) or "Asset_ID not available"
        if key not in seen_missing:
            seen_missing.add(key)
            missing_asset_keys.append(key)

    logger.info(
        f"{prefix}Found {len(asset_ids)} unique asset_id(s) for content_type lookup; "
        f"{len(missing_asset_keys)} programme(s) without asset_id will use sheet default "
        f"content_type={default_content_type}"
    )

    content_type_list = []
    for asset_id in asset_ids:
        content_type = fetch_content_type_for_asset(
            token=token,
            amg_id=ids["amg_id"],
            channel_id=ids["channel_id"],
            platform_id=ids["platform_id"],
            asset_id=asset_id,
            ticket_id=ticket_id,
        )
        if content_type:
            normalized = normalize_api_content_type(content_type)
            logger.info(
                f"{prefix}asset_id={asset_id} API content_type={content_type} "
                f"normalized={normalized}"
            )
            content_type_list.append({asset_id: normalized})
        else:
            logger.info(
                f"{prefix}API content_type missing for asset_id={asset_id}; "
                f"using sheet default content_type={default_content_type}"
            )
            content_type_list.append({asset_id: default_content_type})

    for key in missing_asset_keys:
        logger.info(
            f"{prefix}No asset_id for programme key={key}; "
            f"using sheet default content_type={default_content_type}"
        )
        content_type_list.append({key: default_content_type})

    logger.info(
        f"{prefix}Captured content_type list size={len(content_type_list)}: {content_type_list}"
    )
    return content_type_list
