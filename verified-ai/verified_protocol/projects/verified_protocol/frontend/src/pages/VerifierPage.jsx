import { useState } from 'react';
import ScoreCircle from '../components/ScoreCircle';
import DomainChart from '../components/DomainChart';
import Timeline from '../components/SkillTimeline';

const API = 'http://localhost:8000';

export default function VerifierPage() {
    const [wallet, setWallet] = useState('');
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    async function handleVerify() {
        setLoading(true);
        setError('');
        setResult(null);

        try {
            const res = await fetch(`${API}/verify/${wallet}`);
            if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Verification failed');
            setResult(await res.json());
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="page">
            <div className="page-header">
                <h1 className="page-title">Verifier Panel</h1>
                <p className="page-subtitle">
                    Recruiter & employer view. Look up any wallet to verify on-chain skill credentials with trust scoring.
                </p>
            </div>

            {/* Wallet Input */}
            <div className="card" style={{ marginBottom: '24px' }}>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <input
                        id="verifier-wallet-input"
                        className="form-input form-input-mono"
                        placeholder="Enter wallet address to verify…"
                        value={wallet}
                        onChange={e => setWallet(e.target.value)}
                        style={{ flex: 1 }}
                    />
                    <button
                        id="verifier-btn"
                        className={`btn btn-primary ${loading ? 'btn-loading' : ''}`}
                        onClick={handleVerify}
                        disabled={loading || !wallet}
                    >
                        {loading ? '' : '🔍 Verify'}
                    </button>
                </div>
                {error && <div className="result-panel result-error" style={{ marginTop: '12px' }}>{error}</div>}
            </div>

            {result && (
                <div className="animate-in">
                    {/* Verification Hero */}
                    <div className="verification-hero">
                        <div className={`verification-icon ${result.verified ? 'verified' : 'unverified'}`}>
                            {result.verified ? '✓' : '⚠'}
                        </div>
                        <h2 style={{
                            fontSize: '1.5rem',
                            fontWeight: 700,
                            color: result.verified ? 'var(--success)' : 'var(--warning)',
                            marginBottom: '8px',
                        }}>
                            {result.verified ? 'Verified Talent' : 'Not Yet Verified'}
                        </h2>
                        <p style={{ color: 'var(--text-secondary)', maxWidth: 600, margin: '0 auto' }}>
                            {result.message}
                        </p>
                    </div>

                    {result.reputation && (
                        <>
                            {/* Stats */}
                            <div className="stats-grid">
                                <div className="stat-card">
                                    <div className="stat-value">{Math.round(result.reputation.total_reputation)}</div>
                                    <div className="stat-label">Reputation</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-value">{result.record_count}</div>
                                    <div className="stat-label">Records</div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-value">{(result.reputation.trust_index * 100).toFixed(1)}%</div>
                                    <div className="stat-label">Trust Index</div>
                                    <div className="trust-meter">
                                        <div className="trust-meter-fill" style={{ width: `${result.reputation.trust_index * 100}%` }} />
                                    </div>
                                </div>
                                <div className="stat-card">
                                    <div className="stat-value" style={{
                                        WebkitTextFillColor: 'unset',
                                        color: result.verified ? 'var(--success)' : 'var(--warning)',
                                        fontSize: '1.3rem',
                                    }}>
                                        {result.reputation.credibility_level}
                                    </div>
                                    <div className="stat-label">Credibility</div>
                                </div>
                            </div>

                            <div className="grid-2">
                                {/* Domain Chart */}
                                <div className="card">
                                    <div className="card-header">
                                        <div className="card-icon">📊</div>
                                        <div>
                                            <div className="card-title">Domain Breakdown</div>
                                            <div className="card-description">Verified skill domains</div>
                                        </div>
                                    </div>
                                    <DomainChart domainScores={result.reputation.domain_scores} />
                                </div>

                                {/* Proof Card */}
                                <div className="card">
                                    <div className="card-header">
                                        <div className="card-icon">🔒</div>
                                        <div>
                                            <div className="card-title">Blockchain Proof</div>
                                            <div className="card-description">On-chain verification details</div>
                                        </div>
                                    </div>
                                    <div style={{ fontSize: '0.85rem', lineHeight: '2' }}>
                                        <div><span style={{ color: 'var(--text-muted)' }}>Network:</span> Algorand Testnet</div>
                                        <div><span style={{ color: 'var(--text-muted)' }}>App ID:</span> <code style={{ color: 'var(--accent-2)' }}>755779875</code></div>
                                        <div><span style={{ color: 'var(--text-muted)' }}>Wallet:</span> <code style={{ color: 'var(--accent-2)', fontSize: '0.75rem' }}>{wallet}</code></div>
                                        <div><span style={{ color: 'var(--text-muted)' }}>Records:</span> {result.record_count}</div>
                                        <div><span style={{ color: 'var(--text-muted)' }}>Badge:</span>{' '}
                                            <span className={`verification-badge ${result.verified ? 'verified' : 'unverified'}`} style={{ fontSize: '0.75rem' }}>
                                                {result.verified ? '✓ Eligible' : '◯ Pending'}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </>
                    )}

                    {/* Records Timeline */}
                    {result.records?.length > 0 && (
                        <div className="card" style={{ marginTop: '24px' }}>
                            <div className="card-header">
                                <div className="card-icon">📜</div>
                                <div>
                                    <div className="card-title">On-Chain Records</div>
                                    <div className="card-description">Immutable skill attestations</div>
                                </div>
                            </div>
                            <Timeline records={result.records} />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
