import { useState } from 'react'
import { ArrowIcon, SearchIcon } from './icons'

export default function CommandBar({ onTaskStarted }) {
  const [command, setCommand] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    const cmd = command.trim()
    if (!cmd) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
      })
      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const { task_id } = await res.json()
      onTaskStarted(task_id, cmd)
      setCommand('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">Command</label>
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={command}
            onChange={e => setCommand(e.target.value)}
            placeholder="e.g. fill the form at ... with my details"
            disabled={loading}
            className="w-full bg-slate-50 border border-slate-200 rounded-full pl-11 pr-4 py-3 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 disabled:opacity-50"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !command.trim()}
          className="inline-flex items-center justify-center gap-1.5 px-6 py-3 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-full shadow-sm shadow-slate-900/20 transition-colors"
        >
          {loading ? 'Queuing…' : 'Run'}
          {!loading && <ArrowIcon className="w-4 h-4" />}
        </button>
      </div>
      {error && <p className="text-red-500 text-xs">{error}</p>}
    </form>
  )
}
