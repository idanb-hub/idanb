from __future__ import annotations

import base64
import socket

import typing_extensions as T
import pydantic.dataclasses

from analytics.connectors.http import HTTPConnector
from idanb import meta

# ---------------------------------------------------------------------------
# VirusTotal helper: observable type detection and endpoint routing
# ---------------------------------------------------------------------------

def _is_url(observable: str) -> bool:
    return observable.startswith(("https://", "http://"))


def _url_id(url: str) -> str:
    """VirusTotal URL identifier (base64url-encoded, no padding)."""
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


def _vt_endpoint(observable: str) -> str:
    """Return the VT API v3 path for the given observable."""
    if _is_url(observable):
        return f"urls/{_url_id(observable)}?relationships=comments"

    # IPv4 / IPv6 heuristic: contains '.' or ':'
    if "." in observable or ":" in observable:
        try:
            socket.inet_pton(socket.AF_INET, observable)
        except OSError:
            pass
        else:
            return f"ip_addresses/{observable}?relationships=resolutions"
        try:
            socket.inet_pton(socket.AF_INET6, observable)
        except OSError:
            pass
        else:
            return f"ip_addresses/{observable}?relationships=resolutions"
        # Otherwise treat as domain
        return f"domains/{observable}?relationships=resolutions"

    # No '.' or ':' → file hash
    return (
        f"files/{observable}"
        "?relationships=contacted_ips,contacted_domains,contacted_urls,"
        "bundled_files,dropped_files"
    )


# ---------------------------------------------------------------------------
# VirusTotal connector
# ---------------------------------------------------------------------------

@meta.CONFIG.register("virustotal")
@pydantic.dataclasses.dataclass()
class VirusTotalConfig:
    api_key: str


class VirtusTotalConnector(HTTPConnector[T.Any]):
    def __init__(self, config: VirusTotalConfig | None = None) -> None:
        if config is None:
            config = meta.CONFIG[VirusTotalConfig]

        super().__init__(
            base_url="https://www.virustotal.com/api/v3/",
            headers={
                "accept": "application/json",
                "x-apikey": config.api_key,
            },
            mode="json",
        )

    async def observable(self, obs: str) -> dict[str, T.Any]:
        endpoint = _vt_endpoint(obs)
        async with self.get(endpoint) as response:
            return await response.json()

    async def file_report(self, file_hash: str) -> dict[str, T.Any]:
        async with self.get(
            f"files/{file_hash}",
            params={
                "relationships": [
                    "contacted_ips",
                    "contacted_domains",
                    "contacted_urls",
                ],
            },
        ) as response:
            return await response.json()

    @staticmethod
    def gui_link(report: dict[str, T.Any]) -> str:
        link: str = report["data"]["links"]["self"]
        return (
            link
            .replace("/api/v3/", "/gui/")
            .replace("/files/", "/file/")
            .replace("/ip_addresses/", "/ip-address/")
            .replace("/domains/", "/domain/")
            .replace("/urls/", "/url/")
        )
