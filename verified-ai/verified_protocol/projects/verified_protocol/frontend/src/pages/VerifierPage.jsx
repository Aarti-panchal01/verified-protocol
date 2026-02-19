import { useState } from 'react'
import SkillTimeline from '../components/SkillTimeline.jsx'

export default function VerifierPage({ apiBase }) {
    const [wallet, setWallet] = useState('')
    const [loading, setLoading] = useState(false)
    const [data, setData] = useState(null)
    const [error, setError] = useState(null)

    const handleVerify = async () => {
        if (!wallet.trim()) return
        setLoading(true)
        setData(null)
        setError(null)

        try {
            const res = await fetch(`${apiBase}/verify/${wallet.trim()}`)
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

    return (
        <>
            <div className="page-header">
                <h1>Skill Verifier</h1>
                <p>
                    Verify any wallet's on-chain skill reputation. Records are
                    cryptographically secured and immutable on Algorand.
                </p>
            </div>

            <div className="wallet-bar">
                <input
                    id="verify-wallet-input"
                    className="form-input"
                    type="text"
                    placeholder="Paste wallet address to verify…"
                    value={wallet}
                    onChange={(e) => setWallet(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleVerify()}
                />
                <button
                    id="verify-btn"
                    className="btn btn-primary"
                    onClick={handleVerify}
                    disabled={loading || !wallet.trim()}
                >
                    {loading ? '⏳' : '🛡️'} Verify
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
                    {/* Verification Badge */}
                    <div className="card" style={{ marginBottom: '1.5rem' }}>
                        <div className="verify-badge">
                            <div className={`verify-icon ${data.verified ? 'verified' : 'unverified'}`}>
                                {data.verified ? '✅' : '❌'}
                            </div>
                            <h2>{data.verified ? 'Wallet Verified' : 'Not Verified'}</h2>
                            <p>{data.message}</p>

                            {data.verified && (
                                <div
                                    className="stats-grid"
                                    style={{ marginTop: '1.5rem', width: '100%', maxWidth: '400px' }}
                                >
                                    <div className="stat-card">
                                        <div className="stat-value">{data.record_count}</div>
                                        <div className="stat-label">On-Chain Records</div>
                                    </div>
                                    <div className="stat-card">
                                        <div className="stat-value">
                                            {data.records?.length
                                                ? Math.round(
                                                    data.records.reduce((s, r) => s + (r.score || 0), 0) /
                                                    data.records.length
                                                )
                                                : 0}
                                        </div>
                                        <div className="stat-label">Avg Score</div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Records */}
                    {data.records?.length > 0 && (
                        <div className="card">
                            <div className="card-title">
                                <span className="icon">📋</span> Verified Records
                            </div>
                            <SkillTimeline records={data.records} />
                        </div>
                    )}

                    {/* Wallet meta */}
                    <div className="card" style={{ marginTop: '1.5rem' }}>
                        <div className="card-title">
                            <span className="icon">🔗</span> Blockchain Proof
                        </div>
                        <dl className="record-meta">
                            <dt>Wallet</dt>
                            <dd style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>{data.wallet}</dd>
                            <dt>Network</dt>
                            <dd>Algorand Testnet</dd>
                            <dt>App ID</dt>
                            <dd>
                                <a
                                    className="tx-link"
                                    href="https://testnet.explorer.perawallet.app/application/755779875"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    755779875
                                </a>
                            </dd>
                            <dt>Storage</dt>
                            <dd>Box Storage (per wallet)</dd>
                        </dl>
                    </div>
                </>
            )}
        </>
    )
}
