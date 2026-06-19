"""SSRF egress guard for outbound webhook delivery.

A webhook URL is tenant-controlled, so before the worker POSTs to it the target must be proven safe:
otherwise a tenant could point an endpoint at ``169.254.169.254`` (cloud metadata) or an internal
service and turn the delivery worker into an SSRF proxy. :func:`resolve_pinned_target` parses the
URL, resolves the host, and rejects the delivery if *any* resolved address is non-public (private,
loopback, link-local, reserved, multicast, unspecified, or CGNAT).

It then **pins** the connection: the returned target dials a validated IP *literal*, so the host is
never re-resolved between the check and the connect — a malicious nameserver can't rebind it to a
private address (DNS-rebinding-safe). TLS SNI and certificate verification still use the original
hostname (carried as ``sni_hostname``), and vhost routing still works (``host_header``). Deliveries
are made with redirects disabled, so a 3xx pointing at an internal host is never followed either.

Pure stdlib for the check (``ipaddress`` + the event loop's ``getaddrinfo``); a literal-IP host
resolves to itself without a DNS lookup, so the guard is deterministic and network-free in tests.
"""

from __future__ import annotations

import asyncio
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_PORTS = {"http": 80, "https": 443}
# Carrier-grade NAT (RFC 6598) is not flagged by ipaddress.is_private on every Python version.
_CGNAT_V4 = ipaddress.ip_network("100.64.0.0/10")


class WebhookEgressError(Exception):
    """Raised when a webhook target URL is unsafe to fetch (bad scheme or non-public address)."""


@dataclass(frozen=True)
class PinnedTarget:
    """A webhook target proven safe and pinned to one validated public IP.

    ``url`` dials a validated IP *literal*, so the host is never re-resolved — a nameserver can't
    rebind it to a private address between the check and the connect. ``host_header`` and
    ``sni_hostname`` carry the original hostname so vhost routing and TLS cert verification still
    work against the real name.
    """

    url: str
    host_header: str
    sni_hostname: str


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True only for globally-routable unicast addresses that are safe to POST to."""
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # covers 169.254.169.254 cloud metadata
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return False
    if isinstance(ip, ipaddress.IPv4Address):
        return ip not in _CGNAT_V4
    # An IPv4-mapped IPv6 address (::ffff:10.0.0.1) must be judged on its embedded v4 address.
    if ip.ipv4_mapped is not None:
        return _is_public(ip.ipv4_mapped)
    return True


async def _resolve_public_ips(host: str, port: int) -> list[str]:
    """Resolve ``host`` and return its addresses, raising if *any* is non-public (SSRF check)."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port)
    except OSError as exc:
        raise WebhookEgressError(f"cannot resolve host: {host}") from exc
    addresses = [str(info[4][0]).split("%", 1)[0] for info in infos]  # strip any IPv6 zone id
    if not addresses:
        raise WebhookEgressError(f"no addresses for host: {host}")
    for address in addresses:
        if not _is_public(ipaddress.ip_address(address)):
            raise WebhookEgressError(f"{host} resolves to non-public address {address}")
    return addresses


async def resolve_pinned_target(url: str) -> PinnedTarget:
    """Validate ``url`` and pin it to a validated public IP — the SSRF egress guard.

    Raises :class:`WebhookEgressError` unless ``url`` is http(s) and *every* address the host
    resolves to is public. Returns a :class:`PinnedTarget` whose ``url`` dials a validated IP
    literal so the host is never re-resolved (DNS-rebinding-safe), while TLS/cert verification
    stays bound to the real hostname.
    """
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme not in _ALLOWED_SCHEMES:
        raise WebhookEgressError(f"unsupported scheme: {scheme!r}")
    host = parts.hostname
    if not host:
        raise WebhookEgressError("missing host")
    try:
        port = parts.port  # parsed lazily; raises ValueError on a malformed port
    except ValueError as exc:
        raise WebhookEgressError(f"invalid port: {url!r}") from exc
    addresses = await _resolve_public_ips(host, port or _DEFAULT_PORTS[scheme])
    pinned_ip = addresses[0]
    authority = f"[{pinned_ip}]" if ":" in pinned_ip else pinned_ip  # bracket IPv6 literals
    if port is not None:
        authority = f"{authority}:{port}"
    pinned_url = urlunsplit((scheme, authority, parts.path, parts.query, parts.fragment))
    # Keep the original name (+ explicit non-default port) for vhost routing; drop any userinfo.
    host_header = parts.netloc.rsplit("@", 1)[-1]
    return PinnedTarget(url=pinned_url, host_header=host_header, sni_hostname=host)


async def assert_public_url(url: str) -> None:
    """Raise :class:`WebhookEgressError` unless ``url`` is http(s) and resolves to public IPs."""
    await resolve_pinned_target(url)
