import { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  useScenario,
  useSetupStatus,
  useCreateScenario,
  useUpdateScenario,
  useAnalyzeScenario,
  useAnalysis,
} from '../hooks'
import { ScenarioData, AnalysisPayload } from '../types'
import { ScenarioWizard } from '../components/ScenarioWizard'
import { ComparisonDashboard } from '../components/ComparisonDashboard'
import { MissingSetupBanner } from '../components/MissingSetupBanner'
import { ErrorPanel } from '../../../components/ui/ErrorPanel'
import { Button } from '../../../components/ui/Button'
import { ApiRequestError } from '@/lib/api'
import { RefreshCw, ArrowLeft } from 'lucide-react'

export default function DecisionPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const analysisIdParam = searchParams.get('analysis_id')

  // API Hooks
  const { data: setupStatus } = useSetupStatus()
  const { data: existingScenario } = useScenario(id)
  const createScenarioMutation = useCreateScenario()
  const updateScenarioMutation = useUpdateScenario(id)
  const analyzeMutation = useAnalyzeScenario(id || '')
  const { data: existingAnalysis } = useAnalysis(analysisIdParam || undefined)

  // Local state
  const [analysisResult, setAnalysisResult] = useState<AnalysisPayload | null>(null)
  const [activeAnalysisId, setActiveAnalysisId] = useState<string | null>(analysisIdParam)
  const [staleError, setStaleError] = useState<string | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)

  // If analysis ID is in URL, populate analysisResult
  useEffect(() => {
    if (existingAnalysis?.result_json) {
      try {
        const parsed = JSON.parse(existingAnalysis.result_json)
        setAnalysisResult(parsed)
      } catch {
        // ignore parse error
      }
    }
  }, [existingAnalysis])

  // Draft Autosave Handler
  const handleSaveDraft = async (data: ScenarioData) => {
    try {
      if (id) {
        await updateScenarioMutation.mutateAsync({ id, data })
      } else {
        const created = await createScenarioMutation.mutateAsync(data)
        if (created?.id) {
          navigate(`/decision/${created.id}`, { replace: true })
        }
      }
    } catch (err: unknown) {
      console.error('Failed to autosave draft:', err)
      throw err
    }
  }

  // Run Analysis Handler
  const handleRunAnalysis = async (data: ScenarioData) => {
    setStaleError(null)
    setApiError(null)

    try {
      let scenarioIdToUse = id
      if (!scenarioIdToUse) {
        const created = await createScenarioMutation.mutateAsync(data)
        scenarioIdToUse = created.id
        if (scenarioIdToUse) {
          navigate(`/decision/${scenarioIdToUse}`, { replace: true })
        }
      } else {
        await updateScenarioMutation.mutateAsync({ id: scenarioIdToUse, data })
      }

      if (!scenarioIdToUse) return

      const res = await analyzeMutation.mutateAsync({
        scenario_version: data.version || 1,
        expected_data_version: setupStatus?.profile_data_version || 1,
        stress_cases: ['income_delay_30d', 'expense_spike_20pct'],
      })

      setActiveAnalysisId(res.id)
      setSearchParams({ analysis_id: res.id })

      const parsed = JSON.parse(res.result_json)
      setAnalysisResult(parsed)
    } catch (err: unknown) {
      if (err instanceof ApiRequestError) {
        if (err.status === 409) {
          setStaleError(
            'Your financial profile data has changed since this scenario was created. Please refresh and re-simulate.'
          )
        } else if (err.status === 503) {
          setApiError(
            err.error.message ||
              'Financial calculation engine is currently unavailable (Pending Person C integration).'
          )
        } else {
          setApiError(err.error.message || 'Analysis failed. Please check inputs and retry.')
        }
      } else {
        setApiError('An unexpected error occurred during simulation.')
      }
    }
  }

  return (
    <div style={{ paddingBottom: 'var(--space-6)' }}>
      {/* Missing Setup Banner */}
      <MissingSetupBanner status={setupStatus} />

      {/* Stale Analysis Warning (HTTP 409) */}
      {staleError && (
        <div
          role="alert"
          style={{
            padding: 16,
            background: '#fffbeb',
            border: '1px solid #fef3c7',
            borderLeft: '4px solid var(--color-caution)',
            borderRadius: 'var(--radius)',
            marginBottom: 'var(--space-3)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <h4 style={{ margin: '0 0 2px', fontSize: 14, fontWeight: 600, color: '#92400e' }}>
              Data Version Conflict (HTTP 409)
            </h4>
            <p style={{ margin: 0, fontSize: 13, color: '#b45309' }}>{staleError}</p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setStaleError(null)
              if (existingScenario) handleRunAnalysis(existingScenario)
            }}
          >
            <RefreshCw size={14} /> Refresh & Rerun
          </Button>
        </div>
      )}

      {/* API Error Panel with Retry */}
      {apiError && (
        <div style={{ marginBottom: 'var(--space-3)' }}>
          <ErrorPanel
            message={apiError}
            onRetry={() => {
              setApiError(null)
              if (existingScenario) handleRunAnalysis(existingScenario)
            }}
          />
        </div>
      )}

      {/* View Toggle: If analysis is ready, show ComparisonDashboard with Back button */}
      {analysisResult && activeAnalysisId && id ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setAnalysisResult(null)
                setSearchParams({})
              }}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <ArrowLeft size={14} /> Edit Scenario Inputs
            </Button>
            <span style={{ fontSize: 12, color: '#64748b' }}>
              Analysis ID: {activeAnalysisId.slice(0, 8)}...
            </span>
          </div>

          <ComparisonDashboard
            scenarioId={id}
            analysisId={activeAnalysisId}
            analysis={analysisResult}
            onRerun={() => {
              if (existingScenario) handleRunAnalysis(existingScenario)
            }}
          />
        </div>
      ) : (
        <ScenarioWizard
          initialData={existingScenario || undefined}
          onSaveDraft={handleSaveDraft}
          onRunAnalysis={handleRunAnalysis}
          isAnalyzing={analyzeMutation.isPending}
        />
      )}
    </div>
  )
}
