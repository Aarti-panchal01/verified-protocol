/**
 * SkillTimeline — renders an animated vertical timeline of skill records.
 */
export default function SkillTimeline({ records }) {
    if (!records || records.length === 0) {
        return (
            <div className="empty-state">
                <div className="icon">📭</div>
                <p>No skill records found for this wallet.</p>
            </div>
        )
    }

    const getScoreClass = (score) => {
        if (score >= 70) return 'score-high'
        if (score >= 40) return 'score-mid'
        return 'score-low'
    }

    const formatTimestamp = (ts) => {
        if (!ts) return '—'
        const d = new Date(ts * 1000)
        return d.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        })
    }

    return (
        <div className="timeline">
            {records.map((rec, i) => (
                <div className="timeline-item" key={i} style={{ animationDelay: `${i * 0.08}s` }}>
                    <div className="timeline-dot" />
                    <div className="timeline-card">
                        <div className="record-header">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span className="domain-badge">🧠 {rec.domain}</span>
                                <span className="mode-badge">{rec.mode}</span>
                            </div>
                            <div className={`score-circle ${getScoreClass(rec.score)}`}>
                                {rec.score}
                            </div>
                        </div>
                        <dl className="record-meta">
                            <dt>Artifact Hash</dt>
                            <dd style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
                                {rec.artifact_hash
                                    ? `${rec.artifact_hash.slice(0, 16)}…${rec.artifact_hash.slice(-8)}`
                                    : '—'}
                            </dd>
                            <dt>Timestamp</dt>
                            <dd>{formatTimestamp(rec.timestamp)}</dd>
                        </dl>
                    </div>
                </div>
            ))}
        </div>
    )
}
