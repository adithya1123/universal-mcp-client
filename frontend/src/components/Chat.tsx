import { useState, useEffect, useRef } from 'react'
import SessionSelector from './SessionSelector'
import ApprovalModal from './ApprovalModal'
import './Chat.css'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  toolExecutions?: ToolExecution[]
  isStreaming?: boolean
}

interface ToolExecution {
  id: string
  name: string
  status: 'running' | 'completed' | 'error'
  arguments?: string
  result?: string
  error?: string
}

interface PendingApproval {
  requestId: string
  toolCalls: Array<{
    id: string
    name: string
    arguments: string
    parsed_arguments: Record<string, any>
  }>
}

function Chat() {
  const [currentSessionId, setCurrentSessionId] = useState<string>(() => {
    return localStorage.getItem('currentSessionId') || 'default'
  })
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [toolCount, setToolCount] = useState(0)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState<string>('')
  const [currentToolExecutions, setCurrentToolExecutions] = useState<ToolExecution[]>([])
  const [statusMessage, setStatusMessage] = useState<string>('')
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentStreamingMessage, currentToolExecutions])

  useEffect(() => {
    // Fetch tool count on mount
    fetch('http://localhost:9000/health')
      .then(res => res.json())
      .then(data => {
        setToolCount(data.available_tools || 0)
      })
      .catch(err => console.error('Failed to fetch tools:', err))
  }, [])

  // Load conversation history when session changes
  useEffect(() => {
    const loadConversationHistory = async () => {
      try {
        const response = await fetch(`http://localhost:9000/chat/history/${currentSessionId}`)
        if (response.ok) {
          const data = await response.json()
          // Convert API messages to UI format
          const uiMessages: Message[] = data.messages
            .filter((msg: any) => msg.role === 'user' || msg.role === 'assistant')
            .map((msg: any) => ({
              role: msg.role,
              content: msg.content || ''
            }))
          setMessages(uiMessages)
        }
      } catch (err) {
        console.error('Failed to load conversation history:', err)
      }
    }

    loadConversationHistory()
    localStorage.setItem('currentSessionId', currentSessionId)
  }, [currentSessionId])

  const handleSessionChange = (newSessionId: string) => {
    setCurrentSessionId(newSessionId)
    setMessages([])
    setInput('')
    setCurrentStreamingMessage('')
    setCurrentToolExecutions([])
    setStatusMessage('')
  }

  const handleSessionCreate = async (sessionId: string, title: string) => {
    // Optionally, you can show a notification or perform additional actions
    console.log(`New session created: ${title} (${sessionId})`)
  }

  const sendMessage = async () => {
    if (!input.trim() || isProcessing) {
      return
    }

    const userMessage: Message = {
      role: 'user',
      content: input
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsProcessing(true)
    setCurrentStreamingMessage('')
    setCurrentToolExecutions([])
    setStatusMessage('Connecting...')

    try {
      const response = await fetch('http://localhost:9000/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          session_id: currentSessionId
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No reader available')
      }

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })

        // Process complete SSE messages
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || '' // Keep incomplete message in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.substring(6))
            handleStreamEvent(data)
          }
        }
      }

      // Finalize the streaming message
      if (currentStreamingMessage) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: currentStreamingMessage,
          toolExecutions: currentToolExecutions.length > 0 ? currentToolExecutions : undefined
        }])
      }

    } catch (error) {
      console.error('Streaming error:', error)
      setMessages(prev => [...prev, {
        role: 'system',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`
      }])
    } finally {
      setIsProcessing(false)
      setCurrentStreamingMessage('')
      setCurrentToolExecutions([])
      setStatusMessage('')
    }
  }

  const handleApprove = async (toolIds?: string[]) => {
    if (!pendingApproval) return

    try {
      await fetch(`http://localhost:9000/approvals/${pendingApproval.requestId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved: true,
          tool_ids: toolIds
        })
      })
      setPendingApproval(null)
      setStatusMessage('Approval granted, executing tools...')
    } catch (error) {
      console.error('Approval error:', error)
      setStatusMessage('Failed to send approval')
    }
  }

  const handleReject = async (reason?: string) => {
    if (!pendingApproval) return

    try {
      await fetch(`http://localhost:9000/approvals/${pendingApproval.requestId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved: false,
          reason
        })
      })
      setPendingApproval(null)
      setStatusMessage('Tool execution rejected')
    } catch (error) {
      console.error('Rejection error:', error)
      setStatusMessage('Failed to send rejection')
    }
  }

  const handleStreamEvent = (event: any) => {
    console.log('Stream event:', event)

    switch (event.type) {
      case 'status':
        setStatusMessage(event.data.message)
        break

      case 'llm_response':
        setCurrentStreamingMessage(event.data.content)
        break

      case 'tool_approval_required':
        setPendingApproval({
          requestId: event.data.request_id,
          toolCalls: event.data.tool_calls
        })
        setStatusMessage('⏸️ Waiting for tool execution approval...')
        break

      case 'tool_approval_granted':
        setPendingApproval(null)
        setStatusMessage('✓ Approval granted, executing tools...')
        break

      case 'tool_approval_rejected':
        setPendingApproval(null)
        setStatusMessage('✗ Tool execution rejected')
        break

      case 'tool_start':
        setCurrentToolExecutions(prev => [...prev, {
          id: event.data.tool_id,
          name: event.data.tool_name,
          status: 'running',
          arguments: event.data.arguments
        }])
        setStatusMessage(`Executing tool: ${event.data.tool_name}`)
        break

      case 'tool_end':
        setCurrentToolExecutions(prev => prev.map(tool =>
          tool.id === event.data.tool_id
            ? { ...tool, status: 'completed', result: event.data.result }
            : tool
        ))
        break

      case 'tool_error':
        setCurrentToolExecutions(prev => prev.map(tool =>
          tool.id === event.data.tool_id
            ? { ...tool, status: 'error', error: event.data.error }
            : tool
        ))
        break

      case 'complete':
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: event.data.response,
          toolExecutions: currentToolExecutions.length > 0 ? currentToolExecutions : undefined
        }])
        setCurrentStreamingMessage('')
        setCurrentToolExecutions([])
        setIsProcessing(false)
        setStatusMessage('')
        break

      case 'error':
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Error: ${event.data}`
        }])
        setIsProcessing(false)
        setStatusMessage('')
        break

      default:
        console.warn('Unknown event type:', event.type)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-container">
      {pendingApproval && (
        <ApprovalModal
          requestId={pendingApproval.requestId}
          toolCalls={pendingApproval.toolCalls}
          onApprove={handleApprove}
          onReject={handleReject}
        />
      )}

      <div className="chat-status">
        <SessionSelector
          currentSessionId={currentSessionId}
          onSessionChange={handleSessionChange}
          onSessionCreate={handleSessionCreate}
        />
        <div className="status-indicator">
          <span className="status-dot connected"></span>
          <span>Ready</span>
        </div>
        <div className="tools-count">
          {toolCount} MCP Tools Available
        </div>
      </div>

      <div className="messages-container">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="message-role">{msg.role}</div>
            <div className="message-content">
              {msg.content}

              {msg.toolExecutions && msg.toolExecutions.length > 0 && (
                <div className="tool-executions">
                  <div className="tool-executions-header">Tool Executions:</div>
                  {msg.toolExecutions.map((tool, toolIdx) => (
                    <div key={toolIdx} className={`tool-execution ${tool.status}`}>
                      <div className="tool-name">
                        <span className={`tool-status-icon ${tool.status}`}>
                          {tool.status === 'running' && '⏳'}
                          {tool.status === 'completed' && '✓'}
                          {tool.status === 'error' && '✗'}
                        </span>
                        {tool.name}
                      </div>
                      {tool.result && (
                        <div className="tool-result">
                          <details>
                            <summary>Result</summary>
                            <pre>{tool.result}</pre>
                          </details>
                        </div>
                      )}
                      {tool.error && (
                        <div className="tool-error">Error: {tool.error}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isProcessing && (
          <div className="message assistant streaming">
            <div className="message-role">assistant</div>
            <div className="message-content">
              {statusMessage && (
                <div className="status-message">{statusMessage}</div>
              )}

              {currentStreamingMessage && (
                <div className="streaming-text">{currentStreamingMessage}</div>
              )}

              {currentToolExecutions.length > 0 && (
                <div className="tool-executions">
                  <div className="tool-executions-header">Tool Executions:</div>
                  {currentToolExecutions.map((tool, toolIdx) => (
                    <div key={toolIdx} className={`tool-execution ${tool.status}`}>
                      <div className="tool-name">
                        <span className={`tool-status-icon ${tool.status}`}>
                          {tool.status === 'running' && '⏳'}
                          {tool.status === 'completed' && '✓'}
                          {tool.status === 'error' && '✗'}
                        </span>
                        {tool.name}
                      </div>
                      {tool.result && (
                        <div className="tool-result">
                          <details>
                            <summary>Result</summary>
                            <pre>{tool.result}</pre>
                          </details>
                        </div>
                      )}
                      {tool.error && (
                        <div className="tool-error">Error: {tool.error}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {!currentStreamingMessage && !currentToolExecutions.length && (
                <div className="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="input-container">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
          disabled={isProcessing}
          rows={3}
        />
        <button
          onClick={sendMessage}
          disabled={!input.trim() || isProcessing}
          className="send-button"
        >
          {isProcessing ? 'Processing...' : 'Send'}
        </button>
      </div>
    </div>
  )
}

export default Chat
