"""Hardcoded test-case priorities derived from Samsung EPG XML Test Cases.xlsx (Sheet1)."""

from __future__ import annotations

import re
from typing import Dict, Iterable, Tuple

PRIORITY_BLOCKER = "Blocker"

# Reference catalog (path, summary) — used as documentation only; lookup is explicit.
BLOCKER_CATALOG: Tuple[Tuple[str, str], ...] = (
    ("XML Nodes", "Check Availability of Top_Level Keys"),
    ("XML Nodes", "Check Availability of Top_Level Node Value"),
    ("programs", "Check availability of programs Nodes"),
    ("programs", "Check availability of programs Nodes values"),
    ("programs->asset_id", "validate asset_id type"),
    ("programs->program", "Check availability of program Nodes"),
    ("programs->program->content_type", "Validate content_type type"),
    ("programs->program->content_type", "Validate content_type Capitalization"),
    ("programs->program->content_uri", "Validate content_uri  type"),
    ("programs->program->content_uri", "Validate content_uri"),
    ("programs->program->content_uri", "Validate content_uri format"),
    ("programs->program->desc", "Validate desc  type"),
    ("programs->program->desc", "Validate desc special character"),
    ("programs->program->desc", "Validate desc Capitalization"),
    ("programs->program->desc", "Validate length of Description"),
    ("programs->program->duration", "Validate duration type"),
    ("programs->program->id", "Validate id type"),
    ("programs->program->poster", "Validate poster type"),
    ("programs->program->poster", "Validate poster list data type"),
    ("programs->program->poster", "Validate poster  Node"),
    ("programs->program->poster", "Validate poster  Node values"),
    ("programs->program->poster", "Validate hight type"),
    ("programs->program->poster", "Validate type format"),
    ("programs->program->poster", "Validate url type"),
    ("programs->program->poster", "Validate Aspect Ratio of url"),
    ("programs->program->poster", "Validate widthl type"),
    ("programs->program->rating", "Validate rating type"),
    ("programs->program->rating", "Validate rating Capitalization "),
    ("programs->program->rating", "Validate rating as per Samsung standard"),
    ("programs->program->title", "Validate title type"),
    ("programs->program->title", "Validate title spacing"),
    ("programs->program->title", "Validate title Capitalization "),
    ("programs->program->title", "Validate title special character"),
    ("programs->program->title", "Validate length of Asset Title"),
    ("schedules", "Check availability of schedules Nodes"),
    ("schedules->content_id", "Validate content_id type"),
    ("schedules->content_id", "Validate content_id is same as id "),
    ("schedules->duration", "Validate duration type"),
    ("schedules->duration", "Validate duration is same as duration listed under program"),
    ("schedules->duration", "Validate duration "),
    ("schedules->schedule_id", "Validate schedule_id  type"),
    ("schedules->service_id", "Validate service_id  type"),
    ("schedules->service_id", "Validate service_id for all content_id"),
    ("schedules->starttime", "Validate starttime  type"),
    ("schedules->starttime", "Validate starttime format"),
)


def _normalize_scenario(text: str) -> str:
    s = re.sub(r"\s+", " ", (text or "").lower().strip())
    s = re.sub(r"\s+in all (?:\d+ )?days?\s*$", "", s)
    s = re.sub(r"\s+in all returned days\s*$", "", s)
    s = s.replace("asset id", "asset_id")
    s = s.replace("description", "desc")
    return re.sub(r"\s+", " ", s).strip()


def _key(module: str, scenario: str) -> Tuple[str, str]:
    return ((module or "").strip(), _normalize_scenario(scenario))


# Explicit runtime (module, normalized scenario) keys only — no fuzzy matching.
_EXPLICIT_BLOCKER_KEYS: Dict[Tuple[str, str], str] = {}
for module, scenario in [
    # --- SSAI Asset_Level ---
    ("Asset_Level", "Validate Asset ID Type in all returned days"),
    ("Asset_Level", "Validate Title type in all returned days"),
    ("Asset_Level", "Validate Title length in all returned days"),
    ("Asset_Level", "Validate Title has no unexpected special characters in all returned days"),
    ("Asset_Level", "Validate Description type in all returned days"),
    ("Asset_Level", "Validate Description length in all returned days"),
    ("Asset_Level", "Validate Description has no unexpected special characters in all returned days"),
    ("Asset_Level", "Validate poster type is list in all returned days"),
    ("Asset_Level", "Validate poster list entry type is object in all returned days"),
    ("Asset_Level", "Validate Poster URL type is string in all returned days"),
    ("Asset_Level", "Validate Poster type present in all returned days"),
    ("Asset_Level", "Validate Poster width present in all returned days"),
    ("Asset_Level", "Validate Poster height present in all returned days"),
    ("Asset_Level", "Validate Poster image format is JPG/JPEG in all returned days"),
    ("Asset_Level", "Validate Poster resolution is 1920x1080 in all returned days"),
    ("Asset_Level", "Validate Rating Capitalization in all returned days"),
    ("Asset_Level", "Validate Rating against expected list in all returned days"),
    ("Asset_Level", "Validate Duration type is int in all returned days"),
    ("Asset_Level", "Validate duplicate program id within each day in all returned days"),
    ("Asset_Level", "Validate content_uri equals sheet Stream URL in all returned days"),
    ("Asset_Level", "Validate content_uri ads macro keys in all returned days"),
    ("Asset_Level", "Validate content_uri macro encoding in all returned days"),
    ("Asset_Level", "Validate assets having in-correct content_type in all returned days"),
    ('Asset_Level', 'Validate Asset ID Length in all returned days'),
    ('Asset_Level', 'Validate Asset ID should not contain Description in all returned days'),
    ('Asset_Level', 'Validate Title is not TBA / To Be Announced in all returned days'),
    ('Asset_Level', 'Validate Title is not equal to Description in all returned days'),
    ('Asset_Level', 'Validate Poster URL availability in all returned days'),
    ('Asset_Level', 'Validate Poster URL length in all returned days'),
    ('Asset_Level', 'Validate Poster HTTP status is 200 in all returned days'),
    ('Asset_Level', 'Validate Poster URL has no redirect in all returned days'),
    ('Asset_Level', 'Validate Genre list type in all returned days'),
    ('Asset_Level', 'Validate Genre original_name as per expected list in all returned days'),
    ('Asset_Level', 'Validate Duration is not zero in all returned days'),
    ('Asset_Level', 'Validate episode_num type is string in all returned days'),
    ('Asset_Level', 'Validate Cast is non-empty in all returned days'),
    # --- NON-SSAI Asset_Level ---
    ("Asset_Level", "Validate Length of Asset Title in all 7 days"),
    ("Asset_Level", "Validate Special Characters in Asset Title in all 7 days"),
    ("Asset_Level", "Validate Length of Description in all 7 days"),
    ("Asset_Level", "Validate Special Characters in Description in all 7 days"),
    ("Asset_Level", "Validate assets having in-correct content_type in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail availability in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail_Width availability in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail_Height availability in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail_URL Length in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail Format in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail Resolution in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail_Width XML_thumbnail_width in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail_Height XML_thumbnail_height in all 7 days"),
    ("Asset_Level", "Validate Asset Thumbnail Aspect Ratio in all 7 days"),
    ("Asset_Level", "Validate Rating Value as per Samsung standard in all 7 days"),
    ('Asset_Level', 'Validate language node availability for title tag in all 7 days')
    ('Asset_Level', 'Validate Asset Title availability in all 7 days')
    ('Asset_Level', 'Validate To Be Announced Assets in all 7 days'),
    ('Asset_Level', 'Validate Asset Title and Description are matching in all 7 days'),
    ('Asset_Level', 'Validate Title_Language node match with Channel_Language in all 7 days'),
    ('Asset_Level', 'Validate start time format for Assets in all 7 days'),
    ('Asset_Level', 'Validate end time format for Assets in all 7 days'),
    ('Asset_Level', 'Validate Asset Sub-Title availability in all 7 days'),
    ('Asset_Level', 'Validate Sub-Title and Asset Title are matching in all 7 days'),
    ('Asset_Level', 'Validate Sub-Title and Description are matching in all 7 days'),
    ('Asset_Level', 'Validate Length of Sub-Title in all 7 days'),
    ('Asset_Level', 'Validate Special Characters in Sub-Title in all 7 days'),
    ('Asset_Level', 'Validate language node availability for Sub-Title tag in all 7 days'),
    ('Asset_Level', 'Validate Sub-Title_Language node match with Channel_Language in all 7 days'),
    ('Asset_Level', 'Validate Asset Description availability in all 7 days'),
    ('Asset_Level', 'Validate language node availability for Description tag in all 7 days'),
    ('Asset_Level', 'Validate Description_Language node match with Channel_Language in all 7 days'),
    ('Asset_Level', 'Validate Asset Category availability in all 7 days'),
    ('Asset_Level', 'Validate language node availability for Category tag in all 7 days'),
    ('Asset_Level', 'Validate Category_Language node match with Channel_Language in all 7 days'),
    ('Asset_Level', 'Validate Category as per Samsung standard in all 7 days'),
    ('Asset_Level', 'Validate Asset_Language availability in all 7 days'),
    ('Asset_Level', 'Validate Asset_Language value match with Channel_Language in all 7 days'),
    ('Asset_Level', 'Validate Asset Thumbnail status code in all 7 days'),
    ('Asset_Level', 'Validate Rating Source availability in all 7 days'),
    ('Asset_Level', 'Validate Rating Source as per Samsung standard in all 7 days'),
    ('Asset_Level', 'Validate Rating Value availability in all 7 days'),
    ('Asset_Level', 'Validate Asset ID availability in all 7 days'),
    ('Asset_Level', 'Validate Asset ID Length in all 7 days'),
    ('Asset_Level', 'Validate Episode Number value availability in all 7 days'),
    # --- NON-SSAI Channel Level and URL ---
    ('URL', 'Validate URL format'),
    ('URL', 'Validation of URL Date Format'),
    ('URL', 'Validate the status code of XML in all 7 days'),
    ('Channel_Level', 'Validate availability of channel tag in all 7 days'),
    # --- SSAI Channel Level and URL ---
    ('URL', 'Validate scheduling API / EPG delivery availability'),
    ('URL', 'Validate EPG day JSON load status for all returned days'),
    ('Asset_Level', 'Validate mandatory fields presence for Assets in all returned days'),
    (),
    # --- SSAI Schedule ---
    ("Schedule", "Validate schedule field types are string in all returned days"),
    ("Schedule", "Validate schedule starttime strict format in all returned days"),
    ("Schedule", "Validate schedule starttime parseable in all returned days"),
    ("Schedule", "Validate schedule duration parseable as int seconds in all returned days"),
    ("Schedule", "Validate schedule duration matches program duration in all returned days"),
    ("Schedule", "Validate schedule content_id exists in program id in all returned days"),
    ("Schedule", "Validate service_id is constant per day in all returned days"),
    ('Schedule', 'Validate schedule mandatory fields presence in all returned days'),
    ('Schedule', 'Validate schedule mandatory fields non-empty in all returned days'),
    ('Schedule', 'Validate schedule duration is at least 1200 seconds in all returned days'),
    ('Schedule', 'Validate schedule duration is at most 21600 seconds in all returned days'),
    ('Schedule', 'Validate no schedule gaps between consecutive assets in all returned days'),
    ('Schedule', 'Validate no schedule overlaps between consecutive assets in all returned days'),
    (),
    # --- NON-SSAI Schedule ---
    ("Schedule", "Validate Asset Duration in minutes match with Minutes Value in all 7 days"),
    ("Schedule", "Validate Asset Duration in seconds match with Seconds Value in all 7 days"),
    ('Schedule', 'Validate less than 20 minutes (1200 seconds) of Assets are not scheduled in all 7 days'),
    ('Schedule', 'Validate greater than 6 hours (21600 seconds) of Assets are not scheduled in all 7 days'),
    ('Schedule', 'Validate schedule gap between Assets in all 7 days'),
    ('Schedule', 'Validate Minutes attribute availability in all 7 days'),
    ('Schedule', 'Validate Minutes Value availability in all 7 days'),
    ('Schedule', 'Validate Seconds attribute availability in all 7 days'),
    ('Schedule', 'Validate Seconds Value availability in all 7 days'),
    ('Schedule', 'Validate Asset Duration in seconds match with Seconds Value in all 7 days'),
]:
    _EXPLICIT_BLOCKER_KEYS[_key(module, scenario)] = PRIORITY_BLOCKER


def lookup_priority(module: str, scenario: str) -> str:
    return _EXPLICIT_BLOCKER_KEYS.get(_key(module, scenario), "")


def apply_priorities_to_validation_output(rows: Iterable[dict]) -> None:
    for row in rows:
        row["Priority"] = lookup_priority(row.get("Module", ""), row.get("Scenario", ""))


def issue_with_priority_suffix(issue_text: str, priority: str) -> str:
    p = (priority or "").strip()
    return f"{issue_text} ({p})" if p else issue_text
