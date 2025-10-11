import { useState, useEffect, useRef } from 'react'
import './Chat.css'

interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
}

function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [toolCount, setToolCount] = useState(0)

  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket('ws://localhost:8000/ws/chat')

    ws.onopen = () => {
      console.log('WebSocket connected')
      setIsConnected(true)
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      console.log('Received:', data)

      if (data.type === 'connection') {
        setToolCount(data.available_tools)
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Connected! ${data.available_tools} tools available from MCP servers.`
        }])
      } else if (data.type === 'processing') {
        setIsProcessing(true)
      } else if (data.type === 'message') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.response
        }])
        setIsProcessing(false)
      } else if (data.type === 'error') {
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Error: ${data.message}`
        }])
        setIsProcessing(false)
      }
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      setIsConnected(false)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setIsConnected(false)
    }

    wsRef.current = ws

    return () => {
      ws.close()
    }
  }, [])

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return
    }

    const userMessage: Message = {
      role: 'user',
      content: input
    }

    setMessages(prev => [...prev, userMessage])

    wsRef.current.send(JSON.stringify({
      message: input,
      session_id: 'default'
    }))

    setInput('')
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-status">
        <div className="status-indicator">
          <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
        <div className="tools-count">
          {toolCount} MCP Tools Available
        </div>
      </div>

      <div className="messages-container">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="message-role">{msg.role}</div>
            <div className="message-content">{msg.content}</div>
          </div>
        ))}
        {isProcessing && (
          <div className="message assistant">
            <div className="message-role">assistant</div>
            <div className="message-content typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-container">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
          disabled={!isConnected}
          rows={3}
        />
        <button
          onClick={sendMessage}
          disabled={!isConnected || !input.trim() || isProcessing}
          className="send-button"
        >
          Send
        </button>
      </div>
    </div>
  )
}

export default Chat
