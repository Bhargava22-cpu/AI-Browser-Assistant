import { useState } from 'react'
import CommandBar from './components/CommandBar'
import ActivityLog from './components/ActivityLog'
import ProfileSettings from './components/ProfileSettings'
import { CalendarIcon, FormIcon, MailIcon, SearchIcon, SparkleIcon } from './components/icons'

const TABS = [
  { key: 'agent', label: 'Agent' },
  { key: 'profile', label: 'Profile' },
]

const CAPABILITIES = [
  { icon: FormIcon, label: 'Fills forms' },
  { icon: MailIcon, label: 'Drafts emails' },
  { icon: CalendarIcon, label: 'Schedules events' },
  { icon: SearchIcon, label: 'Reads pages' },
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
    <div className="min-h-screen bg-gradient-to-b from-[#eef2fb] via-[#e9edfb] to-[#dde4f7]">
      <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-5">
        <header className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-6 py-7 shadow-lg shadow-indigo-950/20">
          <div className="pointer-events-none absolute -top-16 -right-16 w-56 h-56 rounded-full bg-blue-500/20 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-20 -left-10 w-48 h-48 rounded-full bg-violet-500/10 blur-3xl" />

          <div className="relative flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 text-white flex items-center justify-center shadow-md shadow-blue-900/40 shrink-0">
                <SparkleIcon className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-lg font-bold text-white leading-tight">AI Browser Agent</h1>
                <p className="text-xs text-slate-400">Autonomous browsing, on command</p>
              </div>
            </div>

            <nav className="flex items-center gap-1 bg-white/10 backdrop-blur rounded-full p-1">
              {TABS.map(t => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${
                    tab === t.key
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-300 hover:text-white'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          </div>

          <p className="relative mt-5 max-w-md text-sm text-slate-300 leading-relaxed">
            Give it one command — it plans, browses, and gets things done, always
            checking with you before it sends or creates anything real.
          </p>

          <div className="relative mt-4 flex flex-wrap gap-2">
            {CAPABILITIES.map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="inline-flex items-center gap-1.5 rounded-full bg-white/10 text-slate-200 text-xs font-medium px-3 py-1.5"
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </span>
            ))}
          </div>
        </header>

        <main className="flex flex-col gap-5">
          {tab === 'agent' && (
            <>
              <section className="bg-white rounded-3xl shadow-sm shadow-slate-200 p-5">
                <CommandBar onTaskStarted={addTask} />
              </section>
              <ActivityLog tasks={tasks} onTaskUpdate={updateTask} />
            </>
          )}
          {tab === 'profile' && (
            <section className="bg-white rounded-3xl shadow-sm shadow-slate-200 p-5">
              <ProfileSettings />
            </section>
          )}
        </main>
      </div>
    </div>
  )
}
