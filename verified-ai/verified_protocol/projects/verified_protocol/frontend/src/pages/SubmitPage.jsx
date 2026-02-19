import { useState } from 'react';
import ScoreCircle from '../components/ScoreCircle';

const API = 'http://localhost:8000';

export default function SubmitPage() {
    const [mode, setMode] = useState('developer');
    const [sourceType, setSourceType] = useState('repo');
    const [repoUrl, setRepoUrl] = useState('');
    const [skillId, setSkillId] = useState('');
    const [score, setScore] = useState(null);
    const [analysis, setAnalysis] = useState(null);
    const [submitResult, setSubmitResult] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    async function handleAnalyze() {
        setError('');
        setAnalysis(null);
        setSubmitResult(null);
        setAnalyzing(true);

        try {
            const endpoint = sourceType === 'repo' ? '/analyze/repo' : '/analyze/certificate';
            const body = sourceType === 'repo'
                ? { repo_url: repoUrl, mode }
                : { file_path: repoUrl, mode };

            const res = await fetch(`${API}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            if (!res.ok) {
                const d = await res.json().catch(() => ({}));
                throw new Error(d.detail || `HTTP ${res.status}`);
            }

            const data = await res.json();
            setAnalysis(data);
            setScore(data.credibility_score);
            setSkillId(data.domain);
        } catch (e) {
            setError(e.message);
        } finally {
            setAnalyzing(false);
        }
    }

    async function handleSubmit() {
        if (!analysis) return;
        setSubmitting(true);
        setError('');

        try {
            const res = await fetch(`${API}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    skill_id: analysis.domain,
                    score: analysis.credibility_score,
                    mode: analysis.mode,
                    artifact_hash: analysis.artifact_hash,
                    subdomain: analysis.subdomain,
                    source_type: analysis.source_type,
                    source_url: repoUrl,
                }),
            });

            if (!res.ok) {
                const d = await res.json().catch(() => ({}));
                throw new Error(d.detail || `HTTP ${res.status}`);
            }

            setSubmitResult(await res.json());
        } catch (e) {
            setError(e.message);
        } finally {
            setSubmitting(false);
        }
    }

    const tierLabel = score >= 90 ? 'Exceptional' : score >= 70 ? 'Strong' : score >= 50 ? 'Moderate' : score >= 30 ? 'Developing' : 'Minimal';

    return (
        <div className="page">
            <div className="page-header">
                <h1 className="page-title">Submit Evidence</h1>
                <p className="page-subtitle">
                    Upload your repo, certificate, or project. Our AI engine analyzes it, generates a credibility score, and submits it on-chain.
                </p>
            </div>

            {/* Mode Tabs */}
            <div className="mode-tabs">
                <button className={`mode-tab ${mode === 'developer' ? 'active' : ''}`} onClick={() => setMode('developer')}>
                    🛠 Developer
                </button>
                <button className={`mode-tab ${mode === 'learner' ? 'active' : ''}`} onClick={() => setMode('learner')}>
                    📚 Learner
                </button>
            </div>

            <div className="grid-2">
                {/* Left: Input */}
                <div className="card">
                    <div className="card-header">
                        <div className="card-icon">
                            {sourceType === 'repo' ? '🔗' : '📄'}
                        </div>
                        <div>
                            <div className="card-title">Evidence Source</div>
                            <div className="card-description">
                                {mode === 'developer' ? 'Paste a GitHub repo URL' : 'Upload certificate or project path'}
                            </div>
                        </div>
                    </div>

                    {/* Source type selector */}
                    <div className="form-group">
                        <label className="form-label">Source Type</label>
                        <div style={{ display: 'flex', gap: '8px' }}>
                            {['repo', 'certificate', 'project'].map(st => (
                                <button
                                    key={st}
                                    className={`btn ${sourceType === st ? 'btn-primary' : 'btn-secondary'}`}
                                    onClick={() => setSourceType(st)}
                                    style={{ fontSize: '0.8rem', padding: '8px 16px' }}
                                >
                                    {st === 'repo' ? '🔗 Repo' : st === 'certificate' ? '📄 Certificate' : '📁 Project'}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">
                            {sourceType === 'repo' ? 'Repository URL' : sourceType === 'certificate' ? 'Certificate File Path' : 'Project Directory Path'}
                        </label>
                        <input
                            id="evidence-source-input"
                            className="form-input form-input-mono"
                            placeholder={sourceType === 'repo' ? 'https://github.com/owner/repo' : '/path/to/file'}
                            value={repoUrl}
                            onChange={e => setRepoUrl(e.target.value)}
                        />
                    </div>

                    <button
                        id="analyze-btn"
                        className={`btn btn-primary ${analyzing ? 'btn-loading' : ''}`}
                        onClick={handleAnalyze}
                        disabled={analyzing || !repoUrl}
                        style={{ width: '100%' }}
                    >
                        {analyzing ? '' : '🔍 Analyze Evidence'}
                    </button>

                    {error && (
                        <div className="result-panel result-error" style={{ marginTop: '16px' }}>
                            <strong>Error:</strong> {error}
                        </div>
                    )}
                </div>

                {/* Right: Analysis Result */}
                <div className="card" style={{ opacity: analysis ? 1 : 0.4 }}>
                    <div className="card-header">
                        <div className="card-icon">🧠</div>
                        <div>
                            <div className="card-title">AI Analysis</div>
                            <div className="card-description">Credibility assessment preview</div>
                        </div>
                    </div>

                    {analysis ? (
                        <>
                            <ScoreCircle score={analysis.credibility_score} label={tierLabel} />

                            <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: '16px' }}>
                                <div className="stat-card" style={{ padding: '12px' }}>
                                    <div className="stat-value" style={{ fontSize: '1.2rem' }}>{analysis.domain}</div>
                                    <div className="stat-label">Domain</div>
                                </div>
                                <div className="stat-card" style={{ padding: '12px' }}>
                                    <div className="stat-value" style={{ fontSize: '1.2rem' }}>{(analysis.confidence * 100).toFixed(0)}%</div>
                                    <div className="stat-label">Confidence</div>
                                </div>
                            </div>

                            <div className="explanation">{analysis.explanation}</div>

                            {analysis.breakdown?.length > 0 && (
                                <ul className="breakdown-list" style={{ marginTop: '16px' }}>
                                    {analysis.breakdown.map((b, i) => (
                                        <li key={i} className="breakdown-item">
                                            <span className="breakdown-factor">{b.factor.replace(/_/g, ' ')}</span>
                                            <span className="breakdown-score">{(b.raw_score * 100).toFixed(0)}%</span>
                                        </li>
                                    ))}
                                </ul>
                            )}

                            <button
                                id="submit-btn"
                                className={`btn btn-primary ${submitting ? 'btn-loading' : ''}`}
                                onClick={handleSubmit}
                                disabled={submitting}
                                style={{ width: '100%', marginTop: '20px' }}
                            >
                                {submitting ? '' : '⬡ Submit On-Chain'}
                            </button>
                        </>
                    ) : (
                        <div className="empty-state">
                            <div className="empty-state-icon">🔍</div>
                            <p>Analyze evidence to see credibility preview</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Submit Result */}
            {submitResult && (
                <div className="result-panel result-success animate-in" style={{ marginTop: '24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                        <span style={{ fontSize: '1.5rem' }}>✅</span>
                        <strong style={{ fontSize: '1.1rem' }}>Skill Record Submitted On-Chain</strong>
                    </div>
                    <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
                        <div className="stat-card" style={{ padding: '12px' }}>
                            <div className="stat-value" style={{ fontSize: '1rem' }}>{submitResult.skill_id}</div>
                            <div className="stat-label">Domain</div>
                        </div>
                        <div className="stat-card" style={{ padding: '12px' }}>
                            <div className="stat-value" style={{ fontSize: '1rem' }}>{submitResult.score}</div>
                            <div className="stat-label">Score</div>
                        </div>
                        <div className="stat-card" style={{ padding: '12px' }}>
                            <div className="stat-value" style={{ fontSize: '1rem' }}>{submitResult.mode}</div>
                            <div className="stat-label">Mode</div>
                        </div>
                    </div>
                    <div style={{ marginTop: '12px', fontSize: '0.85rem' }}>
                        <strong>TX:</strong>{' '}
                        <a href={submitResult.explorer_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-2)' }}>
                            {submitResult.transaction_id}
                        </a>
                    </div>
                </div>
            )}
        </div>
    );
}
