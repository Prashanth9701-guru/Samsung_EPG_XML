"""Filter Failed SSAI validation rows into summary list for HTML reports.

Mirrors NON_SSAI failed_cases_seperator: wrap Asset IDs with [...] then parse.
Supports Asset_Level ({date: [{id: details}]}) and Schedule ({id: [date, ...]}).
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from utilities.helper import Validation_Output

logger = logging.getLogger(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _is_date_key(key: Any) -> bool:
    return bool(_DATE_RE.match(str(key or "").strip()))


def _parse_ssai_asset_ids(asset_ids_raw: Any) -> Dict[str, Dict[str, List[Any]]]:
    """
    Parse NON_SSAI-style Asset IDs cell into {program_id: {date: [details]}}.

    Asset_Level: {date: [{program_id: [details]}, ...]},{date2: [...]}
    Schedule:    {program_id: [date, ...details]},{program_id2: [...]}
    """
    common_asset_ids: Dict[str, Dict[str, List[Any]]] = {}
    if not asset_ids_raw:
        return common_asset_ids

    raw = asset_ids_raw if isinstance(asset_ids_raw, str) else str(asset_ids_raw)
    try:
        parsed = ast.literal_eval(f"[{raw}]")
    except (ValueError, SyntaxError) as exc:
        logger.warning("SSAI Asset IDs parse failed: %s raw=%s", exc, raw[:200])
        return common_asset_ids

    if not isinstance(parsed, list):
        parsed = [parsed]

    for entry in parsed:
        if not isinstance(entry, dict):
            continue

        # Detect shape from first key: date-outer (Asset_Level) vs asset-outer (Schedule)
        keys = list(entry.keys())
        if not keys:
            continue

        if all(_is_date_key(k) for k in keys):
            for date, id_list in entry.items():
                if not isinstance(id_list, list):
                    continue
                for id_obj in id_list:
                    if not isinstance(id_obj, dict):
                        continue
                    for asset_id, value in id_obj.items():
                        if asset_id not in common_asset_ids:
                            common_asset_ids[asset_id] = {}
                        if date not in common_asset_ids[asset_id]:
                            common_asset_ids[asset_id][date] = []
                        details = value if isinstance(value, list) else [value]
                        common_asset_ids[asset_id][date].extend(
                            v for v in details if v not in common_asset_ids[asset_id][date]
                        )
            continue

        # Schedule-style: {asset_id: [date, ...details]}
        for asset_id, value in entry.items():
            details = value if isinstance(value, list) else [value]
            date = str(details[0]) if details and _is_date_key(details[0]) else "unknown"
            rest = details[1:] if details and _is_date_key(details[0]) else details
            if asset_id not in common_asset_ids:
                common_asset_ids[asset_id] = {}
            if date not in common_asset_ids[asset_id]:
                common_asset_ids[asset_id][date] = []
            common_asset_ids[asset_id][date].extend(
                v for v in rest if v not in common_asset_ids[asset_id][date]
            )

    return common_asset_ids


def _flat_details(values: Dict[str, List[Any]]) -> List[Any]:
    out: List[Any] = []
    for items in values.values():
        for item in items:
            if item not in out:
                out.append(item)
    return out


def _dates_csv(values: Dict[str, List[Any]]) -> str:
    return ", ".join(sorted(values.keys()))


def _with_dates_prefix(issue_summary: str, values: Dict[str, List[Any]]) -> str:
    """Prefix Issue Summary with failing day(s), matching NON-SSAI grouped tab style."""
    dates = _dates_csv(values)
    if not dates:
        return issue_summary
    return f"In {dates} days, {issue_summary}"


def _iter_schedule_asset_entries(asset_ids_raw: Any):
    """Yield (asset_id, [date, ...details]) for schedule-shaped Asset IDs cells."""
    if not asset_ids_raw:
        return
    raw = asset_ids_raw if isinstance(asset_ids_raw, str) else str(asset_ids_raw)
    try:
        parsed = ast.literal_eval(f"[{raw}]")
    except (ValueError, SyntaxError) as exc:
        logger.warning("SSAI schedule Asset IDs parse failed: %s raw=%s", exc, raw[:200])
        return
    if not isinstance(parsed, list):
        parsed = [parsed]
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        keys = list(entry.keys())
        if keys and all(_is_date_key(k) for k in keys):
            continue
        for asset_id, value in entry.items():
            details = value if isinstance(value, list) else [value]
            if details and _is_date_key(details[0]):
                yield str(asset_id), details


def _parse_gap_overlap_entry(details: List[Any]) -> Optional[Tuple[str, str]]:
    """Return (date, starttime) from schedule gap/overlap Asset IDs details."""
    if len(details) < 3:
        return None
    date = str(details[0])
    second = details[1]

    if isinstance(second, str) and second.startswith("delta="):
        if len(details) < 4:
            return None
        return date, str(details[3])

    if isinstance(second, (int, float)) and not isinstance(second, bool):
        if len(details) < 4:
            return None
        return date, str(details[3])

    return None


def _schedule_gap_issue_summary(date_csv: str, starttime: str) -> str:
    return (
        f"In {date_csv} days, Observing schedule gap of (delta - duration) "
        f"between consecutive assets (Asset Start Time's: {starttime})"
    )


def _schedule_overlap_issue_summary(date_csv: str, starttime: str) -> str:
    return (
        f"In {date_csv} days, Observing schedule overlap of (duration - delta) "
        f"between consecutive assets (Asset Start Time's: {starttime})"
    )


def _aggregate_schedule_gap_overlap_entries(
    asset_ids_raw: Any,
    *,
    is_overlap: bool,
):
    """Yield (asset_id, issue_summary) with merged date prefix per asset + starttime."""
    grouped: Dict[str, Dict[str, set]] = {}
    for asset_id, details in _iter_schedule_asset_entries(asset_ids_raw):
        parsed = _parse_gap_overlap_entry(details)
        if not parsed:
            continue
        date, starttime = parsed
        grouped.setdefault(asset_id, {}).setdefault(starttime, set()).add(date)

    builder = _schedule_overlap_issue_summary if is_overlap else _schedule_gap_issue_summary
    for asset_id, by_start in grouped.items():
        for starttime, dates in by_start.items():
            date_csv = ", ".join(sorted(dates))
            yield asset_id, builder(date_csv, starttime)


def ssai_failed_cases_seperator() -> List[Dict[str, Any]]:
    """Build updated_summary_list for summary_report_writer (NON_SSAI-style)."""
    filtered_list: List[Dict[str, Any]] = []
    updated_summary_list: List[Dict[str, Any]] = []
    i = 1
    logger.info("Started SSAI filtering of Failed Cases")

    for data in Validation_Output:
        if data.get("Status") != "Failed":
            continue
        filtered_list.append(
            {
                "S.No": i,
                "Module": data.get("Module"),
                "Scenario": data.get("Scenario"),
                "Issue Summary": data.get("Issue Summary"),
                "Asset IDs": data.get("Asset IDs"),
            }
        )
        i += 1

    for data in filtered_list:
        module = data.get("Module") or ""
        issue_summary = data.get("Issue Summary") or ""
        scenario = (data.get("Scenario") or "").strip()

        if module in ("URL", "Channel_Level"):
            updated_summary_list.append(
                {
                    "Asset ID": "",
                    "Module": module,
                    "Issue Summary": issue_summary,
                }
            )
            continue

        common_asset_ids = _parse_ssai_asset_ids(data.get("Asset IDs"))
        if not common_asset_ids:
            updated_summary_list.append(
                {
                    "Asset ID": "",
                    "Module": module,
                    "Issue Summary": issue_summary,
                }
            )
            continue

        if "Mandatory" in issue_summary:
            for key, values in common_asset_ids.items():
                duplicate_values = _flat_details(values)
                updated_summary_list.append(
                    {
                        "Asset ID": key,
                        "Module": module,
                        "Issue Summary": issue_summary.replace(
                            "Mandatory",
                            f"In {_dates_csv(values)} days, {', '.join(set(map(str, duplicate_values)))}",
                        ),
                    }
                )

        elif "in-correct length" in issue_summary and "proper-length" in issue_summary:
            for key, values in common_asset_ids.items():
                duplicate_values = _flat_details(values)
                json_val = duplicate_values[0] if duplicate_values else ""
                actual_val = duplicate_values[1] if len(duplicate_values) > 1 else ""
                summary = issue_summary.replace("in-correct length", str(actual_val)).replace(
                    "proper-length", str(json_val)
                )
                updated_summary_list.append(
                    {
                        "Asset ID": key,
                        "Module": module,
                        "Issue Summary": _with_dates_prefix(summary, values),
                    }
                )

        elif "in-correct-thumbnail" in issue_summary or "in-correct-length" in issue_summary:
            for key, values in common_asset_ids.items():
                duplicate_values = _flat_details(values)
                detail = duplicate_values[0] if duplicate_values else ""
                if "in-correct-thumbnail" in issue_summary:
                    summary = issue_summary.replace("in-correct-thumbnail", str(detail))
                else:
                    summary = issue_summary.replace("in-correct-length", str(detail))
                updated_summary_list.append(
                    {
                        "Asset ID": key,
                        "Module": module,
                        "Issue Summary": _with_dates_prefix(summary, values),
                    }
                )

        elif "fields are matching" in issue_summary:
            for key, values in common_asset_ids.items():
                updated_summary_list.append(
                    {
                        "Asset ID": key,
                        "Module": module,
                        "Issue Summary": f"In {_dates_csv(values)} days, {issue_summary}",
                    }
                )

        elif "in-correct-rating" in issue_summary or "invalid" in issue_summary.lower():
            for key, values in common_asset_ids.items():
                duplicate_values = _flat_details(values)
                token = "in-correct-rating" if "in-correct-rating" in issue_summary else "invalid"
                if token in issue_summary:
                    summary = (
                        f"In {_dates_csv(values)} days, "
                        f"{issue_summary.replace(token, ', '.join(set(map(str, duplicate_values))))}"
                    )
                else:
                    summary = (
                        f"In {_dates_csv(values)} days, {issue_summary}"
                        f" ({', '.join(set(map(str, duplicate_values)))})"
                    )
                updated_summary_list.append(
                    {
                        "Asset ID": key,
                        "Module": module,
                        "Issue Summary": summary,
                    }
                )

        elif "schedule duration is at least" in scenario.lower():
            for asset_id, details in _iter_schedule_asset_entries(data.get("Asset IDs")):
                if len(details) < 4:
                    continue
                date, dur, dur_min, start_time = details[0], details[1], details[2], details[3]
                updated_summary_list.append(
                    {
                        "Asset ID": asset_id,
                        "Module": module,
                        "Issue Summary": (
                            f"In {date} day, Scheduled asset duration is {dur} sec which is less "
                            f"than 20 minutes ({dur_min} seconds) "
                            f"(Asset Scheduled Time: {start_time})"
                        ),
                    }
                )

        elif "schedule duration is at most" in scenario.lower():
            for asset_id, details in _iter_schedule_asset_entries(data.get("Asset IDs")):
                if len(details) < 4:
                    continue
                date, dur, dur_max, start_time = details[0], details[1], details[2], details[3]
                updated_summary_list.append(
                    {
                        "Asset ID": asset_id,
                        "Module": module,
                        "Issue Summary": (
                            f"In {date} day, Scheduled asset duration is {dur} sec which is greater "
                            f"than 6 hours ({dur_max} seconds) "
                            f"(Asset Scheduled Time: {start_time})"
                        ),
                    }
                )

        elif "no schedule gaps" in scenario.lower():
            for asset_id, summary in _aggregate_schedule_gap_overlap_entries(
                data.get("Asset IDs"),
                is_overlap=False,
            ):
                updated_summary_list.append(
                    {
                        "Asset ID": asset_id,
                        "Module": module,
                        "Issue Summary": summary,
                    }
                )

        elif "no schedule overlaps" in scenario.lower():
            for asset_id, summary in _aggregate_schedule_gap_overlap_entries(
                data.get("Asset IDs"),
                is_overlap=True,
            ):
                updated_summary_list.append(
                    {
                        "Asset ID": asset_id,
                        "Module": module,
                        "Issue Summary": summary,
                    }
                )

        else:
            for key, values in common_asset_ids.items():
                updated_summary_list.append(
                    {
                        "Asset ID": key,
                        "Module": module,
                        "Issue Summary": _with_dates_prefix(issue_summary, values),
                    }
                )

    logger.info("Updated_Summary_List: %s", updated_summary_list)
    logger.info("SSAI Failed Cases Filtering is completed successfully")
    return updated_summary_list
