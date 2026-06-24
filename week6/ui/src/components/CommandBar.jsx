import { useState } from 'react'

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
      <div className="flex gap-2">
        <input
          type="text"
          value={command}
          onChange={e => setCommand(e.target.value)}
          placeholder="Enter a command — e.g. go to python.org and tell me the latest version"
          disabled={loading}
          className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !command.trim()}
          className="px-5 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? 'Queuing…' : 'Run'}
        </button>
      </div>
      {error && <p className="text-red-400 text-xs">{error}</p>}
    </form>
  )
}
