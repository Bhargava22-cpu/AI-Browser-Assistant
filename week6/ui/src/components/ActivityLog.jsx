import { useEffect, useRef } from 'react'

const STATUS_BADGE = {
  pending:   'bg-yellow-900 text-yellow-300',
  running:   'bg-blue-900 text-blue-300',
  completed: 'bg-emerald-900 text-emerald-300',
  failed:    'bg-red-900 text-red-300',
}

function stepStyle(content) {
  if (content.startsWith('[model]'))  return 'text-indigo-300'
  if (content.startsWith('[tools]'))  return 'text-emerald-300'
  if (content.startsWith('[ERROR]'))  return 'text-red-400'
  return 'text-gray-400'
}

function TaskCard({ task, onTaskUpdate }) {
  const bottomRef = useRef(null)
  // Accumulate steps here so the WebSocket closure doesn't go stale
  const stepsRef = useRef([])

  useEffect(() => {
    if (!task.live) return
    stepsRef.current = []

    let cancelled = false
    const ws = new WebSocket(`ws://${location.host}/ws/${task.taskId}`)

    ws.onmessage = (e) => {
      if (cancelled) return
      let msg
      try {
        msg = JSON.parse(e.data)
      } catch {
        return
      }
      if (msg.type === 'step') {
        stepsRef.current = [...stepsRef.current, msg.content]
        onTaskUpdate(task.taskId, { steps: stepsRef.current, status: 'running' })
      } else if (msg.type === 'done') {
        onTaskUpdate(task.taskId, { status: msg.status, live: false })
        ws.close()
      } else if (msg.type === 'error') {
        onTaskUpdate(task.taskId, { status: 'failed', live: false })
        ws.close()
      }
    }

    ws.onerror = () => {
      if (!cancelled) onTaskUpdate(task.taskId, { status: 'failed', live: false })
    }

    return () => {
      cancelled = true
      ws.close()
    }
  }, [task.taskId, task.live]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [task.steps.length])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-gray-200 font-medium leading-snug">{task.command}</p>
        <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[task.status] ?? 'bg-gray-800 text-gray-400'}`}>
          {task.status}
        </span>
      </div>

      {task.steps.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-gray-800 pt-3 max-h-64 overflow-y-auto">
          {task.steps.map((s, i) => (
            <p key={i} className={`text-xs font-mono leading-relaxed ${stepStyle(s)}`}>{s}</p>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      {task.live && task.steps.length === 0 && (
        <p className="text-xs text-gray-500 animate-pulse">Waiting for agent…</p>
      )}
    </div>
  )
}

export default function ActivityLog({ tasks, onTaskUpdate }) {
  if (tasks.length === 0) {
    return (
      <div className="text-center text-gray-600 text-sm py-16">
        No tasks yet. Run a command above.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500">Activity Log</h2>
      {tasks.map(task => (
        <TaskCard key={task.taskId} task={task} onTaskUpdate={onTaskUpdate} />
      ))}
    </div>
  )
}
