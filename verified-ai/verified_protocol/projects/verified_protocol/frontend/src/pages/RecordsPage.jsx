import { useState } from 'react'
import SkillTimeline from '../components/SkillTimeline.jsx'

export default function RecordsPage({ apiBase }) {
    const [wallet, setWallet] = useState('')
    const [loading, setLoading] = useState(false)
    const [data, setData] = useState(null)
    const [error, setError] = useState(null)

    const fetchRecords = async () => {
        if (!wallet.trim()) return
        setLoading(true)
        setData(null)
        setError(null)

        try {
            const res = await fetch(`${apiBase}/records/${wallet.trim()}`)
            if (!res.ok) {
                const d = await res.json().catch(() => ({}))
                throw new Error(d.detail || `HTTP ${res.status}`)
            }
            const json = await res.json()
            setData(json)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const avgScore = data?.records?.length
        ? Math.round(data.records.reduce((s, r) => s + (r.score || 0), 0) / data.records.length)
        : 0

    const domains = data?.records
        ? [...new Set(data.records.map(r => r.domain).filter(Boolean))]
        : []

    return (
        <>
            <div className="page-header">
                <h1>Wallet Records</h1>
                <p>
                    Enter any Algorand wallet address to fetch and decode
                    its on-chain skill reputation records.
                </p>
            </div>

            <div className="wallet-bar">
                <input
                    id="wallet-input"
                    className="form-input"
                    type="text"
                    placeholder="Paste Algorand wallet address (58 chars)…"
                    value={wallet}
                    onChange={(e) => setWallet(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && fetchRecords()}
                />
                <button
                    id="fetch-records-btn"
                    className="btn btn-primary"
                    onClick={fetchRecords}
                    disabled={loading || !wallet.trim()}
                >
                    {loading ? '⏳' : '🔍'} Fetch
                </button>
            </div>

            {error && (
                <div className="alert alert-error">
                    <span>❌</span> {error}
                </div>
            )}

            {loading && <div className="spinner" />}

            {data && !loading && (
                <>
                    {/* Stats strip */}
                    <div className="stats-grid">
                        <div className="stat-card">
                            <div className="stat-value">{data.record_count}</div>
                            <div className="stat-label">Total Records</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value">{avgScore}</div>
                            <div className="stat-label">Average Score</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value">{domains.length}</div>
                            <div className="stat-label">Skill Domains</div>
                        </div>
                    </div>

                    {/* Timeline */}
                    <div className="card">
                        <div className="card-title">
                            <span className="icon">📜</span> Skill Timeline
                        </div>
                        <SkillTimeline records={data.records} />
                    </div>
                </>
            )}
        </>
    )
}
