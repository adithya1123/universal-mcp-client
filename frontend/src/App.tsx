import { useState } from 'react'
import './App.css'
import Chat from './components/Chat'
import ServerManager from './components/ServerManager'

function App() {
  const [showServerManager, setShowServerManager] = useState(false)

  return (
    <div className="App">
      {showServerManager && (
        <ServerManager onClose={() => setShowServerManager(false)} />
      )}

      <header className="App-header">
        <div className="header-content">
          <div>
            <h1>Universal MCP Client</h1>
            <p>Agentic Chat Assistant with MCP Server Integration</p>
          </div>
          <button
            className="btn-servers"
            onClick={() => setShowServerManager(true)}
            title="Manage MCP Servers"
          >
            🔧 Servers
          </button>
        </div>
      </header>
      <main className="App-main">
        <Chat />
      </main>
    </div>
  )
}

export default App
