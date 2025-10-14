import { useState, useEffect } from 'react'
import './SessionSelector.css'

interface Session {
  id: string
  session_id: string
  title: string
  description?: string
  message_count: string
  created_at: string
  updated_at: string
  last_message_at?: string
}

interface SessionSelectorProps {
  currentSessionId: string
  onSessionChange: (sessionId: string) => void
  onSessionCreate: (sessionId: string, title: string) => void
}

function SessionSelector({ currentSessionId, onSessionChange, onSessionCreate }: SessionSelectorProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [newSessionTitle, setNewSessionTitle] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen) {
      loadSessions()
    }
  }, [isOpen])

  const loadSessions = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('http://localhost:9000/sessions')
      if (!response.ok) throw new Error('Failed to load sessions')
      const data = await response.json()
      setSessions(data.sessions)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sessions')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateSession = async () => {
    if (!newSessionTitle.trim()) return

    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    try {
      const response = await fetch('http://localhost:9000/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          title: newSessionTitle
        })
      })

      if (!response.ok) throw new Error('Failed to create session')

      setNewSessionTitle('')
      setIsCreating(false)
      await loadSessions()
      onSessionCreate(sessionId, newSessionTitle)
      onSessionChange(sessionId)
      setIsOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create session')
    }
  }

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation()

    if (!confirm('Are you sure you want to delete this session? All messages will be lost.')) {
      return
    }

    try {
      const response = await fetch(`http://localhost:9000/sessions/${sessionId}`, {
        method: 'DELETE'
      })

      if (!response.ok) throw new Error('Failed to delete session')

      await loadSessions()

      // If deleting current session, switch to default
      if (sessionId === currentSessionId) {
        onSessionChange('default')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session')
    }
  }

  const handleSelectSession = (sessionId: string) => {
    onSessionChange(sessionId)
    setIsOpen(false)
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never'
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  const currentSession = sessions.find(s => s.session_id === currentSessionId)

  return (
    <div className="session-selector">
      <button
        className="session-trigger"
        onClick={() => setIsOpen(!isOpen)}
        title="Manage Sessions"
      >
        <span className="session-icon">💬</span>
        <span className="session-current">
          {currentSession?.title || currentSessionId}
        </span>
        <span className={`session-arrow ${isOpen ? 'open' : ''}`}>▼</span>
      </button>

      {isOpen && (
        <>
          <div className="session-overlay" onClick={() => setIsOpen(false)} />
          <div className="session-dropdown">
            <div className="session-header">
              <h3>Chat Sessions</h3>
              <button
                className="session-new-btn"
                onClick={() => setIsCreating(true)}
                title="New Session"
              >
                + New
              </button>
            </div>

            {error && (
              <div className="session-error">{error}</div>
            )}

            {isCreating && (
              <div className="session-create-form">
                <input
                  type="text"
                  value={newSessionTitle}
                  onChange={(e) => setNewSessionTitle(e.target.value)}
                  placeholder="Session name..."
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreateSession()
                    if (e.key === 'Escape') setIsCreating(false)
                  }}
                />
                <div className="session-create-actions">
                  <button onClick={handleCreateSession} className="btn-create">
                    Create
                  </button>
                  <button onClick={() => setIsCreating(false)} className="btn-cancel">
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {loading ? (
              <div className="session-loading">Loading sessions...</div>
            ) : (
              <div className="session-list">
                {sessions.length === 0 ? (
                  <div className="session-empty">
                    No sessions yet. Create one to get started!
                  </div>
                ) : (
                  sessions.map((session) => (
                    <div
                      key={session.id}
                      className={`session-item ${session.session_id === currentSessionId ? 'active' : ''}`}
                      onClick={() => handleSelectSession(session.session_id)}
                    >
                      <div className="session-item-content">
                        <div className="session-item-title">{session.title}</div>
                        <div className="session-item-meta">
                          <span>{session.message_count} messages</span>
                          <span>•</span>
                          <span>{formatDate(session.last_message_at || session.updated_at)}</span>
                        </div>
                      </div>
                      {session.session_id !== 'default' && (
                        <button
                          className="session-delete-btn"
                          onClick={(e) => handleDeleteSession(session.session_id, e)}
                          title="Delete session"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default SessionSelector
