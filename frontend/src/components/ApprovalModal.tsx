import { useState } from 'react'
import './ApprovalModal.css'

interface ToolCall {
  id: string
  name: string
  arguments: string
  parsed_arguments: Record<string, any>
}

interface ApprovalModalProps {
  requestId: string
  toolCalls: ToolCall[]
  onApprove: (toolIds?: string[]) => void
  onReject: (reason?: string) => void
}

function ApprovalModal({ requestId: _requestId, toolCalls, onApprove, onReject }: ApprovalModalProps) {
  // requestId is available for future use (e.g., logging, analytics)
  // Prefixed with _ to indicate intentionally unused
  const [selectedTools, setSelectedTools] = useState<Set<string>>(
    new Set(toolCalls.map(tc => tc.id))
  )
  const [rejectionReason, setRejectionReason] = useState('')
  const [showRejectForm, setShowRejectForm] = useState(false)

  const toggleTool = (toolId: string) => {
    const newSelected = new Set(selectedTools)
    if (newSelected.has(toolId)) {
      newSelected.delete(toolId)
    } else {
      newSelected.add(toolId)
    }
    setSelectedTools(newSelected)
  }

  const handleApprove = () => {
    if (selectedTools.size === 0) {
      alert('Please select at least one tool to approve')
      return
    }
    // If all tools selected, pass undefined (approve all)
    if (selectedTools.size === toolCalls.length) {
      onApprove()
    } else {
      onApprove(Array.from(selectedTools))
    }
  }

  const handleReject = () => {
    onReject(rejectionReason || undefined)
  }

  const formatArguments = (args: Record<string, any>) => {
    return JSON.stringify(args, null, 2)
  }

  return (
    <div className="approval-modal-overlay">
      <div className="approval-modal">
        <div className="approval-header">
          <h2>🔐 Tool Execution Approval Required</h2>
          <p className="approval-subtitle">
            The assistant wants to execute {toolCalls.length} tool{toolCalls.length > 1 ? 's' : ''}.
            Please review and approve.
          </p>
        </div>

        <div className="tool-list">
          {toolCalls.map((tool) => (
            <div
              key={tool.id}
              className={`tool-card ${selectedTools.has(tool.id) ? 'selected' : ''}`}
            >
              <div className="tool-card-header">
                <label className="tool-checkbox">
                  <input
                    type="checkbox"
                    checked={selectedTools.has(tool.id)}
                    onChange={() => toggleTool(tool.id)}
                  />
                  <span className="checkbox-custom"></span>
                </label>
                <div className="tool-info">
                  <h3 className="tool-name">{tool.name}</h3>
                  <span className="tool-id">ID: {tool.id.substring(0, 8)}...</span>
                </div>
              </div>

              <div className="tool-arguments">
                <details>
                  <summary>View Arguments</summary>
                  <pre>{formatArguments(tool.parsed_arguments)}</pre>
                </details>
              </div>
            </div>
          ))}
        </div>

        {!showRejectForm ? (
          <div className="approval-actions">
            <button
              className="btn-approve"
              onClick={handleApprove}
              disabled={selectedTools.size === 0}
            >
              ✓ Approve {selectedTools.size > 0 ? `(${selectedTools.size})` : ''}
            </button>
            <button
              className="btn-reject"
              onClick={() => setShowRejectForm(true)}
            >
              ✗ Reject All
            </button>
          </div>
        ) : (
          <div className="rejection-form">
            <label>
              Rejection Reason (Optional):
              <textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="Why are you rejecting this tool execution?"
                rows={3}
              />
            </label>
            <div className="rejection-actions">
              <button
                className="btn-reject-confirm"
                onClick={handleReject}
              >
                Confirm Rejection
              </button>
              <button
                className="btn-cancel"
                onClick={() => setShowRejectForm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="approval-footer">
          <p className="warning-text">
            ⚠️ Only approve tools you understand and trust
          </p>
        </div>
      </div>
    </div>
  )
}

export default ApprovalModal
