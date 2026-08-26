"""SSAI AN3 program + schedule field validators (suites a–n).

Callable without master/runner via run_ssai_day_validations().
"""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
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


_EXCEL_ASSET_IDS_MAX = 32767


def _merge_day_failures(
    failed_by_date: Dict[str, Dict[str, List[Any]]],
    max_len: int = _EXCEL_ASSET_IDS_MAX,
) -> str:
    """
    NON_SSAI Asset_Level Asset IDs cell (no outer list):
      {date: [{asset_id: [details]}, ...]},{date2: [...]}

    Round-robins one entry per day so every failing day appears when clipped
    to Excel's cell limit (complete valid literal, never mid-token).
    """
    if not failed_by_date:
        return ""

    dates = sorted(failed_by_date.keys())
    day_queues: Dict[str, List[Dict[str, List[Any]]]] = {}
    for date in dates:
        id_map = failed_by_date[date] or {}
        day_queues[date] = [{pid: details} for pid, details in id_map.items()]

    selected: Dict[str, List[Dict[str, List[Any]]]] = {d: [] for d in dates}
    indices = {d: 0 for d in dates}
    progressed = True
    while progressed:
        progressed = False
        for date in dates:
            idx = indices[date]
            queue = day_queues[date]
            if idx >= len(queue):
                continue
            trial = {d: list(selected[d]) for d in dates}
            trial[date] = trial[date] + [queue[idx]]
            parts = [{d: trial[d]} for d in dates if trial[d]]
            candidate_text = ",".join(map(str, parts))
            if selected[date] or any(selected[d] for d in dates if d != date):
                if len(candidate_text) > max_len:
                    continue
            elif len(candidate_text) > max_len and not any(selected.values()):
                # First asset ever: include even if over max_len (unavoidable)
                selected[date] = [queue[idx]]
                indices[date] = idx + 1
                progressed = True
                continue
            selected[date] = trial[date]
            indices[date] = idx + 1
            progressed = True

    out_parts = [{d: selected[d]} for d in dates if selected[d]]
    return ",".join(map(str, out_parts)) if out_parts else ""


def _merge_schedule_failures(
    failed_by_date: Dict[str, Dict[str, List[Any]]],
    max_len: int = _EXCEL_ASSET_IDS_MAX,
) -> str:
    """
    NON_SSAI Schedule Asset IDs cell (no outer list):
      {program_id: [date, ...details]},{program_id2: [...]}
    """
    if not failed_by_date:
        return ""
    parts: List[Dict[str, List[Any]]] = []
    for date in sorted(failed_by_date.keys()):
        id_map = failed_by_date[date] or {}
        for pid, details in id_map.items():
            detail_list = details if isinstance(details, list) else [details]
            candidate = {pid: [date, *detail_list]}
            candidate_parts = parts + [candidate]
            candidate_text = ",".join(map(str, candidate_parts))
            if parts and len(candidate_text) > max_len:
                return ",".join(map(str, parts))
            if not parts and len(candidate_text) > max_len:
                return ",".join(map(str, [candidate]))
            parts.append(candidate)
    return ",".join(map(str, parts)) if parts else ""


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


def _format_schedule_iso(dt: datetime) -> str:
    """Format datetime as YYYY-MM-DDTHH:MM:SSZ for schedule grouped-report payloads."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or _is_empty(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return None


def _is_word_capitalized(value: str) -> bool:
    for word in str(value).split():
        if not word:
            continue
        if word[0].isalpha() and not word[0].isupper():
            return False
    return True


def _is_rating_uppercase(value: str) -> bool:
    for ch in str(value):
        if ch.isalpha() and not ch.isupper():
            return False
    return True


def _strict_starttime_match(value: Any, pattern: str) -> bool:
    if value is None or _is_empty(value):
        return False
    return bool(re.match(pattern, str(value).strip()))


def _content_uri_has_ads_macros(uri: str, config: dict) -> bool:
    markers = config.get("content_uri_required_markers") or ["ads."]
    macro_keys = config.get("content_uri_macro_keys") or []
    if not all(marker in uri for marker in markers):
        return False
    uri_lower = uri.lower()
    for key in macro_keys:
        encoded = f"%7b{key.lower()}%7d"
        if encoded not in uri_lower:
            return False
    return True


def _content_uri_encoding_ok(uri: str, config: dict) -> bool:
    if not config.get("content_uri_forbid_unencoded_macro", True):
        return True
    return not bool(re.search(r"\{[A-Z0-9_]+\}", uri))


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
        logger.info(f'failed: {failed}')
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
) -> None:
    """Presence-only (NON_SSAI-aligned). Empty/value checks live in dedicated suites."""
    logger.info(f"Running suite_ab_mandatory for date: {date}")
    fields = config.get("mandatory_fields") or []
    for prog in programs:
        if not isinstance(prog, dict):
            _record(missing, date, "unknown", ["program entry is not an object"])
            continue
        key = _program_key(prog)
        for field in fields:
            if field not in prog:
                _record(missing, date, key, [f"{field} missing"])

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
    buckets: Dict[str, Dict[str, List[Any]]],
) -> None:
    """
    Validate every poster[i] entry per program.
    buckets: list_type, item_type, missing, url_missing, url_type, url_len, status,
             redirect, format, resolution, type_missing, width_missing, height_missing,
             width_mismatch, height_mismatch
    """
    logger.info(f"Running suite_e_poster for date: {date}")
    lengths = config.get("lengths") or {}
    thumb = config.get("thumbnail") or {}
    max_url = lengths.get("poster_url", 2000)
    exp_w = int(thumb.get("width", 1920))
    exp_h = int(thumb.get("height", 1080))
    formats = {str(f).lower() for f in (thumb.get("formats") or ["jpg", "jpeg"])}
    image_cache: Dict[str, Tuple[Optional[Any], Optional[str], Optional[str], Optional[int], Optional[int]]] = {}

    def _load_image(url: str):
        if url in image_cache:
            return image_cache[url]
        response, net_err = _fetch_poster_image(url)
        if net_err or response is None:
            image_cache[url] = (None, net_err, None, None, None)
            return image_cache[url]
        if response.status_code in (301, 302, 303, 307, 308):
            image_cache[url] = (response, f"redirect:{response.status_code}", None, None, None)
            return image_cache[url]
        if response.status_code != 200:
            image_cache[url] = (response, f"status:{response.status_code}", None, None, None)
            return image_cache[url]
        try:
            image = Image.open(BytesIO(response.content))
            width, height = image.size
            fmt = str(image.format or "").lower()
            image_cache[url] = (response, None, fmt, width, height)
        except Exception as exc:
            image_cache[url] = (response, f"processing error: {exc}", None, None, None)
        return image_cache[url]

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
            _record(buckets["list_type"], date, key, [f"poster not a list: {type(poster).__name__}"])
            continue

        for idx, entry in enumerate(poster):
            tag = f"poster[{idx}]"
            if not isinstance(entry, dict):
                _record(buckets["item_type"], date, key, [f"{tag} not an object"])
                continue

            url = entry.get("url")
            if _is_empty(url):
                _record(buckets["url_missing"], date, key, [f"{tag}.url missing"])
                continue
            if not isinstance(url, str):
                _record(buckets["url_type"], date, key, [f"{tag}.url not string: {type(url).__name__}"])
                continue
            if len(url) > max_url:
                _record(buckets["url_len"], date, key, [len(url), url, tag])

            ptype = entry.get("type")
            pwidth = entry.get("width")
            pheight = entry.get("height")
            if _is_empty(ptype):
                _record(buckets["type_missing"], date, key, [f"{tag}.type missing"])
            if _is_empty(pwidth):
                _record(buckets["width_missing"], date, key, [f"{tag}.width missing"])
            if _is_empty(pheight):
                _record(buckets["height_missing"], date, key, [f"{tag}.height missing"])

            _response, err, img_fmt, img_w, img_h = _load_image(url)
            if err:
                if err.startswith("redirect:"):
                    code = err.split(":", 1)[1]
                    _record(buckets["redirect"], date, key, [code, url, tag])
                elif err.startswith("status:"):
                    code = err.split(":", 1)[1]
                    _record(buckets["status"], date, key, [code, url, tag])
                else:
                    _record(buckets["status"], date, key, [err, url, tag])
                continue

            if img_fmt and img_fmt not in formats and img_fmt not in {"jpeg", "jpg"}:
                _record(buckets["format"], date, key, [img_fmt, url, tag])
            if img_w is not None and img_h is not None and (img_w, img_h) != (exp_w, exp_h):
                _record(buckets["resolution"], date, key, [f"{img_w}X{img_h}", url, tag])

            jw = _coerce_int(pwidth)
            jh = _coerce_int(pheight)
            if pwidth is not None and not _is_empty(pwidth) and jw is None:
                _record(buckets["width_mismatch"], date, key, ["width not numeric", pwidth, tag])
            elif jw is not None and img_w is not None and jw != img_w:
                _record(buckets["width_mismatch"], date, key, [pwidth, img_w, url, tag])
            if pheight is not None and not _is_empty(pheight) and jh is None:
                _record(buckets["height_mismatch"], date, key, ["height not numeric", pheight, tag])
            elif jh is not None and img_h is not None and jh != img_h:
                _record(buckets["height_mismatch"], date, key, [pheight, img_h, url, tag])

            if not _is_empty(ptype) and img_fmt:
                ptype_l = str(ptype).lower()
                if ptype_l not in formats and ptype_l not in {"jpeg", "jpg", "image/jpeg", "image/jpg"}:
                    if ptype_l not in {img_fmt, f"image/{img_fmt}"}:
                        _record(buckets["format"], date, key, [f"json type={ptype}", img_fmt, url, tag])

    logger.info(f"Completed suite_e_poster for date: {date}")


def _suite_f_genre(
    date: str,
    programs: List[dict],
    config: dict,
    list_type_fail: Dict[str, Dict[str, List[Any]]],
    item_type_fail: Dict[str, Dict[str, List[Any]]],
    id_type_fail: Dict[str, Dict[str, List[Any]]],
    name_type_fail: Dict[str, Dict[str, List[Any]]],
    cap_fail: Dict[str, Dict[str, List[Any]]],
    allowlist_fail: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    allowed = set(config.get("genres") or [])
    check_cap = config.get("genre_capitalization", True)
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
            _record(list_type_fail, date, key, [f"genre not a list: {type(genre).__name__}"])
            continue
        for item in genre:
            if not isinstance(item, dict):
                _record(item_type_fail, date, key, ["genre item not an object"])
                continue
            gid = item.get("id")
            name = item.get("original_name")
            if _is_empty(gid) or not isinstance(gid, str):
                _record(id_type_fail, date, key, ["genre.id missing or not string", item])
            if _is_empty(name) or not isinstance(name, str):
                _record(name_type_fail, date, key, ["genre.original_name missing or not string", item])
            elif isinstance(name, str):
                if check_cap and not _is_word_capitalized(name):
                    _record(cap_fail, date, key, [name])
                if name not in allowed:
                    _record(allowlist_fail, date, key, [name])

    logger.info(f"Completed suite_f_genre for date: {date}")


def _suite_g_rating(
    date: str,
    programs: List[dict],
    config: dict,
    allowlist_fail: Dict[str, Dict[str, List[Any]]],
    cap_fail: Dict[str, Dict[str, List[Any]]],
    not_tested: Dict[str, Dict[str, List[Any]]],
) -> None:
    allowed = {str(r) for r in (config.get("ratings") or [])}
    check_cap = config.get("rating_require_uppercase", True)
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
            _record(allowlist_fail, date, key, [f"rating not string: {type(rating).__name__}"])
            continue
        if check_cap and not _is_rating_uppercase(rating):
            _record(cap_fail, date, key, [rating])
        if rating not in allowed:
            _record(allowlist_fail, date, key, [rating])

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
    config: dict,
    stream_fail: Dict[str, Dict[str, List[Any]]],
    ads_fail: Dict[str, Dict[str, List[Any]]],
    encoding_fail: Dict[str, Dict[str, List[Any]]],
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
            continue
        if uri != stream_url:
            _record(stream_fail, date, key, [uri, stream_url])
        if not _content_uri_has_ads_macros(uri, config):
            _record(ads_fail, date, key, [uri])
        if not _content_uri_encoding_ok(uri, config):
            _record(encoding_fail, date, key, [uri])

    logger.info(f"Completed suite_k_content_uri for date: {date}")


def _suite_m_episode_release(
    date: str,
    programs: List[dict],
    episode_type_fail: Dict[str, Dict[str, List[Any]]],
    episode_nt: Dict[str, Dict[str, List[Any]]],
    release_fail: Dict[str, Dict[str, List[Any]]],
    release_nt: Dict[str, Dict[str, List[Any]]],
) -> None:
    logger.info(f"Running suite_m_episode_release for date: {date}")
    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        if "episode_num" not in prog:
            _record(episode_nt, date, key, ["episode_num not available"])
        else:
            ep = prog.get("episode_num")
            if _is_empty(ep) and ep != 0:
                _record(episode_nt, date, key, ["episode_num empty"])
            elif not isinstance(ep, str):
                _record(episode_type_fail, date, key, [f"episode_num not string: {type(ep).__name__}", ep])

        if "release_year" not in prog:
            _record(release_nt, date, key, ["release_year not available"])
        else:
            ry = prog.get("release_year")
            if _is_empty(ry):
                _record(release_nt, date, key, ["release_year empty"])
            elif not isinstance(ry, str) or not re.match(r"^\d{4}$", ry):
                _record(release_fail, date, key, [ry])

    logger.info(f"Completed suite_m_episode_release for date: {date}")


def _suite_n_soft_fields(
    date: str,
    programs: List[dict],
    schedules: List[dict],
    config: dict,
    connecting_fail: Dict[str, Dict[str, List[Any]]],
    connecting_nt: Dict[str, Dict[str, List[Any]]],
    link_uri_fail: Dict[str, Dict[str, List[Any]]],
    link_uri_nt: Dict[str, Dict[str, List[Any]]],
    tags_fail: Dict[str, Dict[str, List[Any]]],
    tags_nt: Dict[str, Dict[str, List[Any]]],
    link_type_fail: Dict[str, Dict[str, List[Any]]],
    link_type_nt: Dict[str, Dict[str, List[Any]]],
    program_type_fail: Dict[str, Dict[str, List[Any]]],
    program_type_nt: Dict[str, Dict[str, List[Any]]],
    repeat_type_fail: Dict[str, Dict[str, List[Any]]],
    repeat_type_nt: Dict[str, Dict[str, List[Any]]],
    repeat_expire_fail: Dict[str, Dict[str, List[Any]]],
    repeat_expire_nt: Dict[str, Dict[str, List[Any]]],
) -> None:
    soft_prog = config.get("soft_empty_program_fields") or {}
    soft_sched = config.get("soft_empty_schedule_fields") or {}
    soft_repeat = config.get("soft_empty_repeat_fields") or {}
    prog_buckets = {
        "connecting_id": (connecting_fail, connecting_nt),
        "link_uri": (link_uri_fail, link_uri_nt),
        "tags": (tags_fail, tags_nt),
        "link_type": (link_type_fail, link_type_nt),
    }

    for prog in programs:
        if not isinstance(prog, dict):
            continue
        key = _program_key(prog)
        for field, expected in soft_prog.items():
            fail_b, nt_b = prog_buckets.get(field, (None, None))
            if fail_b is None:
                continue
            if field not in prog:
                _record(nt_b, date, key, [f"{field} not available"])
            elif prog.get(field) != expected:
                _record(fail_b, date, key, [prog.get(field), expected])

    for entry in schedules:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("content_id")
        key = str(cid) if not _is_empty(cid) else str(entry.get("schedule_id") or "unknown")
        for field, expected in soft_sched.items():
            if field not in entry:
                _record(program_type_nt, date, key, [f"{field} not available"])
            elif entry.get(field) != expected:
                _record(program_type_fail, date, key, [entry.get(field), expected])

        if "repeat" not in entry:
            _record(repeat_type_nt, date, key, ["repeat not available"])
            continue
        repeat = entry.get("repeat")
        if not isinstance(repeat, dict):
            _record(repeat_type_fail, date, key, ["repeat not an object", repeat])
            continue
        if "type" not in repeat:
            _record(repeat_type_nt, date, key, ["repeat.type not available"])
        elif repeat.get("type") != soft_repeat.get("type", "none"):
            _record(repeat_type_fail, date, key, [repeat.get("type"), soft_repeat.get("type", "none")])
        if "expire_date" not in repeat:
            _record(repeat_expire_nt, date, key, ["repeat.expire_date not available"])
        elif repeat.get("expire_date") != soft_repeat.get("expire_date", ""):
            _record(repeat_expire_fail, date, key, [repeat.get("expire_date"), soft_repeat.get("expire_date", "")])


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
    buckets: Dict[str, Dict[str, List[Any]]],
) -> None:
    """
    buckets: missing_fields, empty_fields, gap, overlap, content_missing,
             duration_mismatch, id_equals_schedule, start_parse, dur_parse,
             field_type, service_id_inconsistent, dur_min, dur_max, start_strict
    """
    logger.info(f"Running suite_j_schedule for date: {date}")
    mand = config.get("schedule_mandatory_fields") or []
    dur_min = int(config.get("schedule_duration_min", 1200))
    dur_max = int(config.get("schedule_duration_max", 21600))
    strict_re = config.get("schedule_starttime_strict_regex") or r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    program_by_id: Dict[str, dict] = {}
    for prog in programs:
        if isinstance(prog, dict) and prog.get("id") is not None:
            program_by_id[str(prog.get("id"))] = prog

    parsed_rows: List[Tuple[datetime, dict, str, Optional[int]]] = []
    service_ids_seen: set = set()

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
            elif not isinstance(entry.get(field), str):
                _record(buckets["field_type"], date, key, [f"{field} not string: {type(entry.get(field)).__name__}"])

        sid = entry.get("service_id")
        if not _is_empty(sid):
            service_ids_seen.add(str(sid))

        start_raw = entry.get("starttime")
        start = _parse_starttime(start_raw)
        if start_raw is not None and not _is_empty(start_raw) and start is None:
            _record(buckets["start_parse"], date, key, [start_raw])
        if start_raw is not None and not _is_empty(start_raw) and isinstance(start_raw, str):
            if not _strict_starttime_match(start_raw, strict_re):
                _record(buckets["start_strict"], date, key, [start_raw])

        dur = _parse_duration_seconds(entry.get("duration"))
        if entry.get("duration") is not None and not _is_empty(entry.get("duration")) and dur is None:
            _record(buckets["dur_parse"], date, key, [entry.get("duration")])
        if dur is not None:
            if dur < dur_min:
                _record(buckets["dur_min"], date, key, [dur, dur_min, entry.get("starttime")])
            if dur > dur_max:
                _record(buckets["dur_max"], date, key, [dur, dur_max, entry.get("starttime")])

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
            sched_id = entry.get("schedule_id")
            if not _is_empty(sched_id) and str(cid) == str(sched_id):
                _record(buckets["id_equals_schedule"], date, key, [cid, sched_id])

        if start is not None:
            parsed_rows.append((start, entry, key, dur))

    if len(service_ids_seen) > 1:
        for entry in schedules:
            if not isinstance(entry, dict):
                continue
            cid = entry.get("content_id")
            key = str(cid) if not _is_empty(cid) else str(entry.get("schedule_id") or "unknown")
            _record(
                buckets["service_id_inconsistent"],
                date,
                key,
                [entry.get("service_id"), sorted(service_ids_seen)],
            )

    parsed_rows.sort(key=lambda row: row[0])
    for i in range(len(parsed_rows) - 1):
        curr_start, curr_entry, curr_key, curr_dur = parsed_rows[i]
        next_start, _, _, _ = parsed_rows[i + 1]
        if curr_dur is None:
            _record(buckets["dur_parse"], date, curr_key, ["cannot compute gap/overlap; duration unparseable"])
            continue
        delta = int((next_start - curr_start).total_seconds())
        starttime = curr_entry.get("starttime")
        if delta > curr_dur:
            _record(
                buckets["gap"],
                date,
                curr_key,
                [delta, curr_dur, starttime],
            )
        elif delta < curr_dur:
            _record(
                buckets["overlap"],
                date,
                curr_key,
                [delta, curr_dur, starttime],
            )

    logger.info(f"Completed suite_j_schedule for date: {date}")

def run_ssai_day_validations(
    by_date: dict,
    stream_url: str,
    sequence_number: int = 1,
    ticket_id: str = "",
) -> int:
    """
    Run suites a–n across all days in by_date and append Validation_Output rows.

    by_date: {date: {program: [...], schedule: [...]}}
    Returns next sequence_number.
    """
    prefix = f"{ticket_id} " if ticket_id else ""
    config = _load_config()
    num = sequence_number

    # Accumulators across dates
    ab_missing: Dict[str, Dict[str, List[Any]]] = {}
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
        "list_type",
        "item_type",
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
        "width_mismatch",
        "height_mismatch",
    )
    poster_buckets = {k: {} for k in poster_keys}

    f_list_type: Dict[str, Dict[str, List[Any]]] = {}
    f_item_type: Dict[str, Dict[str, List[Any]]] = {}
    f_id_type: Dict[str, Dict[str, List[Any]]] = {}
    f_name_type: Dict[str, Dict[str, List[Any]]] = {}
    f_cap: Dict[str, Dict[str, List[Any]]] = {}
    f_allowlist: Dict[str, Dict[str, List[Any]]] = {}
    f_nt: Dict[str, Dict[str, List[Any]]] = {}

    g_allow_fail: Dict[str, Dict[str, List[Any]]] = {}
    g_cap_fail: Dict[str, Dict[str, List[Any]]] = {}
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
        "field_type",
        "service_id_inconsistent",
        "dur_min",
        "dur_max",
        "start_strict",
    )
    sched_buckets = {k: {} for k in sched_keys}

    k_stream_fail: Dict[str, Dict[str, List[Any]]] = {}
    k_ads_fail: Dict[str, Dict[str, List[Any]]] = {}
    k_encoding_fail: Dict[str, Dict[str, List[Any]]] = {}
    k_nt: Dict[str, Dict[str, List[Any]]] = {}

    m_ep_type: Dict[str, Dict[str, List[Any]]] = {}
    m_ep_nt: Dict[str, Dict[str, List[Any]]] = {}
    m_ry_fail: Dict[str, Dict[str, List[Any]]] = {}
    m_ry_nt: Dict[str, Dict[str, List[Any]]] = {}

    n_connecting_fail: Dict[str, Dict[str, List[Any]]] = {}
    n_connecting_nt: Dict[str, Dict[str, List[Any]]] = {}
    n_link_uri_fail: Dict[str, Dict[str, List[Any]]] = {}
    n_link_uri_nt: Dict[str, Dict[str, List[Any]]] = {}
    n_tags_fail: Dict[str, Dict[str, List[Any]]] = {}
    n_tags_nt: Dict[str, Dict[str, List[Any]]] = {}
    n_link_type_fail: Dict[str, Dict[str, List[Any]]] = {}
    n_link_type_nt: Dict[str, Dict[str, List[Any]]] = {}
    n_program_type_fail: Dict[str, Dict[str, List[Any]]] = {}
    n_program_type_nt: Dict[str, Dict[str, List[Any]]] = {}
    n_repeat_type_fail: Dict[str, Dict[str, List[Any]]] = {}
    n_repeat_type_nt: Dict[str, Dict[str, List[Any]]] = {}
    n_repeat_expire_fail: Dict[str, Dict[str, List[Any]]] = {}
    n_repeat_expire_nt: Dict[str, Dict[str, List[Any]]] = {}

    l_type: Dict[str, Dict[str, List[Any]]] = {}
    l_empty: Dict[str, Dict[str, List[Any]]] = {}
    l_nt: Dict[str, Dict[str, List[Any]]] = {}

    sched_dur_min = int(config.get("schedule_duration_min", 1200))
    sched_dur_max = int(config.get("schedule_duration_max", 21600))

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

        _suite_ab_mandatory(date, programs, config, ab_missing)
        _suite_dup_ids(date, programs, dup_failed)
        _suite_c_asset_id(date, programs, config, c_type, c_len, c_eq_title, c_eq_desc, c_nt)
        _suite_d_title(date, programs, config, d_type, d_tba, d_eq, d_len, d_spec, d_nt)
        _suite_e_poster(date, programs, config, poster_buckets)
        _suite_f_genre(
            date, programs, config,
            f_list_type, f_item_type, f_id_type, f_name_type, f_cap, f_allowlist, f_nt,
        )
        _suite_g_rating(date, programs, config, g_allow_fail, g_cap_fail, g_nt)
        _suite_h_desc(date, programs, config, h_type, h_len, h_spec, h_nt)
        _suite_i_duration(date, programs, i_type, i_zero, i_nt)
        _suite_j_schedule(date, programs, schedules, config, sched_buckets)
        _suite_k_content_uri(
            date, programs, stream_url, config,
            k_stream_fail, k_ads_fail, k_encoding_fail, k_nt,
        )
        _suite_m_episode_release(date, programs, m_ep_type, m_ep_nt, m_ry_fail, m_ry_nt)
        _suite_n_soft_fields(
            date, programs, schedules, config,
            n_connecting_fail, n_connecting_nt,
            n_link_uri_fail, n_link_uri_nt,
            n_tags_fail, n_tags_nt,
            n_link_type_fail, n_link_type_nt,
            n_program_type_fail, n_program_type_nt,
            n_repeat_type_fail, n_repeat_type_nt,
            n_repeat_expire_fail, n_repeat_expire_nt,
        )
        _suite_l_cast(date, programs, l_type, l_empty, l_nt)

    mod = "Asset_Level"
    sch = "Schedule"

    # a — mandatory presence only (empty/value checks are dedicated suites)
    num = _append_row(
        num, mod,
        "Validate mandatory fields presence for Assets in all returned days",
        "All mandatory fields should be present on every program in all returned days",
        ab_missing, {},
        "All mandatory fields are present for all Assets in all returned days",
        "Mandatory Fields are not available",
        "",
    )

    # duplicate ids
    num = _append_row(
        num, mod,
        "Validate duplicate program id within each day in all returned days",
        "program id should be unique within each day in all returned days",
        dup_failed, {},
        "No duplicate program id values were found in all returned days",
        "Duplicate program id values were found within a day",
        "",
    )

    asset_id_max = (config.get("lengths") or {}).get("asset_id", 50)
    title_max = (config.get("lengths") or {}).get("title", 200)
    desc_max = (config.get("lengths") or {}).get("desc", 4000)
    poster_url_max = (config.get("lengths") or {}).get("poster_url", 2000)
    empty_nt: Dict[str, Dict[str, List[Any]]] = {}

    # c — Asset ID (4 atomic cases)
    num = _append_row(
        num, mod,
        "Validate Asset ID Type in all returned days",
        "Asset ID should be a string for all Assets in all returned days",
        c_type, c_nt,
        "Asset ID type is a string for all Assets in all returned days",
        "Asset ID type is in-correct (not a string)",
        "Asset ID is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate Asset ID Length in all returned days",
        f"Length of Asset ID should not exceed {asset_id_max} characters in all returned days",
        c_len, empty_nt,
        f"Asset ID length is within the expected limit of {asset_id_max} characters for all Assets in all returned days",
        f"Asset ID length is in-correct-length which is more than expected limit of {asset_id_max} characters",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Asset ID should not contain Title in all returned days",
        "Asset ID and Title should not be same for all Assets in all returned days",
        c_eq_title, empty_nt,
        "Asset ID and Title fields are not matching for all Assets in all returned days",
        "Asset ID and Title fields are matching",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Asset ID should not contain Description in all returned days",
        "Asset ID and Description should not be same for all Assets in all returned days",
        c_eq_desc, empty_nt,
        "Asset ID and Description fields are not matching for all Assets in all returned days",
        "Asset ID and Description fields are matching",
        "",
    )

    # d — Title
    num = _append_row(
        num, mod,
        "Validate Title type in all returned days",
        "Title should be a string for all Assets in all returned days",
        d_type, d_nt,
        "Title type is a string for all Assets in all returned days",
        "Title type is in-correct (not a string)",
        "Title is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate Title is not TBA / To Be Announced in all returned days",
        "Title should not be TBA or To Be Announced for all Assets in all returned days",
        d_tba, empty_nt,
        "No Title values are TBA or To Be Announced in all returned days",
        "Asset Title contains To Be Announced instead of the actual title",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Title is not equal to Description in all returned days",
        "Title should not equal Description for all Assets in all returned days",
        d_eq, empty_nt,
        "Title and Description are distinct for all Assets in all returned days",
        "Asset Title and Description fields are matching",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Title length in all returned days",
        f"Title length should not exceed {title_max} characters for all Assets in all returned days",
        d_len, empty_nt,
        f"Title length is within the expected limit of {title_max} characters for all Assets in all returned days",
        f"Asset Title has in-correct-length (chars) which exceeds the maximum allowed length of {title_max} characters",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Title has no unexpected special characters in all returned days",
        "Title should match the allowed character set for all Assets in all returned days",
        d_spec, empty_nt,
        "No unexpected special characters are present in Title for all Assets in all returned days",
        "Asset Title contains unexpected special characters",
        "",
    )

    # e — poster
    num = _append_row(
        num, mod,
        "Validate poster type is list in all returned days",
        "poster should be a list for all Assets in all returned days",
        poster_buckets["list_type"], poster_buckets["missing"],
        "Poster is a list for all Assets in all returned days",
        "Poster type is in-correct (not a list)",
        "Poster is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate poster list entry type is object in all returned days",
        "Each poster entry should be an object for all Assets in all returned days",
        poster_buckets["item_type"], empty_nt,
        "All poster entries are objects for all Assets in all returned days",
        "Poster list entry type is in-correct (not an object)",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster URL availability in all returned days",
        "Poster URL should be available for all poster entries in all returned days",
        poster_buckets["url_missing"], empty_nt,
        "Poster URL is available for all Assets in all returned days",
        "Poster URL is not available",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster URL type is string in all returned days",
        "Poster URL should be a string for all poster entries in all returned days",
        poster_buckets["url_type"], empty_nt,
        "Poster URL type is a string for all Assets in all returned days",
        "Poster URL type is in-correct (not a string)",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster URL length in all returned days",
        f"Poster URL length should not exceed {poster_url_max} characters for all poster entries in all returned days",
        poster_buckets["url_len"], empty_nt,
        f"Poster URL length is within the expected limit of {poster_url_max} characters for all Assets in all returned days",
        f"Poster URL length is in-correct-length which is more than expected limit of {poster_url_max} characters",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster HTTP status is 200 in all returned days",
        "Poster URL should return HTTP 200 for all poster entries in all returned days",
        poster_buckets["status"], empty_nt,
        "All Poster URLs return HTTP 200 for all Assets in all returned days",
        "Poster URL request is returning in-correct-thumbnail status code",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster URL has no redirect in all returned days",
        "Poster URL should not redirect for all poster entries in all returned days",
        poster_buckets["redirect"], empty_nt,
        "No Poster URL redirects were observed for all Assets in all returned days",
        "Poster URL request is getting re-directed with in-correct-thumbnail status code",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster image format is JPG/JPEG in all returned days",
        "Poster image format should be JPG/JPEG for all poster entries in all returned days",
        poster_buckets["format"], empty_nt,
        "All Poster images are JPG/JPEG for all Assets in all returned days",
        "Poster has in-correct-thumbnail format; expected format is JPEG/JPG",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster resolution is 1920x1080 in all returned days",
        "Poster actual image size should be 1920x1080 for all poster entries in all returned days",
        poster_buckets["resolution"], empty_nt,
        "All Poster images are 1920x1080 for all Assets in all returned days",
        "Poster has in-correct-thumbnail resolution; expected resolution is 1920X1080",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster type present in all returned days",
        "poster type should be present for all poster entries in all returned days",
        poster_buckets["type_missing"], empty_nt,
        "Poster type is present for all Assets in all returned days",
        "Mandatory poster fields are missing",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster width present in all returned days",
        "poster width should be present for all poster entries in all returned days",
        poster_buckets["width_missing"], empty_nt,
        "Poster width is present for all Assets in all returned days",
        "Mandatory poster fields are missing",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster height present in all returned days",
        "poster height should be present for all poster entries in all returned days",
        poster_buckets["height_missing"], empty_nt,
        "Poster height is present for all Assets in all returned days",
        "Mandatory poster fields are missing",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster JSON width match actual image in all returned days",
        "poster width should match the downloaded image width for all poster entries in all returned days",
        poster_buckets["width_mismatch"], empty_nt,
        "Poster JSON width matches the downloaded image for all Assets in all returned days",
        "Poster JSON width is in-correct length and proper-length is in-correct length for the downloaded image",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Poster JSON height match actual image in all returned days",
        "poster height should match the downloaded image height for all poster entries in all returned days",
        poster_buckets["height_mismatch"], empty_nt,
        "Poster JSON height matches the downloaded image for all Assets in all returned days",
        "Poster JSON height is in-correct length and proper-length is in-correct length for the downloaded image",
        "",
    )

    # f — genre
    num = _append_row(
        num, mod,
        "Validate Genre list type in all returned days",
        "genre should be a list for all Assets in all returned days",
        f_list_type, f_nt,
        "Genre is a list for all Assets in all returned days",
        "Genre type is in-correct (not a list)",
        "Genre is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate Genre item type in all returned days",
        "Each genre entry should be an object for all Assets in all returned days",
        f_item_type, empty_nt,
        "All genre entries are objects for all Assets in all returned days",
        "Genre item type is in-correct (not an object)",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Genre id type in all returned days",
        "genre id should be a non-empty string for all Assets in all returned days",
        f_id_type, empty_nt,
        "Genre id is a string for all Assets in all returned days",
        "Genre id type is in-correct (not a string)",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Genre original_name type in all returned days",
        "genre original_name should be a non-empty string for all Assets in all returned days",
        f_name_type, empty_nt,
        "Genre original_name is a string for all Assets in all returned days",
        "Genre original_name type is in-correct (not a string)",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Genre original_name Capitalization in all returned days",
        "genre original_name should be capitalized for all Assets in all returned days",
        f_cap, empty_nt,
        "Genre original_name capitalization is valid for all Assets in all returned days",
        "Genre original_name has in-correct capitalization",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Genre original_name as per expected list in all returned days",
        "genre original_name should be present in the expected genre list for all Assets in all returned days",
        f_allowlist, empty_nt,
        "All Genre original_name values are in the expected list for all Assets in all returned days",
        "Genre original_name is not included in Samsung_Supported_Category_List",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Rating Capitalization in all returned days",
        "Rating alphabet should be capital letters for all Assets in all returned days",
        g_cap_fail, g_nt,
        "All Rating values have valid capitalization for all Assets in all returned days",
        "Rating has in-correct-rating capitalization",
        "Rating is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate Rating against expected list in all returned days",
        "Rating should be a string in the expected ratings list for all Assets in all returned days",
        g_allow_fail, empty_nt,
        "All Rating values are valid for all Assets in all returned days",
        "Rating is not included in Samsung_Supported_Rating_List",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Description type in all returned days",
        "Description should be a string for all Assets in all returned days",
        h_type, h_nt,
        "Description type is a string for all Assets in all returned days",
        "Description type is in-correct (not a string)",
        "Description is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate Description length in all returned days",
        f"Description length should not exceed {desc_max} characters for all Assets in all returned days",
        h_len, empty_nt,
        f"Description length is within the expected limit of {desc_max} characters for all Assets in all returned days",
        f"Description has in-correct-length (chars) which exceeds the maximum allowed length of {desc_max} characters",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Description has no unexpected special characters in all returned days",
        "Description should match the allowed character set for all Assets in all returned days",
        h_spec, empty_nt,
        "No unexpected special characters are present in Description for all Assets in all returned days",
        "Description contains unexpected special characters",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate Duration type is int in all returned days",
        "duration should be an int for all Assets in all returned days",
        i_type, i_nt,
        "Duration type is an int for all Assets in all returned days",
        "Duration type is in-correct (not an int)",
        "Duration is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate Duration is not zero in all returned days",
        "duration should not be equal to 0 for all Assets in all returned days",
        i_zero, empty_nt,
        "All Duration values are non-zero for all Assets in all returned days",
        "Duration is equal to 0",
        "",
    )

    # j — schedule
    num = _append_row(
        num, sch,
        "Validate schedule mandatory fields presence in all returned days",
        "service_id, content_id, schedule_id, starttime, duration should be present in all returned days",
        sched_buckets["missing_fields"], empty_nt,
        "All schedule mandatory fields are present in all returned days",
        "Schedule mandatory fields are missing",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule mandatory fields non-empty in all returned days",
        "Schedule mandatory fields should be non-empty in all returned days",
        sched_buckets["empty_fields"], empty_nt,
        "All schedule mandatory field values are non-empty in all returned days",
        "Schedule mandatory field values are empty",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule starttime parseable in all returned days",
        "starttime should be a parseable ISO datetime in all returned days",
        sched_buckets["start_parse"], empty_nt,
        "All starttime values are parseable in all returned days",
        "Schedule starttime is not parseable",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule duration parseable as int seconds in all returned days",
        "duration should parse to int seconds in all returned days",
        sched_buckets["dur_parse"], empty_nt,
        "All schedule duration values are parseable as int seconds in all returned days",
        "Schedule duration is not parseable as int seconds",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule field types are string in all returned days",
        "service_id, content_id, schedule_id, starttime, duration should be strings in all returned days",
        sched_buckets["field_type"], empty_nt,
        "All schedule mandatory field types are strings in all returned days",
        "Schedule field type is in-correct (not a string)",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate service_id is constant per day in all returned days",
        "service_id should be the same for all schedule entries within each day in all returned days",
        sched_buckets["service_id_inconsistent"], empty_nt,
        "service_id is constant for all schedule entries in all returned days",
        "Schedule service_id is not constant within the day",
        "",
    )
    num = _append_row(
        num, sch,
        f"Validate schedule duration is at least {sched_dur_min} seconds in all returned days",
        f"Scheduled duration should be greater than or equal to {sched_dur_min} seconds (20 minutes) in all returned days",
        sched_buckets["dur_min"], empty_nt,
        f"All schedule durations are greater than or equal to {sched_dur_min} seconds in all returned days",
        f"Scheduled asset duration is less than the required 20 minutes ({sched_dur_min} seconds)",
        "",
    )
    num = _append_row(
        num, sch,
        f"Validate schedule duration is at most {sched_dur_max} seconds in all returned days",
        f"Scheduled duration should be less than or equal to {sched_dur_max} seconds (6 hours) in all returned days",
        sched_buckets["dur_max"], empty_nt,
        f"All schedule durations are less than or equal to {sched_dur_max} seconds in all returned days",
        f"Scheduled asset duration exceeds the maximum allowed duration of 6 hours ({sched_dur_max} seconds)",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule starttime strict format in all returned days",
        "starttime should match YYYY-MM-DDTHH:MM:SSZ format in all returned days",
        sched_buckets["start_strict"], empty_nt,
        "All starttime values match the strict ISO format in all returned days",
        "Schedule starttime format is in-correct",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate no schedule gaps between consecutive assets in all returned days",
        "consecutive schedule entries should align without gaps or overlaps in all returned days",
        sched_buckets["gap"], empty_nt,
        "No schedule gaps were observed between consecutive assets in all returned days",
        "A schedule gap is observed between consecutive assets",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate no schedule overlaps between consecutive assets in all returned days",
        "consecutive schedule entries should align without gaps or overlaps in all returned days",
        sched_buckets["overlap"], empty_nt,
        "No schedule overlaps were observed between consecutive assets in all returned days",
        "A schedule overlap is observed between consecutive assets",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule content_id exists in program id in all returned days",
        "content_id should match a program id in all returned days",
        sched_buckets["content_missing"], empty_nt,
        "All content_id values resolve to a program id in all returned days",
        "Schedule content_id does not resolve to a program id",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate schedule duration matches program duration in all returned days",
        "schedule_duration should equal program duration in all returned days",
        sched_buckets["duration_mismatch"], empty_nt,
        "Schedule duration matches program duration for all entries in all returned days",
        "Schedule duration does not match program duration",
        "",
    )
    num = _append_row(
        num, sch,
        "Validate content_id is not equal to schedule_id in all returned days",
        "content_id should differ from schedule_id in all returned days",
        sched_buckets["id_equals_schedule"], empty_nt,
        "content_id differs from schedule_id for all entries in all returned days",
        "Schedule content_id equals schedule_id",
        "",
    )

    # k — content_uri + m — episode/release + n — soft fields
    num = _append_row(
        num, mod,
        "Validate content_uri equals sheet Stream URL in all returned days",
        "content_uri should equal the control-sheet Stream URL for all Assets in all returned days",
        k_stream_fail, k_nt,
        "All content_uri values match the control-sheet Stream URL for all Assets in all returned days",
        "content_uri does not match the control-sheet Stream URL",
        "content_uri is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate content_uri ads macro keys in all returned days",
        "content_uri should contain ads. parameters with required macro keys for all Assets in all returned days",
        k_ads_fail, empty_nt,
        "All content_uri values contain required ads. macro keys for all Assets in all returned days",
        "content_uri is missing required ads. macro keys",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate content_uri macro encoding in all returned days",
        "content_uri macro placeholders should be URL-encoded for all Assets in all returned days",
        k_encoding_fail, empty_nt,
        "All content_uri macro placeholders are URL-encoded for all Assets in all returned days",
        "content_uri contains unencoded macro placeholders",
        "",
    )
    num = _append_row(
        num, mod,
        "Validate episode_num type is string in all returned days",
        "episode_num should be a string for all Assets in all returned days",
        m_ep_type, m_ep_nt,
        "episode_num is a string for all Assets in all returned days",
        "episode_num type is in-correct (not a string)",
        "episode_num is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate release_year format in all returned days",
        "release_year should be a string in YYYY format for all Assets in all returned days",
        m_ry_fail, m_ry_nt,
        "release_year is in YYYY format for all Assets in all returned days",
        "release_year is in-correct (expected YYYY string format)",
        "release_year is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate connecting_id soft empty value in all returned days",
        'connecting_id should be empty string ("") for all Assets in all returned days',
        n_connecting_fail, n_connecting_nt,
        "connecting_id has the expected empty value for all Assets in all returned days",
        "connecting_id does not have the expected empty value",
        "connecting_id is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate link_uri soft empty value in all returned days",
        'link_uri should be empty string ("") for all Assets in all returned days',
        n_link_uri_fail, n_link_uri_nt,
        "link_uri has the expected empty value for all Assets in all returned days",
        "link_uri does not have the expected empty value",
        "link_uri is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate tags soft empty value in all returned days",
        'tags should be empty string ("") for all Assets in all returned days',
        n_tags_fail, n_tags_nt,
        "tags has the expected empty value for all Assets in all returned days",
        "tags does not have the expected empty value",
        "tags is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate link_type soft empty value in all returned days",
        'link_type should be "none" for all Assets in all returned days',
        n_link_type_fail, n_link_type_nt,
        'link_type has the expected value "none" for all Assets in all returned days',
        'link_type does not have the expected value "none"',
        "link_type is not available for the asset",
    )
    num = _append_row(
        num, sch,
        "Validate program_type soft empty value in all returned days",
        'program_type should be empty string ("") for all schedule entries in all returned days',
        n_program_type_fail, n_program_type_nt,
        "program_type has the expected empty value for all schedule entries in all returned days",
        "program_type does not have the expected empty value",
        "program_type is not available for the schedule entry",
    )
    num = _append_row(
        num, sch,
        "Validate repeat.type soft empty value in all returned days",
        'repeat.type should be "none" for all schedule entries in all returned days',
        n_repeat_type_fail, n_repeat_type_nt,
        'repeat.type has the expected value "none" for all schedule entries in all returned days',
        'repeat.type does not have the expected value "none"',
        "repeat is not available for the schedule entry",
    )
    num = _append_row(
        num, sch,
        "Validate repeat.expire_date soft empty value in all returned days",
        'repeat.expire_date should be empty string ("") for all schedule entries in all returned days',
        n_repeat_expire_fail, n_repeat_expire_nt,
        "repeat.expire_date has the expected empty value for all schedule entries in all returned days",
        "repeat.expire_date does not have the expected empty value",
        "repeat.expire_date is not available for the schedule entry",
    )

    # l — cast
    num = _append_row(
        num, mod,
        "Validate Cast is a list in all returned days",
        "cast should be a list for all Assets in all returned days",
        l_type, l_nt,
        "Cast is a list for all Assets in all returned days",
        "Cast type is in-correct (not a list)",
        "Cast is not available for the asset",
    )
    num = _append_row(
        num, mod,
        "Validate Cast is non-empty in all returned days",
        "cast should be a non-empty list for all Assets in all returned days",
        l_empty, empty_nt,
        "Cast is a non-empty list for all Assets in all returned days",
        "Cast list is empty",
        "",
    )

    logger.info("%sSSAI day validations complete; next_seq=%s rows=%s", prefix, num, len(Validation_Output))
    return num
