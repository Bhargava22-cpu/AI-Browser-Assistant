import { useState } from 'react'
import CommandBar from './components/CommandBar'
import ActivityLog from './components/ActivityLog'
import ProfileSettings from './components/ProfileSettings'

const TABS = [
  { key: 'agent', label: 'Agent' },
  { key: 'profile', label: 'Profile' },
]

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
    <div className="min-h-screen bg-gradient-to-b from-[#eef2fb] to-[#e3e9f7]">
      <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-5">
        <header className="bg-white rounded-2xl shadow-sm shadow-slate-200 px-5 py-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center text-lg font-semibold shrink-0">
              A
            </div>
            <div>
              <h1 className="text-base font-semibold text-slate-800 leading-tight">AI Browser Agent</h1>
              <p className="text-xs text-slate-400">Autonomous browsing, on command</p>
            </div>
          </div>

          <nav className="flex items-center gap-1 bg-slate-100 rounded-full p-1">
            {TABS.map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${
                  tab === t.key
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/30'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </header>

        <main className="flex flex-col gap-5">
          {tab === 'agent' && (
            <>
              <section className="bg-white rounded-2xl shadow-sm shadow-slate-200 p-5">
                <CommandBar onTaskStarted={addTask} />
              </section>
              <ActivityLog tasks={tasks} onTaskUpdate={updateTask} />
            </>
          )}
          {tab === 'profile' && (
            <section className="bg-white rounded-2xl shadow-sm shadow-slate-200 p-5">
              <ProfileSettings />
            </section>
          )}
        </main>
      </div>
    </div>
  )
}
