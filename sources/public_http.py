"""Public HTTPS transport with DNS validation and pinned destination addresses."""
import ipaddress
import re
import socket
from urllib.parse import urlsplit

import httpx

from core.exceptions import DataValidationError, SourceReadError


def public_address(value):
    address = ipaddress.ip_address(value)
    # Exclude translation/tunnelling forms and scoped IPv6 as well as local IPs.
    return (address.is_global and not address.is_multicast
            and '%' not in value
            and not (address.version == 6 and
                     (address.ipv4_mapped or address.sixtofour or address.teredo
                      or address in ipaddress.ip_network('64:ff9b::/96')
                      or address in ipaddress.ip_network('64:ff9b:1::/48'))))


def validate_api_url(value):
    """Validate syntax without DNS or network access."""
    message = 'API URL must be a public HTTPS URL on port 443, without credentials or a fragment.'
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise DataValidationError(message)
    try:
        parts = urlsplit(value)
        url = httpx.URL(value)
        if (parts.scheme.lower() != 'https' or not parts.hostname or parts.port not in (None, 443)
                or parts.username is not None or parts.password is not None or '#' in value
                or '\\' in value):
            raise ValueError()
        host = url.host.lower()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            labels = host.split('.')
            if (len(labels) < 2 or len(host) > 253
                    or labels[-1].isdigit()
                    or labels[-1] in ('localhost', 'local', 'internal', 'lan', 'home', 'test', 'invalid')
                    or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels)):
                raise ValueError()
        else:
            if not public_address(host):
                raise ValueError()
        return str(url)
    except (ValueError, httpx.InvalidURL):
        raise DataValidationError(message) from None


class PublicHTTPTransport(httpx.HTTPTransport):
    """Resolve once, reject any nonpublic answer, then connect to that exact IP.

    Original Host and TLS server name retain certificate verification. Redirects
    are disabled by the reader; environment proxies are disabled by the client.
    Each reader call owns a fresh transport and connection pool.
    """
    def handle_request(self, request):
        validate_api_url(str(request.url))
        host = request.url.host
        try:
            answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise SourceReadError('Cannot resolve task API hostname. Check the URL and network.') from exc
        addresses = [answer[4][0] for answer in answers]
        if not addresses or any(not public_address(address) for address in addresses):
            raise DataValidationError('API hostname must resolve only to public IP addresses. Private or internal destinations are blocked.')
        pinned = httpx.Request(request.method, request.url.copy_with(host=addresses[0]),
                               headers=request.headers, stream=request.stream,
                               extensions=dict(request.extensions, sni_hostname=host))
        return super().handle_request(pinned)
