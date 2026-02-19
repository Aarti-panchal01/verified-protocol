import { useState } from 'react';

const API = 'http://localhost:8000';

export default function ExplorerPage() {
    const [wallet, setWallet] = useState('');
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [sortBy, setSortBy] = useState('score');

    async function handleSearch() {
        if (!wallet) return;
        setLoading(true);
        setError('');

        try {
            const res = await fetch(`${API}/verify/${wallet}`);
            if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Search failed');
            const data = await res.json();

            if (data.reputation) {
                setResults([data]);
            } else {
                setResults([data]);
            }
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="page">
            <div className="page-header">
                <h1 className="page-title">Talent Explorer</h1>
                <p className="page-subtitle">
                    Browse and discover verified talent across domains. Search by wallet address.
                </p>
            </div>

            {/* Search */}
            <div className="card" style={{ marginBottom: '24px' }}>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <input
                        id="explorer-search-input"
                        className="form-input form-input-mono"
                        placeholder="Search by wallet address…"
                        value={wallet}
                        onChange={e => setWallet(e.target.value)}
                        style={{ flex: 1 }}
                    />
                    <button
                        id="explorer-search-btn"
                        className={`btn btn-primary ${loading ? 'btn-loading' : ''}`}
                        onClick={handleSearch}
                        disabled={loading || !wallet}
                    >
                        {loading ? '' : '🔍 Search'}
                    </button>
                </div>
                {error && <div className="result-panel result-error" style={{ marginTop: '12px' }}>{error}</div>}
            </div>

            {/* Sort controls */}
            {results.length > 0 && (
                <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', alignSelf: 'center' }}>Sort by:</span>
                    {['score', 'records', 'trust'].map(s => (
                        <button
                            key={s}
                            className={`btn ${sortBy === s ? 'btn-primary' : 'btn-ghost'}`}
                            onClick={() => setSortBy(s)}
                            style={{ fontSize: '0.8rem', padding: '6px 14px' }}
                        >
                            {s === 'score' ? '📊 Score' : s === 'records' ? '📋 Records' : '🛡 Trust'}
                        </button>
                    ))}
                </div>
            )}

            {/* Results */}
            {results.map((r, i) => {
                const rep = r.reputation;
                const tierColor = !rep ? 'var(--text-muted)'
                    : rep.credibility_level === 'exceptional' ? 'var(--tier-exceptional)'
                        : rep.credibility_level === 'strong' ? 'var(--tier-strong)'
                            : rep.credibility_level === 'moderate' ? 'var(--tier-moderate)'
                                : rep.credibility_level === 'developing' ? 'var(--tier-developing)'
                                    : 'var(--tier-minimal)';

                return (
                    <div key={i} className="card animate-in" style={{ marginBottom: '16px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                                    <span className={`verification-badge ${r.verified ? 'verified' : 'unverified'}`}>
                                        {r.verified ? '✓ Verified' : '◯ Pending'}
                                    </span>
                                    {rep?.top_domain && <span className="tag tag-domain">{rep.top_domain}</span>}
                                </div>
                                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
                                    {r.wallet}
                                </div>
                                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                    {r.message}
                                </div>
                            </div>
                            {rep && (
                                <div style={{ textAlign: 'center', minWidth: '100px' }}>
                                    <div style={{ fontSize: '2rem', fontWeight: 800, color: tierColor, lineHeight: 1 }}>
                                        {Math.round(rep.total_reputation)}
                                    </div>
                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                                        Reputation
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Domain bars inline */}
                        {rep?.domain_scores?.length > 0 && (
                            <div style={{ marginTop: '16px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                {rep.domain_scores.map(ds => (
                                    <div key={ds.domain} style={{
                                        display: 'flex', alignItems: 'center', gap: '6px',
                                        background: 'rgba(99, 102, 241, 0.06)', padding: '6px 12px',
                                        borderRadius: 'var(--radius-full)', fontSize: '0.8rem',
                                    }}>
                                        <span style={{ fontWeight: 600 }}>{ds.domain}</span>
                                        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-2)' }}>{Math.round(ds.score)}</span>
                                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>({ds.record_count})</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                );
            })}

            {/* Empty state */}
            {!loading && results.length === 0 && (
                <div className="empty-state" style={{ marginTop: '48px' }}>
                    <div className="empty-state-icon">🌐</div>
                    <p>Search for a wallet to explore verified talent</p>
                </div>
            )}
        </div>
    );
}
