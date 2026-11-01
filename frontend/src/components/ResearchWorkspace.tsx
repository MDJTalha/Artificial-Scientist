import { useEffect, useState, type FormEvent } from 'react'

import { apiClient, apiConfiguration } from '../lib/api'
import type { ServiceStatus } from '../lib/status'

type WorkspaceView = 'overview' | 'missions' | 'literature' | 'knowledge' | 'hypotheses' | 'lab' | 'analysis' | 'journal' | 'memory' | 'manuscript' | 'math' | 'records'
type BusyAction = 'create-task' | 'decompose' | 'literature' | 'save-sources' | 'knowledge-search' | 'knowledge-create' | 'knowledge-relation' | 'knowledge-graph' | 'generate' | 'prior-work' | 'assess' | 'statistics' | 'plot' | 'lab-run' | 'lab-history' | 'lab-verify' | 'memory-load' | 'memory-save' | 'memory-history' | 'memory-contradict' | 'memory-rollback' | 'manuscript-load' | 'manuscript-create' | 'math' | null

interface ResearchWorkspaceProps {
  apiStatus: ServiceStatus
  onRetry: () => void
}

interface RecordEnvelope {
  id: string
  record_type: string
  created_at: string
  content_sha256: string
  payload: Record<string, unknown>
}

interface RecordListResponse {
  items: RecordEnvelope[]
  total: number
  limit: number
  offset: number
}

interface KnowledgeVocabulary {
  concept_types: string[]
  scientific_domains: string[]
  concept_statuses: string[]
  relationship_predicates: string[]
  relationship_statuses: string[]
  note: string
}

interface KnowledgeConceptResponse {
  items: RecordEnvelope[]
  total: number
  limit: number
  offset: number
}

interface KnowledgeGraphResponse {
  root: RecordEnvelope
  nodes: RecordEnvelope[]
  relationships: RecordEnvelope[]
  depth: number
  truncated: boolean
  note: string
}

interface DecompositionResponse {
  research_question: string
  question_type: string
  independent_variable: string | null
  dependent_variable: string | null
  system_or_population: string | null
  context: string | null
  missing_elements: string[]
  clarification_prompts: string[]
  method: string
  limitations: string[]
}

interface HypothesisCandidate {
  title: string
  statement: string
  assumptions: string[]
  alternative_explanations: string[]
  predictions: string[]
  falsification_criteria: string[]
  discriminating_test: string
  source_record_ids: string[]
  claim_record_ids: string[]
}

interface GeneratedHypothesis {
  candidate: HypothesisCandidate
  generation_method: string
  review_status: string
}

interface HypothesisGenerationResponse {
  research_question: string
  candidates: GeneratedHypothesis[]
  limitations: string[]
}

interface LiteratureResult {
  title: string
  authors: string[]
  doi: string | null
  publication_date: string | null
  publication_year: number | null
  source_url: string
  source_kind: 'journal_article' | 'preprint' | 'dataset' | 'standard' | 'other'
  matched_providers: string[]
  is_retracted: boolean | null
  has_open_access_location: boolean | null
  cited_by_count: number | null
  saved_record_id: string | null
}

interface LiteratureResponse {
  query: string
  status: 'ok' | 'partial' | 'unavailable'
  total_results: number
  results: LiteratureResult[]
  providers: { provider: string; status: string; result_count: number; message: string | null }[]
  note: string
}

interface PriorWorkResponse {
  overall_status: 'complete' | 'partial' | 'unavailable'
  limitations: string[]
  results: {
    title: string
    search_status: string
    total_results: number
    matches: {
      title: string
      doi: string | null
      publication_year: number | null
      source_url: string
      cited_by_count: number | null
      is_retracted: boolean | null
    }[]
    interpretation: string
  }[]
}

interface AssessmentResponse {
  overall_status: string
  assessments: {
    title: string
    completeness_score: number
    rubric: Record<string, boolean>
    concerns: string[]
    near_duplicate_of: string | null
    novelty_status: string
    persisted_record_id: string | null
  }[]
  limitations: string[]
}

interface SymbolicResponse {
  operation: string
  expression: string
  result: string
  results: string[]
  free_symbols: string[]
  numeric_value: number | null
  method: string
  note: string
}

interface StatisticsResponse {
  count: number
  mean: number
  median: number
  variance: number
  standard_deviation: number
  minimum: number
  maximum: number
  quartiles: Record<string, number>
  variance_mode: 'sample' | 'population'
  method: string
  note: string
}

interface LabStepResult {
  step_id: string
  operation: string
  status: 'completed' | 'failed' | 'skipped'
  output?: Record<string, unknown> | null
  error?: string | null
  duration_ms: number
}

interface LabRunResponse {
  run_id: string
  title: string
  status: 'completed' | 'failed'
  configuration_sha256: string
  result_sha256: string
  started_at: string
  completed_at: string
  duration_ms: number
  steps: LabStepResult[]
  logs: string[]
  configuration: Record<string, unknown>
  environment_manifest: Record<string, string>
  limitations: string[]
}

interface LabRunListResponse {
  items: LabRunResponse[]
  total: number
  limit: number
  offset: number
}

interface LabArtifactMetadata {
  artifact_id: string
  run_id: string
  artifact_type: string
  content_type: string
  sha256: string
  size_bytes: number
  created_at: string
  provenance: Record<string, unknown>
}

interface LabVerificationResponse {
  run_id: string
  reproducible: boolean
  configuration_matches: boolean
  environment_matches: boolean
  outputs_match: boolean
  differences: string[]
  recorded_environment: Record<string, string>
  current_environment: Record<string, string>
}

interface MemorySummary {
  key: string
  version: number
  status: string
  created_at: string
  digest: string
  evidence_count: number
}

interface MemoryListResponse {
  items: MemorySummary[]
  total: number
  limit: number
  offset: number
}

interface MemoryVersion {
  key: string
  version: number
  value: Record<string, unknown>
  status: string
  evidence: string[]
  created_at: string
  digest: string
  supersedes: number | null
}

interface MemoryHistoryResponse {
  key: string
  items: MemoryVersion[]
  total: number
}

interface ManuscriptSummary {
  id: string
  title: string
  created_at: string
  content_sha256: string
  claim_count: number
  citation_count: number
  status: string
  submission_approved: boolean
}

interface ManuscriptListResponse {
  items: ManuscriptSummary[]
  total: number
  limit: number
  offset: number
}

interface ManuscriptClaimDraft {
  id: number
  text: string
  sourceIds: string[]
}

const navigation: { id: WorkspaceView; label: string; symbol: string; detail: string }[] = [
  { id: 'overview', label: 'Command center', symbol: '◫', detail: 'System overview and workspace maturity' },
  { id: 'missions', label: 'Research agenda', symbol: '⌖', detail: 'Create and structure research questions' },
  { id: 'literature', label: 'Literature explorer', symbol: '⌕', detail: 'Search scholarly metadata and save evidence' },
  { id: 'knowledge', label: 'Knowledge graph', symbol: '⌘', detail: 'Create concepts, controlled vocabulary and evidence-linked relationships' },
  { id: 'hypotheses', label: 'Hypothesis lab', symbol: '◇', detail: 'Compare, screen and assess candidate hypotheses' },
  { id: 'lab', label: 'Computational lab', symbol: '⌬', detail: 'Run bounded, allowlisted computational experiments' },
  { id: 'journal', label: 'Experiment journal', symbol: '▧', detail: 'Inspect run history, artifacts and reproducibility evidence' },
  { id: 'memory', label: 'Scientific memory', symbol: '◈', detail: 'Maintain evidence-linked, versioned scientific knowledge' },
  { id: 'manuscript', label: 'Manuscript studio', symbol: '✎', detail: 'Prepare and export evidence-linked manuscript drafts' },
  { id: 'analysis', label: 'Data analysis', symbol: '∿', detail: 'Descriptive statistics and mathematical plots' },
  { id: 'math', label: 'Mathematics workbench', symbol: '∑', detail: 'Bounded symbolic calculations' },
  { id: 'records', label: 'Research records', symbol: '▤', detail: 'Browse immutable, provenance-aware records' },
]

const workspaceRoadmap = [
  { name: 'Scientific Command Center', status: 'AVAILABLE', note: 'Runtime health, maturity and release posture.' },
  { name: 'Research Agenda & Problem Observatory', status: 'AVAILABLE', note: 'Create tasks and decompose questions.' },
  { name: 'Literature & Evidence Explorer', status: 'AVAILABLE', note: 'OpenAlex and Crossref metadata retrieval.' },
  { name: 'Scientific Knowledge Graph & Vocabulary', status: 'AVAILABLE', note: 'Create, search and explore tenant-scoped concepts and relationship assertions.' },

  { name: 'Hypothesis & Discovery Lab', status: 'AVAILABLE', note: 'Bounded templates, prior-work screen and assessment.' },
  { name: 'Mathematics & Formal Reasoning Workbench', status: 'AVAILABLE', note: 'Bounded symbolic calculation and review notes.' },
  { name: 'Computational Laboratory & Simulation Center', status: 'DEV UI / NOT PRODUCTION CERTIFIED', note: 'Bounded allowlisted operations only; production execution remains blocked pending reviewed OS sandbox and identity controls.' },
  { name: 'Data Analysis & Results Observatory', status: 'AVAILABLE', note: 'Descriptive statistics and bounded function plots.' },
  { name: 'Experiment Journal & Reproducibility', status: 'AVAILABLE / DEV ONLY', note: 'Browse run history, hashes and artifacts; replay and export remain disabled in production pending identity and sandbox review.' },
  { name: 'Scientific Memory & Learning', status: 'AVAILABLE / TENANT GATED', note: 'Evidence-linked versioning, contradiction tracking and rollback; protected access requires identity integration.' },
  { name: 'Scientific Manuscript & Publication Studio', status: 'AVAILABLE / DRAFT ONLY', note: 'Claim-to-source citation mapping and persistent drafts; external submission is disabled.' },
  { name: 'Independent Review, Evaluation & Governance', status: 'NEXT', note: 'Review queues, benchmark evidence and approvals.' },
]

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'The operation could not be completed.'
}

function recordTitle(record: RecordEnvelope): string {
  const payload = record.payload
  for (const key of ['title', 'preferred_label', 'claim_text', 'research_question', 'hypothesis']) {
    const value = payload[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return 'Untitled ' + record.record_type.replaceAll('_', ' ')
}

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function ResearchWorkspace({ apiStatus, onRetry }: ResearchWorkspaceProps) {
  const [activeView, setActiveView] = useState<WorkspaceView>('overview')
  const [busy, setBusy] = useState<BusyAction>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [pageError, setPageError] = useState<string | null>(null)

  const [taskTitle, setTaskTitle] = useState('')
  const [researchQuestion, setResearchQuestion] = useState('')
  const [objective, setObjective] = useState('')
  const [domainContext, setDomainContext] = useState('')
  const [createdTask, setCreatedTask] = useState<RecordEnvelope | null>(null)
  const [decomposition, setDecomposition] = useState<DecompositionResponse | null>(null)
  const [independentVariable, setIndependentVariable] = useState('')
  const [dependentVariable, setDependentVariable] = useState('')
  const [systemOrPopulation, setSystemOrPopulation] = useState('')

  const [literatureQuery, setLiteratureQuery] = useState('')
  const [literatureResponse, setLiteratureResponse] = useState<LiteratureResponse | null>(null)
  const [savedSourceUrls, setSavedSourceUrls] = useState<string[]>([])

  const [knowledgeVocabulary, setKnowledgeVocabulary] = useState<KnowledgeVocabulary | null>(null)
  const [knowledgeConcepts, setKnowledgeConcepts] = useState<RecordEnvelope[]>([])
  const [knowledgeTotal, setKnowledgeTotal] = useState(0)
  const [knowledgeSearch, setKnowledgeSearch] = useState('')
  const [knowledgeRefresh, setKnowledgeRefresh] = useState(0)
  const [conceptLabel, setConceptLabel] = useState('')
  const [conceptDefinition, setConceptDefinition] = useState('')
  const [conceptDomain, setConceptDomain] = useState('interdisciplinary')
  const [conceptType, setConceptType] = useState('entity')
  const [relationshipSourceId, setRelationshipSourceId] = useState('')
  const [relationshipTargetId, setRelationshipTargetId] = useState('')
  const [relationshipPredicate, setRelationshipPredicate] = useState('related_to')
  const [knowledgeGraph, setKnowledgeGraph] = useState<KnowledgeGraphResponse | null>(null)
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null)

  const [hypothesisResponse, setHypothesisResponse] = useState<HypothesisGenerationResponse | null>(null)
  const [priorWorkResponse, setPriorWorkResponse] = useState<PriorWorkResponse | null>(null)
  const [assessmentResponse, setAssessmentResponse] = useState<AssessmentResponse | null>(null)

  const [records, setRecords] = useState<RecordEnvelope[]>([])
  const [recordTotal, setRecordTotal] = useState(0)
  const [recordError, setRecordError] = useState<string | null>(null)
  const [recordsRefresh, setRecordsRefresh] = useState(0)

  const [sampleValues, setSampleValues] = useState('12, 14, 14, 15, 18, 21, 23')
  const [varianceMode, setVarianceMode] = useState<'sample' | 'population'>('sample')
  const [statisticsResponse, setStatisticsResponse] = useState<StatisticsResponse | null>(null)
  const [plotExpression, setPlotExpression] = useState('sin(x)')
  const [plotVariable, setPlotVariable] = useState('x')
  const [plotLower, setPlotLower] = useState('-10')
  const [plotUpper, setPlotUpper] = useState('10')
  const [plotUrl, setPlotUrl] = useState<string | null>(null)

  const [labConfigJson, setLabConfigJson] = useState(`{
  "title": "Polynomial simplification and sample statistics",
  "steps": [
    {
      "step_id": "simplify",
      "operation": "symbolic",
      "inputs": {
        "operation": "simplify",
        "expression": "x**2 + 2*x + 1",
        "symbols": ["x"]
      }
    },
    {
      "step_id": "sample_stats",
      "operation": "statistics",
      "inputs": {
        "values": [2, 4, 4, 6, 8],
        "variance_mode": "sample"
      }
    }
  ],
  "random_seed": 42,
  "step_timeout_seconds": 10
}`)
  const [labRunResponse, setLabRunResponse] = useState<LabRunResponse | null>(null)
  const [labHistory, setLabHistory] = useState<LabRunResponse[]>([])
  const [labTotal, setLabTotal] = useState(0)
  const [labError, setLabError] = useState<string | null>(null)
  const [labHistoryRefresh, setLabHistoryRefresh] = useState(0)
  const [labVerification, setLabVerification] = useState<LabVerificationResponse | null>(null)
  const [journalArtifacts, setJournalArtifacts] = useState<LabArtifactMetadata[]>([])

  const [memoryItems, setMemoryItems] = useState<MemorySummary[]>([])
  const [memoryTotal, setMemoryTotal] = useState(0)
  const [memoryHistory, setMemoryHistory] = useState<MemoryVersion[]>([])
  const [memoryRecords, setMemoryRecords] = useState<RecordEnvelope[]>([])
  const [memoryKey, setMemoryKey] = useState('research-note-001')
  const [memoryValueJson, setMemoryValueJson] = useState(`{\n  "note": "Researcher-authored note; inspect the linked evidence before reuse.",\n  "scope": "Define the system, population and conditions where this note may apply.",\n  "review_required": true\n}`)
  const [memoryEvidenceIds, setMemoryEvidenceIds] = useState<string[]>([])
  const [memoryContradictionReason, setMemoryContradictionReason] = useState('')
  const [memoryRollbackVersion, setMemoryRollbackVersion] = useState('1')
  const [memoryError, setMemoryError] = useState<string | null>(null)
  const [memoryRefresh, setMemoryRefresh] = useState(0)

  const [manuscriptItems, setManuscriptItems] = useState<ManuscriptSummary[]>([])
  const [manuscriptSources, setManuscriptSources] = useState<RecordEnvelope[]>([])
  const [manuscriptTotal, setManuscriptTotal] = useState(0)
  const [manuscriptTitle, setManuscriptTitle] = useState('')
  const [manuscriptAbstract, setManuscriptAbstract] = useState('')
  const [manuscriptClaims, setManuscriptClaims] = useState<ManuscriptClaimDraft[]>([{ id: 1, text: '', sourceIds: [] }])
  const [nextManuscriptClaimId, setNextManuscriptClaimId] = useState(2)
  const [manuscriptMethods, setManuscriptMethods] = useState('')
  const [manuscriptLimitations, setManuscriptLimitations] = useState('')
  const [manuscriptDataStatement, setManuscriptDataStatement] = useState('')
  const [manuscriptRecord, setManuscriptRecord] = useState<RecordEnvelope | null>(null)
  const [manuscriptError, setManuscriptError] = useState<string | null>(null)
  const [manuscriptRefresh, setManuscriptRefresh] = useState(0)

  const [mathOperation, setMathOperation] = useState<'simplify' | 'differentiate' | 'integrate' | 'solve' | 'evaluate'>('simplify')
  const [mathExpression, setMathExpression] = useState('x**2 + 2*x + 1')
  const [mathVariable, setMathVariable] = useState('x')
  const [mathResponse, setMathResponse] = useState<SymbolicResponse | null>(null)

  const apiConfigured = Boolean(apiConfiguration.baseUrl)
  const protectedActionsAvailable = apiConfigured && !import.meta.env.PROD
  const labExecutionAvailable = apiConfigured && !import.meta.env.PROD

  useEffect(() => {
    if (activeView !== 'records' || !protectedActionsAvailable) return

    const controller = new AbortController()
    setRecordError(null)
    apiClient
      .get<RecordListResponse>('/api/v1/records?limit=50&offset=0', { signal: controller.signal })
      .then((result) => {
        setRecords(result.items)
        setRecordTotal(result.total)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setRecordError(errorText(error))
      })

    return () => controller.abort()
  }, [activeView, recordsRefresh, protectedActionsAvailable])

  useEffect(() => {
    if (activeView !== 'manuscript' || !protectedActionsAvailable) return

    const controller = new AbortController()
    setManuscriptError(null)
    Promise.all([
      apiClient.get<ManuscriptListResponse>('/api/v1/manuscripts?limit=50&offset=0', { signal: controller.signal }),
      apiClient.get<RecordListResponse>('/api/v1/records?record_type=source&limit=100&offset=0', { signal: controller.signal }),
    ])
      .then(([manuscriptResult, sourceResult]) => {
        setManuscriptItems(manuscriptResult.items)
        setManuscriptTotal(manuscriptResult.total)
        setManuscriptSources(sourceResult.items.filter((record) => {
          const identifier = record.payload.external_identifier
          const assessment = record.payload.assessment_status
          return typeof identifier === 'string' && identifier.trim().length > 0 &&
            !['retracted', 'disputed', 'unavailable'].includes(String(assessment))
        }))
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setManuscriptError(errorText(error))
      })

    return () => controller.abort()
  }, [activeView, manuscriptRefresh, protectedActionsAvailable])

  useEffect(() => {
    if (activeView !== 'memory' || !protectedActionsAvailable) return

    const controller = new AbortController()
    setMemoryError(null)
    Promise.all([
      apiClient.get<MemoryListResponse>('/api/v1/memory?limit=50&offset=0', { signal: controller.signal }),
      apiClient.get<RecordListResponse>('/api/v1/records?limit=50&offset=0', { signal: controller.signal }),
    ])
      .then(([memoryResult, recordResult]) => {
        setMemoryItems(memoryResult.items)
        setMemoryTotal(memoryResult.total)
        setMemoryRecords(recordResult.items)
        setMemoryEvidenceIds((current) => current.length > 0
          ? current.filter((id) => recordResult.items.some((record) => record.id === id))
          : recordResult.items.slice(0, 1).map((record) => record.id))
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setMemoryError(errorText(error))
      })

    return () => controller.abort()
  }, [activeView, memoryRefresh, protectedActionsAvailable])

  useEffect(() => {
    if (!['lab', 'journal'].includes(activeView) || !labExecutionAvailable) return

    const controller = new AbortController()
    setLabError(null)
    apiClient
      .get<LabRunListResponse>('/api/v1/lab/runs?limit=20&offset=0', { signal: controller.signal })
      .then((result) => {
        setLabHistory(result.items)
        setLabTotal(result.total)
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLabError(errorText(error))
      })

    return () => controller.abort()
  }, [activeView, labHistoryRefresh, labExecutionAvailable])

  useEffect(() => {
    if (!plotUrl) return
    return () => URL.revokeObjectURL(plotUrl)
  }, [plotUrl])

  useEffect(() => {
    if (activeView !== 'knowledge' || !protectedActionsAvailable) return

    const controller = new AbortController()
    setKnowledgeError(null)
    Promise.all([
      apiClient.get<KnowledgeVocabulary>('/api/v1/knowledge/vocabulary', { signal: controller.signal }),
      apiClient.get<KnowledgeConceptResponse>('/api/v1/knowledge/concepts?limit=50&offset=0', { signal: controller.signal }),
    ])
      .then(([vocabulary, result]) => {
        setKnowledgeVocabulary(vocabulary)
        setKnowledgeConcepts(result.items)
        setKnowledgeTotal(result.total)
        setConceptDomain((current) => vocabulary.scientific_domains.includes(current) ? current : 'interdisciplinary')
        setConceptType((current) => vocabulary.concept_types.includes(current) ? current : 'entity')
        setRelationshipPredicate((current) => vocabulary.relationship_predicates.includes(current) ? current : 'related_to')
        if (result.items.length > 0) {
          setRelationshipSourceId((current) => current || result.items[0].id)
          if (result.items.length > 1) setRelationshipTargetId((current) => current || result.items[1].id)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setKnowledgeError(errorText(error))
      })

    return () => controller.abort()
  }, [activeView, knowledgeRefresh, protectedActionsAvailable])

  function beginAction(action: Exclude<BusyAction, null>) {
    setBusy(action)
    setNotice(null)
    setPageError(null)
  }

  function finishAction() {
    setBusy(null)
  }

  async function createResearchTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('create-task')
    try {
      const task = await apiClient.post<RecordEnvelope>('/api/v1/records', {
        record_type: 'research_task',
        title: taskTitle.trim(),
        research_question: researchQuestion.trim(),
        objective: objective.trim(),
        status: 'created',
        priority: 'normal',
        provenance: {
          method: 'human_provided',
          notes: 'Created by the ASDS Research Agenda workspace.',
        },
      })
      setCreatedTask(task)
      setRecordsRefresh((value) => value + 1)
      setNotice('Research task saved as an immutable research record.')
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function decomposeQuestion() {
    if (researchQuestion.trim().length < 10) {
      setPageError('Enter a research question containing at least 10 characters.')
      return
    }
    beginAction('decompose')
    try {
      const result = await apiClient.post<DecompositionResponse>('/api/v1/discovery/decompose', {
        research_question: researchQuestion.trim(),
        domain_context: domainContext.trim() || null,
      })
      setDecomposition(result)
      setIndependentVariable(result.independent_variable ?? '')
      setDependentVariable(result.dependent_variable ?? '')
      setSystemOrPopulation(result.system_or_population ?? '')
      setNotice('Question structure returned. Confirm or edit every extracted field before proceeding.')
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function searchLiterature(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('literature')
    try {
      const result = await apiClient.post<LiteratureResponse>('/api/v1/literature/search', {
        query: literatureQuery.trim(),
        limit: 8,
        providers: ['openalex', 'crossref'],
        persist_results: false,
      })
      setLiteratureResponse(result)
      setNotice(
        result.status === 'ok'
          ? 'Metadata search completed. Inspect original sources before relying on any claim.'
          : 'Metadata search returned partial or unavailable provider results.',
      )
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function persistLiteratureSources() {
    if (!literatureResponse || literatureResponse.results.length === 0) return
    beginAction('save-sources')
    let saved = 0
    let failed = 0
    const newlySavedUrls: string[] = []
    for (const result of literatureResponse.results) {
      if (savedSourceUrls.includes(result.source_url)) continue
      try {
        await apiClient.post<RecordEnvelope>('/api/v1/records', {
          record_type: 'source',
          title: result.title,
          source_url: result.source_url,
          source_kind: result.source_kind,
          authors: result.authors,
          published_date: result.publication_date,
          external_identifier: result.doi,
          assessment_status: 'unassessed',
          provenance: {
            method: 'literature_retrieval',
            notes: 'Bibliographic metadata retrieved from: ' + result.matched_providers.join(', ') +
              '. Metadata is a discovery lead, not scientific verification.',
          },
        })
        saved += 1
        newlySavedUrls.push(result.source_url)
      } catch {
        failed += 1
      }
    }
    setSavedSourceUrls((current) => [...current, ...newlySavedUrls])
    setRecordsRefresh((value) => value + 1)
    setNotice(
      saved + ' source record(s) saved; ' + failed +
        ' failed. Each saved source remains unassessed until a researcher reviews the original material.',
    )
    finishAction()
  }

  async function searchKnowledgeConcepts(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('knowledge-search')
    setKnowledgeError(null)
    try {
      const query = knowledgeSearch.trim()
      const path = '/api/v1/knowledge/concepts?limit=50&offset=0' + (query ? '&query=' + encodeURIComponent(query) : '')
      const result = await apiClient.get<KnowledgeConceptResponse>(path)
      setKnowledgeConcepts(result.items)
      setKnowledgeTotal(result.total)
      setKnowledgeGraph(null)
    } catch (error) {
      setKnowledgeError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function createKnowledgeConcept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('knowledge-create')
    setKnowledgeError(null)
    try {
      const result = await apiClient.post<RecordEnvelope>('/api/v1/knowledge/concepts', {
        record_type: 'knowledge_concept',
        preferred_label: conceptLabel.trim(),
        definition: conceptDefinition.trim(),
        aliases: [],
        concept_type: conceptType,
        scientific_domain: conceptDomain,
        language: 'en',
        status: 'proposed',
        external_identifiers: {},
        source_record_ids: [],
        assessment_notes: 'New concept captured by a researcher; definition and vocabulary mapping require domain review.',
        provenance: {
          method: 'human_provided',
          notes: 'Created in the ASDS Scientific Knowledge Graph workspace.',
        },
      })
      setKnowledgeConcepts((items) => [result, ...items.filter((item) => item.id !== result.id)])
      setKnowledgeTotal((value) => value + 1)
      setConceptLabel('')
      setConceptDefinition('')
      setNotice('Concept saved as a proposed, provenance-aware knowledge record. It is not treated as an established fact.')
      setKnowledgeRefresh((value) => value + 1)
    } catch (error) {
      setKnowledgeError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function createKnowledgeRelationship(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!relationshipSourceId || !relationshipTargetId || relationshipSourceId === relationshipTargetId) {
      setKnowledgeError('Choose two different concepts before creating a relationship.')
      return
    }
    beginAction('knowledge-relation')
    setKnowledgeError(null)
    try {
      await apiClient.post<RecordEnvelope>('/api/v1/knowledge/relationships', {
        record_type: 'knowledge_relationship',
        source_concept_id: relationshipSourceId,
        target_concept_id: relationshipTargetId,
        predicate: relationshipPredicate,
        evidence_source_record_ids: [],
        assertion_status: 'proposed',
        notes: 'Researcher-created relationship assertion; not independently verified.',
        provenance: {
          method: 'human_provided',
          notes: 'Created in the ASDS Scientific Knowledge Graph workspace.',
        },
      })
      setNotice('Relationship saved with proposed status. It is an assertion requiring evidence and review, not a verified scientific fact.')
      setKnowledgeGraph(null)
      setKnowledgeRefresh((value) => value + 1)
    } catch (error) {
      setKnowledgeError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function loadKnowledgeGraph(conceptId: string) {
    beginAction('knowledge-graph')
    setKnowledgeError(null)
    try {
      const path = '/api/v1/knowledge/graph/neighborhood?concept_id=' + encodeURIComponent(conceptId) + '&depth=2&limit=50'
      const result = await apiClient.get<KnowledgeGraphResponse>(path)
      setKnowledgeGraph(result)
    } catch (error) {
      setKnowledgeError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function generateHypotheses() {
    beginAction('generate')
    setPriorWorkResponse(null)
    setAssessmentResponse(null)
    try {
      const result = await apiClient.post<HypothesisGenerationResponse>('/api/v1/discovery/generate', {
        research_question: researchQuestion.trim(),
        independent_variable: independentVariable.trim(),
        dependent_variable: dependentVariable.trim(),
        system_or_population: systemOrPopulation.trim(),
        context: domainContext.trim() || null,
        include_null: true,
        include_inverse: true,
      })
      setHypothesisResponse(result)
      setNotice('Bounded candidate templates generated. These are not AI inference, evidence, novelty or truth claims.')
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function screenPriorWork() {
    const candidates = hypothesisResponse?.candidates.map((item) => ({
      title: item.candidate.title,
      statement: item.candidate.statement,
    })) ?? []
    if (candidates.length < 2) {
      setPageError('Generate at least two candidate hypotheses before prior-work screening.')
      return
    }
    beginAction('prior-work')
    try {
      const result = await apiClient.post<PriorWorkResponse>('/api/v1/discovery/prior-work-screen', {
        research_question: researchQuestion.trim(),
        candidates,
        providers: ['openalex', 'crossref'],
        results_per_candidate: 5,
      })
      setPriorWorkResponse(result)
      setNotice(
        'Prior-work metadata screen completed with status: ' + result.overall_status +
          '. A metadata search cannot establish novelty.',
      )
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function assessAndPersistHypotheses() {
    const candidates = hypothesisResponse?.candidates.map((item) => item.candidate) ?? []
    if (candidates.length < 2) {
      setPageError('Generate at least two candidate hypotheses before assessment.')
      return
    }
    beginAction('assess')
    try {
      const hasCompleteMetadataScreen = priorWorkResponse?.overall_status === 'complete'
      const result = await apiClient.post<AssessmentResponse>('/api/v1/discovery/assess', {
        research_question: researchQuestion.trim(),
        candidates,
        novelty_screen_status: hasCompleteMetadataScreen ? 'screened' : 'not_run',
        novelty_screen_notes: hasCompleteMetadataScreen
          ? 'A bounded OpenAlex/Crossref metadata screen was completed. This is not a full-text review or proof of novelty.'
          : null,
      })
      setAssessmentResponse(result)
      setRecordsRefresh((value) => value + 1)
      setNotice('Hypothesis assessment saved. Rubric scores measure structural completeness, not probability or scientific merit.')
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function runStatistics(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('statistics')
    try {
      const values = sampleValues.split(/[\s,;]+/).filter(Boolean).map(Number)
      if (values.length < 2 || values.length > 100000 || values.some((value) => !Number.isFinite(value))) {
        throw new Error('Enter between 2 and 100,000 finite numeric values, separated by commas or whitespace.')
      }
      const result = await apiClient.post<StatisticsResponse>('/api/v1/math/statistics', {
        values,
        variance_mode: varianceMode,
      })
      setStatisticsResponse(result)
      setNotice('Descriptive statistics calculated from the supplied values. No inference about sampling quality or causality is made.')
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function renderFunctionPlot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('plot')
    try {
      const lower = Number(plotLower)
      const upper = Number(plotUpper)
      if (!Number.isFinite(lower) || !Number.isFinite(upper) || lower >= upper) {
        throw new Error('Plot bounds must be finite numbers, with the lower bound smaller than the upper bound.')
      }
      const blob = await apiClient.postBlob('/api/v1/math/plot', {
        expression: plotExpression.trim(),
        variable: plotVariable.trim(),
        parameters: {},
        lower,
        upper,
        points: 500,
        title: 'ASDS mathematical function plot',
        x_label: plotVariable.trim(),
        y_label: 'f(' + plotVariable.trim() + ')',
      })
      setPlotUrl(URL.createObjectURL(blob))
      setNotice('PNG plot generated by the bounded mathematical plotting service.')
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function openMemoryHistory(key: string) {
    beginAction('memory-history')
    setMemoryError(null)
    try {
      const result = await apiClient.get<MemoryHistoryResponse>(`/api/v1/memory/${encodeURIComponent(key)}`)
      setMemoryKey(result.key)
      setMemoryHistory(result.items)
      setMemoryRollbackVersion(String(result.items[0]?.version ?? 1))
    } catch (error) {
      setMemoryError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function saveMemoryVersion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('memory-save')
    setMemoryError(null)
    try {
      const value: unknown = JSON.parse(memoryValueJson)
      if (typeof value !== 'object' || value === null || Array.isArray(value)) {
        throw new Error('Memory value must be a JSON object.')
      }
      if (memoryEvidenceIds.length === 0) {
        throw new Error('Select at least one existing research record as evidence.')
      }
      const result = await apiClient.post<MemoryVersion>(`/api/v1/memory/${encodeURIComponent(memoryKey.trim())}`, {
        value,
        evidence_record_ids: memoryEvidenceIds,
        status: 'active',
      })
      setMemoryHistory((current) => [...current, result])
      setMemoryRollbackVersion(String(result.version))
      setMemoryRefresh((value) => value + 1)
      setNotice('A new immutable memory version was saved with tenant-validated research evidence. The linked record is not automatically scientifically verified.')
    } catch (error) {
      setMemoryError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function contradictMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (memoryEvidenceIds.length === 0) {
      setMemoryError('Select at least one existing research record that supports the contradiction.')
      return
    }
    beginAction('memory-contradict')
    setMemoryError(null)
    try {
      const result = await apiClient.post<MemoryVersion>(`/api/v1/memory/${encodeURIComponent(memoryKey.trim())}/contradict`, {
        reason: memoryContradictionReason.trim(),
        evidence_record_ids: memoryEvidenceIds,
      })
      setMemoryHistory((current) => [...current, result])
      setMemoryContradictionReason('')
      setMemoryRefresh((value) => value + 1)
      setNotice('Contradiction recorded as a new disputed memory version. Earlier versions remain available in the history.')
    } catch (error) {
      setMemoryError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function rollbackMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('memory-rollback')
    setMemoryError(null)
    try {
      const result = await apiClient.post<MemoryVersion>(`/api/v1/memory/${encodeURIComponent(memoryKey.trim())}/rollback`, {
        version: Number(memoryRollbackVersion),
      })
      setMemoryHistory((current) => [...current, result])
      setMemoryRefresh((value) => value + 1)
      setNotice('Rollback created a new immutable version. It did not delete or rewrite the historical versions.')
    } catch (error) {
      setMemoryError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function runLab(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('lab-run')
    setLabError(null)
    setLabVerification(null)
    try {
      const payload: unknown = JSON.parse(labConfigJson)
      if (typeof payload !== 'object' || payload === null || Array.isArray(payload)) {
        throw new Error('The run configuration must be a JSON object.')
      }
      const result = await apiClient.post<LabRunResponse>('/api/v1/lab/runs', payload)
      setLabRunResponse(result)
      setLabHistoryRefresh((value) => value + 1)
      setNotice(result.status === 'completed'
        ? 'Bounded computational run completed and persisted. Review each step and the recorded environment before relying on results.'
        : 'The run completed with a failed step. Later steps were skipped; inspect the returned error and configuration.')
    } catch (error) {
      setLabError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function verifyLabRun(runId: string) {
    beginAction('lab-verify')
    setLabError(null)
    setLabVerification(null)
    try {
      const result = await apiClient.post<LabVerificationResponse>(`/api/v1/lab/runs/${encodeURIComponent(runId)}/verify`, {})
      setLabVerification(result)
      setNotice(result.reproducible
        ? 'Replay outputs and environment matched. This supports computational reproducibility, not scientific validity.'
        : 'Replay differences were detected. Compare the configuration, runtime manifest and step outputs.')
    } catch (error) {
      setLabError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function openJournalRun(runId: string) {
    beginAction('lab-history')
    setLabError(null)
    setJournalArtifacts([])
    try {
      const [run, artifacts] = await Promise.all([
        apiClient.get<LabRunResponse>(`/api/v1/lab/runs/${encodeURIComponent(runId)}`),
        apiClient.get<LabArtifactMetadata[]>(`/api/v1/lab/runs/${encodeURIComponent(runId)}/artifacts`),
      ])
      setLabRunResponse(run)
      setJournalArtifacts(artifacts)
      setLabVerification(null)
    } catch (error) {
      setLabError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function downloadLabExport(runId: string) {
    beginAction('lab-history')
    setLabError(null)
    try {
      const archive = await apiClient.getBlob(`/api/v1/lab/runs/${encodeURIComponent(runId)}/export`, 'application/zip')
      const url = URL.createObjectURL(archive)
      const link = document.createElement('a')
      link.href = url
      link.download = `asds-lab-run-${runId}.zip`
      link.rel = 'noopener'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setNotice('Integrity-manifest export requested for the selected run.')
    } catch (error) {
      setLabError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function loadLabRun(runId: string) {
    beginAction('lab-history')
    setLabError(null)
    try {
      const result = await apiClient.get<LabRunResponse>(`/api/v1/lab/runs/${encodeURIComponent(runId)}`)
      setLabRunResponse(result)
      setLabVerification(null)
    } catch (error) {
      setLabError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function runSymbolicTool(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('math')
    try {
      const requiresVariable = ['differentiate', 'integrate', 'solve'].includes(mathOperation)
      const result = await apiClient.post<SymbolicResponse>('/api/v1/math/symbolic', {
        operation: mathOperation,
        expression: mathExpression.trim(),
        symbols: [mathVariable.trim()],
        variable: requiresVariable ? mathVariable.trim() : null,
        substitutions: {},
      })
      setMathResponse(result)
      setNotice('Calculation completed. Review the assumptions and mathematical domain before scientific use.')
    } catch (error) {
      setPageError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function createManuscriptDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    beginAction('manuscript-create')
    setManuscriptError(null)
    try {
      const invalidClaim = manuscriptClaims.find((claim) => claim.text.trim().length < 5 || claim.sourceIds.length === 0)
      if (invalidClaim) throw new Error('Every claim must contain at least five characters and cite at least one source record.')
      const result = await apiClient.post<RecordEnvelope>('/api/v1/manuscripts', {
        title: manuscriptTitle.trim(),
        abstract: manuscriptAbstract.trim(),
        claims: manuscriptClaims.map((claim) => ({
          text: claim.text.trim(),
          source_record_ids: claim.sourceIds,
        })),
        methods: manuscriptMethods.trim(),
        limitations: manuscriptLimitations.trim(),
        data_statement: manuscriptDataStatement.trim(),
      })
      setManuscriptRecord(result)
      setManuscriptRefresh((value) => value + 1)
      setNotice('Manuscript draft saved. Each citation resolves to an integrity-checked tenant source record; this does not verify that the source supports its mapped claim.')
    } catch (error) {
      setManuscriptError(errorText(error))
    } finally {
      finishAction()
    }
  }

  async function openManuscript(manuscriptId: string) {
    beginAction('manuscript-load')
    setManuscriptError(null)
    try {
      const result = await apiClient.get<RecordEnvelope>(`/api/v1/manuscripts/${encodeURIComponent(manuscriptId)}`)
      setManuscriptRecord(result)
    } catch (error) {
      setManuscriptError(errorText(error))
    } finally {
      finishAction()
    }
  }

  function downloadManuscript() {
    const markdown = manuscriptRecord?.payload.rendered_markdown
    if (typeof markdown !== 'string' || !manuscriptRecord) return
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `asds-manuscript-${manuscriptRecord.id}.md`
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  function updateManuscriptClaim(id: number, patch: Partial<ManuscriptClaimDraft>) {
    setManuscriptClaims((current) => current.map((claim) => claim.id === id ? { ...claim, ...patch } : claim))
  }

  function selectView(view: WorkspaceView) {
    setActiveView(view)
    setNotice(null)
    setPageError(null)
    if (view === 'records') setRecordsRefresh((value) => value + 1)
    if (view === 'lab' || view === 'journal') setLabHistoryRefresh((value) => value + 1)
    if (view === 'memory') setMemoryRefresh((value) => value + 1)
    if (view === 'manuscript') setManuscriptRefresh((value) => value + 1)
  }

  const savedForCurrentSearch = literatureResponse?.results.filter((item) => savedSourceUrls.includes(item.source_url)).length ?? 0
  const protectedNotice = import.meta.env.PROD
    ? 'Production OIDC sign-in and tenant selection are not yet connected to this frontend. Protected research-record and discovery actions will remain unavailable until a reviewed identity session is supplied.'
    : null

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
          <div>
            <p className="brand-name">ARTIFICIAL</p>
            <p className="brand-name brand-name-secondary">SCIENTIST</p>
          </div>
        </div>
        <div className="sidebar-section-label">RESEARCH WORKSPACES</div>
        <nav aria-label="Research workspaces">
          {navigation.map((item) => (
            <button
              className={'nav-item' + (activeView === item.id ? ' nav-item-active' : '')}
              key={item.id}
              type="button"
              aria-current={activeView === item.id ? 'page' : undefined}
              title={item.detail}
              onClick={() => selectView(item.id)}
            >
              <span className="nav-symbol" aria-hidden="true">{item.symbol}</span>
              {item.label}
              {activeView === item.id && <span className="nav-indicator" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-orbit" aria-hidden="true"><span /><span /><span /></div>
          <p className="sidebar-note">Research before autonomy.</p>
          <p className="sidebar-subnote">Evidence, falsification, provenance and authorization are system invariants.</p>
          <div className="sidebar-version">RESEARCH WORKSPACE · V1</div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>ASDS</span><span className="breadcrumb-divider">/</span>
            <strong>{navigation.find((item) => item.id === activeView)?.label ?? 'Workspace'}</strong>
          </div>
          <div className="topbar-status">
            <span className={apiStatus === 'connected' ? 'status-dot status-dot-ok' : apiStatus === 'unavailable' ? 'status-dot status-dot-error' : 'status-dot'} />
            <span>{apiStatus === 'connected' ? 'HEALTH ENDPOINT OK' : apiStatus === 'unavailable' ? 'API UNAVAILABLE' : 'CHECKING API'}</span>
            <button className="topbar-retry" type="button" onClick={onRetry}>Refresh</button>
          </div>
        </header>

        {!apiConfigured && (
          <div className="workspace-alert" role="status">
            <strong>API endpoint not configured.</strong>
            <span>{apiConfiguration.error ?? 'Configure VITE_API_BASE_URL to connect this workspace.'}</span>
          </div>
        )}
        {protectedNotice && <div className="workspace-alert workspace-alert-warning" role="note">{protectedNotice}</div>}
        {notice && <div className="workspace-message" role="status" aria-live="polite">{notice}</div>}
        {pageError && <div className="workspace-alert workspace-alert-error" role="alert">{pageError}</div>}

        {activeView === 'overview' && (
          <>
            <section className="workspace-hero">
              <div className="eyebrow"><span /> ARTIFICIAL SCIENTIST · RESEARCH-FIRST SYSTEM</div>
              <h1>From research question<br /><span>to traceable scientific work.</span></h1>
              <p>
                ASDS provides a governed environment for recording questions, locating scholarly
                evidence, structuring hypotheses and running bounded mathematical tools. Each
                capability is exposed only at the level supported by its implementation and evidence.
              </p>
              <div className="workspace-hero-actions">
                <button className="primary-button" type="button" onClick={() => selectView('missions')}>Start a research mission <span aria-hidden="true">↗</span></button>
                <button className="secondary-button" type="button" onClick={() => selectView('records')}>Open research records</button>
              </div>
            </section>

            <section className="workspace-stats" aria-label="Workspace status">
              <article className="workspace-stat">
                <span className="card-label">API HEALTH</span>
                <strong>{apiStatus === 'connected' ? 'Connected' : apiStatus === 'checking' ? 'Checking' : 'Unavailable'}</strong>
                <p>Health endpoint only; not a database or production-readiness certificate.</p>
              </article>
              <article className="workspace-stat">
                <span className="card-label">WORKSPACES IMPLEMENTED</span>
                <strong>11 <small>/ 12</small></strong>
                <p>Eleven capability screens implemented. Protected research records, memory and manuscript persistence remain disabled in production until reviewed OIDC identity and tenant access are integrated.</p>
              </article>
              <article className="workspace-stat">
                <span className="card-label">AI INFERENCE</span>
                <strong>Not connected</strong>
                <p>Hypothesis suggestions use deterministic templates; no provider model is invoked.</p>
              </article>
              <article className="workspace-stat">
                <span className="card-label">RELEASE POSTURE</span>
                <strong>Evidence-gated</strong>
                <p>Identity, sandbox deployment, operations and external scientific review remain open.</p>
              </article>
            </section>

            <section className="workspace-card workspace-roadmap">
              <div className="section-heading">
                <div><p className="card-label">TWELVE RESEARCH WORKSPACES</p><h2>Capability and integration status</h2></div>
                <span className="section-index">PRODUCT MAP / 01</span>
              </div>
              <div className="workspace-roadmap-grid">
                {workspaceRoadmap.map((item, index) => (
                  <article className="workspace-roadmap-item" key={item.name}>
                    <div className="workspace-roadmap-top">
                      <span className="capability-number">{String(index + 1).padStart(2, '0')}</span>
                      <span className={item.status === 'AVAILABLE' ? 'workspace-state workspace-state-live' : 'workspace-state'}>{item.status}</span>
                    </div>
                    <h3>{item.name}</h3>
                    <p>{item.note}</p>
                  </article>
                ))}
              </div>
            </section>

            <section className="workspace-card">
              <div className="section-heading">
                <div><p className="card-label">CONTROLLED RESEARCH FLOW</p><h2>Run a first end-to-end research cycle</h2></div>
                <span className="section-index">WORKFLOW / 01</span>
              </div>
              <div className="workflow-strip">
                {[
                  ['01', 'Define', 'Create a research task and scope.'],
                  ['02', 'Retrieve', 'Search scholarly metadata and save reviewed sources.'],
                  ['03', 'Compare', 'Generate, screen and assess competing hypotheses.'],
                  ['04', 'Calculate', 'Use bounded symbolic tools and retain the result.'],
                  ['05', 'Review', 'Inspect traceability and decide the next approved step.'],
                ].map(([number, title, detail]) => (
                  <div className="workflow-step" key={number}>
                    <span>{number}</span><strong>{title}</strong><p>{detail}</p>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}

        {activeView === 'missions' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">RESEARCH AGENDA & PROBLEM OBSERVATORY</p>
              <h1>Define a research mission</h1>
              <p>Capture the question and objective as a durable record, then structure its unknowns before forming hypotheses.</p>
            </div>
            <div className="workspace-two-column">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">MISSION DEFINITION</p><h2>Research task</h2></div><span className="section-index">RECORD / 01</span></div>
                <form className="workspace-form" onSubmit={createResearchTask}>
                  <label htmlFor="task-title">Mission title</label>
                  <input id="task-title" value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} minLength={3} maxLength={200} required placeholder="e.g. Relationship between material composition and conductivity" />
                  <label htmlFor="research-question">Research question</label>
                  <textarea id="research-question" value={researchQuestion} onChange={(event) => setResearchQuestion(event.target.value)} minLength={10} maxLength={5000} required rows={4} placeholder="State one clear, researchable question. Include variables, system and context where known." />
                  <label htmlFor="research-objective">Research objective</label>
                  <textarea id="research-objective" value={objective} onChange={(event) => setObjective(event.target.value)} minLength={3} maxLength={4000} required rows={3} placeholder="What should this investigation establish, compare, measure or explain?" />
                  <label htmlFor="domain-context">Domain and boundary context</label>
                  <input id="domain-context" value={domainContext} onChange={(event) => setDomainContext(event.target.value)} maxLength={1000} placeholder="e.g. materials science; room temperature; controlled laboratory dataset" />
                  <div className="form-actions">
                    <button className="primary-button" type="submit" disabled={busy !== null || !protectedActionsAvailable}>
                      {busy === 'create-task' ? 'Saving task…' : 'Save research task'}
                    </button>
                    <button className="secondary-button" type="button" disabled={busy !== null || !protectedActionsAvailable || researchQuestion.trim().length < 10} onClick={decomposeQuestion}>
                      {busy === 'decompose' ? 'Structuring question…' : 'Structure question'}
                    </button>
                  </div>
                </form>
                {createdTask && (
                  <div className="inline-result" role="status">
                    <strong>Task record saved</strong>
                    <span>{createdTask.id}</span>
                    <small>SHA-256: {createdTask.content_sha256}</small>
                  </div>
                )}
              </section>
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">QUESTION DECOMPOSITION</p><h2>Review the structure</h2></div><span className="section-index">HEURISTIC / 01</span></div>
                {decomposition ? (
                  <div className="decomposition-result">
                    <div className="result-chip-row"><span className="result-chip">{decomposition.question_type}</span><span className="result-chip">{decomposition.method}</span></div>
                    <dl className="result-definition-list">
                      <div><dt>Independent variable</dt><dd>{decomposition.independent_variable ?? 'Not identified — enter manually'}</dd></div>
                      <div><dt>Dependent variable</dt><dd>{decomposition.dependent_variable ?? 'Not identified — enter manually'}</dd></div>
                      <div><dt>System / population</dt><dd>{decomposition.system_or_population ?? 'Not identified — enter manually'}</dd></div>
                      <div><dt>Domain context</dt><dd>{decomposition.context ?? 'Not supplied'}</dd></div>
                    </dl>
                    <h3>Missing elements</h3>
                    {decomposition.missing_elements.length > 0
                      ? <ul className="workspace-list">{decomposition.missing_elements.map((item) => <li key={item}>{item.replaceAll('_', ' ')}</li>)}</ul>
                      : <p>No missing elements were flagged by the heuristic. Human review is still required.</p>}
                    <h3>Clarification prompts</h3>
                    <ul className="workspace-list">{decomposition.clarification_prompts.map((item) => <li key={item}>{item}</li>)}</ul>
                    <div className="workspace-caveat">{decomposition.limitations.join(' ')}</div>
                  </div>
                ) : (
                  <div className="empty-state"><span>⌖</span><strong>No decomposition yet</strong><p>Structure the question to extract conservative variable hints and identify missing information.</p></div>
                )}
              </section>
            </div>
            {decomposition && (
              <section className="workspace-card variable-editor">
                <div className="section-heading"><div><p className="card-label">RESEARCHER CONFIRMATION</p><h2>Confirm the variables before hypothesis drafting</h2></div><span className="section-index">HUMAN REVIEW</span></div>
                <div className="workspace-form variable-grid">
                  <div><label htmlFor="independent-variable">Independent variable</label><input id="independent-variable" value={independentVariable} onChange={(event) => setIndependentVariable(event.target.value)} minLength={2} maxLength={300} /></div>
                  <div><label htmlFor="dependent-variable">Dependent variable</label><input id="dependent-variable" value={dependentVariable} onChange={(event) => setDependentVariable(event.target.value)} minLength={2} maxLength={300} /></div>
                  <div><label htmlFor="system-population">System / population</label><input id="system-population" value={systemOrPopulation} onChange={(event) => setSystemOrPopulation(event.target.value)} minLength={2} maxLength={500} /></div>
                  <button className="primary-button" type="button" disabled={!researchQuestion.trim() || !independentVariable.trim() || !dependentVariable.trim() || !systemOrPopulation.trim()} onClick={() => selectView('hypotheses')}>Continue to hypothesis lab</button>
                </div>
              </section>
            )}
          </section>
        )}

        {activeView === 'literature' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">LITERATURE & EVIDENCE EXPLORER</p>
              <h1>Find scholarly metadata</h1>
              <p>Search OpenAlex and Crossref, inspect provider coverage and save individual results as unassessed source records.</p>
            </div>
            <section className="workspace-card">
              <form className="workspace-search-form" onSubmit={searchLiterature}>
                <div className="workspace-search-field"><label htmlFor="literature-query">Search terms</label><input id="literature-query" value={literatureQuery} onChange={(event) => setLiteratureQuery(event.target.value)} minLength={3} maxLength={500} required placeholder="Search by concept, method, material, population or research question" /></div>
                <button className="primary-button" type="submit" disabled={busy !== null || !apiConfigured}>{busy === 'literature' ? 'Searching…' : 'Search metadata'}</button>
              </form>
              <p className="form-help">Search results are bibliographic leads. Full-text retrieval, claim extraction and scientific truth assessment are not part of this search endpoint.</p>
            </section>
            {literatureResponse && (
              <>
                <section className="workspace-card">
                  <div className="section-heading"><div><p className="card-label">RETRIEVAL STATUS</p><h2>{literatureResponse.total_results} metadata result(s)</h2></div><span className={'result-chip result-chip-' + literatureResponse.status}>{literatureResponse.status}</span></div>
                  <div className="provider-status-grid">
                    {literatureResponse.providers.map((provider) => (
                      <div className="provider-status" key={provider.provider}>
                        <strong>{provider.provider}</strong><span>{provider.status} · {provider.result_count} result(s)</span>
                        {provider.message && <small>{provider.message}</small>}
                      </div>
                    ))}
                  </div>
                  <p className="form-help">{literatureResponse.note}</p>
                </section>
                <div className="literature-result-list">
                  {literatureResponse.results.map((result, index) => (
                    <article className="workspace-card literature-result" key={result.doi ?? result.source_url}>
                      <div className="literature-result-top"><span className="result-chip">SOURCE {String(index + 1).padStart(2, '0')}</span><span className={result.is_retracted ? 'result-chip result-chip-danger' : 'result-chip'}>{result.is_retracted ? 'RETRACTION FLAG' : 'METADATA ONLY'}</span></div>
                      <h2>{result.title}</h2>
                      <p>{result.authors.slice(0, 5).join(', ') || 'Author metadata unavailable'}{result.authors.length > 5 ? ' et al.' : ''}</p>
                      <div className="literature-metadata">
                        <span>{result.publication_year ?? 'Year unknown'}</span>
                        <span>{result.doi ? 'DOI: ' + result.doi : 'No DOI supplied'}</span>
                        <span>{result.cited_by_count === null ? 'Citation count unavailable' : result.cited_by_count + ' citations reported'}</span>
                      </div>
                      <div className="literature-result-actions">
                        <a href={result.source_url} target="_blank" rel="noreferrer noopener">Open source record ↗</a>
                        <span>{result.matched_providers.join(' + ')}</span>
                      </div>
                    </article>
                  ))}
                </div>
                {literatureResponse.results.length > 0 && (
                  <section className="workspace-card source-save-panel">
                    <div><p className="card-label">PROVENANCE CAPTURE</p><h2>Save retrieved sources to the record store</h2><p>Saving creates tenant-authorized source records with bibliographic provenance. It does not copy or license the full text.</p></div>
                    <button className="primary-button" type="button" onClick={persistLiteratureSources} disabled={busy !== null || !protectedActionsAvailable || savedForCurrentSearch >= literatureResponse.results.length}>{busy === 'save-sources' ? 'Saving sources…' : 'Save source records (' + savedForCurrentSearch + '/' + literatureResponse.results.length + ')'}</button>
                  </section>
                )}
              </>
            )}
          </section>
        )}

        {activeView === 'knowledge' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">SCIENTIFIC KNOWLEDGE GRAPH & VOCABULARY</p>
              <h1>Build a traceable concept graph</h1>
              <p>Create versioned concepts, search controlled scientific vocabulary, assert typed relationships and inspect bounded graph neighborhoods. Proposed links are not scientific facts.</p>
            </div>
            {knowledgeError && <div className="workspace-alert workspace-alert-error" role="alert">{knowledgeError}</div>}
            <div className="workspace-two-column">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">CONCEPT REGISTRY</p><h2>Create a concept</h2></div><span className="section-index">PROPOSED / NEW</span></div>
                <form className="workspace-form" onSubmit={createKnowledgeConcept}>
                  <label htmlFor="concept-label">Preferred label</label>
                  <input id="concept-label" value={conceptLabel} onChange={(event) => setConceptLabel(event.target.value)} minLength={2} maxLength={250} required placeholder="e.g. Thermal conductivity" />
                  <label htmlFor="concept-definition">Definition</label>
                  <textarea id="concept-definition" value={conceptDefinition} onChange={(event) => setConceptDefinition(event.target.value)} minLength={10} maxLength={4000} required rows={4} placeholder="Provide a precise definition and note the intended scientific context." />
                  <div className="variable-grid">
                    <div><label htmlFor="concept-domain">Scientific domain</label><select id="concept-domain" value={conceptDomain} onChange={(event) => setConceptDomain(event.target.value)}>{(knowledgeVocabulary?.scientific_domains ?? ['interdisciplinary']).map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select></div>
                    <div><label htmlFor="concept-type">Concept type</label><select id="concept-type" value={conceptType} onChange={(event) => setConceptType(event.target.value)}>{(knowledgeVocabulary?.concept_types ?? ['entity']).map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select></div>
                  </div>
                  <button className="primary-button" type="submit" disabled={busy !== null || !protectedActionsAvailable || !knowledgeVocabulary}>{busy === 'knowledge-create' ? 'Saving concept…' : 'Save proposed concept'}</button>
                </form>
              </section>
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">CONTROLLED VOCABULARY</p><h2>Supported terms and domains</h2></div><span className="section-index">API / VOCABULARY</span></div>
                {knowledgeVocabulary ? (
                  <>
                    <div className="vocabulary-summary"><div><strong>{knowledgeVocabulary.scientific_domains.length}</strong><span>scientific domains</span></div><div><strong>{knowledgeVocabulary.concept_types.length}</strong><span>concept types</span></div><div><strong>{knowledgeVocabulary.relationship_predicates.length}</strong><span>relationship predicates</span></div></div>
                    <h3>Scientific domains</h3>
                    <div className="vocabulary-tags">{knowledgeVocabulary.scientific_domains.map((item) => <span key={item}>{item.replaceAll('_', ' ')}</span>)}</div>
                    <p className="form-help">{knowledgeVocabulary.note}</p>
                  </>
                ) : <div className="empty-state"><strong>{protectedActionsAvailable ? 'Loading vocabulary' : 'Sign-in required'}</strong><p>{protectedActionsAvailable ? 'The controlled vocabulary is read from the backend, not hard-coded as a complete ontology.' : 'Concept search and graph operations require authenticated tenant access. Production identity is not yet connected to this frontend.'}</p></div>}
              </section>
            </div>
            <section className="workspace-card knowledge-registry">
              <div className="section-heading"><div><p className="card-label">TENANT-SCOPED CONCEPT SEARCH</p><h2>{knowledgeTotal} concept record(s)</h2></div><span className="section-index">IMMUTABLE RECORDS</span></div>
              <form className="workspace-search-form" onSubmit={searchKnowledgeConcepts}>
                <div className="workspace-search-field"><label htmlFor="knowledge-search">Search concepts, aliases or definitions</label><input id="knowledge-search" value={knowledgeSearch} onChange={(event) => setKnowledgeSearch(event.target.value)} minLength={2} maxLength={200} placeholder="Search the concept registry" /></div>
                <button className="primary-button" type="submit" disabled={busy !== null || !protectedActionsAvailable}>{busy === 'knowledge-search' ? 'Searching…' : 'Search concepts'}</button>
              </form>
              {!protectedActionsAvailable && <div className="workspace-alert workspace-alert-warning" role="note">Authenticated tenant access is required to browse and modify concept records. Production OIDC integration is pending.</div>}
              {knowledgeConcepts.length === 0 ? (
                <div className="empty-state"><span>⌘</span><strong>No concept records found</strong><p>Create a proposed concept or search a broader term. Concepts are not automatically merged by similar names.</p></div>
              ) : (
                <div className="knowledge-concept-grid">
                  {knowledgeConcepts.map((concept) => (
                    <article className="knowledge-concept" key={concept.id}>
                      <div className="literature-result-top"><span className="result-chip">{String(concept.payload.status ?? 'proposed')}</span><span className="result-chip">{String(concept.payload.scientific_domain ?? 'unknown').replaceAll('_', ' ')}</span></div>
                      <h3>{String(concept.payload.preferred_label ?? 'Untitled concept')}</h3>
                      <p>{String(concept.payload.definition ?? '')}</p>
                      <small>{String(concept.payload.concept_type ?? 'other').replaceAll('_', ' ')} · {concept.id}</small>
                      <button className="secondary-button" type="button" onClick={() => void loadKnowledgeGraph(concept.id)} disabled={busy !== null || !protectedActionsAvailable}>Explore neighborhood</button>
                    </article>
                  ))}
                </div>
              )}
            </section>
            <div className="workspace-two-column knowledge-bottom-grid">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">RELATIONSHIP ASSERTIONS</p><h2>Connect two concepts</h2></div><span className="section-index">PROPOSED EDGE</span></div>
                <form className="workspace-form" onSubmit={createKnowledgeRelationship}>
                  <label htmlFor="relationship-source">Source concept</label>
                  <select id="relationship-source" value={relationshipSourceId} onChange={(event) => setRelationshipSourceId(event.target.value)} required>
                    <option value="">Select a concept</option>
                    {knowledgeConcepts.map((concept) => <option key={concept.id} value={concept.id}>{String(concept.payload.preferred_label ?? concept.id)}</option>)}
                  </select>
                  <label htmlFor="relationship-predicate">Relationship predicate</label>
                  <select id="relationship-predicate" value={relationshipPredicate} onChange={(event) => setRelationshipPredicate(event.target.value)}>{(knowledgeVocabulary?.relationship_predicates ?? ['related_to']).map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select>
                  <label htmlFor="relationship-target">Target concept</label>
                  <select id="relationship-target" value={relationshipTargetId} onChange={(event) => setRelationshipTargetId(event.target.value)} required>
                    <option value="">Select a concept</option>
                    {knowledgeConcepts.map((concept) => <option key={concept.id} value={concept.id}>{String(concept.payload.preferred_label ?? concept.id)}</option>)}
                  </select>
                  <p className="form-help">New relationships are saved as proposed assertions without an evidence source. They must be reviewed before use as knowledge.</p>
                  <button className="primary-button" type="submit" disabled={busy !== null || !protectedActionsAvailable || knowledgeConcepts.length < 2 || relationshipSourceId === relationshipTargetId}>{busy === 'knowledge-relation' ? 'Saving relationship…' : 'Save proposed relationship'}</button>
                </form>
              </section>
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">GRAPH NEIGHBORHOOD</p><h2>Explore connected concepts</h2></div><span className="section-index">DEPTH 2 / BOUNDED</span></div>
                {knowledgeGraph ? (
                  <>
                    <div className="graph-root"><span>ROOT CONCEPT</span><strong>{String(knowledgeGraph.root.payload.preferred_label ?? 'Concept')}</strong><small>{knowledgeGraph.nodes.length} node(s) · {knowledgeGraph.relationships.length} edge(s){knowledgeGraph.truncated ? ' · truncated' : ''}</small></div>
                    <div className="graph-edge-list">
                      {knowledgeGraph.relationships.map((edge) => (
                        <div className="graph-edge" key={edge.id}>
                          <strong>{String(edge.payload.predicate ?? 'related_to').replaceAll('_', ' ')}</strong>
                          <span>{String(edge.payload.assertion_status ?? 'proposed')}</span>
                          <small>{String(edge.payload.notes ?? 'No relationship notes supplied.')}</small>
                        </div>
                      ))}
                    </div>
                    <div className="vocabulary-tags">{knowledgeGraph.nodes.filter((node) => node.id !== knowledgeGraph.root.id).map((node) => <button type="button" key={node.id} onClick={() => void loadKnowledgeGraph(node.id)}>{String(node.payload.preferred_label ?? node.id)}</button>)}</div>
                    <p className="form-help">{knowledgeGraph.note}</p>
                  </>
                ) : <div className="empty-state"><span>⌘</span><strong>No graph neighborhood selected</strong><p>Select Explore neighborhood on a concept card to inspect its bounded relationships.</p></div>}
              </section>
            </div>
          </section>
        )}

        {activeView === 'hypotheses' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">HYPOTHESIS & DISCOVERY LAB</p>
              <h1>Develop competing explanations</h1>
              <p>Use researcher-confirmed variables to create bounded candidate templates, screen prior-work metadata and save structured assessments.</p>
            </div>
            <section className="workspace-card">
              <div className="section-heading"><div><p className="card-label">INPUT REVIEW</p><h2>Question and variable definitions</h2></div><span className="section-index">HUMAN-LED</span></div>
              <div className="workspace-form variable-grid">
                <div className="variable-grid-question"><label htmlFor="hypothesis-question">Research question</label><textarea id="hypothesis-question" rows={3} value={researchQuestion} onChange={(event) => setResearchQuestion(event.target.value)} minLength={10} maxLength={5000} /></div>
                <div><label htmlFor="hyp-iv">Independent variable</label><input id="hyp-iv" value={independentVariable} onChange={(event) => setIndependentVariable(event.target.value)} minLength={2} maxLength={300} /></div>
                <div><label htmlFor="hyp-dv">Dependent variable</label><input id="hyp-dv" value={dependentVariable} onChange={(event) => setDependentVariable(event.target.value)} minLength={2} maxLength={300} /></div>
                <div><label htmlFor="hyp-system">System / population</label><input id="hyp-system" value={systemOrPopulation} onChange={(event) => setSystemOrPopulation(event.target.value)} minLength={2} maxLength={500} /></div>
                <div><label htmlFor="hyp-context">Domain context</label><input id="hyp-context" value={domainContext} onChange={(event) => setDomainContext(event.target.value)} maxLength={1000} /></div>
              </div>
              <div className="form-actions">
                <button className="primary-button" type="button" disabled={busy !== null || !protectedActionsAvailable || researchQuestion.trim().length < 10 || independentVariable.trim().length < 2 || dependentVariable.trim().length < 2 || systemOrPopulation.trim().length < 2} onClick={() => void generateHypotheses()}>{busy === 'generate' ? 'Generating…' : 'Generate candidate templates'}</button>
                <button className="secondary-button" type="button" onClick={() => selectView('missions')}>Edit research mission</button>
              </div>
            </section>
            {hypothesisResponse && (
              <>
                <div className="workspace-alert workspace-alert-warning"><strong>Interpretation boundary:</strong> The API uses deterministic directional templates. It does not invoke an LLM, infer evidence, establish truth, predict probabilities or guarantee novelty. Every candidate requires human review.</div>
                <div className="hypothesis-grid">
                  {hypothesisResponse.candidates.map((item) => (
                    <article className="workspace-card hypothesis-card" key={item.candidate.title}>
                      <div className="literature-result-top"><span className="result-chip">{item.generation_method.replaceAll('_', ' ')}</span><span className="result-chip">{item.review_status.replaceAll('_', ' ')}</span></div>
                      <h2>{item.candidate.title}</h2>
                      <p className="hypothesis-statement">{item.candidate.statement}</p>
                      <h3>Assumptions</h3><ul className="workspace-list">{item.candidate.assumptions.map((text) => <li key={text}>{text}</li>)}</ul>
                      <h3>Alternative explanations</h3><ul className="workspace-list">{item.candidate.alternative_explanations.map((text) => <li key={text}>{text}</li>)}</ul>
                      <h3>Predictions</h3><ul className="workspace-list">{item.candidate.predictions.map((text) => <li key={text}>{text}</li>)}</ul>
                      <h3>Falsification criteria</h3><ul className="workspace-list">{item.candidate.falsification_criteria.map((text) => <li key={text}>{text}</li>)}</ul>
                      <h3>Discriminating test</h3><p>{item.candidate.discriminating_test}</p>
                    </article>
                  ))}
                </div>
                <div className="form-actions">
                  <button className="secondary-button" type="button" onClick={screenPriorWork} disabled={busy !== null || !protectedActionsAvailable}>{busy === 'prior-work' ? 'Screening metadata…' : 'Screen prior work'}</button>
                  <button className="primary-button" type="button" onClick={assessAndPersistHypotheses} disabled={busy !== null || !protectedActionsAvailable}>{busy === 'assess' ? 'Assessing and saving…' : 'Assess and save candidates'}</button>
                </div>
                {priorWorkResponse && (
                  <section className="workspace-card">
                    <div className="section-heading"><div><p className="card-label">PRIOR-WORK METADATA SCREEN</p><h2>Search status: {priorWorkResponse.overall_status}</h2></div><span className="section-index">NOT A NOVELTY PROOF</span></div>
                    {priorWorkResponse.results.map((result) => (
                      <div className="prior-work-result" key={result.title}>
                        <h3>{result.title}</h3><p>{result.interpretation}</p>
                        <span className="result-chip">{result.search_status} · {result.total_results} match(es)</span>
                        {result.matches.map((match) => <div className="prior-work-match" key={match.doi ?? match.source_url}><a href={match.source_url} target="_blank" rel="noreferrer noopener">{match.title} ↗</a><small>{match.publication_year ?? 'Year unknown'}{match.doi ? ' · DOI ' + match.doi : ''}{match.is_retracted ? ' · RETRACTION FLAG' : ''}</small></div>)}
                      </div>
                    ))}
                    <div className="workspace-caveat">{priorWorkResponse.limitations.join(' ')}</div>
                  </section>
                )}
                {assessmentResponse && (
                  <section className="workspace-card">
                    <div className="section-heading"><div><p className="card-label">STRUCTURAL ASSESSMENT</p><h2>{assessmentResponse.overall_status.replaceAll('_', ' ')}</h2></div><span className="section-index">PERSISTED</span></div>
                    <div className="assessment-grid">
                      {assessmentResponse.assessments.map((item) => (
                        <article className="assessment-item" key={item.title}>
                          <h3>{item.title}</h3><strong>{item.completeness_score}%</strong>
                          <p>Completeness rubric score — not truth, probability or scientific merit.</p>
                          <small>{item.persisted_record_id ? 'Record: ' + item.persisted_record_id : 'Record identifier unavailable'}</small>
                          {item.concerns.length > 0 && <ul className="workspace-list">{item.concerns.map((concern) => <li key={concern}>{concern}</li>)}</ul>}
                        </article>
                      ))}
                    </div>
                    <div className="workspace-caveat">{assessmentResponse.limitations.join(' ')}</div>
                  </section>
                )}
              </>
            )}
          </section>
        )}

        {activeView === 'lab' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">COMPUTATIONAL LABORATORY & SIMULATION CENTER</p>
              <h1>Run a controlled computational experiment</h1>
              <p>Submit a declarative sequence of allowlisted mathematical operations. The laboratory accepts structured inputs only; it does not execute arbitrary code, notebooks, shell commands or generated scripts.</p>
            </div>
            {!labExecutionAvailable && <div className="workspace-alert workspace-alert-warning" role="note"><strong>Execution is disabled in this environment.</strong><span>A configured API and development-mode backend are required for this workspace. Production execution remains blocked until a reviewed OS-level sandbox, adversarial isolation evidence and authenticated tenant session are deployed.</span></div>}
            {labError && <div className="workspace-alert workspace-alert-error" role="alert">{labError}</div>}
            <div className="workspace-alert workspace-alert-warning"><strong>Execution boundary</strong><span>Supported operations: symbolic math, numerical integration, bracketed root finding, descriptive statistics and unit conversion. POSIX resource limits are not full filesystem, network, syscall or kernel isolation. Use trusted development infrastructure only.</span></div>
            <div className="workspace-two-column">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">DECLARATIVE RUN CONFIGURATION</p><h2>Experiment definition</h2></div><span className="section-index">JSON / 64 KiB MAX</span></div>
                <form className="workspace-form" onSubmit={runLab}>
                  <label htmlFor="lab-config">Run configuration JSON</label>
                  <textarea id="lab-config" className="lab-json-editor" value={labConfigJson} onChange={(event) => setLabConfigJson(event.target.value)} rows={22} maxLength={65536} spellCheck={false} required aria-describedby="lab-config-help" />
                  <p id="lab-config-help" className="form-help">The backend validates every field and operation. Each run may contain 1–20 steps; each operation has a per-step timeout of up to 30 seconds.</p>
                  <button className="primary-button" type="submit" disabled={busy !== null || !labExecutionAvailable || labConfigJson.length === 0}>{busy === 'lab-run' ? 'Running controlled experiment…' : 'Run controlled experiment'}</button>
                </form>
              </section>
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">EXECUTION RESULT</p><h2>Run outcome</h2></div><span className="section-index">PERSISTED / TRACEABLE</span></div>
                {labRunResponse ? (
                  <div className="lab-result">
                    <div className="literature-result-top"><span className="result-chip">{labRunResponse.status.toUpperCase()}</span><span className="result-chip">{labRunResponse.steps.length} step(s)</span></div>
                    <h3>{labRunResponse.title}</h3>
                    <p className="lab-run-id">Run ID: {labRunResponse.run_id}</p>
                    <div className="lab-hash-grid"><div><span>Configuration SHA-256</span><code>{labRunResponse.configuration_sha256}</code></div><div><span>Result SHA-256</span><code>{labRunResponse.result_sha256}</code></div></div>
                    <div className="lab-step-list">
                      {labRunResponse.steps.map((step) => (
                        <article className="lab-step" key={step.step_id}>
                          <div><strong>{step.step_id}</strong><span className={'result-chip ' + (step.status === 'completed' ? '' : 'result-chip-warning')}>{step.status}</span></div>
                          <small>{step.operation} · {Number(step.duration_ms.toFixed(2))} ms</small>
                          {step.output && <pre>{JSON.stringify(step.output, null, 2)}</pre>}
                          {step.error && <p className="lab-step-error">{step.error}</p>}
                        </article>
                      ))}
                    </div>
                    <div className="form-actions"><button className="secondary-button" type="button" onClick={() => void verifyLabRun(labRunResponse.run_id)} disabled={busy !== null || !labExecutionAvailable}>{busy === 'lab-verify' ? 'Replaying…' : 'Replay & compare'}</button></div>
                    <p className="form-help">{labRunResponse.limitations.join(' ')}</p>
                  </div>
                ) : <div className="empty-state"><span>⌬</span><strong>No execution result yet</strong><p>Submit the bounded example or a reviewed declarative configuration to create a persisted run.</p></div>}
              </section>
            </div>
            {labVerification && (
              <section className="workspace-card lab-verification">
                <div className="section-heading"><div><p className="card-label">REPRODUCIBILITY CHECK</p><h2>{labVerification.reproducible ? 'Replay matched' : 'Replay differences detected'}</h2></div><span className="section-index">COMPARE / VERIFY</span></div>
                <div className="vocabulary-tags"><span>Configuration: {labVerification.configuration_matches ? 'MATCH' : 'DIFFERENT'}</span><span>Environment: {labVerification.environment_matches ? 'MATCH' : 'DIFFERENT'}</span><span>Step outputs: {labVerification.outputs_match ? 'MATCH' : 'DIFFERENT'}</span></div>
                {labVerification.differences.length > 0 && <ul className="workspace-list">{labVerification.differences.map((item) => <li key={item}>{item.replaceAll('_', ' ')}</li>)}</ul>}
                <p className="workspace-caveat">A matching replay supports reproducibility under the recorded software/runtime assumptions. It does not prove model correctness, source validity or a scientific conclusion.</p>
              </section>
            )}
            <section className="workspace-card lab-history">
              <div className="section-heading"><div><p className="card-label">EXPERIMENT HISTORY</p><h2>{labTotal} recorded run(s)</h2></div><button className="secondary-button" type="button" onClick={() => setLabHistoryRefresh((value) => value + 1)} disabled={!labExecutionAvailable || busy !== null}>Refresh history</button></div>
              {labExecutionAvailable && labHistory.length === 0 ? <div className="empty-state"><strong>No prior runs returned</strong><p>Completed and failed runs are retained by the backend store and appear here when available.</p></div> : null}
              {labHistory.length > 0 && <div className="lab-history-list">{labHistory.map((run) => <article className="lab-history-item" key={run.run_id}><div><strong>{run.title}</strong><span className="lab-run-id">{run.run_id}</span></div><span className={'result-chip ' + (run.status === 'completed' ? '' : 'result-chip-warning')}>{run.status}</span><div className="lab-history-actions"><button className="secondary-button" type="button" onClick={() => void loadLabRun(run.run_id)} disabled={busy !== null}>Open run</button><button className="secondary-button" type="button" onClick={() => void verifyLabRun(run.run_id)} disabled={busy !== null || !labExecutionAvailable}>Replay</button></div></article>)}</div>}
            </section>
          </section>
        )}

        {activeView === 'journal' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">EXPERIMENT JOURNAL & REPRODUCIBILITY</p>
              <h1>Inspect the computational evidence trail</h1>
              <p>Review stored run configurations, immutable identifiers, execution environments, step outputs and generated artifacts. Replaying a run checks computational consistency; it does not prove a scientific claim.</p>
            </div>
            {!labExecutionAvailable && <div className="workspace-alert workspace-alert-warning" role="note"><strong>Authenticated run history is unavailable here.</strong><span>Journal data is tenant-scoped. A reviewed OIDC session and tenant selector, together with an approved lab execution boundary, are required before this workspace can query or replay runs.</span></div>}
            {labError && <div className="workspace-alert workspace-alert-error" role="alert">{labError}</div>}
            <section className="workspace-card">
              <div className="section-heading"><div><p className="card-label">PERSISTED EXECUTION HISTORY</p><h2>{labTotal} run record(s)</h2></div><button className="secondary-button" type="button" onClick={() => setLabHistoryRefresh((value) => value + 1)} disabled={!labExecutionAvailable || busy !== null}>Refresh journal</button></div>
              {labExecutionAvailable && labHistory.length === 0 ? <div className="empty-state"><span>▧</span><strong>No execution history returned</strong><p>Run a controlled experiment in the Computational Lab. Persisted runs will appear here with their identifiers and hashes.</p><button className="secondary-button" type="button" onClick={() => selectView('lab')}>Open computational lab</button></div> : null}
              {labHistory.length > 0 && <div className="lab-history-list">{labHistory.map((run) => <article className="lab-history-item" key={run.run_id}><div><strong>{run.title}</strong><span className="lab-run-id">{run.run_id}</span><small>{formatDate(run.completed_at)} · {run.steps.length} step(s)</small></div><span className={'result-chip ' + (run.status === 'completed' ? '' : 'result-chip-warning')}>{run.status}</span><div className="lab-history-actions"><button className="secondary-button" type="button" onClick={() => void openJournalRun(run.run_id)} disabled={busy !== null}>Inspect evidence</button><button className="secondary-button" type="button" onClick={() => void verifyLabRun(run.run_id)} disabled={busy !== null || !labExecutionAvailable}>Replay & compare</button><button className="secondary-button" type="button" onClick={() => void downloadLabExport(run.run_id)} disabled={busy !== null || !labExecutionAvailable}>Export ZIP</button></div></article>)}</div>}
            </section>
            {labRunResponse && (
              <div className="workspace-two-column journal-detail-grid">
                <section className="workspace-card">
                  <div className="section-heading"><div><p className="card-label">RUN MANIFEST</p><h2>{labRunResponse.title}</h2></div><span className="result-chip">{labRunResponse.status}</span></div>
                  <p className="lab-run-id">{labRunResponse.run_id}</p>
                  <div className="lab-hash-grid"><div><span>Configuration SHA-256</span><code>{labRunResponse.configuration_sha256}</code></div><div><span>Result SHA-256</span><code>{labRunResponse.result_sha256}</code></div></div>
                  <h3 className="journal-subheading">Runtime environment manifest</h3>
                  <div className="manifest-list">{Object.entries(labRunResponse.environment_manifest).map(([key, value]) => <div key={key}><span>{key}</span><code>{value}</code></div>)}</div>
                  <div className="form-actions"><button className="secondary-button" type="button" onClick={() => void downloadLabExport(labRunResponse.run_id)} disabled={busy !== null || !labExecutionAvailable}>Download integrity-manifest ZIP</button><button className="secondary-button" type="button" onClick={() => void verifyLabRun(labRunResponse.run_id)} disabled={busy !== null || !labExecutionAvailable}>Replay this run</button></div>
                </section>
                <section className="workspace-card">
                  <div className="section-heading"><div><p className="card-label">IMMUTABLE RUN ARTIFACTS</p><h2>{journalArtifacts.length} artifact(s)</h2></div><span className="section-index">CHECKSUMS</span></div>
                  {journalArtifacts.length > 0 ? <div className="artifact-list">{journalArtifacts.map((artifact) => <article className="artifact-item" key={artifact.artifact_id}><strong>{artifact.artifact_type.replaceAll('_', ' ')}</strong><span>{artifact.content_type} · {artifact.size_bytes.toLocaleString()} bytes</span><code>{artifact.sha256}</code><small>{artifact.artifact_id}</small></article>)}</div> : <div className="empty-state"><strong>No JSON artifacts reported</strong><p>Artifact metadata will be shown when the backend has stored a run result artifact.</p></div>}
                </section>
              </div>
            )}
            {labVerification && <section className="workspace-card lab-verification"><div className="section-heading"><div><p className="card-label">REPRODUCIBILITY RESULT</p><h2>{labVerification.reproducible ? 'Replay matched' : 'Replay differences detected'}</h2></div><span className="section-index">RUN REPLAY</span></div><div className="vocabulary-tags"><span>Configuration: {labVerification.configuration_matches ? 'MATCH' : 'DIFFERENT'}</span><span>Environment: {labVerification.environment_matches ? 'MATCH' : 'DIFFERENT'}</span><span>Outputs: {labVerification.outputs_match ? 'MATCH' : 'DIFFERENT'}</span></div><p className="workspace-caveat">A matching replay supports computational reproducibility under the recorded runtime. It does not certify scientific truth or source validity.</p></section>}
          </section>
        )}

        {activeView === 'manuscript' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">SCIENTIFIC MANUSCRIPT & PUBLICATION STUDIO</p>
              <h1>Prepare an evidence-linked research draft</h1>
              <p>Write and structure each claim, map it to specific source records, document methods and limitations, then persist and export a traceable Markdown draft.</p>
            </div>
            {!protectedActionsAvailable && <div className="workspace-alert workspace-alert-warning" role="note"><strong>Manuscript persistence is protected in this production build.</strong><span>Authenticated tenant access and OIDC sign-in are required. Draft storage and source lookup remain disabled until a reviewed identity session is connected.</span></div>}
            {manuscriptError && <div className="workspace-alert workspace-alert-error" role="alert">{manuscriptError}</div>}
            <section className="workspace-card">
              <div className="section-heading"><div><p className="card-label">PERSISTED DRAFTS</p><h2>{manuscriptTotal} manuscript draft(s)</h2></div><button className="secondary-button" type="button" onClick={() => setManuscriptRefresh((value) => value + 1)} disabled={!protectedActionsAvailable || busy !== null}>Refresh drafts</button></div>
              {protectedActionsAvailable && manuscriptItems.length === 0 ? <div className="empty-state"><span>✎</span><strong>No manuscript drafts</strong><p>Create a draft below. Each claim must cite one or more source records that exist in this tenant.</p></div> : null}
              {manuscriptItems.length > 0 && <div className="manuscript-draft-list">{manuscriptItems.map((item) => <button className="manuscript-draft-item" type="button" key={item.id} onClick={() => void openManuscript(item.id)} disabled={busy !== null}><span><strong>{item.title}</strong><small>{formatDate(item.created_at)} · {item.claim_count} claim(s) · {item.citation_count} source(s) · {item.content_sha256.slice(0, 12)}…</small></span><span className="result-chip">{item.status}</span></button>)}</div>}
            </section>
            <div className="workspace-two-column manuscript-edit-grid">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">MANUSCRIPT STRUCTURE</p><h2>Research draft inputs</h2></div><span className="section-index">RESEARCHER AUTHORED</span></div>
                <form className="workspace-form" onSubmit={createManuscriptDraft}>
                  <label htmlFor="manuscript-title">Manuscript title</label>
                  <input id="manuscript-title" value={manuscriptTitle} onChange={(event) => setManuscriptTitle(event.target.value)} minLength={3} maxLength={300} required placeholder="Enter a precise working title" />
                  <label htmlFor="manuscript-abstract">Abstract (optional)</label>
                  <textarea id="manuscript-abstract" value={manuscriptAbstract} onChange={(event) => setManuscriptAbstract(event.target.value)} rows={3} maxLength={5000} placeholder="Provide a draft abstract; the system does not invent scientific results." />
                  <div className="section-heading manuscript-claims-heading"><div><p className="card-label">CLAIMS & SOURCE MAPPING</p><h2>Map evidence to each claim</h2></div><button className="secondary-button" type="button" onClick={() => { setManuscriptClaims((current) => [...current, { id: nextManuscriptClaimId, text: '', sourceIds: [] }]); setNextManuscriptClaimId((value) => value + 1) }} disabled={manuscriptClaims.length >= 100}>Add claim</button></div>
                  {manuscriptClaims.map((claim, index) => (
                    <fieldset className="manuscript-claim-fieldset" key={claim.id}>
                      <legend>Claim {index + 1}</legend>
                      <label htmlFor={`manuscript-claim-${claim.id}`}>Claim statement</label>
                      <textarea id={`manuscript-claim-${claim.id}`} value={claim.text} onChange={(event) => updateManuscriptClaim(claim.id, { text: event.target.value })} rows={3} minLength={5} maxLength={5000} required />
                      <label htmlFor={`manuscript-sources-${claim.id}`}>Supporting source records</label>
                      <select id={`manuscript-sources-${claim.id}`} className="memory-evidence-select" multiple size={Math.min(7, Math.max(3, manuscriptSources.length))} value={claim.sourceIds} onChange={(event) => updateManuscriptClaim(claim.id, { sourceIds: Array.from(event.currentTarget.selectedOptions).map((option) => option.value) })}>
                        {manuscriptSources.map((source) => <option key={source.id} value={source.id}>{recordTitle(source)} · {String(source.payload.external_identifier)}</option>)}
                      </select>
                      <small>{claim.sourceIds.length} source record(s) selected. The backend validates tenant ownership, record integrity and identifier presence.</small>
                      {manuscriptClaims.length > 1 && <button className="text-button" type="button" onClick={() => setManuscriptClaims((current) => current.filter((item) => item.id !== claim.id))}>Remove claim</button>}
                    </fieldset>
                  ))}
                  <label htmlFor="manuscript-methods">Methods</label>
                  <textarea id="manuscript-methods" value={manuscriptMethods} onChange={(event) => setManuscriptMethods(event.target.value)} rows={4} minLength={10} maxLength={12000} required placeholder="Describe actual methods, materials, measurement conditions and analysis decisions." />
                  <label htmlFor="manuscript-limitations">Limitations</label>
                  <textarea id="manuscript-limitations" value={manuscriptLimitations} onChange={(event) => setManuscriptLimitations(event.target.value)} rows={4} minLength={10} maxLength={12000} required placeholder="State uncertainties, weaknesses, assumptions and scope boundaries." />
                  <label htmlFor="manuscript-data">Data availability statement</label>
                  <textarea id="manuscript-data" value={manuscriptDataStatement} onChange={(event) => setManuscriptDataStatement(event.target.value)} rows={3} minLength={5} maxLength={5000} required placeholder="Describe what data exists and whether it can be accessed or shared." />
                  <p className="form-help">The editor does not generate findings or infer claims. Every claim must have explicit source mappings; the service verifies record integrity and identifiers but cannot determine whether a source supports the wording.</p>
                  <button className="primary-button" type="submit" disabled={!protectedActionsAvailable || busy !== null || manuscriptSources.length === 0 || manuscriptClaims.some((claim) => claim.text.trim().length < 5 || claim.sourceIds.length === 0)}>{busy === 'manuscript-create' ? 'Saving manuscript draft…' : 'Save manuscript draft'}</button>
                </form>
              </section>
              <section className="workspace-card manuscript-preview-card">
                <div className="section-heading"><div><p className="card-label">MANUSCRIPT PREVIEW</p><h2>Rendered Markdown draft</h2></div><span className="section-index">NOT SUBMITTED</span></div>
                {manuscriptRecord ? (
                  <>
                    <div className="literature-result-top"><span className="result-chip">{String(manuscriptRecord.payload.status ?? 'draft')}</span><span className="result-chip">{manuscriptRecord.content_sha256.slice(0, 16)}…</span></div>
                    <pre className="manuscript-markdown-preview">{String(manuscriptRecord.payload.rendered_markdown ?? '')}</pre>
                    <div className="form-actions"><button className="secondary-button" type="button" onClick={downloadManuscript}>Export Markdown</button><span className="manuscript-approval-state">External submission disabled · Approval: {manuscriptRecord.payload.submission_approved ? 'approved' : 'not approved'}</span></div>
                  </>
                ) : <div className="empty-state"><span>✎</span><strong>No draft preview selected</strong><p>Save a new manuscript or open a draft from the persisted list to inspect the rendered Markdown.</p></div>}
              </section>
            </div>
            <div className="workspace-alert workspace-alert-warning"><strong>Publication control:</strong><span>This studio creates research drafts only. It does not submit manuscripts, post preprints, contact journals, claim peer review, or certify that citations support claims. All substantive content and source interpretation remain the responsibility of qualified human researchers.</span></div>
          </section>
        )}

        {activeView === 'memory' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">SCIENTIFIC MEMORY & LEARNING</p>
              <h1>Maintain evidence-linked research memory</h1>
              <p>Record a research note or structured finding as an immutable version, link it to existing tenant research records, track contradictions and roll back by appending a new version.</p>
            </div>
            {!protectedActionsAvailable && <div className="workspace-alert workspace-alert-warning" role="note"><strong>Memory is protected and unavailable in this production build.</strong><span>Authenticated tenant access is required. OIDC login and tenant selection are not yet connected to this frontend.</span></div>}
            {memoryError && <div className="workspace-alert workspace-alert-error" role="alert">{memoryError}</div>}
            <section className="workspace-card">
              <div className="section-heading"><div><p className="card-label">PERSISTENT MEMORY INDEX</p><h2>{memoryTotal} memory key(s)</h2></div><button className="secondary-button" type="button" onClick={() => setMemoryRefresh((value) => value + 1)} disabled={!protectedActionsAvailable || busy !== null}>Refresh memory</button></div>
              {protectedActionsAvailable && memoryItems.length === 0 ? <div className="empty-state"><span>◈</span><strong>No saved memory entries</strong><p>Create a versioned memory note linked to an existing source, claim or research record.</p></div> : null}
              {memoryItems.length > 0 && <div className="memory-index-list">{memoryItems.map((item) => <button className={'memory-index-item' + (memoryKey === item.key ? ' memory-index-active' : '')} type="button" key={item.key} onClick={() => void openMemoryHistory(item.key)} disabled={busy !== null}><span><strong>{item.key}</strong><small>Version {item.version} · {item.evidence_count} evidence record(s) · {formatDate(item.created_at)}</small></span><span className="result-chip">{item.status}</span></button>)}</div>}
            </section>
            <div className="workspace-two-column memory-form-grid">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">CREATE A MEMORY VERSION</p><h2>Research note or finding</h2></div><span className="section-index">APPEND-ONLY</span></div>
                <form className="workspace-form" onSubmit={saveMemoryVersion}>
                  <label htmlFor="memory-key">Memory key</label>
                  <input id="memory-key" value={memoryKey} onChange={(event) => setMemoryKey(event.target.value)} minLength={1} maxLength={200} pattern="[A-Za-z0-9._:-]+" required />
                  <label htmlFor="memory-value">Memory value (JSON object)</label>
                  <textarea id="memory-value" className="lab-json-editor" value={memoryValueJson} onChange={(event) => setMemoryValueJson(event.target.value)} rows={10} maxLength={65536} spellCheck={false} required />
                  <label htmlFor="memory-evidence">Evidence records (select one or more)</label>
                  <select id="memory-evidence" className="memory-evidence-select" multiple value={memoryEvidenceIds} onChange={(event) => setMemoryEvidenceIds(Array.from(event.currentTarget.selectedOptions).map((option) => option.value))} size={Math.min(8, Math.max(3, memoryRecords.length))}>
                    {memoryRecords.map((record) => <option key={record.id} value={record.id}>{recordTitle(record)} · {record.record_type}</option>)}
                  </select>
                  <p className="form-help">Evidence IDs are validated against records owned by the same tenant. A link records provenance; it does not confer scientific validity or prove the linked record's claims.</p>
                  <button className="primary-button" type="submit" disabled={!protectedActionsAvailable || busy !== null || memoryEvidenceIds.length === 0}>{busy === 'memory-save' ? 'Saving version…' : 'Save memory version'}</button>
                </form>
              </section>
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">VERSION HISTORY</p><h2>{memoryHistory.length} version(s)</h2></div><span className="section-index">CHECKSUMMED</span></div>
                {memoryHistory.length > 0 ? <div className="memory-version-list">{memoryHistory.map((item) => <article className="memory-version-item" key={item.version}><div><strong>Version {item.version}</strong><span className="result-chip">{item.status}</span></div><small>{formatDate(item.created_at)}{item.supersedes ? ' · supersedes v' + item.supersedes : ' · first version'}</small><pre>{JSON.stringify(item.value, null, 2)}</pre><code>{item.digest}</code><small>Evidence: {item.evidence.join(', ')}</small></article>)}</div> : <div className="empty-state"><span>◈</span><strong>No memory history selected</strong><p>Select a saved key from the memory index or create the first version.</p></div>}
              </section>
            </div>
            <div className="workspace-two-column memory-action-grid">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">CONTRADICTION TRACKING</p><h2>Dispute a current memory entry</h2></div><span className="section-index">NEW DISPUTED VERSION</span></div>
                <form className="workspace-form" onSubmit={contradictMemory}>
                  <label htmlFor="memory-contradiction">Reason for contradiction</label>
                  <textarea id="memory-contradiction" value={memoryContradictionReason} onChange={(event) => setMemoryContradictionReason(event.target.value)} minLength={5} maxLength={2000} rows={3} required placeholder="Describe the conflicting evidence and what it challenges." />
                  <button className="secondary-button" type="submit" disabled={!protectedActionsAvailable || busy !== null || memoryHistory.length === 0 || memoryEvidenceIds.length === 0}>{busy === 'memory-contradict' ? 'Recording contradiction…' : 'Record contradiction'}</button>
                </form>
              </section>
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">VERSION ROLLBACK</p><h2>Restore an earlier value</h2></div><span className="section-index">NON-DESTRUCTIVE</span></div>
                <form className="workspace-form" onSubmit={rollbackMemory}>
                  <label htmlFor="memory-rollback-version">Historical version</label>
                  <select id="memory-rollback-version" value={memoryRollbackVersion} onChange={(event) => setMemoryRollbackVersion(event.target.value)}>{memoryHistory.map((item) => <option key={item.version} value={item.version}>Version {item.version} · {item.status}</option>)}</select>
                  <p className="form-help">Rollback appends a new version containing the selected historical value and its prior evidence references. It never erases the audit trail.</p>
                  <button className="secondary-button" type="submit" disabled={!protectedActionsAvailable || busy !== null || memoryHistory.length === 0}>{busy === 'memory-rollback' ? 'Creating rollback…' : 'Create rollback version'}</button>
                </form>
              </section>
            </div>
          </section>
        )}

        {activeView === 'analysis' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">DATA ANALYSIS & RESULTS OBSERVATORY</p>
              <h1>Explore numerical evidence</h1>
              <p>Calculate descriptive statistics for supplied samples and create bounded mathematical plots. These tools describe the inputs; they do not infer causality or establish scientific significance.</p>
            </div>
            <div className="workspace-two-column">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">DESCRIPTIVE STATISTICS</p><h2>Analyze a numeric sample</h2></div><span className="section-index">NUMPY / BOUNDED</span></div>
                <form className="workspace-form" onSubmit={runStatistics}>
                  <label htmlFor="sample-values">Numeric values</label>
                  <textarea id="sample-values" value={sampleValues} onChange={(event) => setSampleValues(event.target.value)} rows={5} required placeholder="Enter values separated by commas, spaces or new lines" />
                  <label htmlFor="variance-mode">Variance interpretation</label>
                  <select id="variance-mode" value={varianceMode} onChange={(event) => setVarianceMode(event.target.value as typeof varianceMode)}><option value="sample">Sample variance</option><option value="population">Population variance</option></select>
                  <button className="primary-button" type="submit" disabled={busy !== null || !apiConfigured}>{busy === 'statistics' ? 'Analyzing…' : 'Calculate statistics'}</button>
                </form>
                {statisticsResponse ? (
                  <div className="statistics-result">
                    <div className="statistics-grid">
                      {[
                        ['Count', statisticsResponse.count],
                        ['Mean', statisticsResponse.mean],
                        ['Median', statisticsResponse.median],
                        ['Std. deviation', statisticsResponse.standard_deviation],
                        ['Variance', statisticsResponse.variance],
                        ['Minimum', statisticsResponse.minimum],
                        ['Maximum', statisticsResponse.maximum],
                      ].map(([label, value]) => <div className="statistics-cell" key={String(label)}><span>{label}</span><strong>{typeof value === 'number' ? Number(value.toPrecision(7)).toString() : value}</strong></div>)}
                    </div>
                    <h3>Quartiles</h3>
                    <div className="vocabulary-tags">{Object.entries(statisticsResponse.quartiles).map(([label, value]) => <span key={label}>{label}: {Number(value.toPrecision(7)).toString()}</span>)}</div>
                    <p className="form-help">{statisticsResponse.method}. {statisticsResponse.note}</p>
                  </div>
                ) : <div className="empty-state"><span>∿</span><strong>No statistics computed</strong><p>Enter a numeric sample to calculate descriptive measures.</p></div>}
              </section>
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">FUNCTION PLOTTING</p><h2>Render a mathematical function</h2></div><span className="section-index">PNG / BOUNDED</span></div>
                <form className="workspace-form" onSubmit={renderFunctionPlot}>
                  <label htmlFor="plot-expression">Mathematical expression</label>
                  <input id="plot-expression" value={plotExpression} onChange={(event) => setPlotExpression(event.target.value)} minLength={1} maxLength={500} required />
                  <div className="variable-grid">
                    <div><label htmlFor="plot-variable">Variable</label><input id="plot-variable" value={plotVariable} onChange={(event) => setPlotVariable(event.target.value)} minLength={1} maxLength={32} required /></div>
                    <div><label htmlFor="plot-lower">Lower bound</label><input id="plot-lower" type="number" value={plotLower} onChange={(event) => setPlotLower(event.target.value)} step="any" required /></div>
                    <div><label htmlFor="plot-upper">Upper bound</label><input id="plot-upper" type="number" value={plotUpper} onChange={(event) => setPlotUpper(event.target.value)} step="any" required /></div>
                  </div>
                  <button className="primary-button" type="submit" disabled={busy !== null || !apiConfigured}>{busy === 'plot' ? 'Rendering plot…' : 'Render plot'}</button>
                </form>
                {plotUrl ? (
                  <figure className="plot-result"><img src={plotUrl} alt={'Plot of ' + plotExpression + ' over ' + plotVariable + ' from ' + plotLower + ' to ' + plotUpper} /><figcaption>Generated PNG · {plotExpression} · {plotVariable} ∈ [{plotLower}, {plotUpper}]</figcaption></figure>
                ) : <div className="empty-state"><span>⌁</span><strong>No plot generated</strong><p>Submit a bounded expression and finite interval to render a PNG image.</p></div>}
              </section>
            </div>
            <div className="workspace-caveat">Statistical summaries depend on the supplied sample and variance mode. They do not establish representativeness, independence, statistical significance, causal effects or measurement validity. Review data provenance and assumptions separately.</div>
          </section>
        )}

        {activeView === 'math' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">MATHEMATICS & FORMAL REASONING WORKBENCH</p>
              <h1>Run a bounded symbolic calculation</h1>
              <p>Use the allowlisted mathematical engine for explicit expressions. Inputs are parsed as mathematical expressions, not executed as arbitrary code.</p>
            </div>
            <div className="workspace-two-column">
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">SYMBOLIC TOOL</p><h2>Calculation input</h2></div><span className="section-index">BOUNDED / 01</span></div>
                <form className="workspace-form" onSubmit={runSymbolicTool}>
                  <label htmlFor="math-operation">Operation</label>
                  <select id="math-operation" value={mathOperation} onChange={(event) => setMathOperation(event.target.value as typeof mathOperation)}>
                    <option value="simplify">Simplify</option>
                    <option value="differentiate">Differentiate</option>
                    <option value="integrate">Integrate</option>
                    <option value="solve">Solve</option>
                    <option value="evaluate">Evaluate</option>
                  </select>
                  <label htmlFor="math-expression">Expression</label>
                  <textarea id="math-expression" rows={4} value={mathExpression} onChange={(event) => setMathExpression(event.target.value)} minLength={1} maxLength={500} required />
                  <label htmlFor="math-variable">Variable</label>
                  <input id="math-variable" value={mathVariable} onChange={(event) => setMathVariable(event.target.value)} minLength={1} maxLength={32} required />
                  <div className="form-actions"><button className="primary-button" type="submit" disabled={busy !== null || !apiConfigured}>{busy === 'math' ? 'Calculating…' : 'Run calculation'}</button></div>
                </form>
              </section>
              <section className="workspace-card">
                <div className="section-heading"><div><p className="card-label">COMPUTATION RESULT</p><h2>Review output</h2></div><span className="section-index">RESULT / 01</span></div>
                {mathResponse ? (
                  <div className="math-result">
                    <span className="result-chip">{mathResponse.method}</span>
                    <p className="math-expression">{mathResponse.expression}</p>
                    <div className="math-result-value">{mathResponse.result}</div>
                    {mathResponse.results.length > 1 && <ul className="workspace-list">{mathResponse.results.map((item) => <li key={item}>{item}</li>)}</ul>}
                    <p>{mathResponse.note}</p>
                  </div>
                ) : (
                  <div className="empty-state"><span>∑</span><strong>No calculation yet</strong><p>Submit an expression to inspect the bounded engine output and its stated limitations.</p></div>
                )}
              </section>
            </div>
          </section>
        )}

        {activeView === 'records' && (
          <section className="workspace-page">
            <div className="page-heading">
              <p className="card-label">SCIENTIFIC MEMORY FOUNDATION · RECORD STORE</p>
              <h1>Research records</h1>
              <p>Browse append-only research records with server-generated identifiers, timestamps and content digests.</p>
            </div>
            <section className="workspace-card">
              <div className="section-heading"><div><p className="card-label">PERSISTED RECORDS</p><h2>{recordTotal} total record(s)</h2></div><button className="secondary-button" type="button" onClick={() => setRecordsRefresh((value) => value + 1)}>Refresh records</button></div>
              {!protectedActionsAvailable && <div className="workspace-alert workspace-alert-warning" role="note">Record browsing requires an authenticated tenant session. Production OIDC sign-in and tenant selection are pending.</div>}
              {recordError && <div className="workspace-alert workspace-alert-error" role="alert">{recordError}</div>}
              {records.length === 0 && !recordError && protectedActionsAvailable ? (
                <div className="empty-state"><span>▤</span><strong>No records returned</strong><p>Create a research task, save source metadata or assess hypotheses to begin a traceable record history.</p></div>
              ) : (
                <div className="records-table-wrap">
                  <table className="records-table">
                    <thead><tr><th scope="col">Type</th><th scope="col">Record</th><th scope="col">Created</th><th scope="col">Identifier</th></tr></thead>
                    <tbody>
                      {records.map((record) => (
                        <tr key={record.id}>
                          <td><span className="result-chip">{record.record_type.replaceAll('_', ' ')}</span></td>
                          <td><strong>{recordTitle(record)}</strong></td>
                          <td>{formatDate(record.created_at)}</td>
                          <td><code>{record.id}</code></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="form-help">Record payloads are immutable through the public API. The content SHA-256 digest supports integrity checking; it does not verify the truth of the payload.</p>
            </section>
          </section>
        )}

        <footer className="page-footer">
          <div><span className="footer-mark" /> ARTIFICIAL SCIENTIST <span className="footer-version">ASDS</span></div>
          <p>Research-first · evidence-led · bounded autonomy · scientific claims require independent evidence and review.</p>
        </footer>
      </main>
    </div>
  )
}
