"""SSAI AN3 program + schedule field validators (suites a–l).

Callable without master/runner via run_ssai_day_validations().
"""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from PIL import Image

from utilities.helper import Validation_Output, helper_fuc

logger = logging.getLogger(__name__)

_CONFIG: Optional[dict] = None
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config_ssai.yaml",
)

TITLE_SPECIAL_RE = re.compile(r"""^[A-Za-z0-9 _\-?:;,.’"!&/()']+$""")
DESC_SPECIAL_RE = re.compile(r"""^[A-Za-z0-9 !\-?:;,'’&.%"]+$""")
TBA_VALUES = {"tba", "to be announced", "to-be-announced"}


def _load_config() -> dict:
    global _CONFIG
    if _CONFIG is None:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            _CONFIG = yaml.safe_load(fh) or {}
    return _CONFIG


def _program_key(prog: Any) -> str:
    if not isinstance(prog, dict):
        return "unknown"
    pid = prog.get("id")
    if pid is None or pid == "":
        return "unknown"
    return str(pid)


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict, tuple, set)) and len(value) == 0:
        return True
    return False


def _merge_day_failures(
    failed_by_date: Dict[str, Dict[str, List[Any]]],
) -> str:
    """
    NON_SSAI Asset_Level Asset IDs cell (no outer list):
      {date: [{program_id: [details]}, ...]},{date2: [...]}
    """
    if not failed_by_date:
        return ""
    parts: List[str] = []
    for date in sorted(failed_by_date.keys()):
        id_map = failed_by_date[date] or {}
        day_entries = [{pid: details} for pid, details in id_map.items()]
        if day_entries:
            parts.append(str({date: day_entries}))
    return ",".join(parts)


def _merge_schedule_failures(
    failed_by_date: Dict[str, Dict[str, List[Any]]],
) -> str:
    """
    NON_SSAI Schedule Asset IDs cell (no outer list):
      {program_id: [date, ...details]},{program_id2: [...]}
    """
    if not failed_by_date:
        return ""
    parts: List[str] = []
    for date in sorted(failed_by_date.keys()):
        id_map = failed_by_date[date] or {}
        for pid, details in id_map.items():
            detail_list = details if isinstance(details, list) else [details]
            parts.append(str({pid: [date, *detail_list]}))
    return ",".join(parts)


def _serialize_asset_ids(
    module: str,
    bucket: Dict[str, Dict[str, List[Any]]],
) -> str:
    if (module or "").strip() == "Schedule":
        return _merge_schedule_failures(bucket)
    return _merge_day_failures(bucket)


def _record(
    bucket: Dict[str, Dict[str, List[Any]]],
    date: str,
    key: str,
    detail: Any,
) -> None:
    dest = bucket.setdefault(date, {}).setdefault(key, [])
    if isinstance(detail, list):
        dest.extend(detail)
    else:
        dest.append(detail)


def _strip_control_chars(text: str) -> str:
    return "".join(
        ch for ch in text if not unicodedata.category(ch).startswith("C")
    )


def _translate_to_english(text: str) -> str:
    try:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="auto", target="en").translate(text) or text
    except Exception as exc:
        logger.debug("translate skipped: %s", exc)
        return text


def _has_special_chars(text: str, kind: str) -> bool:
    """Return True if text fails the NON_SSAI allow-list regex for title/desc."""
    cleaned = _strip_control_chars(text)
    english = _translate_to_english(cleaned)
    pattern = DESC_SPECIAL_RE if kind == "desc" else TITLE_SPECIAL_RE
    return not bool(pattern.search(english))


def _parse_starttime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            if fmt.endswith("%z") and s.endswith("Z"):
                s2 = s[:-1] + "+0000"
                return datetime.strptime(s2, "%Y-%m-%dT%H:%M:%S%z")
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        # Last resort: fromisoformat with Z
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _parse_duration_seconds(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return None


def _append_row(
    num: int,
    module: str,
    scenario: str,
    expected: str,
    failed: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
    pass_msg: str,
    fail_msg: str,
    not_tested_msg: str,
) -> int:
    if failed:
        Validation_Output.append(
            helper_fuc(
                num,
                module,
                scenario,
                expected,
                "Failed",
                fail_msg,
                _serialize_asset_ids(module, failed),
            )
        )
    elif not_tested:
        Validation_Output.append(
            helper_fuc(
                num,
                module,
                scenario,
                expected,
                "Not Tested",
                not_tested_msg,
                _serialize_asset_ids(module, not_tested),
            )
        )
    else:
        Validation_Output.append(
            helper_fuc(num, module, scenario, expected, "Passed", pass_msg, "")
        )
    return num + 1


# ---------------------------------------------------------------------------
# Suite collectors (mutate failed / not_tested buckets)
# ---------------------------------------------------------------------------


def _suite_ab_mandatory(
    date: str,
    programs: List[dict],
    config: dict,
    missing: Dict[str, Dict[str, List[Any]]],
    empty: Dict[str, Dict[str, List[Any]]],
) -> None:
    logger.info(f"Running suite_ab_mandatory for date: {date}")
    fields = config.get("mandatory_fields") or []
    for prog in programs:
        if not isinstance(prog, dict):
            _record(missing, date, "unknown", ["program entry is not an object"])
            continue
        key = _program_key(prog)
        logger.info(f'Mandatory Fields Validation {date}: {fields} and {prog}')
        for field in fields:
            if field not in prog:
                _record(missing, date, key, [f"{field} missing"])
            elif _is_empty(prog.get(field)):
                _record(empty, date, key, [f"{field} empty"])

    logger.info(f"Completed suite_ab_mandatory for date: {date}")

def _suite_dup_ids(
    date: str,
    programs: List[dict],
    failed: Dict[str, Dict[str, List[Any]]],
) -> None:
    seen: Dict[str, int] = {}
    logger.info(f"Running suite_dup_ids for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        pid = prog.get("id")
        if pid is None or pid == "":
            continue
        pid_s = str(pid)
        seen[pid_s] = seen.get(pid_s, 0) + 1
    for pid_s, count in seen.items():
        if count > 1:
            _record(failed, date, pid_s, [f"duplicate program.id count={count}"])

    logger.info(f"Completed suite_dup_ids for date: {date}")

def _suite_c_asset_id(
    date: str,
    programs: List[dict],
    config: dict,
    type_fail: Dict[str, Dict[str, List[Any]]],
    length_fail: Dict[str, Dict[str, List[Any]]],
    eq_title: Dict[str, Dict[str, List[Any]]],
    eq_desc: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    max_len = (config.get("lengths") or {}).get("id", 50)
    logger.info(f"Running suite_c_asset_id for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "id" not in prog:
            _record(not_tested, date, key, ["asset_id not available"])
            continue
        asset_id = prog.get("id")
        if _is_empty(asset_id):
            _record(not_tested, date, key, ["asset_id empty"])
            continue
        if not isinstance(asset_id, str):
            _record(type_fail, date, key, [f"asset_id not string: {type(asset_id).__name__}"])
            continue
        if len(asset_id) > max_len:
            _record(length_fail, date, key, [len(asset_id), asset_id])
        title = prog.get("title")
        desc = prog.get("desc")
        if isinstance(title, str) and title in asset_id:
            _record(eq_title, date, key, [asset_id])
        if isinstance(desc, str) and desc in asset_id:
            _record(eq_desc, date, key, [asset_id])

    logger.info(f"Completed suite_c_asset_id for date: {date}")


def _suite_d_title(
    date: str,
    programs: List[dict],
    config: dict,
    type_fail: Dict[str, Dict[str, List[Any]]],
    tba_fail: Dict[str, Dict[str, List[Any]]],
    eq_desc: Dict[str, Dict[str, List[Any]]],
    length_fail: Dict[str, Dict[str, List[Any]]],
    special_fail: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    max_len = (config.get("lengths") or {}).get("title", 200)
    logger.info(f"Running suite_d_title for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "title" not in prog:
            _record(not_tested, date, key, ["title not available"])
            continue
        title = prog.get("title")
        if _is_empty(title):
            _record(not_tested, date, key, ["title empty"])
            continue
        if not isinstance(title, str):
            _record(type_fail, date, key, [f"title not string: {type(title).__name__}"])
            continue
        if title.strip().lower() in TBA_VALUES:
            _record(tba_fail, date, key, [title])
        desc = prog.get("desc")
        if isinstance(desc, str) and title == desc:
            _record(eq_desc, date, key, [title])
        if len(title) > max_len:
            _record(length_fail, date, key, [len(title), title])
        if _has_special_chars(title, "title"):
            _record(special_fail, date, key, [title])

    logger.info(f"Completed suite_d_title for date: {date}")

def _fetch_poster_image(url: str, timeout: int = 60):
    """Return (response, error_detail). Uses allow_redirects=False."""
    last_exc = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=timeout, allow_redirects=False)
            return response, None
        except requests.RequestException as exc:
            last_exc = exc
            logger.info("Poster fetch attempt %s failed: %s url=%s", attempt + 1, exc, url)
            time.sleep(1)
    return None, f"network error: {last_exc}"


def _suite_e_poster(
    date: str,
    programs: List[dict],
    config: dict,
    buckets: Dict[str, Dict[str, Dict[str, List[Any]]]],
) -> None:
    """
    buckets keys: missing, url_missing, url_type, url_len, status, redirect,
                  format, resolution, type_missing, width_missing, height_missing, wh_mismatch
    """
    logger.info(f"Running suite_e_poster for date: {date}")
    lengths = config.get("lengths") or {}
    thumb = config.get("thumbnail") or {}
    max_url = lengths.get("poster_url", 2000)
    exp_w = int(thumb.get("width", 1920))
    exp_h = int(thumb.get("height", 1080))
    formats = {str(f).lower() for f in (thumb.get("formats") or ["jpg", "jpeg"])}

    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "poster" not in prog:
            _record(buckets["missing"], date, key, ["poster not available"])
            continue
        poster = prog.get("poster")
        if _is_empty(poster):
            _record(buckets["missing"], date, key, ["poster empty"])
            continue
        if not isinstance(poster, list):
            _record(buckets["missing"], date, key, ["poster not a list"])
            continue
        first = poster[0]
        if not isinstance(first, dict):
            _record(buckets["url_missing"], date, key, ["poster[0] not an object"])
            continue

        url = first.get("url")
        if _is_empty(url):
            _record(buckets["url_missing"], date, key, ["poster[0].url missing"])
            continue
        if not isinstance(url, str):
            _record(buckets["url_type"], date, key, [f"url not string: {type(url).__name__}"])
            continue
        if len(url) > max_url:
            _record(buckets["url_len"], date, key, [len(url), url])

        ptype = first.get("type")
        pwidth = first.get("width")
        pheight = first.get("height")
        if _is_empty(ptype):
            _record(buckets["type_missing"], date, key, ["type missing"])
        if _is_empty(pwidth):
            _record(buckets["width_missing"], date, key, ["width missing"])
        if _is_empty(pheight):
            _record(buckets["height_missing"], date, key, ["height missing"])

        response, net_err = _fetch_poster_image(url)
        if net_err:
            _record(buckets["status"], date, key, [net_err, url])
            continue
        assert response is not None
        if response.status_code in (301, 302, 303, 307, 308):
            _record(buckets["redirect"], date, key, [response.status_code, url])
            continue
        if response.status_code != 200:
            _record(buckets["status"], date, key, [response.status_code, url])
            continue
        try:
            image = Image.open(BytesIO(response.content))
            width, height = image.size
            fmt = str(image.format or "").lower()
            if fmt not in formats and fmt not in {"jpeg", "jpg"}:
                _record(buckets["format"], date, key, [image.format, url])
            if (width, height) != (exp_w, exp_h):
                _record(buckets["resolution"], date, key, [f"{width}X{height}", url])
            try:
                jw = int(pwidth) if pwidth is not None and not _is_empty(pwidth) else None
                jh = int(pheight) if pheight is not None and not _is_empty(pheight) else None
            except (TypeError, ValueError):
                jw, jh = None, None
                _record(buckets["wh_mismatch"], date, key, ["width/height not numeric", pwidth, pheight, url])
            if jw is not None and jw != width:
                _record(buckets["wh_mismatch"], date, key, ["width mismatch", pwidth, width, url])
            if jh is not None and jh != height:
                _record(buckets["wh_mismatch"], date, key, ["height mismatch", pheight, height, url])
            if not _is_empty(ptype) and str(ptype).lower() not in formats and str(ptype).lower() not in {
                "jpeg",
                "jpg",
                "image/jpeg",
                "image/jpg",
            }:
                if str(ptype).lower() not in {fmt, f"image/{fmt}"}:
                    _record(buckets["format"], date, key, [f"json type={ptype}", image.format, url])
        except Exception as exc:
            _record(buckets["status"], date, key, [f"processing error: {exc}", url])

    logger.info(f"Completed suite_e_poster for date: {date}")


def _suite_f_genre(
    date: str,
    programs: List[dict],
    config: dict,
    structure_fail: Dict[str, Dict[str, List[Any]]],
    allowlist_fail: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    allowed = set(config.get("genres") or [])
    logger.info(f"Running suite_f_genre for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "genre" not in prog:
            _record(not_tested, date, key, ["genre not available"])
            continue
        genre = prog.get("genre")
        if _is_empty(genre):
            _record(not_tested, date, key, ["genre empty"])
            continue
        if not isinstance(genre, list):
            _record(structure_fail, date, key, [f"genre not a list: {type(genre).__name__}"])
            continue
        for item in genre:
            if not isinstance(item, dict):
                _record(structure_fail, date, key, ["genre item not an object"])
                continue
            gid = item.get("id")
            name = item.get("original_name")
            struct_ok = True
            if _is_empty(gid) or not isinstance(gid, str):
                _record(structure_fail, date, key, ["genre.id missing or not string", item])
                struct_ok = False
            if _is_empty(name) or not isinstance(name, str):
                _record(structure_fail, date, key, ["genre.original_name missing or not string", item])
                struct_ok = False
            elif struct_ok and name not in allowed:
                _record(allowlist_fail, date, key, [name])

    logger.info(f"Completed suite_f_genre for date: {date}")


def _suite_g_rating(
    date: str,
    programs: List[dict],
    config: dict,
    failed: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    allowed = {str(r) for r in (config.get("ratings") or [])}
    logger.info(f"Running suite_g_rating for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "rating" not in prog:
            _record(not_tested, date, key, ["rating not available"])
            continue
        rating = prog.get("rating")
        if _is_empty(rating):
            _record(not_tested, date, key, ["rating empty"])
            continue
        if not isinstance(rating, str):
            _record(failed, date, key, [f"rating not string: {type(rating).__name__}"])
            continue
        if rating not in allowed:
            _record(failed, date, key, [rating])

    logger.info(f"Completed suite_g_rating for date: {date}")

def _suite_h_desc(
    date: str,
    programs: List[dict],
    config: dict,
    type_fail: Dict[str, Dict[str, List[Any]]],
    length_fail: Dict[str, Dict[str, List[Any]]],
    special_fail: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    max_len = (config.get("lengths") or {}).get("desc", 4000)
    logger.info(f"Running suite_h_desc for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "desc" not in prog:
            _record(not_tested, date, key, ["desc not available"])
            continue
        desc = prog.get("desc")
        if _is_empty(desc):
            _record(not_tested, date, key, ["desc empty"])
            continue
        if not isinstance(desc, str):
            _record(type_fail, date, key, [f"desc not string: {type(desc).__name__}"])
            continue
        if len(desc) > max_len:
            _record(length_fail, date, key, [len(desc), desc[:80]])
        if _has_special_chars(desc, "desc"):
            _record(special_fail, date, key, [desc[:80]])

    logger.info(f"Completed suite_h_desc for date: {date}")

def _suite_i_duration(
    date: str,
    programs: List[dict],
    type_fail: Dict[str, Dict[str, List[Any]]],
    zero_fail: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    logger.info(f"Running suite_i_duration for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "duration" not in prog:
            _record(not_tested, date, key, ["duration not available"])
            continue
        duration = prog.get("duration")
        if _is_empty(duration) and duration != 0:
            _record(not_tested, date, key, ["duration empty"])
            continue
        if not isinstance(duration, int) or isinstance(duration, bool):
            _record(type_fail, date, key, [f"duration not int: {type(duration).__name__}", duration])
            continue
        if duration == 0:
            _record(zero_fail, date, key, ["duration is 0"])

    logger.info(f"Completed suite_i_duration for date: {date}")


def _suite_k_content_uri(
    date: str,
    programs: List[dict],
    stream_url: str,
    failed: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    logger.info(f"Running suite_k_content_uri for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "content_uri" not in prog:
            _record(not_tested, date, key, ["content_uri not available"])
            continue
        uri = prog.get("content_uri")
        if _is_empty(uri):
            _record(not_tested, date, key, ["content_uri empty"])
            continue
        if not isinstance(uri, str):
            _record(failed, date, key, [f"content_uri not string: {type(uri).__name__}"])
            continue
        if uri != stream_url:
            _record(failed, date, key, [uri, stream_url])

    logger.info(f"Completed suite_k_content_uri for date: {date}")

def _suite_l_cast(
    date: str,
    programs: List[dict],
    type_fail: Dict[str, Dict[str, List[Any]]],
    empty_fail: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    logger.info(f"Running suite_l_cast for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "cast" not in prog:
            _record(not_tested, date, key, ["cast not available"])
            continue
        cast = prog.get("cast")
        if cast is None:
            _record(not_tested, date, key, ["cast not available"])
            continue
        if not isinstance(cast, list):
            _record(type_fail, date, key, [f"cast not a list: {type(cast).__name__}"])
            continue
        if len(cast) == 0:
            _record(empty_fail, date, key, ["cast empty"])

    logger.info(f"Completed suite_l_cast for date: {date}")


def _suite_j_schedule(
    date: str,
    programs: List[dict],
    schedules: List[dict],
    config: dict,
    buckets: Dict[str, Dict[str, Dict[str, List[Any]]]],
) -> None:
    """
    buckets: missing_fields, empty_fields, gap, overlap, content_missing,
             duration_mismatch, id_equals_schedule, start_parse, dur_parse
    """
    logger.info(f"Running suite_j_schedule for date: {date}")
    mand = config.get("schedule_mandatory_fields") or []
    program_by_id: Dict[str, dict] = {}
    for prog in programs:
        if isinstance(prog, dict) and prog.get("id") is not None:
            program_by_id[str(prog.get("id"))] = prog

    parsed_rows: List[Tuple[datetime, dict, str, Optional[int]]] = []

    for entry in schedules:
        if not isinstance(entry, dict):
            _record(buckets["missing_fields"], date, "unknown", ["schedule entry not an object"])
            continue
        cid = entry.get("content_id")
        key = str(cid) if not _is_empty(cid) else str(entry.get("schedule_id") or "unknown")

        for field in mand:
            if field not in entry:
                _record(buckets["missing_fields"], date, key, [f"{field} missing"])
            elif _is_empty(entry.get(field)):
                _record(buckets["empty_fields"], date, key, [f"{field} empty"])

        start = _parse_starttime(entry.get("starttime"))
        if entry.get("starttime") is not None and not _is_empty(entry.get("starttime")) and start is None:
            _record(buckets["start_parse"], date, key, [entry.get("starttime")])

        dur = _parse_duration_seconds(entry.get("duration"))
        if entry.get("duration") is not None and not _is_empty(entry.get("duration")) and dur is None:
            _record(buckets["dur_parse"], date, key, [entry.get("duration")])

        if not _is_empty(cid):
            cid_s = str(cid)
            if cid_s not in program_by_id:
                _record(buckets["content_missing"], date, key, [cid_s])
            else:
                prog_dur = program_by_id[cid_s].get("duration")
                if dur is not None and isinstance(prog_dur, int) and not isinstance(prog_dur, bool):
                    if prog_dur != dur:
                        _record(
                            buckets["duration_mismatch"],
                            date,
                            key,
                            [f"program_duration={prog_dur}", f"schedule_duration={dur}"],
                        )
            sid = entry.get("schedule_id")
            if not _is_empty(sid) and str(cid) == str(sid):
                _record(buckets["id_equals_schedule"], date, key, [cid, sid])

        if start is not None:
            parsed_rows.append((start, entry, key, dur))

    parsed_rows.sort(key=lambda row: row[0])
    for i in range(len(parsed_rows) - 1):
        curr_start, curr_entry, curr_key, curr_dur = parsed_rows[i]
        next_start, _, _, _ = parsed_rows[i + 1]
        if curr_dur is None:
            _record(buckets["dur_parse"], date, curr_key, ["cannot compute gap/overlap; duration unparseable"])
            continue
        delta = int((next_start - curr_start).total_seconds())
        if delta > curr_dur:
            _record(
                buckets["gap"],
                date,
                curr_key,
                [f"delta={delta}", f"duration={curr_dur}", curr_entry.get("starttime")],
            )
        elif delta < curr_dur:
            _record(
                buckets["overlap"],
                date,
                curr_key,
                [f"delta={delta}", f"duration={curr_dur}", curr_entry.get("starttime")],
            )

    logger.info(f"Completed suite_j_schedule for date: {date}")

def run_ssai_day_validations(
    by_date: dict,
    stream_url: str,
    sequence_number: int = 1,
    ticket_id: str = "",
) -> int:
    """
    Run suites a–l across all days in by_date and append Validation_Output rows.

    by_date: {date: {program: [...], schedule: [...]}}
    Returns next sequence_number.
    """
    prefix = f"{ticket_id} " if ticket_id else ""
    config = _load_config()
    num = sequence_number

    # Accumulators across dates
    ab_missing: Dict[str, Dict[str, List[Any]]] = {}
    ab_empty: Dict[str, Dict[str, List[Any]]] = {}
    dup_failed: Dict[str, Dict[str, List[Any]]] = {}

    c_type: Dict[str, Dict[str, List[Any]]] = {}
    c_len: Dict[str, Dict[str, List[Any]]] = {}
    c_eq_title: Dict[str, Dict[str, List[Any]]] = {}
    c_eq_desc: Dict[str, Dict[str, List[Any]]] = {}
    c_nt: Dict[str, Dict[str, List[Any]]] = {}

    d_type: Dict[str, Dict[str, List[Any]]] = {}
    d_tba: Dict[str, Dict[str, List[Any]]] = {}
    d_eq: Dict[str, Dict[str, List[Any]]] = {}
    d_len: Dict[str, Dict[str, List[Any]]] = {}
    d_spec: Dict[str, Dict[str, List[Any]]] = {}
    d_nt: Dict[str, Dict[str, List[Any]]] = {}

    poster_keys = (
        "missing",
        "url_missing",
        "url_type",
        "url_len",
        "status",
        "redirect",
        "format",
        "resolution",
        "type_missing",
        "width_missing",
        "height_missing",
        "wh_mismatch",
    )
    poster_buckets = {k: {} for k in poster_keys}

    f_structure: Dict[str, Dict[str, List[Any]]] = {}
    f_allowlist: Dict[str, Dict[str, List[Any]]] = {}
    f_nt: Dict[str, Dict[str, List[Any]]] = {}
    g_failed: Dict[str, Dict[str, List[Any]]] = {}
    g_nt: Dict[str, Dict[str, List[Any]]] = {}

    h_type: Dict[str, Dict[str, List[Any]]] = {}
    h_len: Dict[str, Dict[str, List[Any]]] = {}
    h_spec: Dict[str, Dict[str, List[Any]]] = {}
    h_nt: Dict[str, Dict[str, List[Any]]] = {}

    i_type: Dict[str, Dict[str, List[Any]]] = {}
    i_zero: Dict[str, Dict[str, List[Any]]] = {}
    i_nt: Dict[str, Dict[str, List[Any]]] = {}

    sched_keys = (
        "missing_fields",
        "empty_fields",
        "gap",
        "overlap",
        "content_missing",
        "duration_mismatch",
        "id_equals_schedule",
        "start_parse",
        "dur_parse",
    )
    sched_buckets = {k: {} for k in sched_keys}

    k_failed: Dict[str, Dict[str, List[Any]]] = {}
    k_nt: Dict[str, Dict[str, List[Any]]] = {}
    l_type: Dict[str, Dict[str, List[Any]]] = {}
    l_empty: Dict[str, Dict[str, List[Any]]] = {}
    l_nt: Dict[str, Dict[str, List[Any]]] = {}

    if not by_date:
        logger.warning("%srun_ssai_day_validations: empty by_date", prefix)

    for date in sorted((by_date or {}).keys()):
        day = by_date.get(date) or {}
        programs = day.get("program") if isinstance(day.get("program"), list) else []
        schedules = day.get("schedule") if isinstance(day.get("schedule"), list) else []
        logger.info(
            "%sValidating date=%s programs=%s schedules=%s",
            prefix,
            date,
            len(programs),
            len(schedules),
        )

        _suite_ab_mandatory(date, programs, config, ab_missing, ab_empty)
        _suite_dup_ids(date, programs, dup_failed)
        _suite_c_asset_id(date, programs, config, c_type, c_len, c_eq_title, c_eq_desc, c_nt)
        _suite_d_title(date, programs, config, d_type, d_tba, d_eq, d_len, d_spec, d_nt)
        _suite_e_poster(date, programs, config, poster_buckets)
        _suite_f_genre(date, programs, config, f_structure, f_allowlist, f_nt)
        _suite_g_rating(date, programs, config, g_failed, g_nt)
        _suite_h_desc(date, programs, config, h_type, h_len, h_spec, h_nt)
        _suite_i_duration(date, programs, i_type, i_zero, i_nt)
        _suite_j_schedule(date, programs, schedules, config, sched_buckets)
        _suite_k_content_uri(date, programs, stream_url, k_failed, k_nt)
        _suite_l_cast(date, programs, l_type, l_empty, l_nt)

    mod = "Asset_Level"
    sch = "Schedule"

    # a–b
    num = _append_row(
        num, mod,
        "Validate mandatory fields presence for Assets in all returned days",
        "All mandatory fields should be present on every program",
        ab_missing, {},
        "All mandatory fields are present",
        "Mandatory fields are missing for some assets",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate mandatory fields non-empty for Assets in all returned days",
        "All mandatory fields should have non-empty values",
        ab_empty, {},
        "All mandatory field values are non-empty",
        "Mandatory field values are empty for some assets",
        "",
    )

    # duplicate ids
    num = _append_row(
        num, mod,
        "Validate duplicate program.id within each day",
        "program.id should be unique within a day",
        dup_failed, {},
        "No duplicate program.id values",
        "Duplicate program.id values found",
        "",
    )

    asset_id_max = (config.get("lengths") or {}).get("asset_id", 50)
    empty_nt: Dict[str, Dict[str, List[Any]]] = {}

    # c — Asset ID (4 atomic cases)
    num = _append_row(
        num, mod,
        "Validate Asset ID Type in all returned days",
        "Asset ID should be a string for all Assets in all returned days",
        c_type, c_nt,
        "Asset ID type is string for all assets",
        "Asset ID type is in-correct for some assets (not a string)",
        "Asset ID not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate Asset ID Length in all returned days",
        f"Length of Asset ID should not exceed {asset_id_max} characters in all returned days",
        c_len, empty_nt,
        f"Asset ID Length is within the expected limit of {asset_id_max} characters",
        f"Asset ID length is in-correct-length which is more than expected limit of {asset_id_max} characters",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Asset ID should not contain Title in all returned days",
        "Asset ID and Title should not be same for all Assets in all returned days",
        c_eq_title, empty_nt,
        "Asset ID and Title fields are not matching",
        "Asset ID and Title fields are matching",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Asset ID should not contain Description in all returned days",
        "Asset ID and Description should not be same for all Assets in all returned days",
        c_eq_desc, empty_nt,
        "Asset ID and Description fields are not matching",
        "Asset ID and Description fields are matching",
        "",
    )

    # d
    num = _append_row(
        num, mod,
        "Validate title is a string",
        "title should be a string",
        d_type, d_nt,
        "All titles are strings",
        "Some titles are not strings",
        "title not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate title is not TBA / To Be Announced",
        "title should not be TBA or To Be Announced",
        d_tba, empty_nt,
        "No TBA titles",
        "Some titles are TBA / To Be Announced",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate title is not equal to desc",
        "title should not equal desc",
        d_eq, empty_nt,
        "title and desc are distinct",
        "Some titles equal desc",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate title length",
        f"title length should be <= {(config.get('lengths') or {}).get('title', 200)}",
        d_len, empty_nt,
        "All title lengths within limit",
        "Some titles exceed max length",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate title has no unexpected special characters",
        "title should match allowed character set",
        d_spec, empty_nt,
        "No unexpected special characters in titles",
        "Some titles have unexpected special characters",
        "",
    )

    # e poster
    num = _append_row(
        num, mod,
        "Validate poster availability (poster[0])",
        "poster list with poster[0] should be available",
        {}, poster_buckets["missing"],
        "poster is available for all assets",
        "poster not available for some assets",
        "poster not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate Poster URL availability in all returned days",
        "Poster URL should be available for all Assets in all returned days",
        poster_buckets["url_missing"], empty_nt,
        "Poster URL is available for all assets",
        "Poster URL not available for some assets",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster URL type is string in all returned days",
        "Poster URL should be a string for all Assets in all returned days",
        poster_buckets["url_type"], empty_nt,
        "Poster URL type is string for all assets",
        "Poster URL type is in-correct for some assets (not a string)",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate poster URL length",
        f"poster URL length should be <= {(config.get('lengths') or {}).get('poster_url', 2000)}",
        poster_buckets["url_len"], empty_nt,
        "poster URL lengths within limit",
        "Some poster URLs exceed max length",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate poster HTTP status is 200",
        "poster URL should return HTTP 200",
        poster_buckets["status"], empty_nt,
        "All poster URLs return 200",
        "Some poster URLs failed to load",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate poster URL has no redirect",
        "poster URL should not redirect",
        poster_buckets["redirect"], empty_nt,
        "No poster redirects",
        "Some poster URLs redirect",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate poster image format is JPG/JPEG",
        "poster image format should be JPG/JPEG",
        poster_buckets["format"], empty_nt,
        "All posters are JPG/JPEG",
        "Some posters have unexpected format",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate poster resolution is 1920x1080",
        "poster actual image size should be 1920x1080",
        poster_buckets["resolution"], empty_nt,
        "All posters are 1920x1080",
        "Some posters are not 1920x1080",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster type present in all returned days",
        "poster[0].type should be present for all Assets in all returned days",
        poster_buckets["type_missing"], empty_nt,
        "Poster type is present for all assets",
        "Poster type not available for some assets",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster width present in all returned days",
        "poster[0].width should be present for all Assets in all returned days",
        poster_buckets["width_missing"], empty_nt,
        "Poster width is present for all assets",
        "Poster width not available for some assets",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster height present in all returned days",
        "poster[0].height should be present for all Assets in all returned days",
        poster_buckets["height_missing"], empty_nt,
        "Poster height is present for all assets",
        "Poster height not available for some assets",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate poster JSON width/height match actual image",
        "poster JSON width/height should match downloaded image",
        poster_buckets["wh_mismatch"], empty_nt,
        "poster metadata matches image",
        "poster width/height mismatch vs image",
        "",
    )

    # f–i
    num = _append_row(
        num, mod,
        "Validate Genre structure in all returned days",
        "genre should be a list of objects with id and original_name for all Assets in all returned days",
        f_structure, f_nt,
        "All genre structures are valid",
        "Some genres have invalid structure",
        "genre not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate Genre original_name as per expected list in all returned days",
        "genre original_name should be present in the expected genre list for all Assets in all returned days",
        f_allowlist, empty_nt,
        "All genre original_name values are in the expected list",
        "Some genre original_name values are invalid",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate rating against expected list",
        "rating should be a string in the expected ratings list",
        g_failed, g_nt,
        "All ratings are valid",
        "Some ratings are unexpected",
        "rating not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate desc is a string",
        "desc should be a string",
        h_type, h_nt,
        "All desc values are strings",
        "Some desc values are not strings",
        "desc not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate desc length",
        f"desc length should be <= {(config.get('lengths') or {}).get('desc', 4000)}",
        h_len, empty_nt,
        "All desc lengths within limit",
        "Some desc values exceed max length",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate desc has no unexpected special characters",
        "desc should match allowed character set",
        h_spec, empty_nt,
        "No unexpected special characters in desc",
        "Some desc values have unexpected special characters",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Duration type is int in all returned days",
        "duration should be an int for all Assets in all returned days",
        i_type, i_nt,
        "All durations are ints",
        "Some durations are not ints",
        "duration not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate Duration is not zero in all returned days",
        "duration should not be equal to 0 for all Assets in all returned days",
        i_zero, empty_nt,
        "All durations are non-zero",
        "Some durations are zero",
        "",
    )

    # j schedule
    num = _append_row(
        num, sch,
        "Validate schedule mandatory fields presence",
        "service_id, content_id, schedule_id, starttime, duration should be present",
        sched_buckets["missing_fields"], empty_nt,
        "All schedule mandatory fields present",
        "Schedule mandatory fields missing",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule mandatory fields non-empty",
        "Schedule mandatory fields should be non-empty",
        sched_buckets["empty_fields"], empty_nt,
        "All schedule mandatory values non-empty",
        "Schedule mandatory values empty",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule starttime parseable",
        "starttime should be a parseable ISO datetime",
        sched_buckets["start_parse"], empty_nt,
        "All starttime values parseable",
        "Some starttime values not parseable",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule duration parseable as int seconds",
        "duration should parse to int seconds",
        sched_buckets["dur_parse"], empty_nt,
        "All schedule durations parseable",
        "Some schedule durations not parseable",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate no schedule gaps between consecutive assets",
        "delta(next.start - curr.start) should equal curr.duration",
        sched_buckets["gap"], empty_nt,
        "No schedule gaps",
        "Schedule gaps observed",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate no schedule overlaps between consecutive assets",
        "delta(next.start - curr.start) should equal curr.duration",
        sched_buckets["overlap"], empty_nt,
        "No schedule overlaps",
        "Schedule overlaps observed",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule content_id exists in program[].id",
        "content_id should match a program.id",
        sched_buckets["content_missing"], empty_nt,
        "All content_id values resolve to programs",
        "Some content_id values missing from programs",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule duration matches program duration",
        "int(schedule.duration) should equal program.duration",
        sched_buckets["duration_mismatch"], empty_nt,
        "Schedule and program durations match",
        "Schedule/program duration mismatches",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate content_id is not equal to schedule_id",
        "content_id should differ from schedule_id",
        sched_buckets["id_equals_schedule"], empty_nt,
        "content_id differs from schedule_id",
        "content_id equals schedule_id for some entries",
        "",
    )

    # k–l
    num = _append_row(
        num, mod,
        "Validate content_uri equals sheet Stream URL",
        "content_uri should equal the control-sheet Stream URL",
        k_failed, k_nt,
        "All content_uri values match Stream URL",
        "Some content_uri values do not match Stream URL",
        "content_uri not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate Cast is a list in all returned days",
        "cast should be a list for all Assets in all returned days",
        l_type, l_nt,
        "All cast values are lists",
        "Some cast values are not lists",
        "cast not available for some assets",
    )
    num = _append_row(
        num, mod,
        "Validate Cast is non-empty in all returned days",
        "cast should be a non-empty list for all Assets in all returned days",
        l_empty, empty_nt,
        "All cast lists are non-empty",
        "Some cast lists are empty",
        "",
    )

    logger.info("%sSSAI day validations complete; next_seq=%s rows=%s", prefix, num, len(Validation_Output))
    return num
