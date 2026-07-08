import { useEffect, useRef, useState } from 'react'

const STATUS_BADGE = {
  pending:               'bg-amber-50 text-amber-600',
  running:               'bg-blue-50 text-blue-600',
  awaiting_confirmation: 'bg-amber-50 text-amber-600',
  completed:             'bg-emerald-50 text-emerald-600',
  failed:                'bg-red-50 text-red-500',
}

function stepStyle(content) {
  if (content.startsWith('[model]'))  return 'text-blue-500'
  if (content.startsWith('[tools]'))  return 'text-emerald-600'
  if (content.startsWith('[ERROR]'))  return 'text-red-500'
  return 'text-slate-400'
}

// Shared by both step parsers below — each module emits a different step-string
// vocabulary, but they collapse onto the same four visual outcome categories.
const OUTCOME_META = {
  success: { icon: '✓', chip: 'bg-emerald-50 text-emerald-600' },
  failure: { icon: '✕', chip: 'bg-red-50 text-red-500' },
  warn:    { icon: '⚠', chip: 'bg-amber-50 text-amber-600' },
  info:    { icon: '›', chip: 'bg-slate-100 text-slate-400' },
}

function OutcomeRow({ parsed }) {
  const { icon, chip } = OUTCOME_META[parsed.kind]
  return (
    <div className="flex items-start gap-3 py-2">
      <span className={`shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-semibold ${chip}`}>
        {icon}
      </span>
      <div className="flex-1 min-w-0 text-sm text-slate-600 leading-snug">
        {parsed.label && <span className="font-medium text-slate-700">{parsed.label}</span>}
        {parsed.label && parsed.statusText && ' — '}
        {parsed.statusText}
        {parsed.detail && (
          <span className="block text-xs text-slate-400 mt-0.5 break-words">{parsed.detail}</span>
        )}
      </div>
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
    <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 flex flex-col gap-3 my-1">
      <div className="flex items-center gap-2 text-xs font-semibold text-amber-700">
        <span className="w-5 h-5 rounded-full bg-amber-100 flex items-center justify-center">⚠</span>
        Email draft — needs your confirmation
      </div>
      <div className="text-sm text-slate-600 flex flex-col gap-0.5">
        <div><span className="text-slate-400">To </span>{toEmail}</div>
        <div><span className="text-slate-400">Subject </span>{draft?.subject ?? subject}</div>
      </div>
      {draft && (
        <p className="text-xs text-slate-500 whitespace-pre-wrap leading-relaxed border-t border-amber-200/60 pt-2">
          {draft.body}
        </p>
      )}
      {resolved === null || resolved === 'pending_confirmation' ? (
        <div className="flex gap-2 pt-1">
          <button
            onClick={() => act('send')}
            disabled={pendingAction !== null}
            className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm shadow-blue-600/20 transition-colors"
          >
            {pendingAction === 'send' ? 'Sending…' : 'Send'}
          </button>
          <button
            onClick={() => act('discard')}
            disabled={pendingAction !== null}
            className="px-4 py-1.5 bg-white hover:bg-slate-50 border border-slate-200 disabled:opacity-50 text-slate-500 text-xs font-semibold rounded-lg transition-colors"
          >
            {pendingAction === 'discard' ? 'Discarding…' : 'Discard'}
          </button>
        </div>
      ) : (
        <p className={`text-xs font-semibold ${
          resolved === 'sent' ? 'text-emerald-600' : resolved === 'failed' ? 'text-red-500' : 'text-slate-400'
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
    <div className="bg-white rounded-2xl shadow-sm shadow-slate-200 p-4 flex flex-col gap-1">
      <div className="flex items-start justify-between gap-2 pb-2">
        <p className="text-sm text-slate-700 font-medium leading-snug">{task.command}</p>
        <span className={`shrink-0 text-xs px-2.5 py-1 rounded-full font-semibold ${STATUS_BADGE[task.status] ?? 'bg-slate-100 text-slate-400'}`}>
          {task.status}
        </span>
      </div>

      {task.steps.length > 0 && (
        <div className="flex flex-col divide-y divide-slate-100 border-t border-slate-100 max-h-72 overflow-y-auto">
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
            return <p key={i} className={`text-xs font-mono leading-relaxed py-1.5 ${stepStyle(s)}`}>{s}</p>
          })}
          <div ref={bottomRef} />
        </div>
      )}

      {task.live && task.steps.length === 0 && (
        <p className="text-xs text-slate-400 animate-pulse pt-1">Waiting for agent…</p>
      )}
    </div>
  )
}

export default function ActivityLog({ tasks, onTaskUpdate }) {
  if (tasks.length === 0) {
    return (
      <div className="bg-white rounded-2xl shadow-sm shadow-slate-200 text-center text-slate-400 text-sm py-14">
        No tasks yet. Run a command above.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 px-1">Activity Log</h2>
      {tasks.map(task => (
        <TaskCard key={task.taskId} task={task} onTaskUpdate={onTaskUpdate} />
      ))}
    </div>
  )
}
