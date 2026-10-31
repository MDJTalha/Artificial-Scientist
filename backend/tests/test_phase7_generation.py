"""Regression tests for bounded Phase 7 hypothesis generation."""

import pytest

from artificial_scientist.discovery import (
    HypothesisGenerationRequest,
    generate_hypotheses,
)


def test_generate_hypotheses_returns_competing_directions_and_null():
    response = generate_hypotheses(
        HypothesisGenerationRequest(
            research_question="How does temperature affect reaction rate?",
            independent_variable="temperature",
            dependent_variable="reaction rate",
            system_or_population="the reaction system",
            context="fixed pressure",
        )
    )
    assert len(response.candidates) == 3
    statements = [item.candidate.statement for item in response.candidates]
    assert any("increases" in item for item in statements)
    assert any("decreases" in item for item in statements)
    assert any("does not materially change" in item for item in statements)
    assert all(
        item.review_status == "requires_human_review"
        and item.generation_method == "bounded_directional_templates"
        for item in response.candidates
    )
    assert all(item.candidate.source_record_ids == [] for item in response.candidates)


def test_generate_hypotheses_can_limit_directional_scope():
    response = generate_hypotheses(
        HypothesisGenerationRequest(
            research_question="Does dosage affect response?",
            independent_variable="dosage",
            dependent_variable="response",
            system_or_population="the study population",
            include_null=False,
            include_inverse=False,
        )
    )
    assert len(response.candidates) == 1
    assert "increases" in response.candidates[0].candidate.statement
    assert response.candidates[0].candidate.alternative_explanations


def test_generate_hypotheses_rejects_same_variable():
    with pytest.raises(ValueError, match="must differ"):
        HypothesisGenerationRequest(
            research_question="Does temperature affect temperature?",
            independent_variable="temperature",
            dependent_variable="temperature",
            system_or_population="the system",
        )
