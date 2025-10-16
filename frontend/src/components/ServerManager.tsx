import { useState, useEffect } from 'react'
import './ServerManager.css'

interface MCPServer {
  id: string
  name: string
  command: string
  args: string[] | null
  env: Record<string, string> | null
  transport_type: string
  url: string | null
  enabled: boolean
  health_status: string
  last_health_check: string | null
  created_at: string
  updated_at: string
}

interface ServerManagerProps {
  onClose: () => void
}

function ServerManager({ onClose }: ServerManagerProps) {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingServer, setEditingServer] = useState<MCPServer | null>(null)

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    command: '',
    args: '',
    env: '',
    transport_type: 'stdio',
    url: '',
    enabled: true
  })

  useEffect(() => {
    loadServers()
  }, [])

  const loadServers = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('http://localhost:9000/mcp-servers')
      if (!response.ok) throw new Error('Failed to load servers')
      const data = await response.json()
      setServers(data.servers)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load servers')
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      command: '',
      args: '',
      env: '',
      transport_type: 'stdio',
      url: '',
      enabled: true
    })
    setEditingServer(null)
    setShowAddForm(false)
  }

  const handleEdit = (server: MCPServer) => {
    setFormData({
      name: server.name,
      command: server.command,
      args: server.args ? JSON.stringify(server.args) : '',
      env: server.env ? JSON.stringify(server.env, null, 2) : '',
      transport_type: server.transport_type,
      url: server.url || '',
      enabled: server.enabled
    })
    setEditingServer(server)
    setShowAddForm(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      // Parse JSON fields
      const args = formData.args.trim() ? JSON.parse(formData.args) : null
      const env = formData.env.trim() ? JSON.parse(formData.env) : null

      const payload = {
        name: formData.name,
        command: formData.command,
        args,
        env,
        transport_type: formData.transport_type,
        url: formData.url || null,
        enabled: formData.enabled
      }

      if (editingServer) {
        // Update existing server
        const response = await fetch(`http://localhost:9000/mcp-servers/${editingServer.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        if (!response.ok) throw new Error('Failed to update server')
      } else {
        // Create new server
        const response = await fetch('http://localhost:9000/mcp-servers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        if (!response.ok) throw new Error('Failed to create server')
      }

      resetForm()
      await loadServers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save server')
    }
  }

  const handleDelete = async (serverId: string) => {
    if (!confirm('Are you sure you want to delete this server? This action cannot be undone.')) {
      return
    }

    try {
      const response = await fetch(`http://localhost:9000/mcp-servers/${serverId}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to delete server')
      await loadServers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete server')
    }
  }

  const handleTest = async (serverId: string) => {
    try {
      const response = await fetch(`http://localhost:9000/mcp-servers/${serverId}/test`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Failed to test server')
      const data = await response.json()
      alert(data.message)
      await loadServers()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to test server')
    }
  }

  return (
    <div className="server-manager-overlay">
      <div className="server-manager">
        <div className="server-manager-header">
          <h2>🔧 MCP Server Management</h2>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        {error && (
          <div className="server-error">{error}</div>
        )}

        {!showAddForm ? (
          <>
            <div className="server-actions">
              <button className="btn-add-server" onClick={() => setShowAddForm(true)}>
                + Add New Server
              </button>
              <button className="btn-refresh" onClick={loadServers}>
                🔄 Refresh
              </button>
            </div>

            {loading ? (
              <div className="server-loading">Loading servers...</div>
            ) : servers.length === 0 ? (
              <div className="server-empty">
                No MCP servers configured. Add one to get started!
              </div>
            ) : (
              <div className="server-list">
                {servers.map((server) => (
                  <div key={server.id} className={`server-card ${!server.enabled ? 'disabled' : ''}`}>
                    <div className="server-card-header">
                      <h3>{server.name}</h3>
                      <span className={`server-status ${server.health_status}`}>
                        {server.health_status}
                      </span>
                    </div>

                    <div className="server-details">
                      <div className="server-detail">
                        <strong>Transport:</strong> {server.transport_type}
                      </div>
                      <div className="server-detail">
                        <strong>Command:</strong> <code>{server.command}</code>
                      </div>
                      {server.url && (
                        <div className="server-detail">
                          <strong>URL:</strong> <code>{server.url}</code>
                        </div>
                      )}
                      {server.args && server.args.length > 0 && (
                        <div className="server-detail">
                          <strong>Args:</strong> <code>{JSON.stringify(server.args)}</code>
                        </div>
                      )}
                    </div>

                    <div className="server-card-actions">
                      <button className="btn-edit" onClick={() => handleEdit(server)}>
                        ✏️ Edit
                      </button>
                      <button className="btn-test" onClick={() => handleTest(server.id)}>
                        🧪 Test
                      </button>
                      <button className="btn-delete" onClick={() => handleDelete(server.id)}>
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <form className="server-form" onSubmit={handleSubmit}>
            <h3>{editingServer ? 'Edit Server' : 'Add New Server'}</h3>

            <div className="form-group">
              <label>Server Name *</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                placeholder="e.g., filesystem-server"
              />
            </div>

            <div className="form-group">
              <label>Transport Type *</label>
              <select
                value={formData.transport_type}
                onChange={(e) => setFormData({ ...formData, transport_type: e.target.value })}
                required
              >
                <option value="stdio">STDIO</option>
                <option value="http">HTTP</option>
                <option value="sse">SSE</option>
              </select>
            </div>

            <div className="form-group">
              <label>Command *</label>
              <input
                type="text"
                value={formData.command}
                onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                required
                placeholder="e.g., npx or node"
              />
            </div>

            {formData.transport_type !== 'stdio' && (
              <div className="form-group">
                <label>URL</label>
                <input
                  type="text"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  placeholder="e.g., http://localhost:3000"
                />
              </div>
            )}

            <div className="form-group">
              <label>Arguments (JSON array)</label>
              <textarea
                value={formData.args}
                onChange={(e) => setFormData({ ...formData, args: e.target.value })}
                placeholder='["arg1", "arg2"]'
                rows={2}
              />
            </div>

            <div className="form-group">
              <label>Environment Variables (JSON object)</label>
              <textarea
                value={formData.env}
                onChange={(e) => setFormData({ ...formData, env: e.target.value })}
                placeholder='{"KEY": "value"}'
                rows={3}
              />
            </div>

            <div className="form-group-checkbox">
              <label>
                <input
                  type="checkbox"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                />
                <span>Enabled</span>
              </label>
            </div>

            <div className="form-actions">
              <button type="submit" className="btn-submit">
                {editingServer ? 'Update Server' : 'Create Server'}
              </button>
              <button type="button" className="btn-cancel" onClick={resetForm}>
                Cancel
              </button>
            </div>

            <div className="form-note">
              Note: Server changes require a backend restart to take effect.
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

export default ServerManager
