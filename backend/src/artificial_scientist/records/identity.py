"""Canonical source-identity keys used for duplicate detection."""

import re
from urllib.parse import urlsplit, urlunsplit

from artificial_scientist.records.models import SourceRecord

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_DOI_SHAPE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(value: str | None) -> str | None:
    """Normalize a DOI from a DOI, doi: or DOI-resolver URL representation."""
    if not value:
        return None
    candidate = _DOI_PREFIX.sub("", value.strip()).strip().rstrip(".,;)")
    if _DOI_SHAPE.fullmatch(candidate):
        return candidate.casefold()
    return None


def source_identity_key(record: SourceRecord) -> str:
    """Return a stable, namespaced identity key for deduplication.

    DOI keys unify metadata returned by different scholarly providers. Records
    without a DOI use their external provider identifier; the final fallback is
    a normalized landing-page URL. These keys indicate metadata identity, not truth.
    """
    external_identifier = (record.external_identifier or "").strip()
    doi = normalize_doi(external_identifier)
    if doi:
        return f"doi:{doi}"

    if external_identifier:
        return f"identifier:{external_identifier.casefold()}"

    parts = urlsplit(str(record.source_url))
    scheme = parts.scheme.casefold()
    hostname = (parts.hostname or "").casefold()
    port = parts.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        hostname = f"{hostname}:{port}"
    path = parts.path.rstrip("/") or "/"
    normalized_url = urlunsplit((scheme, hostname, path, "", ""))
    return f"url:{normalized_url}"
