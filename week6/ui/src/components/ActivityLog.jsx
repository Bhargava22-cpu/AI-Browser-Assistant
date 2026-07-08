import { useEffect, useRef, useState } from 'react'

const STATUS_BADGE = {
  pending:               'bg-amber-50 text-amber-600',
  running:               'bg-blue-50 text-blue-600',
  awaiting_confirmation: 'bg-amber-50 text-amber-600',
  awaiting_input:        'bg-amber-50 text-amber-600',
  completed:             'bg-emerald-50 text-emerald-600',
  failed:                'bg-red-50 text-red-500',
}

function stepStyle(content) {
  if (content.startsWith('[model]'))  return 'text-blue-500'
  if (content.startsWith('[tools]'))  return 'text-emerald-600'
  if (content.startsWith('[ERROR]'))  return 'text-red-500'
  return 'text-slate-400'
}

// Shared by FormFillAskCard and DraftConfirmCard — both render an inline amber
// "needs your input" card with a compact text field, and should stay visually
// in sync without duplicating the class strings at each call site.
const INLINE_ACTION_CARD_CLASS = 'rounded-2xl border border-amber-200 bg-amber-50/60 p-4 flex flex-col gap-3 my-1'
const INLINE_TEXT_INPUT_CLASS = 'flex-1 min-w-0 text-xs px-3 py-1.5 rounded-lg border border-amber-200 bg-white disabled:opacity-50 focus:outline-none focus:ring-1 focus:ring-blue-500'

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
// _blocking_run_fill_form / answer_task_reply into a structured outcome so they can
// render as rows instead of raw log lines. The "[ask]" line is special-cased
// separately, same as email/calendar drafts, since it renders as an interactive
// reply card, not a log row.
function parseFormFillingStep(content) {
  if (!content.startsWith('[form_filling]')) return null

  let m = content.match(/^\[form_filling\]\[ask\] (.+)$/)
  if (m) {
    return { ask: true, question: m[1] }
  }

  m = content.match(/^\[form_filling\] resume upload: (uploaded|FAILED \((.*)\))$/)
  if (m) {
    const failed = m[1].startsWith('FAILED')
    return { ask: false, kind: failed ? 'failure' : 'success', label: 'Resume upload', statusText: failed ? 'failed' : 'uploaded', detail: failed ? m[2] : null }
  }

  m = content.match(/^\[form_filling\] needs manual input: (.+?) — (.+)$/)
  if (m) {
    return { ask: false, kind: 'warn', label: m[1], statusText: 'needs manual input', detail: m[2] }
  }

  m = content.match(/^\[form_filling\]\[warning\] (.+)$/)
  if (m) {
    return { ask: false, kind: 'warn', label: null, statusText: null, detail: m[1] }
  }

  if (content === '[form_filling] all questions answered') {
    return { ask: false, kind: 'success', label: null, statusText: 'All questions answered', detail: null }
  }

  m = content.match(/^\[form_filling\] (.+?): (filled|FAILED \((.*)\))$/)
  if (m) {
    const failed = m[2].startsWith('FAILED')
    return { ask: false, kind: failed ? 'failure' : 'success', label: m[1], statusText: failed ? 'failed' : 'filled', detail: failed ? m[3] : null }
  }

  return { ask: false, kind: 'info', label: null, statusText: null, detail: content.replace('[form_filling] ', '') }
}

function FormFillAskCard({ taskId, question, onTaskUpdate }) {
  const [message, setMessage] = useState('')
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function send() {
    if (!message.trim()) return
    setPending(true)
    try {
      const res = await fetch(`/tasks/${taskId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message.trim() }),
      })
      const data = await res.json()
      if (res.ok) {
        setResult(data)
        setMessage('')
        onTaskUpdate(taskId, { status: data.status })
      } else {
        setError(data.detail || 'Reply failed')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className={INLINE_ACTION_CARD_CLASS}>
      <div className="flex items-center gap-2 text-xs font-semibold text-amber-700">
        <span className="w-5 h-5 rounded-full bg-amber-100 flex items-center justify-center">?</span>
        <span className="font-normal text-slate-600">{question}</span>
      </div>
      {result && (
        <div className="text-xs text-slate-600 flex flex-col gap-0.5">
          {result.filled.map((f, i) => (
            <div key={i} className={f.success ? 'text-emerald-600' : 'text-red-500'}>
              {f.success ? '✓' : '✕'} {f.label}{!f.success && f.error ? `: ${f.error}` : ''}
            </div>
          ))}
          {result.still_missing.length > 0 && (
            <div className="text-amber-600 mt-1">Still need: {result.still_missing.join(', ')}</div>
          )}
        </div>
      )}
      {(!result || result.status !== 'completed') && (
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your answer(s)…"
            disabled={pending}
            className={INLINE_TEXT_INPUT_CLASS}
          />
          <button
            onClick={send}
            disabled={pending || !message.trim()}
            className="shrink-0 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm shadow-blue-600/20 transition-colors"
          >
            {pending ? 'Sending…' : 'Reply'}
          </button>
        </div>
      )}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
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

// Parses the "[calendar] ..." step strings emitted by week5/agent_runner.py's
// _run_calendar / confirm_calendar_event / discard_calendar_draft. The "Draft ready"
// line is special-cased separately, same as email, since it renders as an interactive
// card (fetch full event details, Confirm/Discard buttons), not a log row.
function parseCalendarStep(content) {
  if (!content.startsWith('[calendar]')) return null

  let m = content.match(/^\[calendar\] Draft ready — (.+?) at (.+?) \(draft_id=([\w-]+)\)$/)
  if (m) {
    return { draft: true, title: m[1], start: m[2], draftId: m[3] }
  }

  m = content.match(/^\[calendar\] created: (.+?) \(event_id=(.+)\)$/)
  if (m) {
    return { draft: false, kind: 'success', label: null, statusText: `Added "${m[1]}" to calendar`, detail: null }
  }

  m = content.match(/^\[calendar\] create FAILED \((.*)\)$/)
  if (m) {
    return { draft: false, kind: 'failure', label: null, statusText: 'Create failed', detail: m[1] }
  }

  if (content === '[calendar] discarded by user') {
    return { draft: false, kind: 'warn', label: null, statusText: 'Discarded', detail: null }
  }

  return { draft: false, kind: 'info', label: null, statusText: null, detail: content.replace('[calendar] ', '') }
}

// Shared by EmailDraftCard and CalendarEventDraftCard: fetch-on-mount, a primary
// action + Discard, and a pending/resolved state machine. Each caller supplies its
// own endpoint, field rendering, and resolved-status labels via render props —
// only the confirmation *mechanics* are common, not the domain fields.
function DraftConfirmCard({
  endpoint,
  draftId,
  heading,
  initial,
  renderFields,
  renderBody,
  primaryAction,
  resolvedLabels,
  reviseAction, // optional: { key, label, pendingLabel, placeholder } — draft types that
  // support revision (email) pass this; ones that don't (calendar) simply omit it.
  taskId,
  onTaskUpdate,
}) {
  const [draft, setDraft] = useState(null)
  const [pendingAction, setPendingAction] = useState(null) // null | primaryAction.key | 'discard' | reviseAction.key
  const [resolved, setResolved] = useState(null) // null | pending_confirmation | one of resolvedLabels' keys
  const [error, setError] = useState(null)
  const [feedback, setFeedback] = useState('')

  useEffect(() => {
    let cancelled = false
    fetch(`${endpoint}/${draftId}`)
      .then(r => r.json())
      .then(data => {
        if (cancelled) return
        setDraft(data)
        if (data.status !== 'pending_confirmation') {
          setResolved(data.status)
          if (data.error) setError(data.error)
        }
      })
      .catch(err => console.error(`Failed to load draft from ${endpoint}:`, err))
    return () => { cancelled = true }
  }, [endpoint, draftId])

  // Resolving actions (send/confirm/discard) end the confirmation loop and update
  // the task's overall status; revise re-composes the draft in place and leaves
  // both untouched, so it's handled separately below.
  async function resolveWith(action) {
    setPendingAction(action)
    try {
      const res = await fetch(`${endpoint}/${draftId}/${action}`, { method: 'POST' })
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

  async function revise() {
    if (!reviseAction || !feedback.trim()) return
    setPendingAction(reviseAction.key)
    try {
      const res = await fetch(`${endpoint}/${draftId}/${reviseAction.key}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback: feedback.trim() }),
      })
      const data = await res.json()
      if (res.ok) {
        setDraft(data)
        setFeedback('')
      } else {
        setError(data.detail || 'Revision failed')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setPendingAction(null)
    }
  }

  // Fields not yet present on `initial` (e.g. a calendar draft's `end`/`recurrence`,
  // an email draft's `body`) simply read as undefined until the fetch resolves.
  // `initial` never carries a real `to_email`/etc. key from the backend, so it wins
  // permanently for fields the backend response doesn't echo back under the same name.
  const merged = { ...initial, ...(draft || {}) }
  const body = renderBody(merged)
  const resolvedInfo = resolved && (resolvedLabels[resolved] ?? { colorClass: 'text-slate-400', text: () => resolved })
  const isPending = resolved === null || resolved === 'pending_confirmation'

  return (
    <div className={INLINE_ACTION_CARD_CLASS}>
      <div className="flex items-center gap-2 text-xs font-semibold text-amber-700">
        <span className="w-5 h-5 rounded-full bg-amber-100 flex items-center justify-center">⚠</span>
        {heading}
      </div>
      <div className="text-sm text-slate-600 flex flex-col gap-0.5">
        {renderFields(merged)}
      </div>
      {body && (
        <p className="text-xs text-slate-500 whitespace-pre-wrap leading-relaxed border-t border-amber-200/60 pt-2">
          {body}
        </p>
      )}
      {isPending ? (
        <div className="flex flex-col gap-2 pt-1">
          <div className="flex gap-2">
            <button
              onClick={() => resolveWith(primaryAction.key)}
              disabled={pendingAction !== null}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-sm shadow-blue-600/20 transition-colors"
            >
              {pendingAction === primaryAction.key ? primaryAction.pendingLabel : primaryAction.label}
            </button>
            <button
              onClick={() => resolveWith('discard')}
              disabled={pendingAction !== null}
              className="px-4 py-1.5 bg-white hover:bg-slate-50 border border-slate-200 disabled:opacity-50 text-slate-500 text-xs font-semibold rounded-lg transition-colors"
            >
              {pendingAction === 'discard' ? 'Discarding…' : 'Discard'}
            </button>
          </div>
          {reviseAction && (
            <div className="flex gap-2">
              <input
                type="text"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder={reviseAction.placeholder}
                disabled={pendingAction !== null}
                className={INLINE_TEXT_INPUT_CLASS}
              />
              <button
                onClick={revise}
                disabled={pendingAction !== null || !feedback.trim()}
                className="shrink-0 px-3 py-1.5 bg-white hover:bg-slate-50 border border-slate-200 disabled:opacity-50 text-slate-600 text-xs font-semibold rounded-lg transition-colors"
              >
                {pendingAction === reviseAction.key ? reviseAction.pendingLabel : reviseAction.label}
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className={`text-xs font-semibold ${resolvedInfo.colorClass}`}>{resolvedInfo.text(error)}</p>
      )}
    </div>
  )
}

function EmailDraftCard({ draftId, toEmail, subject, taskId, onTaskUpdate }) {
  return (
    <DraftConfirmCard
      endpoint="/email/drafts"
      draftId={draftId}
      heading="Email draft — needs your confirmation"
      initial={{ toEmail, subject }}
      renderFields={(d) => (
        <>
          <div><span className="text-slate-400">To </span>{d.toEmail}</div>
          <div><span className="text-slate-400">Subject </span>{d.subject}</div>
        </>
      )}
      renderBody={(d) => d.body}
      primaryAction={{ key: 'send', label: 'Send', pendingLabel: 'Sending…' }}
      resolvedLabels={{
        sent: { colorClass: 'text-emerald-600', text: () => '✓ Sent' },
        failed: { colorClass: 'text-red-500', text: (err) => `✕ Send failed${err ? `: ${err}` : ''}` },
        discarded: { colorClass: 'text-slate-400', text: () => '⚠ Discarded' },
      }}
      reviseAction={{
        key: 'revise',
        label: 'Suggest changes',
        pendingLabel: 'Revising…',
        placeholder: 'e.g. make it shorter and more formal',
      }}
      taskId={taskId}
      onTaskUpdate={onTaskUpdate}
    />
  )
}

function CalendarEventDraftCard({ draftId, title, start, taskId, onTaskUpdate }) {
  return (
    <DraftConfirmCard
      endpoint="/calendar/drafts"
      draftId={draftId}
      heading="Calendar event — needs your confirmation"
      initial={{ title, start }}
      renderFields={(d) => (
        <>
          <div><span className="text-slate-400">Title </span>{d.title}</div>
          <div><span className="text-slate-400">Start </span>{d.start}</div>
          {d.end && <div><span className="text-slate-400">End </span>{d.end}</div>}
          {d.recurrence && <div><span className="text-slate-400">Repeats </span>{d.recurrence}</div>}
          {d.attendees?.length > 0 && <div><span className="text-slate-400">Invitees </span>{d.attendees.join(', ')}</div>}
        </>
      )}
      renderBody={(d) => d.description}
      primaryAction={{ key: 'confirm', label: 'Confirm', pendingLabel: 'Adding…' }}
      resolvedLabels={{
        created: { colorClass: 'text-emerald-600', text: () => '✓ Added to calendar' },
        failed: { colorClass: 'text-red-500', text: (err) => `✕ Create failed${err ? `: ${err}` : ''}` },
        discarded: { colorClass: 'text-slate-400', text: () => '⚠ Discarded' },
      }}
      taskId={taskId}
      onTaskUpdate={onTaskUpdate}
    />
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
    <div className="bg-white rounded-3xl shadow-sm shadow-slate-200 p-4 flex flex-col gap-1">
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
            const calendarParsed = parseCalendarStep(s)
            if (calendarParsed) {
              return calendarParsed.draft
                ? (
                  <CalendarEventDraftCard
                    key={i}
                    draftId={calendarParsed.draftId}
                    title={calendarParsed.title}
                    start={calendarParsed.start}
                    taskId={task.taskId}
                    onTaskUpdate={onTaskUpdate}
                  />
                )
                : <OutcomeRow key={i} parsed={calendarParsed} />
            }
            const formParsed = parseFormFillingStep(s)
            if (formParsed) {
              return formParsed.ask
                ? (
                  <FormFillAskCard
                    key={i}
                    taskId={task.taskId}
                    question={formParsed.question}
                    onTaskUpdate={onTaskUpdate}
                  />
                )
                : <OutcomeRow key={i} parsed={formParsed} />
            }
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
      <div className="bg-white rounded-3xl shadow-sm shadow-slate-200 text-center text-slate-400 text-sm py-14">
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
