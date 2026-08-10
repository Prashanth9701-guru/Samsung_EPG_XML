"""
S3_html_local.py
----------------
Uploads a generated HTML summary report to S3 using AWS IAM Roles Anywhere
credentials obtained via ``aws_signing_helper``.

Credentials configuration
--------------------------
Roles Anywhere config is read from:

    aws_cred/summary.json

Expected summary.json fields
------------------------------
  trust_anchor_arn   (required)
  profile_arn        (required)
  role_arn           (required)
  aws_region         (optional, default "ap-south-1")
  files.client_cert  (optional – absolute path; falls back to aws_cred/client.crt)
  files.client_key   (optional – absolute path; falls back to aws_cred/client.key)

Public API
----------
    upload_html_report(local_html_path: str) -> dict

Returns
-------
    {
        "bucket":     "onbqa-s3-automation",
        "key":        "roku/summary-reports/<json_name>/<yyyy>/<mm>/<dd>/<filename>",
        "report_url": "https://d1b4xlmaxnswax.cloudfront.net/<key>"
    }
"""

import json
import logging
import os
import re
import subprocess
from datetime import datetime

import boto3

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BUCKET              = "onbqa-s3-automation"
_CLOUDFRONT_BASE     = "https://d1b4xlmaxnswax.cloudfront.net"
_S3_PREFIX           = "samsung/summary-reports"
_S3_JSON_PREFIX      = "samsung/json-snapshots"
_CONTENT_TYPE        = "text/html; charset=utf-8"
_JSON_CONTENT_TYPE   = "application/json"

# aws_cred/ lives in the project root (one level above this services/ file).
_PROJECT_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f'_PROJECT_ROOT: {_PROJECT_ROOT}')
_AWS_CRED_DIR      = os.path.join(_PROJECT_ROOT, "aws_cred")
print(f'_AWS_CRED_DIR: {_AWS_CRED_DIR}')
_SUMMARY_JSON_PATH = os.path.join(_AWS_CRED_DIR, "summary.json")
_DEFAULT_CERT      = os.path.join(_AWS_CRED_DIR, "client.crt")
_DEFAULT_KEY       = os.path.join(_AWS_CRED_DIR, "client.key")

# Matches: Summary-report_<json_name>_<timestamp>.html
_REPORT_FILENAME_RE = re.compile(
    r'^Summary-report_(.+?)_\d+\.html$',
    re.IGNORECASE,
)

# Matches timestamped JSON snapshot: <YYYYMMDD_HHMMSS>_<original_basename>.json
# e.g. 20260318_154210_6321.json  →  group(1) = "6321"
_JSON_SNAPSHOT_RE = re.compile(
    r'^\d{8}_\d{6}_(.+)\.json$',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_roles_anywhere_config() -> dict:
    """Read and validate ``aws_cred/summary.json``.

    Returns a dict with normalised keys:
      trust_anchor_arn, profile_arn, role_arn, region, cert_path, key_path
    """
    if not os.path.isfile(_SUMMARY_JSON_PATH):
        raise FileNotFoundError(
            f"Roles Anywhere config not found: {_SUMMARY_JSON_PATH}"
        )

    with open(_SUMMARY_JSON_PATH, encoding="utf-8") as fh:
        raw = json.load(fh)

    required = ["trust_anchor_arn", "profile_arn", "role_arn"]
    missing  = [k for k in required if not raw.get(k)]
    if missing:
        raise ValueError(
            f"summary.json is missing required fields: {missing}"
        )

    # Resolve cert path: prefer the path recorded in summary.json if the file
    # exists on this machine; otherwise fall back to aws_cred/client.crt.
    files = raw.get("files") or {}

    def _resolve(json_key, default_path):
        candidate = files.get(json_key, "")
        if candidate and os.path.isfile(candidate):
            return candidate
        if os.path.isfile(default_path):
            return default_path
        raise FileNotFoundError(
            f"Credential file not found. "
            f"Tried: '{candidate}' (from summary.json) and '{default_path}' (default)."
        )

    return {
        "trust_anchor_arn": raw["trust_anchor_arn"],
        "profile_arn":      raw["profile_arn"],
        "role_arn":         raw["role_arn"],
        "region":           raw.get("aws_region", "ap-south-1"),
        "cert_path":        _resolve("client_cert", _DEFAULT_CERT),
        "key_path":         _resolve("client_key",  _DEFAULT_KEY),
    }


def _get_temp_credentials(cfg: dict) -> dict:
    """Invoke ``aws_signing_helper credential-process`` and return the
    temporary credential dict (AccessKeyId, SecretAccessKey, SessionToken).

    Raises RuntimeError if the helper is not found or returns an error.
    """
    cmd = [
        "aws_signing_helper", "credential-process",
        "--certificate",       cfg["cert_path"],
        "--private-key",       cfg["key_path"],
        "--trust-anchor-arn",  cfg["trust_anchor_arn"],
        "--profile-arn",       cfg["profile_arn"],
        "--role-arn",          cfg["role_arn"],
    ]

    logger.info("Invoking aws_signing_helper for Roles Anywhere credentials …")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "aws_signing_helper not found on PATH. "
            "Install it from https://github.com/aws/rolesanywhere-credential-helper/releases"
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"aws_signing_helper exited with code {result.returncode}. "
            f"stderr: {result.stderr.strip()}"
        )

    try:
        creds = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"aws_signing_helper returned non-JSON output: {result.stdout[:200]}"
        ) from exc

    for field in ("AccessKeyId", "SecretAccessKey", "SessionToken"):
        if not creds.get(field):
            raise RuntimeError(
                f"aws_signing_helper response is missing field '{field}'."
            )

    logger.info(
        "Temporary credentials obtained (expires: %s).",
        creds.get("Expiration", "unknown"),
    )
    return creds


def _build_s3_client(cfg: dict):
    """Return a boto3 S3 client authenticated with Roles Anywhere temp creds."""
    creds = _get_temp_credentials(cfg)
    return boto3.client(
        "s3",
        region_name          = cfg["region"],
        aws_access_key_id    = creds["AccessKeyId"],
        aws_secret_access_key= creds["SecretAccessKey"],
        aws_session_token    = creds["SessionToken"],
    )


def _extract_json_name_from_report_filename(filename: str) -> str:
    """Parse the json/channel identifier from the report filename.

    Examples
    --------
    Summary-report_6962_1773657988104.html        → "6962"
    Summary-report_feed-name_1773657988104.html   → "feed-name"

    Falls back to "unknown" if the filename does not match the expected pattern.
    """
    m = _REPORT_FILENAME_RE.match(filename)
    if m:
        return m.group(1)

    logger.warning(
        "_extract_json_name_from_report_filename: filename '%s' does not match "
        "expected pattern 'Summary-report_<json_name>_<timestamp>.html'. "
        "Using 'unknown' as fallback.",
        filename,
    )
    return "unknown"


def _build_s3_key(
    json_name: str,
    filename: str,
    upload_dt: datetime = None,
    prefix: str = None,
) -> str:
    """Build the S3 object key under *prefix* (defaults to ``_S3_PREFIX``).

    Pattern: <prefix>/<json_name>/<yyyy>/<mm>/<dd>/<filename>

    Examples
    --------
    HTML : roku/summary-reports/6962/2026/03/18/Summary-report_6962_….html
    JSON : roku/json-snapshots/6321/2026/03/18/20260318_154210_6321.json
    """
    dt  = upload_dt or datetime.utcnow()
    pfx = prefix if prefix is not None else _S3_PREFIX
    return "/".join([
        pfx,
        json_name,
        dt.strftime("%Y"),
        dt.strftime("%m"),
        dt.strftime("%d"),
        filename,
    ])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_html_report(local_html_path: str) -> dict:
    """Upload a generated HTML summary report to S3 via Roles Anywhere.

    Parameters
    ----------
    local_html_path : str
        Absolute (or relative) path to the HTML file to upload.

    Returns
    -------
    dict with keys:
        bucket     – S3 bucket name
        key        – S3 object key
        report_url – CloudFront URL to the uploaded report

    Raises
    ------
    FileNotFoundError  – if the HTML file or credentials are missing.
    ValueError         – if the credentials config is incomplete.
    RuntimeError       – if aws_signing_helper fails.
    """
    # 1. Validate source file
    local_html_path = os.path.abspath(local_html_path)
    if not os.path.isfile(local_html_path):
        raise FileNotFoundError(
            f"HTML report file not found: {local_html_path}"
        )

    filename  = os.path.basename(local_html_path)
    json_name = _extract_json_name_from_report_filename(filename)
    upload_dt = datetime.utcnow()
    s3_key    = _build_s3_key(json_name, filename, upload_dt)

    logger.info(
        "Preparing to upload '%s' → s3://%s/%s",
        filename, _BUCKET, s3_key,
    )

    # 2. Load credentials config and build S3 client
    cfg      = _load_roles_anywhere_config()
    s3_client = _build_s3_client(cfg)

    # 3. Upload
    with open(local_html_path, "rb") as fh:
        s3_client.put_object(
            Bucket      = _BUCKET,
            Key         = s3_key,
            Body        = fh,
            ContentType = _CONTENT_TYPE,
        )

    report_url = f"{_CLOUDFRONT_BASE.rstrip('/')}/{s3_key}"

    logger.info(
        "Upload complete. Report URL: %s",
        report_url,
    )

    return {
        "bucket":     _BUCKET,
        "key":        s3_key,
        "report_url": report_url,
    }


def _extract_json_name_from_snapshot_filename(filename: str) -> str:
    """Parse the channel/feed identifier from a timestamped JSON snapshot filename.

    Examples
    --------
    20260318_154210_6321.json        → "6321"
    20260318_154210_my-feed.json     → "my-feed"

    Falls back to "unknown" if the filename does not match.
    """
    m = _JSON_SNAPSHOT_RE.match(filename)
    if m:
        return m.group(1)

    logger.warning(
        "_extract_json_name_from_snapshot_filename: '%s' does not match "
        "expected pattern '<YYYYMMDD_HHMMSS>_<basename>.json'. "
        "Using 'unknown' as fallback.",
        filename,
    )
    return "unknown"


# def upload_json_snapshot(local_json_path: str) -> dict:
#     """Upload a timestamped JSON validation snapshot to S3 via Roles Anywhere.
#
#     Parameters
#     ----------
#     local_json_path : str
#         Absolute (or relative) path to the JSON snapshot file to upload.
#         Expected filename pattern: ``<YYYYMMDD_HHMMSS>_<original_basename>.json``
#
#     Returns
#     -------
#     dict with keys:
#         bucket     – S3 bucket name
#         key        – S3 object key  (roku/json-snapshots/…)
#         report_url – CloudFront URL to the uploaded snapshot
#
#     Raises
#     ------
#     FileNotFoundError  – if the JSON file or credentials are missing.
#     ValueError         – if the credentials config is incomplete.
#     RuntimeError       – if aws_signing_helper fails.
#     """
#     # 1. Validate source file
#     local_json_path = os.path.abspath(local_json_path)
#     if not os.path.isfile(local_json_path):
#         raise FileNotFoundError(
#             f"JSON snapshot file not found: {local_json_path}"
#         )
#
#     filename  = os.path.basename(local_json_path)
#     json_name = _extract_json_name_from_snapshot_filename(filename)
#     upload_dt = datetime.utcnow()
#     s3_key    = _build_s3_key(json_name, filename, upload_dt, prefix=_S3_JSON_PREFIX)
#
#     logger.info(
#         "Preparing to upload JSON snapshot '%s' → s3://%s/%s",
#         filename, _BUCKET, s3_key,
#     )
#
#     # 2. Load credentials config and build S3 client (reuses existing helpers)
#     cfg       = _load_roles_anywhere_config()
#     s3_client = _build_s3_client(cfg)
#
#     # 3. Upload
#     with open(local_json_path, "rb") as fh:
#         s3_client.put_object(
#             Bucket      = _BUCKET,
#             Key         = s3_key,
#             Body        = fh,
#             ContentType = _JSON_CONTENT_TYPE,
#         )
#
#     report_url = f"{_CLOUDFRONT_BASE.rstrip('/')}/{s3_key}"
#
#     logger.info(
#         "JSON snapshot upload complete. URL: %s",
#         report_url,
#     )
#
#     return {
#         "bucket":     _BUCKET,
#         "key":        s3_key,
#         "report_url": report_url,
#     }
