import { useState } from 'react'
import CommandBar from './components/CommandBar'
import ActivityLog from './components/ActivityLog'
import ProfileSettings from './components/ProfileSettings'

export default function App() {
  const [tab, setTab] = useState('agent')
  const [tasks, setTasks] = useState([])

  function addTask(taskId, command) {
    setTasks(prev => [{ taskId, command, status: 'pending', steps: [], live: true }, ...prev])
  }

  function updateTask(taskId, patch) {
    setTasks(prev => prev.map(t => t.taskId === taskId ? { ...t, ...patch } : t))
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
        <span className="text-xl font-semibold tracking-tight">AI Browser Agent</span>
      </header>

      {/* Tab nav */}
      <nav className="border-b border-gray-800 px-6 flex gap-1">
        {['agent', 'profile'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm capitalize transition-colors ${
              tab === t
                ? 'text-indigo-400 border-b-2 border-indigo-400'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {t === 'agent' ? 'Agent' : 'Profile'}
          </button>
        ))}
      </nav>

      {/* Content */}
      <main className="flex-1 max-w-3xl w-full mx-auto px-4 py-6 flex flex-col gap-6">
        {tab === 'agent' && (
          <>
            <CommandBar onTaskStarted={addTask} />
            <ActivityLog tasks={tasks} onTaskUpdate={updateTask} />
          </>
        )}
        {tab === 'profile' && <ProfileSettings />}
      </main>
    </div>
  )
}
