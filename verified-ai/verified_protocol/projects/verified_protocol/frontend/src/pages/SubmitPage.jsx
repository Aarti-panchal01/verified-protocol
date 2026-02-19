import { useState } from 'react'

export default function SubmitPage({ apiBase }) {
    const [skillId, setSkillId] = useState('')
    const [score, setScore] = useState(75)
    const [mode, setMode] = useState('ai-graded')
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)

    const handleSubmit = async (e) => {
        e.preventDefault()
        setLoading(true)
        setResult(null)
        setError(null)

        try {
            const res = await fetch(`${apiBase}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    skill_id: skillId,
                    score: score,
                    mode: mode,
                }),
            })

            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                throw new Error(data.detail || `HTTP ${res.status}`)
            }

            const data = await res.json()
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <>
            <div className="page-header">
                <h1>Submit Skill Record</h1>
                <p>
                    Append an immutable skill attestation to the Algorand blockchain.
                    Records are stored in per-wallet Boxes and can never be modified.
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                {/* Form Card */}
                <div className="card">
                    <div className="card-title">
                        <span className="icon">📝</span> New Record
                    </div>

                    <form onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label className="form-label">Skill Domain</label>
                            <input
                                id="skill-id-input"
                                className="form-input"
                                type="text"
                                placeholder="e.g. python, solidity, rust"
                                value={skillId}
                                onChange={(e) => setSkillId(e.target.value)}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Evaluation Mode</label>
                            <select
                                id="mode-select"
                                className="form-input"
                                value={mode}
                                onChange={(e) => setMode(e.target.value)}
                            >
                                <option value="ai-graded">AI Graded</option>
                                <option value="peer-review">Peer Review</option>
                                <option value="self-assessed">Self Assessed</option>
                                <option value="exam">Exam</option>
                            </select>
                        </div>

                        <div className="form-group">
                            <label className="form-label">Score (0–100)</label>
                            <div className="score-slider-wrap">
                                <input
                                    id="score-slider"
                                    className="score-slider"
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={score}
                                    onChange={(e) => setScore(Number(e.target.value))}
                                />
                                <span className="score-value">{score}</span>
                            </div>
                        </div>

                        <button
                            id="submit-btn"
                            className="btn btn-primary btn-full"
                            type="submit"
                            disabled={loading || !skillId}
                        >
                            {loading ? '⏳ Submitting…' : '🚀 Submit to Blockchain'}
                        </button>
                    </form>
                </div>

                {/* Result Card */}
                <div className="card">
                    <div className="card-title">
                        <span className="icon">📡</span> Transaction Result
                    </div>

                    {!result && !error && (
                        <div className="empty-state">
                            <div className="icon">🔗</div>
                            <p>Submit a record to see the transaction result here.</p>
                        </div>
                    )}

                    {error && (
                        <div className="alert alert-error">
                            <span>❌</span> {error}
                        </div>
                    )}

                    {result && (
                        <div>
                            <div className="alert alert-success">
                                <span>✅</span> Skill record submitted on-chain!
                            </div>

                            <dl className="record-meta" style={{ marginTop: '1rem' }}>
                                <dt>Transaction ID</dt>
                                <dd>
                                    <a
                                        className="tx-link"
                                        href={result.explorer_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        {result.transaction_id.slice(0, 20)}…
                                    </a>
                                </dd>
                                <dt>Skill</dt>
                                <dd>{result.skill_id}</dd>
                                <dt>Score</dt>
                                <dd>{result.score}</dd>
                                <dt>Timestamp</dt>
                                <dd>{new Date(result.timestamp * 1000).toLocaleString()}</dd>
                                <dt>Artifact Hash</dt>
                                <dd style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
                                    {result.artifact_hash.slice(0, 20)}…
                                </dd>
                            </dl>
                        </div>
                    )}
                </div>
            </div>
        </>
    )
}
