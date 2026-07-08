import { useEffect, useRef, useState } from 'react'

const STATUS_BADGE = {
  pending:              'bg-yellow-900 text-yellow-300',
  running:              'bg-blue-900 text-blue-300',
  awaiting_confirmation: 'bg-amber-900 text-amber-300',
  completed:            'bg-emerald-900 text-emerald-300',
  failed:               'bg-red-900 text-red-300',
}

function stepStyle(content) {
  if (content.startsWith('[model]'))  return 'text-indigo-300'
  if (content.startsWith('[tools]'))  return 'text-emerald-300'
  if (content.startsWith('[ERROR]'))  return 'text-red-400'
  return 'text-gray-400'
}

// Shared by both step parsers below — each module emits a different step-string
// vocabulary, but they collapse onto the same four visual outcome categories.
const OUTCOME_META = {
  success: { icon: '✓', className: 'text-emerald-300' },
  failure: { icon: '✕', className: 'text-red-400' },
  warn:    { icon: '⚠', className: 'text-amber-300' },
  info:    { icon: '›', className: 'text-gray-400' },
}

function OutcomeRow({ parsed }) {
  const { icon, className } = OUTCOME_META[parsed.kind]
  return (
    <div className={`flex items-start gap-2 text-xs font-mono leading-relaxed ${className}`}>
      <span className="shrink-0">{icon}</span>
      <span className="flex-1 min-w-0">
        {parsed.label && <span className="font-medium">{parsed.label}</span>}
        {parsed.label && parsed.statusText && ' — '}
        {parsed.statusText}
        {parsed.detail && (
          <span className="block text-[11px] opacity-75 mt-0.5 break-words">{parsed.detail}</span>
        )}
      </span>
    </div>
  )
}

// Parses the "[form_filling] ..." step strings emitted by week5/agent_runner.py's
// _blocking_run_fill_form into a structured outcome so they can render as rows
// instead of raw log lines.
function parseFormFillingStep(content) {
  if (!content.startsWith('[form_filling]')) return null

  let m = content.match(/^\[form_filling\] resume upload: (uploaded|FAILED \((.*)\))$/)
  if (m) {
    const failed = m[1].startsWith('FAILED')
    return { kind: failed ? 'failure' : 'success', label: 'Resume upload', statusText: failed ? 'failed' : 'uploaded', detail: failed ? m[2] : null }
  }

  m = content.match(/^\[form_filling\] needs manual input: (.+?) — (.+)$/)
  if (m) {
    return { kind: 'warn', label: m[1], statusText: 'needs manual input', detail: m[2] }
  }

  m = content.match(/^\[form_filling\]\[warning\] (.+)$/)
  if (m) {
    return { kind: 'warn', label: null, statusText: null, detail: m[1] }
  }

  m = content.match(/^\[form_filling\] (.+?): (filled|FAILED \((.*)\))$/)
  if (m) {
    const failed = m[2].startsWith('FAILED')
    return { kind: failed ? 'failure' : 'success', label: m[1], statusText: failed ? 'failed' : 'filled', detail: failed ? m[3] : null }
  }

  return { kind: 'info', label: null, statusText: null, detail: content.replace('[form_filling] ', '') }
}

// Parses the "[email] ..." step strings emitted by week5/agent_runner.py's
// _run_email / confirm_email_send / discard_email_draft. The "Draft ready"
// line is special-cased separately since it needs to render as an interactive
// card (fetch full body, Send/Discard buttons), not a log row.
function parseEmailStep(content) {
  if (!content.startsWith('[email]')) return null

  let m = content.match(/^\[email\] Draft ready — to: (.+?) \| subject: (.+?) \(draft_id=([\w-]+)\)$/)
  if (m) {
    return { draft: true, toEmail: m[1], subject: m[2], draftId: m[3] }
  }

  m = content.match(/^\[email\] sent to (.+)$/)
  if (m) {
    return { draft: false, kind: 'success', label: null, statusText: `Sent to ${m[1]}`, detail: null }
  }

  m = content.match(/^\[email\] send FAILED \((.*)\)$/)
  if (m) {
    return { draft: false, kind: 'failure', label: null, statusText: 'Send failed', detail: m[1] }
  }

  if (content === '[email] discarded by user') {
    return { draft: false, kind: 'warn', label: null, statusText: 'Discarded', detail: null }
  }

  return { draft: false, kind: 'info', label: null, statusText: null, detail: content.replace('[email] ', '') }
}

function EmailDraftCard({ draftId, toEmail, subject, taskId, onTaskUpdate }) {
  const [draft, setDraft] = useState(null)
  const [pendingAction, setPendingAction] = useState(null) // null | 'send' | 'discard'
  const [resolved, setResolved] = useState(null) // null | 'sent' | 'failed' | 'discarded'
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    fetch(`/email/drafts/${draftId}`)
      .then(r => r.json())
      .then(data => {
        if (cancelled) return
        setDraft(data)
        if (data.status !== 'pending_confirmation') {
          setResolved(data.status)
          if (data.error) setError(data.error)
        }
      })
      .catch(err => console.error('Failed to load email draft:', err))
    return () => { cancelled = true }
  }, [draftId])

  async function act(action) {
    setPendingAction(action)
    try {
      const res = await fetch(`/email/drafts/${draftId}/${action}`, { method: 'POST' })
      const data = await res.json()
      setDraft(data)
      setResolved(data.status)
      if (data.error) setError(data.error)
      onTaskUpdate(taskId, { status: data.status === 'failed' ? 'failed' : 'completed' })
    } catch (err) {
      setError(err.message)
    } finally {
      setPendingAction(null)
    }
  }

  return (
    <div className="border border-amber-900/50 bg-amber-950/20 rounded-lg p-3 flex flex-col gap-2">
      <div className="flex items-center gap-2 text-xs text-amber-300">
        <span>⚠</span>
        <span className="font-medium">Email draft — needs your confirmation</span>
      </div>
      <div className="text-xs text-gray-300 flex flex-col gap-0.5">
        <div><span className="text-gray-500">To:</span> {toEmail}</div>
        <div><span className="text-gray-500">Subject:</span> {draft?.subject ?? subject}</div>
      </div>
      {draft && (
        <p className="text-xs text-gray-400 whitespace-pre-wrap font-mono leading-relaxed border-t border-gray-800 pt-2">
          {draft.body}
        </p>
      )}
      {resolved === null || resolved === 'pending_confirmation' ? (
        <div className="flex gap-2 pt-1">
          <button
            onClick={() => act('send')}
            disabled={pendingAction !== null}
            className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 text-white text-xs font-medium rounded-md transition-colors"
          >
            {pendingAction === 'send' ? 'Sending…' : 'Send'}
          </button>
          <button
            onClick={() => act('discard')}
            disabled={pendingAction !== null}
            className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 text-xs font-medium rounded-md transition-colors"
          >
            {pendingAction === 'discard' ? 'Discarding…' : 'Discard'}
          </button>
        </div>
      ) : (
        <p className={`text-xs font-medium ${
          resolved === 'sent' ? 'text-emerald-300' : resolved === 'failed' ? 'text-red-400' : 'text-gray-400'
        }`}>
          {resolved === 'sent' && '✓ Sent'}
          {resolved === 'failed' && `✕ Send failed${error ? `: ${error}` : ''}`}
          {resolved === 'discarded' && '⚠ Discarded'}
        </p>
      )}
    </div>
  )
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
          {task.steps.map((s, i) => {
            const emailParsed = parseEmailStep(s)
            if (emailParsed) {
              return emailParsed.draft
                ? (
                  <EmailDraftCard
                    key={i}
                    draftId={emailParsed.draftId}
                    toEmail={emailParsed.toEmail}
                    subject={emailParsed.subject}
                    taskId={task.taskId}
                    onTaskUpdate={onTaskUpdate}
                  />
                )
                : <OutcomeRow key={i} parsed={emailParsed} />
            }
            const formParsed = parseFormFillingStep(s)
            if (formParsed) return <OutcomeRow key={i} parsed={formParsed} />
            return <p key={i} className={`text-xs font-mono leading-relaxed ${stepStyle(s)}`}>{s}</p>
          })}
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
