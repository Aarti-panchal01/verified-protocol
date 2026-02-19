import { useState } from 'react';
import ScoreCircle from '../components/ScoreCircle';
import DomainChart from '../components/DomainChart';
import Timeline from '../components/SkillTimeline';

const API = 'http://localhost:8000';

export default function DashboardPage() {
    const [wallet, setWallet] = useState('');
    const [reputation, setReputation] = useState(null);
    const [records, setRecords] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    async function handleLookup() {
        setLoading(true);
        setError('');
        setReputation(null);
        setRecords([]);

        try {
            const [repRes, walletRes] = await Promise.all([
                fetch(`${API}/reputation/${wallet}`),
                fetch(`${API}/wallet/${wallet}`),
            ]);

            if (!repRes.ok) throw new Error((await repRes.json().catch(() => ({}))).detail || 'Reputation fetch failed');
            if (!walletRes.ok) throw new Error((await walletRes.json().catch(() => ({}))).detail || 'Records fetch failed');

            const repData = await repRes.json();
            const walletData = await walletRes.json();

            setReputation(repData);
            setRecords(walletData.records || []);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }

    const tierClass = reputation ? `tier-${reputation.credibility_level}` : '';

    return (
        <div className="page">
            <div className="page-header">
                <h1 className="page-title">Wallet Dashboard</h1>
                <p className="page-subtitle">
                    View your skill reputation, domain strengths, trust index, and on-chain record timeline.
                </p>
            </div>

            {/* Wallet Input */}
            <div className="card" style={{ marginBottom: '24px' }}>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <input
                        id="dashboard-wallet-input"
                        className="form-input form-input-mono"
                        placeholder="Enter Algorand wallet address…"
                        value={wallet}
                        onChange={e => setWallet(e.target.value)}
                        style={{ flex: 1 }}
                    />
                    <button
                        id="dashboard-lookup-btn"
                        className={`btn btn-primary ${loading ? 'btn-loading' : ''}`}
                        onClick={handleLookup}
                        disabled={loading || !wallet}
                    >
                        {loading ? '' : 'Lookup'}
                    </button>
                </div>
                {error && <div className="result-panel result-error" style={{ marginTop: '12px' }}>{error}</div>}
            </div>

            {reputation && (
                <div className="animate-in">
                    {/* Top Stats */}
                    <div className="stats-grid">
                        <div className="stat-card">
                            <div className="stat-value">{Math.round(reputation.total_reputation)}</div>
                            <div className="stat-label">Reputation Score</div>
                            <div className="trust-meter">
                                <div className="trust-meter-fill" style={{ width: `${reputation.trust_index * 100}%` }} />
                            </div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value">{reputation.total_records}</div>
                            <div className="stat-label">On-Chain Records</div>
                        </div>
                        <div className="stat-card">
                            <div className={`stat-value ${tierClass}`} style={{ WebkitTextFillColor: 'unset' }}>
                                {reputation.credibility_level}
                            </div>
                            <div className="stat-label">Credibility Level</div>
                        </div>
                        <div className="stat-card">
                            <div className="stat-value">{(reputation.trust_index * 100).toFixed(1)}%</div>
                            <div className="stat-label">Trust Index</div>
                        </div>
                    </div>

                    {/* Badge + Metadata */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
                        <span className={`verification-badge ${reputation.verification_badge ? 'verified' : 'unverified'}`}>
                            {reputation.verification_badge ? '✓ Verified Talent' : '◯ Not Yet Verified'}
                        </span>
                        {reputation.top_domain && (
                            <span className="tag tag-domain">Top: {reputation.top_domain}</span>
                        )}
                        {reputation.active_since && (
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                Active since {new Date(reputation.active_since * 1000).toLocaleDateString()}
                            </span>
                        )}
                    </div>

                    <div className="grid-2">
                        {/* Domain Strengths */}
                        <div className="card">
                            <div className="card-header">
                                <div className="card-icon">📊</div>
                                <div>
                                    <div className="card-title">Domain Strengths</div>
                                    <div className="card-description">Skill distribution across domains</div>
                                </div>
                            </div>
                            <DomainChart domainScores={reputation.domain_scores} />
                        </div>

                        {/* Score Overview */}
                        <div className="card" style={{ textAlign: 'center' }}>
                            <div className="card-header" style={{ justifyContent: 'center' }}>
                                <div className="card-icon">⬡</div>
                                <div>
                                    <div className="card-title">Reputation Score</div>
                                    <div className="card-description">Weighted, time-decayed aggregate</div>
                                </div>
                            </div>
                            <ScoreCircle score={Math.round(reputation.total_reputation)} size={160} label={reputation.credibility_level} />
                        </div>
                    </div>

                    {/* Timeline */}
                    <div className="card" style={{ marginTop: '24px' }}>
                        <div className="card-header">
                            <div className="card-icon">📜</div>
                            <div>
                                <div className="card-title">Record Timeline</div>
                                <div className="card-description">{records.length} on-chain attestation(s)</div>
                            </div>
                        </div>
                        <Timeline records={records} />
                    </div>
                </div>
            )}
        </div>
    );
}
