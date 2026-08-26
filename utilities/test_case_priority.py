"""Hardcoded test-case priorities derived from Samsung EPG XML Test Cases.xlsx (Sheet1)."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence, Tuple

PRIORITY_BLOCKER = "Blocker"

BLOCKER_CATALOG: Sequence[Tuple[str, str]] = (
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

_EXPLICIT_BLOCKER_KEYS: Dict[Tuple[str, str], str] = {
    ("Asset_Level", "validate asset id type"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate title type"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate title length"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate length of asset title"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate title has no unexpected special characters"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate description type"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate description length"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate description has no unexpected special characters"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate poster type is list"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate poster list entry type is object"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate poster url type is string"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate poster type present"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate poster width present"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate poster height present"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate poster resolution is 1920x1080"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate poster image format is jpg/jpeg"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate rating capitalization"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate rating against expected list"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate duration type is int"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate duplicate program id within each day"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate content_uri equals sheet stream url"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate content_uri ads macro keys"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate content_uri macro encoding"): PRIORITY_BLOCKER,
    ("Asset_Level", "validate assets having in-correct content_type"): PRIORITY_BLOCKER,
    ("Schedule", "validate schedule field types are string"): PRIORITY_BLOCKER,
    ("Schedule", "validate schedule starttime strict format"): PRIORITY_BLOCKER,
    ("Schedule", "validate schedule starttime parseable"): PRIORITY_BLOCKER,
    ("Schedule", "validate schedule duration parseable as int seconds"): PRIORITY_BLOCKER,
    ("Schedule", "validate schedule duration matches program duration"): PRIORITY_BLOCKER,
    ("Schedule", "validate schedule content_id exists in program id"): PRIORITY_BLOCKER,
    ("Schedule", "validate service_id is constant per day"): PRIORITY_BLOCKER,
}


def _normalize_scenario(text: str) -> str:
    s = re.sub(r"\s+", " ", (text or "").lower().strip())
    s = re.sub(r"\s+in all (?:\d+ )?days?\s*$", "", s)
    s = re.sub(r"\s+in all returned days\s*$", "", s)
    s = s.replace("asset id", "asset_id")
    s = s.replace("description", "desc")
    return re.sub(r"\s+", " ", s).strip()


_NORMALIZED_CATALOG: List[Tuple[str, str]] = [
    (path, _normalize_scenario(summary))
    for path, summary in BLOCKER_CATALOG
    if _normalize_scenario(summary)
]


def _infer_paths(module: str, scenario: str) -> List[str]:
    mod = (module or "").strip()
    s = _normalize_scenario(scenario)
    paths: List[str] = []

    if mod == "URL":
        if "top_level" in s or "top level" in s:
            paths.append("XML Nodes")
        return paths

    if mod == "Channel_Level":
        if "top_level" in s or "top level" in s:
            paths.append("XML Nodes")
        if "programs" in s:
            paths.append("programs")
        if "schedules" in s or "schedule" in s:
            paths.append("schedules")
        return paths

    if mod == "Asset_Level":
        if "asset_id" in s or "asset id" in (scenario or "").lower():
            paths.append("programs->asset_id")
        if "program id" in s or ("duplicate" in s and "id" in s):
            paths.append("programs->program->id")
        if "title" in s:
            paths.append("programs->program->title")
        if "desc" in s or "description" in (scenario or "").lower():
            paths.append("programs->program->desc")
        if "poster" in s:
            paths.append("programs->program->poster")
        if "rating" in s:
            paths.append("programs->program->rating")
        if "content_uri" in s or "content uri" in (scenario or "").lower():
            paths.append("programs->program->content_uri")
        if "content_type" in s or "content type" in (scenario or "").lower():
            paths.append("programs->program->content_type")
        if "duration" in s and "schedule" not in s:
            paths.append("programs->program->duration")

    if mod == "Schedule":
        paths.append("schedules")
        if "content_id" in s or "content id" in (scenario or "").lower():
            paths.append("schedules->content_id")
        if "duration" in s:
            paths.append("schedules->duration")
        if "starttime" in s or "start time" in (scenario or "").lower():
            paths.append("schedules->starttime")
        if "service_id" in s or "service id" in (scenario or "").lower():
            paths.append("schedules->service_id")
        if "schedule_id" in s or "schedule id" in (scenario or "").lower():
            paths.append("schedules->schedule_id")

    return list(dict.fromkeys(paths))


def _path_compatible(catalog_path: str, inferred_paths: Sequence[str]) -> bool:
    if not inferred_paths:
        return False
    for path in inferred_paths:
        if catalog_path == path:
            return True
        if catalog_path.startswith(path + "->") or path.startswith(catalog_path + "->"):
            return True
    return False


def _token_match(catalog_summary: str, runtime_summary: str) -> bool:
    stop = {"validate", "type", "the", "and", "for", "all", "per", "as", "is", "in", "of", "a"}
    tokens = [t for t in catalog_summary.split() if t not in stop and len(t) > 2]
    return bool(tokens) and all(token in runtime_summary for token in tokens)


def lookup_priority(module: str, scenario: str) -> str:
    norm_scenario = _normalize_scenario(scenario)
    explicit = _EXPLICIT_BLOCKER_KEYS.get(((module or "").strip(), norm_scenario))
    if explicit:
        return explicit

    inferred = _infer_paths(module, scenario)
    best_score = 0
    matched = False

    for path, norm_summary in _NORMALIZED_CATALOG:
        if not _path_compatible(path, inferred):
            continue
        if norm_summary == norm_scenario:
            return PRIORITY_BLOCKER
        if norm_summary in norm_scenario or norm_scenario in norm_summary:
            score = len(norm_summary)
            if score > best_score:
                best_score = score
                matched = True
        elif _token_match(norm_summary, norm_scenario):
            score = len(norm_summary)
            if score > best_score:
                best_score = score
                matched = True

    return PRIORITY_BLOCKER if matched else ""


def apply_priorities_to_validation_output(rows: Iterable[dict]) -> None:
    for row in rows:
        row["Priority"] = lookup_priority(row.get("Module", ""), row.get("Scenario", ""))


def issue_with_priority_suffix(issue_text: str, priority: str) -> str:
    p = (priority or "").strip()
    return f"{issue_text} ({p})" if p else issue_text
