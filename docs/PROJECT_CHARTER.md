# Project Charter — Artificial Scientist

**Status:** Draft baseline, Phase 0  
**Project type:** Non-commercial, research-based software and scientific exploration  
**Date:** 2026-10-26

## 1. Mission

Develop a progressively more capable scientific research system that helps investigate questions across disciplines, connect evidence, generate testable hypotheses, conduct computational experiments, evaluate results, retain validated knowledge, and communicate findings reproducibly.

The long-term ambition is to discover useful knowledge that is not explicitly programmed into the system. Novelty and broad autonomy are aspirations to evaluate, not outcomes to guarantee.

## 2. Research objectives

1. Make scientific claims traceable to reliable sources, calculations, or recorded observations.
2. Support literature discovery, synthesis, and identification of unresolved questions.
3. Produce multiple competing hypotheses and design tests that can distinguish them.
4. Execute approved mathematical and computational work in controlled environments.
5. Evaluate uncertainty, alternatives, reproducibility, and known limitations.
6. Retain research history and lessons using versioned, auditable records.
7. Prepare scientific reports with verified citations and transparent methods.
8. Measure improvements with independent benchmarks and expert evaluation when possible.
9. Expand across disciplines only as domain data, tools, safety controls, and evaluation become available.

## 3. Intended scientific scope

The intended scope includes mathematics; physics; chemistry and materials science; electrical, electronics, and hardware engineering; computer science and software engineering; AI and machine learning; astronomy and space science; geology and Earth sciences; and later, carefully selected fields such as biology, environmental science, energy, agriculture, and medicine.

Listing a discipline in this charter does not mean the system already possesses validated competence in it.

## 4. Core operating principles

- **Evidence first:** distinguish retrieved fact, computation, observation, inference, and conjecture.
- **Falsifiability:** seek disconfirming evidence and tests that could reject an appealing hypothesis.
- **Reproducibility:** preserve methods, dependencies, parameters, code, data provenance, and results.
- **Provenance:** retain source identifiers and the chain from evidence to claims.
- **Uncertainty:** report confidence and limitations calibrated to actual evidence.
- **Independent review:** do not treat agreement between agents or models as proof.
- **Research honesty:** never fabricate sources, results, experiments, peer review, or benchmark scores.
- **Controlled autonomy:** use the least privilege necessary and require authorization for consequential actions.
- **Reversibility:** version learning updates and support rollback.
- **Human benefit:** prioritize knowledge and tools that support safety, education, health, sustainability, accessibility, and scientific understanding.

## 5. Initial scope

The first working prototype should complete one bounded computational research cycle:

1. Accept a clearly defined research question.
2. retrieve traceable sources from permitted resources;
3. summarize known evidence and uncertainty;
4. state a testable hypothesis and alternatives;
5. define a reproducible computational test;
6. execute approved code in an isolated environment;
7. validate calculations and results independently where feasible;
8. record methods, inputs, outputs, and limitations; and
9. export a report that differentiates evidence from interpretation.

Start with computationally testable topics. Physical experiments, medical decisions, hazardous procedures, or consequential external actions are outside the initial autonomous scope.

## 6. Explicit non-goals

- Building or training a frontier-scale foundation model from scratch as the starting point.
- Claiming universal or complete knowledge.
- Guaranteeing that a generated idea is novel or scientifically true.
- Unrestricted execution of generated code or instructions from retrieved documents.
- Unsupervised modification of production code, security policies, or model weights.
- Publishing or submitting research externally without appropriate human authorization.
- Sales, subscriptions, customer acquisition, or monetization as project success measures.

## 7. Success measures

Evaluate the system using documented and repeatable measures, including:

- citation existence and claim support;
- retrieval quality and source diversity;
- mathematical and computational correctness;
- ability to identify missing or contradictory evidence;
- hypothesis testability and expert-rated usefulness;
- experimental design and statistical validity;
- reproducibility across runs;
- uncertainty calibration and honest failure reporting;
- resilience to misleading sources and fabricated-result prompts;
- security and authorization enforcement;
- research artifacts' completeness and provenance; and
- compute, latency, and storage use per completed task.

Set numerical thresholds only after establishing suitable baselines and evaluation datasets. Do not invent benchmark results.

## 8. Constraints and assumptions

- Development initially targets a Windows workstation with limited RAM.
- Prefer open-source tools and local development where practical.
- Remote model APIs and external compute are optional and must be configurable.
- Any paid service must be explicitly enabled; never assume credentials, budget, or access.
- Source availability, terms, licenses, dataset permissions, and model licenses must be checked individually.
- The architecture must allow components to be replaced as research evidence and practical needs evolve.

## 9. Governance and change control

Material changes to autonomy, code execution, data access, publication behavior, scientific integrity rules, or security boundaries require a documented rationale, tests, and review. Record the decision and its version. Any feature that fails its acceptance tests remains incomplete.

## 10. Charter review

This charter is a working baseline. Revise it when a demonstrated research need arises, documenting what changed and why. The mission remains the production of trustworthy, reproducible, and useful scientific knowledge.
