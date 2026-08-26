"""Filter Failed SSAI validation rows into summary list for HTML reports.

Mirrors NON_SSAI failed_cases_seperator branching, but parses SSAI Asset IDs
without wrapping them in an extra [...].
"""

from __future__ import annotations

import ast
import logging
from typing import Any, Dict, List

from utilities.helper import Validation_Output

logger = logging.getLogger(__name__)


def _parse_ssai_asset_ids(asset_ids_raw: Any) -> Dict[str, Dict[str, List[Any]]]:
    """
    Parse SSAI Asset IDs shape: [{date: [{program_id: [details]}]}]
    into {program_id: {date: [details]}}.
    """
    common_asset_ids: Dict[str, Dict[str, List[Any]]] = {}
    if not asset_ids_raw:
        return common_asset_ids

    try:
        parsed = ast.literal_eval(asset_ids_raw if isinstance(asset_ids_raw, str) else str(asset_ids_raw))
    except (ValueError, SyntaxError) as exc:
        logger.warning("SSAI Asset IDs parse failed: %s raw=%s", exc, str(asset_ids_raw)[:200])
        return common_asset_ids

    if not isinstance(parsed, list):
        parsed = [parsed]

    for day_entry in parsed:
        if not isinstance(day_entry, dict):
            continue
        for date, id_list in day_entry.items():
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
    return common_asset_ids


def _flat_details(values: Dict[str, List[Any]]) -> List[Any]:
    out: List[Any] = []
    for items in values.values():
        for item in items:
            if item not in out:
                out.append(item)
    return out


def _dates_csv(values: Dict[str, List[Any]]) -> str:
    return ", ".join(list(values.keys()))


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
                        "Issue Summary": summary,
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

        elif "gap" in scenario.lower() or "overlap" in scenario.lower():
            for key, values in common_asset_ids.items():
                duplicate_values = _flat_details(values)
                detail = duplicate_values[0] if duplicate_values else ""
                updated_summary_list.append(
                    {
                        "Asset ID": key,
                        "Module": module,
                        "Issue Summary": (
                            f"In {_dates_csv(values)} days, {issue_summary}"
                            + (f" (e.g. {detail})" if detail != "" else "")
                        ),
                    }
                )

        else:
            for key, values in common_asset_ids.items():
                updated_summary_list.append(
                    {
                        "Asset ID": key,
                        "Module": module,
                        "Issue Summary": f"In {_dates_csv(values)} days, {issue_summary}",
                    }
                )

    logger.info("Updated_Summary_List: %s", updated_summary_list)
    logger.info("SSAI Failed Cases Filtering is completed successfully")
    return updated_summary_list
