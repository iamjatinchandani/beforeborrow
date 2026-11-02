import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div style={{ padding: 24, margin: '24px auto', maxWidth: 600, background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8 }}>
          <h2 style={{ color: '#ef4444', marginBottom: 8 }}>Something went wrong</h2>
          <p style={{ color: '#64748b', fontSize: 14 }}>
            {this.state.error?.message || 'An unexpected rendering error occurred.'}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{ marginTop: 16, padding: '8px 16px', background: '#0d9488', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}
          >
            Reload application
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
