"""
slack_service.py
----------------
Sends consolidated Slack summary messages for EPG validation runs.

Credentials
-----------
  SLACK_BOT_TOKEN   — Slack bot token
  SLACK_CHANNEL     — default channel (e.g. #epg-validation)

Per-channel entry format
------------------------
  :white_check_mark: Channel Name — HTML Report
  :x: Channel Name — HTML Report   (if failed / no HTML link)

Scalability
-----------
Channel entries are chunked into multiple section blocks (≤ 2 200 chars each).
If the total block count exceeds MAX_BLOCKS_PER_MSG the remainder is sent in
follow-up messages so the integration works safely for 40+ channels.
"""

import logging
import os

logger = logging.getLogger(__name__)

_MAX_BLOCK_CHARS   = 2_200   # safe limit per mrkdwn section block
_MAX_BLOCKS_PER_MSG = 38     # Slack allows 50; stay well under


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_client():
    """Return an authenticated slack_sdk WebClient."""
    try:
        from slack_sdk import WebClient
    except ImportError:
        raise ImportError("slack-sdk is required: pip install slack-sdk")

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    logger.info(f'Slack Bot Token: {token}')
    if not token:
        raise ValueError("SLACK_BOT_TOKEN environment variable is not set.")
    return WebClient(token=token)


def _resolve_channel(channel):
    """Return channel, falling back to the SLACK_CHANNEL env var."""
    return channel or os.environ.get("SLACK_CHANNEL", "")


def _status_emoji(status):
    s = str(status or "").upper()
    if s == "SUCCESS":
        return ":white_check_mark:"
    if s in ("FAILED", "ERROR"):
        return ":x:"
    return ":large_yellow_circle:"


def _chunk_text_into_blocks(entries, max_chars=_MAX_BLOCK_CHARS):
    """Group per-channel text entries into section blocks, each ≤ max_chars."""
    blocks = []
    current = ""
    for entry in entries:
        segment = entry + "\n"
        if current and len(current) + len(segment) > max_chars:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": current.rstrip()}})
            current = ""
        current += segment
    if current.strip():
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": current.rstrip()}})
    return blocks


def _send_blocks(client, channel, blocks):
    """Send *blocks* to *channel*, splitting into multiple messages if needed."""
    chunks = [
        blocks[i: i + _MAX_BLOCKS_PER_MSG]
        for i in range(0, len(blocks), _MAX_BLOCKS_PER_MSG)
    ]
    for idx, chunk in enumerate(chunks):
        if idx > 0:
            # Prepend a continuation header for follow-up messages.
            chunk = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*EPG Validation Summary (continued)*",
                    },
                }
            ] + chunk
        try:
            client.chat_postMessage(channel=channel, blocks=chunk, text="EPG Validation Summary")
        except Exception as exc:
            logger.error("Slack chat_postMessage failed (chunk %d/%d): %s", idx + 1, len(chunks), exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_slack_message(channel, text):
    """Send a plain-text message to *channel*."""
    channel = _resolve_channel(channel)
    if not channel:
        logger.warning("send_slack_message: no channel specified, skipping.")
        return
    try:
        client = _get_client()
        client.chat_postMessage(channel=channel, text=text)
    except Exception as exc:
        logger.error("Slack send_slack_message failed: %s", exc)


def send_execution_summary(
    channel,
    execution_results,
    build_number=None,
    build_url=None,
    build_start_time=None,
):
    """Send one consolidated Slack summary for the completed validation run.

    Parameters
    ----------
    channel            : str   — Slack channel; falls back to SLACK_CHANNEL env var.
    execution_results  : list  — one dict per channel/row, with keys:
                                   channel, status, html_link, [psd], [json_url],
                                   [excel_link], [drive_folder], [zip_link]
    build_number       : str   — CI build number (optional).
    build_url          : str   — CI build URL (optional).
    build_start_time   : str   — human-readable start timestamp (optional).

    Per-channel format (the only line rendered per channel)
    -------------------------------------------------------
    :white_check_mark: Channel Name — HTML Report
    """
    channel = _resolve_channel(channel)
    if not channel:
        logger.warning("send_execution_summary: no channel specified, skipping.")
        return

    results = execution_results or []
    total   = len(results)
    executed = sum(1 for r in results if str(r.get("status", "")).upper() in ("SUCCESS", "FAILED", "ERROR"))
    failed   = sum(1 for r in results if str(r.get("status", "")).upper() in ("FAILED", "ERROR"))
    skipped  = total - executed

    # ── Header block ─────────────────────────────────────────────────────────
    bn_text  = f"Build: #{build_number}" if build_number else ""
    bu_text  = f"<{build_url}|{bn_text}>" if (build_url and bn_text) else bn_text
    ts_text  = f"Started: {build_start_time}" if build_start_time else ""
    counts   = f"Total: {total}\u2003Executed: {executed}\u2003Failed: {failed}\u2003Skipped: {skipped}"

    header_lines = [":white_check_mark: *EPG Validation Summary*"]
    if bu_text:
        header_lines.append(bu_text)
    if ts_text:
        header_lines.append(ts_text)
    header_lines.append(counts)

    header_block = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "\n".join(header_lines)},
    }

    divider = {"type": "divider"}

    # ── Per-channel entries ───────────────────────────────────────────────────
    channel_entries = []
    for r in results:
        emoji     = _status_emoji(r.get("status"))
        ch_name   = r.get("channel") or "Unknown Channel"
        html_link = r.get("html_link") or ""
        json_link = r.get("json_link") or ""

        # Format: emoji Channel Name — HTML Report for JSON
        # Degrades gracefully when either or both links are unavailable.
        if html_link and json_link:
            report_part = f"<{html_link}|HTML Report> for <{json_link}|JSON>"
        elif html_link:
            report_part = f"<{html_link}|HTML Report>"
        elif json_link:
            report_part = f"<{json_link}|JSON>"
        else:
            report_part = "HTML Report (unavailable)"

        channel_entries.append(f"{emoji} {ch_name} \u2014 {report_part}")

    channel_blocks = _chunk_text_into_blocks(channel_entries)

    all_blocks = [header_block, divider] + channel_blocks

    try:
        client = _get_client()
        _send_blocks(client, channel, all_blocks)
        logger.info("Slack summary sent: %d channel entries across %d blocks.", total, len(all_blocks))
    except Exception as exc:
        logger.error("send_execution_summary failed: %s", exc)
