"""Optional ClamAV INSTREAM scanning for uploaded scientific attachments.

Production uploads fail closed unless a scanner endpoint is configured and healthy.
This module does not claim that checksum verification or MIME-type validation is malware scanning.
"""

from __future__ import annotations

import os
import socket


class ScannerUnavailable(RuntimeError):
    """Raised when required malware scanning cannot be completed."""


class MalwareDetected(ValueError):
    """Raised when ClamAV reports an infected attachment."""


def scan_binary_content(content: bytes, *, environment: str) -> str:
    """Scan content through ClamAV's TCP INSTREAM protocol.

    Returns 'clean' when a configured scanner reports OK. In development only,
    an unconfigured scanner returns 'skipped_development'. All other scanner
    configuration or communication failures fail closed.
    """
    host = os.getenv("ARTIFICIAL_SCIENTIST_CLAMAV_HOST", "").strip()
    raw_port = os.getenv("ARTIFICIAL_SCIENTIST_CLAMAV_PORT", "3310").strip()
    raw_timeout = os.getenv("ARTIFICIAL_SCIENTIST_CLAMAV_TIMEOUT_SECONDS", "5").strip()
    if not host:
        if environment.lower() == "development":
            return "skipped_development"
        raise ScannerUnavailable("Malware scanner is required but not configured.")
    try:
        port = int(raw_port)
        timeout = float(raw_timeout)
    except ValueError as error:
        raise ScannerUnavailable("Malware scanner configuration is invalid.") from error
    if not 1 <= port <= 65535 or not 0.1 <= timeout <= 30:
        raise ScannerUnavailable("Malware scanner configuration is invalid.")

    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content), 64 * 1024):
                chunk = content[offset : offset + 64 * 1024]
                connection.sendall(len(chunk).to_bytes(4, "big") + chunk)
            connection.sendall((0).to_bytes(4, "big"))
            response = bytearray()
            while len(response) < 4096 and not response.endswith(b"\0"):
                part = connection.recv(1024)
                if not part:
                    break
                response.extend(part)
    except OSError as error:
        raise ScannerUnavailable("Malware scanner is unavailable.") from error

    result = bytes(response).decode("utf-8", errors="replace").strip().rstrip("\0")
    if result.endswith("OK"):
        return "clean"
    if " FOUND" in result:
        raise MalwareDetected("Uploaded attachment was rejected by malware scanning.")
    raise ScannerUnavailable("Malware scanner returned an invalid response.")
