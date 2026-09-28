"""Hardcoded test-case priorities derived from Samsung EPG XML Test Cases.xlsx (Sheet1)."""

from __future__ import annotations

import re
from typing import Dict, Iterable, Tuple

PRIORITY_BLOCKER = "Blocker"
PRIORITY_CRITICAL = "Critical"

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
    ("Asset_Level", "Verify the asset ID type for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the title type for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the title length for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that asset titles do not contain prohibited special characters across the seven-day schedule"),
    ("Asset_Level", "Verify the description type for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the description length for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that asset descriptions do not contain prohibited special characters across the seven-day schedule"),
    ("Asset_Level", "Verify the poster type is a list for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that each poster list entry is an object across the seven-day schedule"),
    ("Asset_Level", "Verify the poster URL type for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of the poster type for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of the thumbnail width for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of the thumbnail height for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the thumbnail format for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the thumbnail resolution for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify rating capitalization for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that all rating values comply with Samsung standards across the seven-day schedule"),
    ("Asset_Level", "Verify the duration type for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that program IDs are unique within each day across the seven-day schedule"),
    ("Asset_Level", "Verify that content_uri equals the sheet Stream URL across the seven-day schedule"),
    ("Asset_Level", "Verify content_uri ads macro keys across the seven-day schedule"),
    ("Asset_Level", "Verify content_uri macro encoding across the seven-day schedule"),
    ("Asset_Level", "Verify the asset ID length across the seven-day schedule"),
    ("Asset_Level", "Verify that asset IDs and descriptions are not identical across the seven-day schedule"),
    ("Asset_Level", "Verify that no asset title contains 'To Be Announced' across the seven-day schedule"),
    ("Asset_Level", "Verify that asset titles and descriptions are not identical across the seven-day schedule"),
    ("Asset_Level", "Verify the availability of posters for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the thumbnail URL length for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the HTTP response status of all asset thumbnails across the seven-day schedule"),
    ("Asset_Level", "Verify the genre list type for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that all categories comply with Samsung standards across the seven-day schedule"),
    ("Asset_Level", "Verify that asset duration is not zero across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of an episode number for all applicable assets across the seven-day schedule"),
    ("Asset_Level", "Verify that cast is non-empty for all assets across the seven-day schedule"),
    # --- NON-SSAI Asset_Level ---
    ("Asset_Level", "Verify the presence of mandatory fields for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that all assets have a valid content_type value across the seven-day schedule"),
    ("Asset_Level", "Verify the start-time format for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the end-time format for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a title for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that no asset title contains 'To Be Announced' across the seven-day schedule"),
    ("Asset_Level", "Verify that asset titles and descriptions are not identical across the seven-day schedule"),
    ("Asset_Level", "Verify the title length for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that asset titles do not contain prohibited special characters across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a language attribute in all title tags across the seven-day schedule"),
    ("Asset_Level", "Verify that title_language matches channel_language across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a subtitle for all applicable assets across the seven-day schedule"),
    ("Asset_Level", "Verify that asset subtitles and titles are not identical across the seven-day schedule"),
    ("Asset_Level", "Verify that asset subtitles and descriptions are not identical across the seven-day schedule"),
    ("Asset_Level", "Verify the subtitle length for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that asset subtitles do not contain prohibited special characters across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a language attribute in all subtitle tags across the seven-day schedule"),
    ("Asset_Level", "Verify that subtitle_language matches channel_language across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a description for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the description length for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that asset descriptions do not contain prohibited special characters across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a language attribute in all description tags across the seven-day schedule"),
    ("Asset_Level", "Verify that description_language matches channel_language across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a category for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a language attribute in all category tags across the seven-day schedule"),
    ("Asset_Level", "Verify that category_language matches channel_language across the seven-day schedule"),
    ("Asset_Level", "Verify that all categories comply with Samsung standards across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of the asset language for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that asset_language matches channel_language across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of the original language for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that asset orig_language matches channel_language across the seven-day schedule"),
    ("Asset_Level", "Verify the availability of thumbnails for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of the thumbnail width for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of the thumbnail height for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the thumbnail URL length for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the HTTP response status of all asset thumbnails across the seven-day schedule"),
    ("Asset_Level", "Verify the thumbnail format for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the thumbnail resolution for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that each actual thumbnail width matches its XML_thumbnail_width value across the seven-day schedule"),
    ("Asset_Level", "Verify that each actual thumbnail height matches its XML_thumbnail_height value across the seven-day schedule"),
    ("Asset_Level", "Verify the thumbnail aspect ratio for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of a rating source for all assets across the seven-day schedule"),
    ("Asset_Level", "Validate Rating Source as per Samsung standard in all 7 days"),
    ("Asset_Level", "Verify the presence of a rating value for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify that all rating values comply with Samsung standards across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of an asset ID for all assets across the seven-day schedule"),
    ("Asset_Level", "Verify the asset ID length across the seven-day schedule"),
    ("Asset_Level", "Verify the presence of an episode number for all applicable assets across the seven-day schedule"),
    # --- NON-SSAI Channel Level and URL ---
    ('URL', 'Verify the URL content format'),
    ('URL', 'Verify the date format in the URL'),
    ('URL', 'Validate the status code of XML in all 7 days'),
    ('Channel_Level', 'Verify the presence of the channel tag across the seven-day schedule'),
    ('Channel_Level', 'Verify the presence of the display-name tag under the channel tag across the seven-day schedule'),
    ('Channel_Level', 'Verify the presence of the channel name across the seven-day schedule'),
    ('Channel_Level', 'Verify the presence of the channel-level language across the seven-day schedule'),
    # --- SSAI Channel Level and URL ---
    ('URL', 'Verify EPG data availability across the seven-day schedule'),
    ('URL', 'Validate the status code of EPG JSON in all 7 days'),
    ('Asset_Level', 'Verify the presence of mandatory fields for all assets across the seven-day schedule'),
    # --- SSAI Schedule ---
    ("Schedule", "Verify that schedule field types are strings across the seven-day schedule"),
    ("Schedule", "Verify the start-time format for all assets across the seven-day schedule"),
    ("Schedule", "Verify that schedule start times are parseable across the seven-day schedule"),
    ("Schedule", "Verify that schedule duration is parseable as int seconds across the seven-day schedule"),
    ("Schedule", "Verify that schedule duration matches program duration across the seven-day schedule"),
    ("Schedule", "Verify that schedule content_id exists in program id across the seven-day schedule"),
    ("Schedule", "Verify that service_id is constant per day across the seven-day schedule"),
    ('Schedule', 'Verify the presence of schedule mandatory fields across the seven-day schedule'),
    ('Schedule', 'Verify that schedule mandatory fields are non-empty across the seven-day schedule'),
    ('Schedule', 'Verify that no asset shorter than 20 minutes (1,200 seconds) is scheduled across the seven-day schedule'),
    ('Schedule', 'Verify that no asset longer than 6 hours (21,600 seconds) is scheduled across the seven-day schedule'),
    ('Schedule', 'Verify that there are no scheduling gaps between assets across the seven-day schedule'),
    ('Schedule', 'Verify that there are no scheduling overlaps between assets across the seven-day schedule'),
    # --- NON-SSAI Schedule ---
    ('Schedule', 'Verify that no asset shorter than 20 minutes (1,200 seconds) is scheduled across the seven-day schedule'),
    ('Schedule', 'Verify that no asset longer than 6 hours (21,600 seconds) is scheduled across the seven-day schedule'),
    ('Schedule', 'Verify that there are no scheduling gaps between assets across the seven-day schedule'),
    ('Schedule', 'Verify the presence of the minutes attribute for all assets across the seven-day schedule'),
    ('Schedule', 'Verify the presence of a minutes value for all assets across the seven-day schedule'),
    ('Schedule', 'Verify that each asset duration in minutes matches its minutes value across the seven-day schedule'),
    ('Schedule', 'Verify the presence of the seconds attribute for all assets across the seven-day schedule'),
    ('Schedule', 'Verify the presence of a seconds value for all assets across the seven-day schedule'),
    ('Schedule', 'Verify that each asset duration in seconds matches its seconds value across the seven-day schedule'),
]:
    _EXPLICIT_BLOCKER_KEYS[_key(module, scenario)] = PRIORITY_BLOCKER


def lookup_priority(module: str, scenario: str) -> str:
    return _EXPLICIT_BLOCKER_KEYS.get(_key(module, scenario), PRIORITY_CRITICAL)


def apply_priorities_to_validation_output(rows: Iterable[dict]) -> None:
    for row in rows:
        row["Priority"] = lookup_priority(row.get("Module", ""), row.get("Scenario", ""))


def issue_with_priority_suffix(issue_text: str, priority: str) -> str:
    p = (priority or "").strip() or PRIORITY_CRITICAL
    return f"{issue_text} ({p})"
