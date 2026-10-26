# Planned Research Workspaces

These 12 panels are user-facing workspaces for the Artificial Scientist. The panels are interfaces into shared research services; they are not 12 independent systems and do not imply completed features.

| # | Panel | Responsibility | Key evidence/artifacts |
|---:|---|---|---|
| 1 | Scientific Command Center | Overview of research tasks, current experiments, failures, pending approvals, and verified findings | Task summaries, event history, system health |
| 2 | Research Agenda & Problem Observatory | Curate open questions, contradictions, research priorities, and proposed missions | Research-question records, priority rationale |
| 3 | Literature & Evidence Explorer | Search literature and inspect source-linked claims | Source records, passages, citation graph |
| 4 | Scientific Knowledge Graph & Vocabulary | Explore concepts, terminology, equations, and cross-disciplinary links | Concept records, relationships, vocabulary provenance |
| 5 | Hypothesis & Discovery Lab | Generate and compare testable hypotheses and alternative explanations | Hypotheses, novelty-search records, falsification plans |
| 6 | Mathematics & Formal Reasoning Workbench | Run symbolic/numerical calculations and supported verification tools | Equations, derivations, computation logs, proof status |
| 7 | Computational Laboratory & Simulation Center | Define and run approved simulations or code experiments | Experiment plans, configuration, code, run logs |
| 8 | Data Analysis & Results Observatory | Inspect datasets, statistics, visualizations, uncertainty, and baselines | Analysis reports, figures, metrics |
| 9 | Experiment Journal & Reproducibility | Review methods, versions, failed attempts, and rerun instructions | Immutable run history, environment manifests, hashes |
| 10 | Scientific Memory & Learning | Inspect retained knowledge, update history, conflicts, and rollback | Versioned memory entries, provenance, evaluations |
| 11 | Scientific Manuscript & Publication Studio | Prepare reports and manuscript packages with traceable references | Drafts, bibliography, figures, supplementary artifacts |
| 12 | Independent Review, Evaluation & Governance | Review findings, benchmark results, risks, approvals, and policy violations | Review findings, test results, audit events |

## Cross-panel workflow

A typical research mission may start in Panel 2, retrieve literature through Panel 3, build a hypothesis in Panel 5, calculate in Panel 6, execute a simulation in Panel 7, analyze results in Panel 8, record reproducibility in Panel 9, retain verified lessons in Panel 10, draft a manuscript in Panel 11, and receive review in Panel 12. Panel 1 provides a current view of the workflow.

## UI delivery rule

Do not create a panel merely to make a panel count look complete. Introduce a workspace only when it can display or control working functionality, clearly label unavailable features, and has tests for its primary workflow.
