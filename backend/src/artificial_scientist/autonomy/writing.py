"""Phase 12: evidence-linked scientific writing with submission gates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Citation:
    citation_id: str
    title: str
    identifier: str
    verified: bool


@dataclass(frozen=True)
class Report:
    title: str
    claims: tuple[str, ...]
    citations: tuple[Citation, ...]
    methods: str
    limitations: str
    data_statement: str
    submission_approved: bool


class WritingError(ValueError):
    """Raised when a report lacks evidence or required sections."""


class ScientificWriter:
    def validate_bibliography(self, citations: Iterable[Citation]) -> tuple[Citation, ...]:
        items = tuple(citations)
        if not items or any(not item.identifier or not item.verified for item in items):
            raise WritingError("all citations must be verified")
        identifiers = [item.citation_id for item in items]
        if len(identifiers) != len(set(identifiers)):
            raise WritingError("duplicate citation IDs")
        return items

    def build(
        self,
        title: str,
        claims: list[str],
        citations: list[Citation],
        *,
        methods: str,
        limitations: str,
        data_statement: str,
        submission_approved: bool = False,
    ) -> Report:
        if not title or not claims or not methods or not limitations or not data_statement:
            raise WritingError("report sections are mandatory")
        if len(claims) > 100:
            raise WritingError("claim limit exceeded")
        references = self.validate_bibliography(citations)
        return Report(
            title, tuple(claims), references, methods, limitations,
            data_statement, submission_approved
        )

    def authorize_submission(self, report: Report, approval: str) -> Report:
        if not approval or len(approval) > 256:
            raise WritingError("explicit submission approval required")
        return Report(
            report.title, report.claims, report.citations, report.methods,
            report.limitations, report.data_statement, True
        )
