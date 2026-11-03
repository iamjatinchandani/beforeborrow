import { CheckCircle2, RefreshCw, AlertCircle } from 'lucide-react'

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error'

interface Props {
  status: SaveStatus
  lastSavedAt?: Date | null
}

export function AutosaveIndicator({ status, lastSavedAt }: Props) {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontSize: 12,
        color:
          status === 'error'
            ? 'var(--color-shortfall)'
            : status === 'saving'
            ? 'var(--color-primary)'
            : '#64748b',
        padding: '4px 8px',
        borderRadius: 'var(--radius-sm)',
        background: 'var(--color-bg-muted)',
      }}
    >
      {status === 'saving' && (
        <>
          <RefreshCw size={12} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
          <span>Autosaving draft...</span>
        </>
      )}
      {status === 'saved' && (
        <>
          <CheckCircle2 size={12} color="var(--color-primary)" />
          <span>
            Draft saved{lastSavedAt ? ` at ${lastSavedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}
          </span>
        </>
      )}
      {status === 'idle' && (
        <>
          <CheckCircle2 size={12} color="#94a3b8" />
          <span>Draft in sync</span>
        </>
      )}
      {status === 'error' && (
        <>
          <AlertCircle size={12} />
          <span>Failed to autosave. Will retry.</span>
        </>
      )}
    </div>
  )
}
