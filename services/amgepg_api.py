"""AMGEPG API client: auth, customer/platform resolution, and schedule fetch.

Credentials load from ``config_ssai.yaml`` (amgepg section). ``customer_id`` is
always passed by the caller (from the sheet), never from config.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

import requests
import yaml

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SEC = 60
_CONFIG: Optional[dict] = None
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config_ssai.yaml",
)


class AMGEPGAPIError(Exception):
    """Raised for AMGEPG HTTP / auth / payload failures (never includes secrets)."""


def _load_amgepg_config() -> dict:
    global _CONFIG
    if _CONFIG is None:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            full = yaml.safe_load(fh) or {}
        _CONFIG = full.get("amgepg") or {}
    return _CONFIG


class AMGEPGClient:
    """Reusable AMGEPG HTTP client. Does not log passwords or access tokens."""

    def __init__(self, config: Optional[dict] = None, timeout: int = _DEFAULT_TIMEOUT_SEC):
        cfg = config if config is not None else _load_amgepg_config()
        base = str(cfg.get("base_url") or "https://amgepg.amagi.tv/v1/").strip()
        if not base.endswith("/"):
            base = base + "/"
        self.base_url = base
        self.username = str(cfg.get("username") or "").strip()
        self.password = str(cfg.get("password") or "")
        self.timeout = timeout
        self._access_token: Optional[str] = None

    def get_token(self) -> str:
        """POST users/login and cache access_token. Raises AMGEPGAPIError on failure."""
        if self._access_token:
            return self._access_token
        if not self.username or not self.password:
            raise AMGEPGAPIError(
                "AMGEPG credentials missing; set amgepg.username and amgepg.password in config_ssai.yaml"
            )
        url = f"{self.base_url}users/login"
        try:
            logger.info("AMGEPG requesting access token from %susers/login", self.base_url)
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json={"username": self.username, "password": self.password},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AMGEPGAPIError(f"AMGEPG login request failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise AMGEPGAPIError("AMGEPG authentication failed: invalid credentials")
        if response.status_code >= 400:
            raise AMGEPGAPIError(f"AMGEPG login HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AMGEPGAPIError("AMGEPG login returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise AMGEPGAPIError("AMGEPG login response is not an object")
        token_obj = payload.get("token")
        if not isinstance(token_obj, dict):
            raise AMGEPGAPIError("AMGEPG login missing token object")
        access_token = token_obj.get("access_token")
        if not access_token or not str(access_token).strip():
            raise AMGEPGAPIError("AMGEPG login missing access_token")

        self._access_token = str(access_token).strip()
        logger.info("AMGEPG authentication succeeded")
        return self._access_token

    def _auth_headers(self) -> Dict[str, str]:
        token = self.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    def get_customer_details(self, customer_id: Any) -> dict:
        """GET customer/{customer_id}. Raises AMGEPGAPIError on failure."""
        cid = str(customer_id or "").strip()
        if not cid:
            raise AMGEPGAPIError("customer_id is required")
        url = f"{self.base_url}customer/{cid}"
        try:
            logger.info("AMGEPG fetching customer details customer_id=%s", cid)
            response = requests.get(url, headers=self._auth_headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise AMGEPGAPIError(f"AMGEPG customer request failed: {exc}") from exc

        if response.status_code >= 400:
            raise AMGEPGAPIError(f"AMGEPG customer HTTP {response.status_code} customer_id={cid}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AMGEPGAPIError("AMGEPG customer returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise AMGEPGAPIError("AMGEPG customer response is not an object")
        return payload

    def get_channel_code(self, customer_id: Any, customer: Optional[dict] = None) -> str:
        """Extract channel ``code`` from customer payload."""
        data = customer if customer is not None else self.get_customer_details(customer_id)
        code = data.get("code")
        if code is None or not str(code).strip():
            raise AMGEPGAPIError(f"AMGEPG customer missing channel code customer_id={customer_id}")
        return str(code).strip()

    def get_platform_id(
        self,
        customer_id: Any,
        delivery_region: str,
        customer: Optional[dict] = None,
    ) -> int:
        """
        Resolve Samsung platform Id for delivery_region.

        Prefer exact actual_platform == samsung{region.lower()}.
        If no exact match and exactly one samsung* platform exists, use that Id.
        """
        data = customer if customer is not None else self.get_customer_details(customer_id)
        region = str(delivery_region or "").strip().lower()
        if not region:
            raise AMGEPGAPIError("delivery_region is required for platform selection")

        platforms = data.get("platforms") or []
        if not isinstance(platforms, list):
            raise AMGEPGAPIError("AMGEPG customer platforms is not a list")

        target = f"samsung{region}"
        exact: list = []
        samsung_any: list = []
        for plat in platforms:
            if not isinstance(plat, dict):
                continue
            actual = str(plat.get("actual_platform") or "").strip().lower()
            if actual.startswith("samsung"):
                samsung_any.append(plat)
            if actual == target:
                exact.append(plat)

        chosen = None
        if exact:
            chosen = exact[0]
        elif len(samsung_any) == 1:
            chosen = samsung_any[0]
        else:
            raise AMGEPGAPIError(
                f"No Samsung platform for region={delivery_region!r} "
                f"(expected actual_platform={target!r}; found {len(samsung_any)} samsung platforms)"
            )

        pid = chosen.get("Id", chosen.get("id"))
        if pid is None:
            raise AMGEPGAPIError(f"Samsung platform missing Id for region={delivery_region!r}")
        try:
            return int(pid)
        except (TypeError, ValueError) as exc:
            raise AMGEPGAPIError(f"Invalid platform Id={pid!r}") from exc

    def resolve_channel_and_platform(
        self,
        customer_id: Any,
        delivery_region: str,
    ) -> Tuple[str, int]:
        """Return (channel_code, platform_id) for the customer + region."""
        customer = self.get_customer_details(customer_id)
        channel_code = self.get_channel_code(customer_id, customer=customer)
        platform_id = self.get_platform_id(
            customer_id, delivery_region, customer=customer
        )
        logger.info(
            "AMGEPG resolved customer_id=%s channel_code=%s platform_id=%s region=%s",
            customer_id,
            channel_code,
            platform_id,
            delivery_region,
        )
        return channel_code, platform_id

    def get_schedule(
        self,
        channel_code: str,
        platform_id: Any,
        schedule_date: str,
    ) -> dict:
        """
        GET epg/{channel_code}/{platform_id}/{token}?date={schedule_date}.

        ``schedule_date`` must be YYYY-MM-DD (caller-supplied; never hardcoded).
        """
        code = str(channel_code or "").strip()
        date = str(schedule_date or "").strip()
        if not code:
            raise AMGEPGAPIError("channel_code is required")
        if not date:
            raise AMGEPGAPIError("schedule_date is required")
        token = self.get_token()
        url = f"{self.base_url}epg/{code}/{platform_id}/{token}?date={date}"
        try:
            logger.info(
                "AMGEPG fetching schedule channel_code=%s platform_id=%s date=%s",
                code,
                platform_id,
                date,
            )
            response = requests.get(
                url,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AMGEPGAPIError(f"AMGEPG schedule request failed date={date}: {exc}") from exc

        if response.status_code >= 400:
            raise AMGEPGAPIError(
                f"AMGEPG schedule HTTP {response.status_code} date={date} "
                f"channel_code={code} platform_id={platform_id}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AMGEPGAPIError(f"AMGEPG schedule invalid JSON date={date}") from exc

        if not isinstance(payload, dict):
            raise AMGEPGAPIError(f"AMGEPG schedule response is not an object date={date}")
        return payload
