import './App.css'
import Chat from './components/Chat'

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>Universal MCP Client</h1>
        <p>Agentic Chat Assistant with MCP Server Integration</p>
      </header>
      <main className="App-main">
        <Chat />
      </main>
    </div>
  )
}

export default App
