/**
 * Timeline — Record history display
 */
export default function Timeline({ records = [] }) {
    if (!records.length) {
        return (
            <div className="empty-state">
                <div className="empty-state-icon">📭</div>
                <p>No records to display</p>
            </div>
        );
    }

    return (
        <div className="timeline">
            {records.map((rec, i) => {
                const dt = rec.timestamp
                    ? new Date(rec.timestamp * 1000).toLocaleDateString('en-US', {
                        month: 'short', day: 'numeric', year: 'numeric',
                    })
                    : 'Unknown';

                const score = rec.score ?? 0;
                const tierColor = score >= 90 ? 'var(--tier-exceptional)'
                    : score >= 70 ? 'var(--tier-strong)'
                        : score >= 50 ? 'var(--tier-moderate)'
                            : score >= 30 ? 'var(--tier-developing)'
                                : 'var(--tier-minimal)';

                return (
                    <div className="timeline-item" key={i} style={{ animationDelay: `${i * 0.1}s` }}>
                        <div className="timeline-dot" style={{ background: tierColor, boxShadow: `0 0 0 3px ${tierColor}33` }} />
                        <div className="timeline-card">
                            <div className="timeline-header">
                                <span className="timeline-domain">{rec.domain || 'Unknown'}</span>
                                <span className="timeline-score" style={{ color: tierColor, background: `${tierColor}18` }}>
                                    {score}/100
                                </span>
                            </div>
                            <div className="timeline-meta">
                                <span className="tag tag-mode">{rec.mode || 'unknown'}</span>
                                <span>{dt}</span>
                            </div>
                            {rec.artifact_hash && (
                                <div className="timeline-hash">🔗 {rec.artifact_hash}</div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
