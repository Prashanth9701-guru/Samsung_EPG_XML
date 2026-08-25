"""Filter Failed SSAI validation rows into summary list for HTML reports."""

from __future__ import annotations

import ast
import logging
from collections import defaultdict
from typing import Any, Dict, List

from utilities.helper import Validation_Output

logger = logging.getLogger(__name__)


def ssai_failed_cases_seperator() -> List[Dict[str, Any]]:
    """
    Build updated_summary_list for summary_report_writer.

    SSAI Asset IDs are already:
      [{date: [{program_id: [details]}]}]
    Do not wrap again with extra [...].
    """
    updated_summary_list: List[Dict[str, Any]] = []
    logger.info("Started SSAI filtering of Failed cases")

    for data in Validation_Output:
        if data.get("Status") != "Failed":
            continue

        module = data.get("Module") or ""
        issue_summary = data.get("Issue Summary") or ""
        asset_ids_raw = data.get("Asset IDs") or ""

        if not asset_ids_raw:
            updated_summary_list.append(
                {
                    "Asset ID": "",
                    "Module": module,
                    "Issue Summary": issue_summary,
                }
            )
            continue

        try:
            parsed = ast.literal_eval(asset_ids_raw)
        except (ValueError, SyntaxError) as exc:
            logger.warning("SSAI Asset IDs parse failed: %s raw=%s", exc, asset_ids_raw[:200])
            updated_summary_list.append(
                {
                    "Asset ID": asset_ids_raw,
                    "Module": module,
                    "Issue Summary": issue_summary,
                }
            )
            continue

        # parsed: [{date: [{program_id: [details]}]}, ...]
        by_asset: Dict[str, Dict[str, List[Any]]] = defaultdict(lambda: defaultdict(list))

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
                    for program_id, details in id_obj.items():
                        detail_list = details if isinstance(details, list) else [details]
                        for detail in detail_list:
                            if detail not in by_asset[str(program_id)][str(date)]:
                                by_asset[str(program_id)][str(date)].append(detail)

        if not by_asset:
            updated_summary_list.append(
                {
                    "Asset ID": "",
                    "Module": module,
                    "Issue Summary": issue_summary,
                }
            )
            continue

        for program_id, date_map in by_asset.items():
            dates = sorted(date_map.keys())
            flat_details: List[Any] = []
            for d in dates:
                for item in date_map[d]:
                    if item not in flat_details:
                        flat_details.append(item)
            detail_preview = flat_details[0] if flat_details else ""
            summary = (
                f"In {', '.join(dates)} day(s): {issue_summary}"
                f" (e.g. {detail_preview})"
                if detail_preview != ""
                else f"In {', '.join(dates)} day(s): {issue_summary}"
            )
            updated_summary_list.append(
                {
                    "Asset ID": program_id,
                    "Module": module,
                    "Issue Summary": summary,
                }
            )

    logger.info("SSAI failed-case summary rows=%s", len(updated_summary_list))
    return updated_summary_list
