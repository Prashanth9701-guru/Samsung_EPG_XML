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
    # --- SSAI Schedule ---
    ("Schedule", "Validate schedule field types are string in all returned days"),
    ("Schedule", "Validate schedule starttime strict format in all returned days"),
    ("Schedule", "Validate schedule starttime parseable in all returned days"),
    ("Schedule", "Validate schedule duration parseable as int seconds in all returned days"),
    ("Schedule", "Validate schedule duration matches program duration in all returned days"),
    ("Schedule", "Validate schedule content_id exists in program id in all returned days"),
    ("Schedule", "Validate service_id is constant per day in all returned days"),
    # --- NON-SSAI Schedule ---
    ("Schedule", "Validate Asset Duration in minutes match with Minutes Value in all 7 days"),
    ("Schedule", "Validate Asset Duration in seconds match with Seconds Value in all 7 days"),
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
