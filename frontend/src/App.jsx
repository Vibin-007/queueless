import { useCallback, useEffect, useState } from 'react'
import './App.css'

const API_BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')
const STORAGE_KEY = 'queueless:my-token'
const POLL_INTERVAL = 3000
const MINUTES_PER_TOKEN = 5
const SERVICE_OPTIONS = ['General', 'Priority', 'Support']

async function apiRequest(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    })
  } catch {
    throw new Error('Cannot reach the QueueLess server. Is Django running on port 8000?')
  }

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(data.error || data.detail || `Request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  return data
}

function readStoredToken() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object' || !parsed.id || !parsed.token_number) return null
    return parsed
  } catch {
    return null
  }
}

function normaliseQueue(data) {
  return {
    now_serving: data.now_serving ?? null,
    waiting_list: Array.isArray(data.waiting_list) ? data.waiting_list : [],
    total_waiting: data.total_waiting ?? 0,
    est_wait_minutes: data.est_wait_minutes ?? 0,
  }
}

function formatTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function ServiceBadge({ service }) {
  const key = String(service || 'General').toLowerCase()
  return <span className={`badge service-${key}`}>{service || 'General'}</span>
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState('customer')
  const [queue, setQueue] = useState(null)
  const [myToken, setMyToken] = useState(readStoredToken)
  const [form, setForm] = useState({ customerName: '', serviceType: 'General' })
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [syncError, setSyncError] = useState('')
  const [flash, setFlash] = useState('')
  const [lastSynced, setLastSynced] = useState(null)

  const storeToken = useCallback((token) => {
    setMyToken(token)
    if (token) {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(token))
    } else {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  }, [])

  const applyQueue = useCallback((data) => {
    setQueue(normaliseQueue(data))
    setLastSynced(new Date())
    setSyncError('')
  }, [])

  const refresh = useCallback(async () => {
    try {
      const data = await apiRequest('/api/status/')
      applyQueue(data)
    } catch (err) {
      setSyncError(err.message)
    }
  }, [applyQueue])

  useEffect(() => {
    const initial = window.setTimeout(refresh, 0)
    const timer = window.setInterval(refresh, POLL_INTERVAL)
    return () => {
      window.clearTimeout(initial)
      window.clearInterval(timer)
    }
  }, [refresh])

  useEffect(() => {
    if (!flash) return undefined
    const timer = window.setTimeout(() => setFlash(''), 5000)
    return () => window.clearTimeout(timer)
  }, [flash])

  const queueLoaded = queue !== null
  const nowServing = queue?.now_serving ?? null
  const waitingList = queue?.waiting_list ?? []
  const totalWaiting = queue?.total_waiting ?? 0
  const estimatedWait = queue?.est_wait_minutes ?? 0

  const myIndex = myToken ? waitingList.findIndex((token) => token.id === myToken.id) : -1
  const myPosition = myIndex >= 0 ? myIndex + 1 : null
  const isMyTurn = Boolean(myToken && nowServing && nowServing.id === myToken.id)

  let myStatus = 'none'
  if (myToken) {
    if (isMyTurn) myStatus = 'serving'
    else if (myPosition !== null) myStatus = 'waiting'
    else myStatus = queueLoaded ? 'finished' : 'pending'
  }

  const handleBook = async (event) => {
    event.preventDefault()
    const customerName = form.customerName.trim()
    if (!customerName) {
      setError('Please enter your name before booking.')
      return
    }

    setBusy('book')
    setError('')
    setFlash('')
    try {
      const token = await apiRequest('/api/book/', {
        method: 'POST',
        body: JSON.stringify({
          customer_name: customerName,
          service_type: form.serviceType,
        }),
      })
      storeToken(token)
      setForm({ customerName: '', serviceType: 'General' })
      setQueue((previous) => {
        const base = previous ?? {
          now_serving: null,
          waiting_list: [],
          total_waiting: 0,
          est_wait_minutes: 0,
        }
        const waiting = [...base.waiting_list, token]
        return {
          ...base,
          waiting_list: waiting,
          total_waiting: waiting.length,
          est_wait_minutes: waiting.length * MINUTES_PER_TOKEN,
        }
      })
      setFlash(`Token #${token.token_number} booked for ${token.customer_name}. You are in line.`)
      refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleLeave = async () => {
    if (!myToken) return
    setBusy('leave')
    setError('')
    try {
      const data = await apiRequest(`/api/cancel/${myToken.token_number}/`, { method: 'POST' })
      storeToken(null)
      applyQueue(data)
      setFlash(`You left the queue. Token #${myToken.token_number} was cancelled.`)
    } catch (err) {
      if (err.status === 404) {
        storeToken(null)
        setFlash('That token was already inactive, so it has been cleared from this device.')
        refresh()
      } else {
        setError(err.message)
      }
    } finally {
      setBusy('')
    }
  }

  const handleCallNext = async () => {
    setBusy('next')
    setError('')
    try {
      const data = await apiRequest('/api/next/', { method: 'POST' })
      applyQueue(data)
      if (data.called) {
        setFlash(`Now serving token #${data.called.token_number} — ${data.called.customer_name}.`)
      } else {
        setFlash('No one is waiting. The counter is clear.')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const handleCancelToken = async (token) => {
    setBusy(`cancel-${token.id}`)
    setError('')
    try {
      const data = await apiRequest(`/api/cancel/${token.token_number}/`, { method: 'POST' })
      applyQueue(data)
      setFlash(`Removed token #${token.token_number} (${token.customer_name}) from the queue.`)
    } catch (err) {
      setError(err.message)
      refresh()
    } finally {
      setBusy('')
    }
  }

  const handleReset = async () => {
    const confirmed = window.confirm(
      'Reset the entire queue? This permanently clears every waiting, serving and completed token.',
    )
    if (!confirmed) return

    setBusy('reset')
    setError('')
    try {
      const data = await apiRequest('/api/reset/', { method: 'POST' })
      applyQueue(data)
      storeToken(null)
      setFlash('Queue reset. Token numbering restarts at 101.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const renderCustomer = () => (
    <div className="customer-layout">
      <section className="glass panel hero-panel">
        <div className="panel-head">
          <span className="eyebrow">Now serving</span>
          <span className={`live-chip ${syncError ? 'is-offline' : ''}`}>
            <span className="dot" />
            {syncError ? 'Reconnecting' : 'Live'}
          </span>
        </div>

        <div className="hero-body">
          <div className="hero-token" aria-live="polite">
            {nowServing ? `#${nowServing.token_number}` : '—'}
          </div>
          {nowServing ? (
            <div className="token-meta">
              <span className="hero-name">{nowServing.customer_name}</span>
              <ServiceBadge service={nowServing.service_type} />
            </div>
          ) : (
            <p className="muted">The counter is idle. Book a token to get started.</p>
          )}
        </div>

        <div className="stat-grid">
          <Stat label="People waiting" value={totalWaiting} />
          <Stat label="Est. wait" value={`${estimatedWait} min`} />
          <Stat label="Per token" value={`${MINUTES_PER_TOKEN} min`} />
        </div>

        <p className="sync-line">
          <span>{lastSynced ? `Synced at ${lastSynced.toLocaleTimeString()}` : 'Connecting to the queue…'}</span>
          <span>Auto-refresh every 3s</span>
        </p>
      </section>

      <section className="glass panel booking-panel">
        <div className="panel-head">
          <span className="eyebrow">Customer</span>
        </div>
        <h2>Book a digital token</h2>
        <p className="muted">Skip the physical line and hold your place virtually.</p>

        <form className="stack" onSubmit={handleBook}>
          <label className="field">
            <span>Your name</span>
            <input
              type="text"
              value={form.customerName}
              onChange={(event) => setForm({ ...form, customerName: event.target.value })}
              placeholder="e.g. Alex Morgan"
              maxLength={100}
              autoComplete="name"
              disabled={busy === 'book'}
            />
          </label>

          <label className="field">
            <span>Service type</span>
            <select
              value={form.serviceType}
              onChange={(event) => setForm({ ...form, serviceType: event.target.value })}
              disabled={busy === 'book'}
            >
              {SERVICE_OPTIONS.map((service) => (
                <option key={service} value={service}>
                  {service}
                </option>
              ))}
            </select>
          </label>

          <button className="btn btn-primary btn-block" type="submit" disabled={busy === 'book'}>
            {busy === 'book' ? (
              <span className="btn-busy">
                <span className="spinner" />
                Booking…
              </span>
            ) : (
              'Book digital token'
            )}
          </button>
        </form>

        <p className="micro">Your token is saved on this device, so refreshing the page will not lose your place.</p>
      </section>

      <section className={`glass panel token-panel ${myStatus === 'serving' ? 'is-serving' : ''}`}>
        <div className="panel-head">
          <span className="eyebrow">My token</span>
          {myToken && <span className="muted small">Saved on this device</span>}
        </div>

        {!myToken && (
          <div className="empty-state">
            <div className="empty-glyph">Q</div>
            <h3>No active token</h3>
            <p>Book a token and it will appear here — even after a refresh.</p>
          </div>
        )}

        {myToken && myStatus === 'pending' && (
          <div className="empty-state">
            <p className="muted">Checking your token…</p>
          </div>
        )}

        {myToken && myStatus === 'serving' && (
          <div className="token-live">
            <div className="turn-alert">
              <span className="pulse-dot" />
              It&apos;s your turn — head to the counter now
            </div>
            <div className="token-big">#{myToken.token_number}</div>
            <div className="token-meta">
              <span>{myToken.customer_name}</span>
              <ServiceBadge service={myToken.service_type} />
            </div>
            <button className="btn btn-ghost" type="button" onClick={() => storeToken(null)}>
              I&apos;ve been served · clear token
            </button>
          </div>
        )}

        {myToken && myStatus === 'waiting' && (
          <div className="token-live">
            <div className="token-big">#{myToken.token_number}</div>
            <div className="token-meta">
              <span>{myToken.customer_name}</span>
              <ServiceBadge service={myToken.service_type} />
            </div>

            <div className="token-stats">
              <div className="mini-stat">
                <span>Position</span>
                <strong>#{myPosition}</strong>
              </div>
              <div className="mini-stat">
                <span>People ahead</span>
                <strong>{Math.max(myPosition - 1, 0)}</strong>
              </div>
              <div className="mini-stat accent">
                <span>Your wait</span>
                <strong>{myPosition * MINUTES_PER_TOKEN} min</strong>
              </div>
            </div>

            <p className="muted small">Keep this page open — your position updates automatically.</p>

            <button
              className="btn btn-danger-ghost"
              type="button"
              onClick={handleLeave}
              disabled={busy === 'leave'}
            >
              {busy === 'leave' ? 'Leaving queue…' : 'Leave queue'}
            </button>
          </div>
        )}

        {myToken && myStatus === 'finished' && (
          <div className="token-live">
            <div className="token-big dim">#{myToken.token_number}</div>
            <h3>This token is no longer in the queue</h3>
            <p className="muted">
              It may have been served, cancelled, or cleared by a reset. You can book a new token above anytime.
            </p>
            <button className="btn btn-ghost" type="button" onClick={() => storeToken(null)}>
              Clear this token
            </button>
          </div>
        )}
      </section>
    </div>
  )

  const renderStaff = () => (
    <div className="staff-layout">
      <section className="glass panel call-panel">
        <div className="panel-head">
          <span className="eyebrow">Counter control</span>
          <span className={`live-chip ${syncError ? 'is-offline' : ''}`}>
            <span className="dot" />
            {syncError ? 'Reconnecting' : 'Live'}
          </span>
        </div>

        <h2>Currently serving</h2>

        {nowServing ? (
          <div className="serving-card">
            <div className="token-big">#{nowServing.token_number}</div>
            <div className="token-meta">
              <span>{nowServing.customer_name}</span>
              <ServiceBadge service={nowServing.service_type} />
            </div>
            <p className="muted small">Called at {formatTime(nowServing.created_at)}</p>
          </div>
        ) : (
          <div className="empty-state compact">
            <h3>Counter is idle</h3>
            <p>Call the next person when someone is waiting.</p>
          </div>
        )}

        <button
          className="btn btn-primary btn-xl btn-block"
          type="button"
          onClick={handleCallNext}
          disabled={busy === 'next' || !queueLoaded}
        >
          {busy === 'next' ? 'Calling next…' : 'Call next token'}
        </button>
        <p className="micro">Completes the current token, then promotes the next person in line.</p>
      </section>

      <section className="glass panel queue-panel">
        <div className="panel-head">
          <span className="eyebrow">Upcoming queue</span>
          <span className="count-chip">{totalWaiting} waiting</span>
        </div>

        {waitingList.length === 0 ? (
          <div className="empty-state compact">
            <h3>Queue is empty</h3>
            <p>New bookings will appear here automatically.</p>
          </div>
        ) : (
          <ul className="queue-list">
            {waitingList.map((token, index) => (
              <li className="queue-item" key={token.id}>
                <span className="queue-pos">#{index + 1}</span>
                <div className="queue-main">
                  <div className="queue-top">
                    <strong>Token #{token.token_number}</strong>
                    <ServiceBadge service={token.service_type} />
                  </div>
                  <div className="queue-sub">
                    <span>{token.customer_name}</span>
                    <span className="dot-sep">·</span>
                    <span>{formatTime(token.created_at)}</span>
                  </div>
                </div>
                <button
                  className="btn btn-sm btn-danger-ghost"
                  type="button"
                  onClick={() => handleCancelToken(token)}
                  disabled={busy === `cancel-${token.id}`}
                >
                  {busy === `cancel-${token.id}` ? 'Removing…' : 'Skip'}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="glass panel reset-panel">
        <div>
          <span className="eyebrow danger-text">Danger zone</span>
          <h3>Reset the queue</h3>
          <p className="muted">Clears every token and restarts numbering at 101. Handy before a live demo.</p>
        </div>
        <button
          className="btn btn-danger"
          type="button"
          onClick={handleReset}
          disabled={busy === 'reset'}
        >
          {busy === 'reset' ? 'Resetting…' : 'Reset queue'}
        </button>
      </section>
    </div>
  )

  return (
    <div className="app-shell">
      <div className="orb orb-one" aria-hidden="true" />
      <div className="orb orb-two" aria-hidden="true" />

      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            Q
          </div>
          <div className="brand-text">
            <span className="brand-name">QueueLess</span>
            <span className="brand-sub">Virtual queue manager</span>
          </div>
        </div>

        <nav className="tabs" aria-label="Choose view">
          <button
            type="button"
            className={view === 'customer' ? 'tab is-active' : 'tab'}
            onClick={() => setView('customer')}
            aria-pressed={view === 'customer'}
          >
            Customer
          </button>
          <button
            type="button"
            className={view === 'staff' ? 'tab is-active' : 'tab'}
            onClick={() => setView('staff')}
            aria-pressed={view === 'staff'}
          >
            Counter staff
          </button>
        </nav>

        <div className={`live-pill ${syncError ? 'is-offline' : ''}`}>
          <span className="dot" />
          {syncError ? 'Offline' : 'Live sync'}
        </div>
      </header>

      <main className="container">
        {syncError && (
          <div className="banner banner-warning" role="status">
            <span>
              Live sync paused: {syncError} Retrying every 3 seconds.
            </span>
          </div>
        )}

        {error && (
          <div className="banner banner-error" role="alert">
            <span>{error}</span>
            <button className="banner-close" type="button" onClick={() => setError('')} aria-label="Dismiss error">
              ×
            </button>
          </div>
        )}

        {flash && (
          <div className="banner banner-success" role="status">
            <span>{flash}</span>
            <button className="banner-close" type="button" onClick={() => setFlash('')} aria-label="Dismiss message">
              ×
            </button>
          </div>
        )}

        {view === 'customer' ? renderCustomer() : renderStaff()}
      </main>

      <footer className="app-footer">
        <span>QueueLess · Virtual queue management</span>
        <span>Live updates every 3 seconds</span>
      </footer>
    </div>
  )
}
