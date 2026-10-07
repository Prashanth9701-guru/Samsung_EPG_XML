"""
mongo_service.py
----------------
Non-blocking MongoDB storage for daily EPG QA executions.

One document per calendar day per pipeline, with each completed input
appended to ``results[]``. NON-SSAI and SSAI use separate collections.

Environment
-----------
  MONGO_URI                    — full connection URI (required to enable)
  MONGO_DB                     — database name (default: onbqa_tm)
  MONGO_COLLECTION_NON_SSAI    — default: non_ssai_daily_executions
  MONGO_COLLECTION_SSAI        — default: ssai_daily_executions

If MONGO_URI is unset, all public helpers no-op and return None/False.
All public helpers catch exceptions, log, and never raise into callers.

Example document
----------------
{
  "execution_date": "2026-09-09",
  "status": "COMPLETED",
  "total_inputs": 5,
  "completed_inputs": 5,
  "results": [
    {
      "input_name": "Channel_A",
      "ticket_id": "PSD-123",
      "status": "PASS",
      "result": [/* Validation_Output */]
    },
    ...
  ]
}

Query examples
--------------
  get_daily_execution("2026-09-09", "non_ssai")
  get_input_result("2026-09-09", "non_ssai", "PSD-123")
  get_daily_statistics("2026-09-09", "ssai")
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PIPELINE_NON_SSAI = "non_ssai"
PIPELINE_SSAI = "ssai"

_VALID_PIPELINES = frozenset({PIPELINE_NON_SSAI, PIPELINE_SSAI})

_SERVER_SELECTION_TIMEOUT_MS = 5000
_CONNECT_TIMEOUT_MS = 5000

_client = None
_indexes_ensured = False
_disabled_logged = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _execution_date_str(execution_date: Optional[str] = None) -> str:
    if execution_date:
        return execution_date
    return _utc_now().strftime("%Y-%m-%d")


def is_enabled() -> bool:
    return bool(os.environ.get("MONGO_URI", "").strip())


def _log_disabled_once() -> None:
    global _disabled_logged
    if not _disabled_logged:
        logger.info("MONGO_URI not set — MongoDB result storage disabled (no-op)")
        _disabled_logged = True


def _get_client():
    """Lazy singleton MongoClient, or None if disabled / unavailable."""
    global _client
    if not is_enabled():
        _log_disabled_once()
        return None
    if _client is not None:
        return _client
    try:
        from pymongo import MongoClient
    except ImportError:
        logger.error("pymongo is not installed — MongoDB storage disabled")
        return None
    try:
        uri = os.environ.get("MONGO_URI", "").strip()
        _client = MongoClient(
            uri,
            serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
            connectTimeoutMS=_CONNECT_TIMEOUT_MS,
        )
        # Force early server selection so failures surface at first use.
        _client.admin.command("ping")
        logger.info("MongoDB client connected")
        return _client
    except Exception as exc:
        logger.error("MongoDB connection failed (non-fatal): %s", exc)
        _client = None
        return None


def get_collection(pipeline: str):
    """Return the collection for ``non_ssai`` or ``ssai``, or None."""
    if pipeline not in _VALID_PIPELINES:
        logger.error("Invalid Mongo pipeline=%r (expected non_ssai|ssai)", pipeline)
        return None
    client = _get_client()
    if client is None:
        return None
    db_name = os.environ.get("MONGO_DB", "onbqa_tm").strip() or "onbqa_tm"
    if pipeline == PIPELINE_NON_SSAI:
        coll_name = (
            os.environ.get("MONGO_COLLECTION_NON_SSAI", "non_ssai_daily_executions").strip()
            or "non_ssai_daily_executions"
        )
    else:
        coll_name = (
            os.environ.get("MONGO_COLLECTION_SSAI", "ssai_daily_executions").strip()
            or "ssai_daily_executions"
        )
    return client[db_name][coll_name]


def ensure_indexes() -> bool:
    """Create unique execution_date index on both collections. Non-fatal."""
    global _indexes_ensured
    if _indexes_ensured:
        return True
    if not is_enabled():
        _log_disabled_once()
        return False
    try:
        for pipeline in (PIPELINE_NON_SSAI, PIPELINE_SSAI):
            coll = get_collection(pipeline)
            if coll is None:
                return False
            coll.create_index("execution_date", unique=True)
        _indexes_ensured = True
        logger.info("MongoDB unique indexes ensured on execution_date")
        return True
    except Exception as exc:
        logger.error("MongoDB ensure_indexes failed (non-fatal): %s", exc)
        return False


def normalize_input_status(
    pipeline_status: Optional[str],
    validation_output: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Map runner/template status + Validation_Output rows to PASS|FAIL."""
    status = (pipeline_status or "").strip().upper()
    if status in ("FAILED", "FAIL", "ERROR"):
        return "FAIL"
    rows = validation_output or []
    for row in rows:
        row_status = str(row.get("Status") or row.get("status") or "").strip().lower()
        if row_status == "failed":
            return "FAIL"
    if status in ("SUCCESS", "PASSED", "PASS"):
        return "PASS"
    if status:
        return "FAIL"
    return "FAIL" if rows else "FAIL"


def build_input_payload(
    *,
    input_name: str,
    status: str,
    execution_start_time: datetime,
    execution_end_time: datetime,
    result: Optional[List[Dict[str, Any]]] = None,
    ticket_id: str = "",
    input_url: str = "",
    partner: str = "",
    html_link: str = "",
    drive_link: str = "",
) -> Dict[str, Any]:
    """Build one ``results[]`` element for store_input_result."""
    start = execution_start_time
    end = execution_end_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    seconds = max(0.0, (end - start).total_seconds())
    return {
        "input_name": input_name or "unknown",
        "ticket_id": ticket_id or "",
        "input_url": input_url or "",
        "partner": partner or "",
        "status": status,
        "execution_start_time": start,
        "execution_end_time": end,
        "execution_time_seconds": round(seconds, 3),
        "html_link": html_link or "",
        "drive_link": drive_link or "",
        "result": list(result) if result else [],
    }


def init_daily_execution(
    pipeline: str,
    total_inputs: int,
    *,
    execution_date: Optional[str] = None,
    build_number: Optional[str] = None,
    build_url: Optional[str] = None,
) -> bool:
    """
    Create or reuse today's daily execution document.

    Uses upsert + $setOnInsert so same-day restart does not create a duplicate.
    """
    if not is_enabled():
        _log_disabled_once()
        return False
    try:
        ensure_indexes()
        coll = get_collection(pipeline)
        if coll is None:
            return False
        date_str = _execution_date_str(execution_date)
        now = _utc_now()
        coll.update_one(
            {"execution_date": date_str},
            {
                "$setOnInsert": {
                    "execution_date": date_str,
                    "pipeline": pipeline,
                    "execution_start_time": now,
                    "execution_end_time": None,
                    "status": "IN_PROGRESS",
                    "completed_inputs": 0,
                    "results": [],
                    "created_at": now,
                },
                "$set": {
                    "total_inputs": int(total_inputs),
                    "build_number": build_number or "",
                    "build_url": build_url or "",
                    "updated_at": now,
                },
            },
            upsert=True,
        )
        logger.info(
            "Mongo daily execution ready date=%s pipeline=%s total_inputs=%s",
            date_str,
            pipeline,
            total_inputs,
        )
        return True
    except Exception as exc:
        logger.error(
            "Mongo init_daily_execution failed pipeline=%s (non-fatal): %s",
            pipeline,
            exc,
        )
        return False


def store_input_result(
    pipeline: str,
    input_payload: Dict[str, Any],
    *,
    execution_date: Optional[str] = None,
) -> bool:
    """
    Append or replace one input result on today's document.

    Same-day identity is ``ticket_id`` (PSD / Ticket ID). If that ticket already
    exists, replace in place without double-incrementing ``completed_inputs``.
    Otherwise ``$push`` + ``$inc``.
    """
    if not is_enabled():
        _log_disabled_once()
        return False
    try:
        coll = get_collection(pipeline)
        if coll is None:
            return False
        date_str = _execution_date_str(execution_date)
        ticket_id = str((input_payload or {}).get("ticket_id") or "").strip()
        if not ticket_id:
            ticket_id = "unknown"
            input_payload = dict(input_payload or {})
            input_payload["ticket_id"] = ticket_id
            logger.warning(
                "Mongo store_input_result missing ticket_id — using fallback %r",
                ticket_id,
            )
        now = _utc_now()

        # Idempotent replace when this ticket already exists for the day.
        replace_result = coll.update_one(
            {"execution_date": date_str, "results.ticket_id": ticket_id},
            {
                "$set": {
                    "results.$": input_payload,
                    "updated_at": now,
                    "status": "IN_PROGRESS",
                }
            },
        )
        if replace_result.matched_count:
            logger.info(
                "Mongo replaced input result date=%s pipeline=%s ticket_id=%s",
                date_str,
                pipeline,
                ticket_id,
            )
            return True

        push_result = coll.update_one(
            {"execution_date": date_str},
            {
                "$push": {"results": input_payload},
                "$inc": {"completed_inputs": 1},
                "$set": {"updated_at": now, "status": "IN_PROGRESS"},
            },
        )
        if push_result.matched_count == 0:
            # Day doc missing (init skipped/failed) — create then push.
            coll.update_one(
                {"execution_date": date_str},
                {
                    "$setOnInsert": {
                        "execution_date": date_str,
                        "pipeline": pipeline,
                        "execution_start_time": now,
                        "execution_end_time": None,
                        "total_inputs": 0,
                        "completed_inputs": 0,
                        "results": [],
                        "created_at": now,
                    },
                    "$set": {"updated_at": now, "status": "IN_PROGRESS"},
                },
                upsert=True,
            )
            push_result = coll.update_one(
                {
                    "execution_date": date_str,
                    "results.ticket_id": {"$ne": ticket_id},
                },
                {
                    "$push": {"results": input_payload},
                    "$inc": {"completed_inputs": 1},
                    "$set": {"updated_at": now},
                },
            )
            if push_result.matched_count == 0:
                # Race: another writer added same ticket — replace.
                coll.update_one(
                    {"execution_date": date_str, "results.ticket_id": ticket_id},
                    {"$set": {"results.$": input_payload, "updated_at": now}},
                )

        logger.info(
            "Mongo stored input result date=%s pipeline=%s ticket_id=%s status=%s",
            date_str,
            pipeline,
            ticket_id,
            input_payload.get("status"),
        )
        return True
    except Exception as exc:
        logger.error(
            "Mongo store_input_result failed pipeline=%s ticket_id=%s (non-fatal): %s",
            pipeline,
            (input_payload or {}).get("ticket_id"),
            exc,
        )
        return False


def mark_daily_execution_completed(
    pipeline: str,
    *,
    execution_date: Optional[str] = None,
) -> bool:
    """Set execution_end_time and overall status COMPLETED or PARTIAL."""
    if not is_enabled():
        _log_disabled_once()
        return False
    try:
        coll = get_collection(pipeline)
        if coll is None:
            return False
        date_str = _execution_date_str(execution_date)
        doc = coll.find_one({"execution_date": date_str})
        if not doc:
            logger.warning(
                "Mongo mark completed skipped — no document date=%s pipeline=%s",
                date_str,
                pipeline,
            )
            return False
        total = int(doc.get("total_inputs") or 0)
        completed = int(doc.get("completed_inputs") or 0)
        overall = "COMPLETED" if total > 0 and completed >= total else "PARTIAL"
        if total == 0 and completed > 0:
            overall = "COMPLETED"
        now = _utc_now()
        coll.update_one(
            {"execution_date": date_str},
            {
                "$set": {
                    "execution_end_time": now,
                    "status": overall,
                    "updated_at": now,
                }
            },
        )
        logger.info(
            "Mongo marked daily execution %s date=%s pipeline=%s completed=%s/%s",
            overall,
            date_str,
            pipeline,
            completed,
            total,
        )
        return True
    except Exception as exc:
        logger.error(
            "Mongo mark_daily_execution_completed failed pipeline=%s (non-fatal): %s",
            pipeline,
            exc,
        )
        return False


def get_daily_execution(
    execution_date: str,
    pipeline: str,
) -> Optional[Dict[str, Any]]:
    """Return the daily document for a date/pipeline, or None."""
    if not is_enabled():
        _log_disabled_once()
        return None
    try:
        coll = get_collection(pipeline)
        if coll is None:
            return None
        return coll.find_one({"execution_date": execution_date})
    except Exception as exc:
        logger.error("Mongo get_daily_execution failed (non-fatal): %s", exc)
        return None


def get_input_result(
    execution_date: str,
    pipeline: str,
    ticket_id: str,
) -> Optional[Dict[str, Any]]:
    """Return one input's entry by PSD/Ticket ID from the daily results array."""
    if not is_enabled():
        _log_disabled_once()
        return None
    try:
        coll = get_collection(pipeline)
        if coll is None:
            return None
        tid = str(ticket_id or "").strip()
        doc = coll.find_one(
            {"execution_date": execution_date, "results.ticket_id": tid},
            {"results": {"$elemMatch": {"ticket_id": tid}}},
        )
        if not doc:
            return None
        results = doc.get("results") or []
        return results[0] if results else None
    except Exception as exc:
        logger.error("Mongo get_input_result failed (non-fatal): %s", exc)
        return None


def fetch_and_log_today_input(
    pipeline: str,
    ticket_id: str,
    *,
    execution_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch today's Mongo entry for the given ticket_id and log summary + full result.

    Uses current UTC date when ``execution_date`` is omitted. Non-fatal.
    """
    if not is_enabled():
        _log_disabled_once()
        return None
    try:
        date_str = _execution_date_str(execution_date)
        tid = str(ticket_id or "").strip() or "unknown"
        fetched = get_input_result(date_str, pipeline, tid)
        if not fetched:
            logger.warning(
                "Mongo no result for date=%s pipeline=%s ticket_id=%s",
                date_str,
                pipeline,
                tid,
            )
            return None
        result_rows = fetched.get("result") or []
        logger.info(
            "Mongo fetched input date=%s pipeline=%s ticket_id=%s rows=%s status=%s",
            date_str,
            pipeline,
            tid,
            len(result_rows),
            fetched.get("status"),
        )
        logger.info(
            "Mongo Validation_Output result for ticket_id=%s: %s",
            tid,
            result_rows,
        )
        return result_rows
    except Exception as exc:
        logger.error(
            "Mongo fetch_and_log_today_input failed pipeline=%s ticket_id=%s (non-fatal): %s",
            pipeline,
            ticket_id,
            exc,
        )
        return None


def get_daily_statistics(
    execution_date: str,
    pipeline: str,
) -> Optional[Dict[str, Any]]:
    """
    Return daily stats::

        {
          "execution_date": "...",
          "pipeline": "...",
          "total_inputs": N,
          "completed_inputs": N,
          "passed_inputs": N,
          "failed_inputs": N,
          "status": "COMPLETED"|"PARTIAL"|"IN_PROGRESS"|None,
        }
    """
    if not is_enabled():
        _log_disabled_once()
        return None
    try:
        doc = get_daily_execution(execution_date, pipeline)
        if not doc:
            return {
                "execution_date": execution_date,
                "pipeline": pipeline,
                "total_inputs": 0,
                "completed_inputs": 0,
                "passed_inputs": 0,
                "failed_inputs": 0,
                "status": None,
            }
        results = doc.get("results") or []
        passed = sum(1 for r in results if str(r.get("status", "")).upper() == "PASS")
        failed = sum(1 for r in results if str(r.get("status", "")).upper() == "FAIL")
        return {
            "execution_date": execution_date,
            "pipeline": pipeline,
            "total_inputs": int(doc.get("total_inputs") or 0),
            "completed_inputs": int(doc.get("completed_inputs") or len(results)),
            "passed_inputs": passed,
            "failed_inputs": failed,
            "status": doc.get("status"),
        }
    except Exception as exc:
        logger.error("Mongo get_daily_statistics failed (non-fatal): %s", exc)
        return None
