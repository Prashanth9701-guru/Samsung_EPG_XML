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
from google.cloud import translate_v2 as translate
from google.oauth2.service_account import Credentials
from PIL import Image

from utilities.helper import Validation_Output, helper_fuc

logger = logging.getLogger(__name__)

_CONFIG: Optional[dict] = None
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config_ssai.yaml",
)

# Dedicated translator SA JSON path — Jenkins must export GOOGLE_TRANSLATOR_JSON.
SA_JSON_TRANS = os.environ.get("GOOGLE_TRANSLATOR_JSON")

TITLE_SPECIAL_RE = re.compile(r"""^[A-Za-z0-9 _\-?:;,.’"!&/()']+$""")
DESC_SPECIAL_RE = re.compile(r"""[$&+\\%]""")
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
    """Translate via Google Cloud Translate v2 using GOOGLE_TRANSLATOR_JSON SA."""
    english_text = ""
    if not SA_JSON_TRANS:
        logger.warning(
            "GOOGLE_TRANSLATOR_JSON is not set; skipping Cloud Translate"
        )
        return english_text

    for attempt in range(5):
        try:
            scope = ["https://www.googleapis.com/auth/cloud-translation"]
            creds = Credentials.from_service_account_file(
                SA_JSON_TRANS,
                scopes=scope,
            )
            translate_client = translate.Client(credentials=creds)
            translated_text = translate_client.translate(
                text, target_language="en"
            )
            english_text = translated_text.get("translatedText") or ""
            logger.info("Translation successful")
            break
        except Exception as exc:
            wait_time = 5 * (2 ** attempt)
            logger.info("Translation failed: %s", exc)
            logger.info(
                "Waiting %s seconds before retrying translation...", wait_time
            )
            time.sleep(wait_time)
    return english_text


def _has_special_chars(text: str, kind: str) -> bool:
    """Return True if translated text fails NON-SSAI special-char rules."""
    cleaned = _strip_control_chars(text)
    english = _translate_to_english(cleaned)
    if kind == "desc":
        return bool(DESC_SPECIAL_RE.search(english))
    return not bool(TITLE_SPECIAL_RE.search(english))


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
        "Verify the presence of mandatory fields for all assets across the seven-day schedule",
        "All mandatory fields should be present for every asset in the seven-day schedule.",
        ab_missing, {},
        "All mandatory fields are present for every episodic asset.",
        "One or more mandatory asset fields are missing.",
        "",
    )

    # duplicate ids
    num = _append_row(
        num, mod,
        "Verify that program IDs are unique within each day across the seven-day schedule",
        "Program IDs should be unique within each day throughout the seven-day schedule.",
        dup_failed, {},
        "No duplicate program ID values were found across the seven-day schedule.",
        "One or more duplicate program ID values were found within a day.",
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
        "Verify the asset ID type for all assets across the seven-day schedule",
        "The asset ID should be a string for every asset in the seven-day schedule.",
        c_type, c_nt,
        "Asset ID type is a string for every asset.",
        "One or more asset IDs have an invalid type (not a string).",
        "The asset ID is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify the asset ID length across the seven-day schedule",
        f"No asset ID should exceed {asset_id_max} characters in the seven-day schedule.",
        c_len, empty_nt,
        f"Every asset ID is within the permitted limit of {asset_id_max} characters.",
        f"One or more asset IDs exceed the maximum permitted length of {asset_id_max} characters.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify that asset IDs and titles are not identical across the seven-day schedule",
        "An asset's ID and title should not be identical anywhere in the seven-day schedule.",
        c_eq_title, empty_nt,
        "The asset ID and title are different for every asset.",
        "The asset ID and title are identical for one or more assets.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify that asset IDs and descriptions are not identical across the seven-day schedule",
        "An asset's ID and description should not be identical anywhere in the seven-day schedule.",
        c_eq_desc, empty_nt,
        "The asset ID and description are different for every asset.",
        "The asset ID and description are identical for one or more assets.",
        "",
    )

    # d — Title
    num = _append_row(
        num, mod,
        "Verify the title type for all assets across the seven-day schedule",
        "The title should be a string for every asset in the seven-day schedule.",
        d_type, d_nt,
        "Title type is a string for every asset.",
        "One or more asset titles have an invalid type (not a string).",
        "The title is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify that no asset title contains 'To Be Announced' across the seven-day schedule",
        "No asset title should contain 'To Be Announced' in the seven-day schedule.",
        d_tba, empty_nt,
        "No asset title contains 'To Be Announced'.",
        "One or more asset titles contain 'To Be Announced'.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify that asset titles and descriptions are not identical across the seven-day schedule",
        "An asset's title and description should not be identical anywhere in the seven-day schedule.",
        d_eq, empty_nt,
        "The title and description are different for every asset.",
        "The title and description are identical for one or more assets.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the title length for all assets across the seven-day schedule",
        f"No asset title should exceed {title_max} characters in the seven-day schedule.",
        d_len, empty_nt,
        f"Every asset title is within the permitted limit of {title_max} characters.",
        f"One or more asset titles exceed the maximum permitted length of {title_max} characters.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify that asset titles do not contain prohibited special characters across the seven-day schedule",
        "Asset titles should not contain special characters prohibited by the platform standards.",
        d_spec, empty_nt,
        "No asset title contains prohibited special characters.",
        "One or more asset titles contain special characters prohibited by the platform standards.",
        "",
    )

    # e — poster
    num = _append_row(
        num, mod,
        "Verify the poster type is a list for all assets across the seven-day schedule",
        "The poster field should be a list for every asset in the seven-day schedule.",
        poster_buckets["list_type"], poster_buckets["missing"],
        "Poster is a list for every asset.",
        "One or more assets have an invalid poster type (not a list).",
        "The asset poster is missing.",
    )
    num = _append_row(
        num, mod,
        "Verify that each poster list entry is an object across the seven-day schedule",
        "Each poster entry should be an object for every asset in the seven-day schedule.",
        poster_buckets["item_type"], empty_nt,
        "All poster entries are objects for every asset.",
        "One or more poster list entries have an invalid type (not an object).",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the availability of posters for all assets across the seven-day schedule",
        "A poster URL should be available for every asset in the seven-day schedule.",
        poster_buckets["url_missing"], empty_nt,
        "A poster is available for every asset.",
        "The asset poster is missing.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the poster URL type for all assets across the seven-day schedule",
        "The poster URL should be a string for every poster entry in the seven-day schedule.",
        poster_buckets["url_type"], empty_nt,
        "Poster URL type is a string for every asset.",
        "One or more poster URLs have an invalid type (not a string).",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the thumbnail URL length for all assets across the seven-day schedule",
        f"No asset thumbnail URL should exceed {poster_url_max:,} characters in the seven-day schedule.",
        poster_buckets["url_len"], empty_nt,
        f"Every asset thumbnail URL is within the permitted limit of {poster_url_max:,} characters.",
        f"One or more asset thumbnail URLs exceed the maximum permitted length of {poster_url_max:,} characters.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the HTTP response status of all asset thumbnails across the seven-day schedule",
        "Every asset thumbnail URL should return an HTTP 200 OK response throughout the seven-day schedule.",
        poster_buckets["status"], empty_nt,
        "Every asset thumbnail is retrieved successfully with an HTTP 200 OK response.",
        "One or more asset thumbnail requests return an unexpected HTTP status code.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the HTTP response status of all asset thumbnails across the seven-day schedule",
        "Every asset thumbnail URL should return an HTTP 200 OK response throughout the seven-day schedule.",
        poster_buckets["redirect"], empty_nt,
        "Every asset thumbnail is retrieved successfully with an HTTP 200 OK response.",
        "One or more asset thumbnail requests are redirected and return an unexpected HTTP status code.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the thumbnail format for all assets across the seven-day schedule",
        "Every asset thumbnail should be in JPEG or JPG format throughout the seven-day schedule.",
        poster_buckets["format"], empty_nt,
        "Every asset thumbnail is in the required JPEG or JPG format.",
        "One or more asset thumbnails are not in the required JPEG or JPG format.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the thumbnail resolution for all assets across the seven-day schedule",
        "Every asset thumbnail should have a resolution of 1920 × 1080 pixels throughout the seven-day schedule.",
        poster_buckets["resolution"], empty_nt,
        "Every asset thumbnail has the required resolution of 1920 × 1080 pixels.",
        "One or more asset thumbnails do not have the required resolution of 1920 × 1080 pixels.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the presence of the poster type for all assets across the seven-day schedule",
        "The poster type should be present for every poster entry in the seven-day schedule.",
        poster_buckets["type_missing"], empty_nt,
        "The poster type is present for every asset.",
        "One or more mandatory poster fields are missing.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the presence of the thumbnail width for all assets across the seven-day schedule",
        "The thumbnail width should be specified for every asset in the seven-day schedule.",
        poster_buckets["width_missing"], empty_nt,
        "The thumbnail width is specified for every asset.",
        "The thumbnail width is missing for one or more assets.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the presence of the thumbnail height for all assets across the seven-day schedule",
        "The thumbnail height should be specified for every asset in the seven-day schedule.",
        poster_buckets["height_missing"], empty_nt,
        "The thumbnail height is specified for every asset.",
        "The thumbnail height is missing for one or more assets.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify that each actual thumbnail width matches its XML_thumbnail_width value across the seven-day schedule",
        "Each asset thumbnail's actual width should match the XML_thumbnail_width value throughout the seven-day schedule.",
        poster_buckets["width_mismatch"], empty_nt,
        "The actual thumbnail width matches the XML_thumbnail_width value for every asset.",
        "The actual thumbnail width does not match the XML_thumbnail_width value for one or more assets.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify that each actual thumbnail height matches its XML_thumbnail_height value across the seven-day schedule",
        "Each asset thumbnail's actual height should match the XML_thumbnail_height value throughout the seven-day schedule.",
        poster_buckets["height_mismatch"], empty_nt,
        "The actual thumbnail height matches the XML_thumbnail_height value for every asset.",
        "The actual thumbnail height does not match the XML_thumbnail_height value for one or more assets.",
        "",
    )

    # f — genre
    num = _append_row(
        num, mod,
        "Verify the genre list type for all assets across the seven-day schedule",
        "The genre field should be a list for every asset in the seven-day schedule.",
        f_list_type, f_nt,
        "Genre is a list for every asset.",
        "One or more assets have an invalid genre type (not a list).",
        "The genre is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify that each genre entry is an object across the seven-day schedule",
        "Each genre entry should be an object for every asset in the seven-day schedule.",
        f_item_type, empty_nt,
        "All genre entries are objects for every asset.",
        "One or more genre entries have an invalid type (not an object).",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the genre id type for all assets across the seven-day schedule",
        "The genre id should be a non-empty string for every asset in the seven-day schedule.",
        f_id_type, empty_nt,
        "Genre id is a string for every asset.",
        "One or more genre ids have an invalid type (not a string).",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the genre original_name type for all assets across the seven-day schedule",
        "The genre original_name should be a non-empty string for every asset in the seven-day schedule.",
        f_name_type, empty_nt,
        "Genre original_name is a string for every asset.",
        "One or more genre original_name values have an invalid type (not a string).",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify genre original_name capitalization for all assets across the seven-day schedule",
        "Genre original_name should be capitalized for every asset in the seven-day schedule.",
        f_cap, empty_nt,
        "Genre original_name capitalization is valid for every asset.",
        "One or more genre original_name values have incorrect capitalization.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify that all categories comply with Samsung standards across the seven-day schedule",
        "Every category should be included in the Samsung_Supported_Category_List throughout the seven-day schedule.",
        f_allowlist, empty_nt,
        "All asset categories are included in the Samsung-supported category list.",
        "One or more assets contain categories that are not included in the Samsung_Supported_Category_List.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify rating capitalization for all assets across the seven-day schedule",
        "Rating values should use capital letters for every asset in the seven-day schedule.",
        g_cap_fail, g_nt,
        "All rating values have valid capitalization for every asset.",
        "One or more assets contain a rating value with incorrect capitalization.",
        "The rating value is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify that all rating values comply with Samsung standards across the seven-day schedule",
        "Every rating value should be included in the Samsung_Supported_Rating_Value_List throughout the seven-day schedule.",
        g_allow_fail, empty_nt,
        "Every rating value is included in the Samsung-supported rating value list.",
        "One or more assets contain a rating value that is not permitted by the platform standard.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the description type for all assets across the seven-day schedule",
        "The description should be a string for every asset in the seven-day schedule.",
        h_type, h_nt,
        "Description type is a string for every asset.",
        "One or more asset descriptions have an invalid type (not a string).",
        "The description is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify the description length for all assets across the seven-day schedule",
        f"No asset description should exceed {desc_max:,} characters in the seven-day schedule.",
        h_len, empty_nt,
        f"Every asset description is within the permitted limit of {desc_max:,} characters.",
        f"One or more asset descriptions exceed the maximum permitted length of {desc_max:,} characters.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify that asset descriptions do not contain prohibited special characters across the seven-day schedule",
        "Asset descriptions should not contain special characters prohibited by the platform standards.",
        h_spec, empty_nt,
        "No asset description contains prohibited special characters.",
        "One or more asset descriptions contain special characters prohibited by the platform standards.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the duration type for all assets across the seven-day schedule",
        "The duration should be an int for every asset in the seven-day schedule.",
        i_type, i_nt,
        "Duration type is an int for every asset.",
        "One or more asset durations have an invalid type (not an int).",
        "The duration is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify that asset duration is not zero across the seven-day schedule",
        "Duration should not equal 0 for any asset in the seven-day schedule.",
        i_zero, empty_nt,
        "All duration values are non-zero for every asset.",
        "One or more assets have a duration equal to 0.",
        "",
    )

    # j — schedule
    num = _append_row(
        num, sch,
        "Verify the presence of schedule mandatory fields across the seven-day schedule",
        "service_id, content_id, schedule_id, starttime, and duration should be present for every schedule entry in the seven-day schedule.",
        sched_buckets["missing_fields"], empty_nt,
        "All schedule mandatory fields are present for every schedule entry.",
        "One or more schedule mandatory fields are missing.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that schedule mandatory fields are non-empty across the seven-day schedule",
        "Schedule mandatory fields should be non-empty for every schedule entry in the seven-day schedule.",
        sched_buckets["empty_fields"], empty_nt,
        "All schedule mandatory field values are non-empty for every schedule entry.",
        "One or more schedule mandatory field values are empty.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that schedule start times are parseable across the seven-day schedule",
        "The start time of every asset should be a parseable ISO datetime throughout the seven-day schedule.",
        sched_buckets["start_parse"], empty_nt,
        "All starttime values are parseable for every schedule entry.",
        "One or more assets have a start time that is not parseable.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that schedule duration is parseable as int seconds across the seven-day schedule",
        "Schedule duration should parse to int seconds for every schedule entry in the seven-day schedule.",
        sched_buckets["dur_parse"], empty_nt,
        "All schedule duration values are parseable as int seconds.",
        "One or more schedule durations are not parseable as int seconds.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that schedule field types are strings across the seven-day schedule",
        "service_id, content_id, schedule_id, starttime, and duration should be strings for every schedule entry in the seven-day schedule.",
        sched_buckets["field_type"], empty_nt,
        "All schedule mandatory field types are strings for every schedule entry.",
        "One or more schedule fields have an invalid type (not a string).",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that service_id is constant per day across the seven-day schedule",
        "service_id should be the same for all schedule entries within each day throughout the seven-day schedule.",
        sched_buckets["service_id_inconsistent"], empty_nt,
        "service_id is constant for all schedule entries within each day.",
        "One or more days have an inconsistent schedule service_id.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that no asset shorter than 20 minutes (1,200 seconds) is scheduled across the seven-day schedule",
        "Every scheduled asset should have a duration of at least 20 minutes (1,200 seconds) throughout the seven-day schedule.",
        sched_buckets["dur_min"], empty_nt,
        "All scheduled assets have a duration of at least 20 minutes.",
        "One or more scheduled assets have a duration of less than the required 20 minutes (1,200 seconds).",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that no asset longer than 6 hours (21,600 seconds) is scheduled across the seven-day schedule",
        "Every scheduled asset should have a duration of no more than 6 hours (21,600 seconds) throughout the seven-day schedule.",
        sched_buckets["dur_max"], empty_nt,
        "All scheduled assets have a duration of no more than 6 hours.",
        "One or more scheduled assets exceed the maximum permitted duration of 6 hours (21,600 seconds).",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify the start-time format for all assets across the seven-day schedule",
        "The start time of every asset should use the expected date-time format throughout the seven-day schedule.",
        sched_buckets["start_strict"], empty_nt,
        "All assets use the expected date-time format.",
        "One or more assets have a start time in an invalid date-time format.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that there are no scheduling gaps between assets across the seven-day schedule",
        "Each asset's stop time should match the next asset's start time throughout the seven-day schedule.",
        sched_buckets["gap"], empty_nt,
        "There are no gaps between scheduled assets.",
        "A scheduling gap exists because an asset's stop time does not match the next asset's start time.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that there are no scheduling overlaps between assets across the seven-day schedule",
        "Consecutive schedule entries should align without overlaps throughout the seven-day schedule.",
        sched_buckets["overlap"], empty_nt,
        "There are no overlaps between scheduled assets.",
        "A scheduling overlap exists between consecutive assets.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that schedule content_id exists in program id across the seven-day schedule",
        "content_id should match a program id for every schedule entry in the seven-day schedule.",
        sched_buckets["content_missing"], empty_nt,
        "All content_id values resolve to a program id.",
        "One or more schedule content_id values do not resolve to a program id.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that schedule duration matches program duration across the seven-day schedule",
        "Schedule duration should equal program duration for every schedule entry in the seven-day schedule.",
        sched_buckets["duration_mismatch"], empty_nt,
        "Schedule duration matches program duration for every entry.",
        "One or more schedule durations do not match program duration.",
        "",
    )
    num = _append_row(
        num, sch,
        "Verify that content_id is not equal to schedule_id across the seven-day schedule",
        "content_id should differ from schedule_id for every schedule entry in the seven-day schedule.",
        sched_buckets["id_equals_schedule"], empty_nt,
        "content_id differs from schedule_id for every entry.",
        "One or more schedule content_id values equal schedule_id.",
        "",
    )

    # k — content_uri + m — episode/release + n — soft fields
    num = _append_row(
        num, mod,
        "Verify that content_uri equals the sheet Stream URL across the seven-day schedule",
        "content_uri should equal the control-sheet Stream URL for every asset in the seven-day schedule.",
        k_stream_fail, k_nt,
        "All content_uri values match the control-sheet Stream URL.",
        "One or more content_uri values do not match the control-sheet Stream URL.",
        "The content_uri is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify content_uri ads macro keys across the seven-day schedule",
        "content_uri should contain ads. parameters with required macro keys for every asset in the seven-day schedule.",
        k_ads_fail, empty_nt,
        "All content_uri values contain required ads. macro keys.",
        "One or more content_uri values are missing required ads. macro keys.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify content_uri macro encoding across the seven-day schedule",
        "content_uri macro placeholders should be URL-encoded for every asset in the seven-day schedule.",
        k_encoding_fail, empty_nt,
        "All content_uri macro placeholders are URL-encoded.",
        "One or more content_uri values contain unencoded macro placeholders.",
        "",
    )
    num = _append_row(
        num, mod,
        "Verify the presence of an episode number for all applicable assets across the seven-day schedule",
        "An episode number should be specified for every applicable asset in the seven-day schedule.",
        m_ep_type, m_ep_nt,
        "An episode number is specified for every applicable asset.",
        "One or more applicable assets have an invalid episode_num type (not a string).",
        "The episode number is missing for one or more applicable assets.",
    )
    num = _append_row(
        num, mod,
        "Verify the release_year format for all assets across the seven-day schedule",
        "release_year should be a string in YYYY format for every asset in the seven-day schedule.",
        m_ry_fail, m_ry_nt,
        "release_year is in YYYY format for every asset.",
        "One or more assets have an invalid release_year format (expected YYYY string).",
        "The release_year is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify the connecting_id soft empty value across the seven-day schedule",
        'connecting_id should be an empty string ("") for every asset in the seven-day schedule.',
        n_connecting_fail, n_connecting_nt,
        "connecting_id has the expected empty value for every asset.",
        "One or more assets do not have the expected empty connecting_id value.",
        "The connecting_id is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify the link_uri soft empty value across the seven-day schedule",
        'link_uri should be an empty string ("") for every asset in the seven-day schedule.',
        n_link_uri_fail, n_link_uri_nt,
        "link_uri has the expected empty value for every asset.",
        "One or more assets do not have the expected empty link_uri value.",
        "The link_uri is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify the tags soft empty value across the seven-day schedule",
        'tags should be an empty string ("") for every asset in the seven-day schedule.',
        n_tags_fail, n_tags_nt,
        "tags has the expected empty value for every asset.",
        "One or more assets do not have the expected empty tags value.",
        "The tags field is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify the link_type soft empty value across the seven-day schedule",
        'link_type should be "none" for every asset in the seven-day schedule.',
        n_link_type_fail, n_link_type_nt,
        'link_type has the expected value "none" for every asset.',
        'One or more assets do not have the expected link_type value "none".',
        "The link_type is missing for one or more assets.",
    )
    num = _append_row(
        num, sch,
        "Verify the program_type soft empty value across the seven-day schedule",
        'program_type should be an empty string ("") for every schedule entry in the seven-day schedule.',
        n_program_type_fail, n_program_type_nt,
        "program_type has the expected empty value for every schedule entry.",
        "One or more schedule entries do not have the expected empty program_type value.",
        "The program_type is missing for one or more schedule entries.",
    )
    num = _append_row(
        num, sch,
        "Verify the repeat.type soft empty value across the seven-day schedule",
        'repeat.type should be "none" for every schedule entry in the seven-day schedule.',
        n_repeat_type_fail, n_repeat_type_nt,
        'repeat.type has the expected value "none" for every schedule entry.',
        'One or more schedule entries do not have the expected repeat.type value "none".',
        "The repeat field is missing for one or more schedule entries.",
    )
    num = _append_row(
        num, sch,
        "Verify the repeat.expire_date soft empty value across the seven-day schedule",
        'repeat.expire_date should be an empty string ("") for every schedule entry in the seven-day schedule.',
        n_repeat_expire_fail, n_repeat_expire_nt,
        "repeat.expire_date has the expected empty value for every schedule entry.",
        "One or more schedule entries do not have the expected empty repeat.expire_date value.",
        "The repeat.expire_date is missing for one or more schedule entries.",
    )

    # l — cast
    num = _append_row(
        num, mod,
        "Verify that cast is a list for all assets across the seven-day schedule",
        "The cast field should be a list for every asset in the seven-day schedule.",
        l_type, l_nt,
        "Cast is a list for every asset.",
        "One or more assets have an invalid cast type (not a list).",
        "The cast is missing for one or more assets.",
    )
    num = _append_row(
        num, mod,
        "Verify that cast is non-empty for all assets across the seven-day schedule",
        "The cast field should be a non-empty list for every asset in the seven-day schedule.",
        l_empty, empty_nt,
        "Cast is a non-empty list for every asset.",
        "One or more assets have an empty cast list.",
        "",
    )

    logger.info("%sSSAI day validations complete; next_seq=%s rows=%s", prefix, num, len(Validation_Output))
    return num
