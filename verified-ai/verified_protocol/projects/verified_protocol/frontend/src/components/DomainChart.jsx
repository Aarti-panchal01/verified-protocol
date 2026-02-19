/**
 * DomainChart — Horizontal bar chart of domain scores
 */
export default function DomainChart({ domainScores = [] }) {
    if (!domainScores.length) {
        return <div className="empty-state"><p>No domain data yet</p></div>;
    }

    const maxScore = Math.max(...domainScores.map(d => d.score), 1);

    return (
        <div className="domain-chart">
            {domainScores.map((ds, i) => (
                <div className="domain-bar" key={ds.domain} style={{ animationDelay: `${i * 0.1}s` }}>
                    <span className="domain-bar-label">{ds.domain}</span>
                    <div className="domain-bar-track">
                        <div
                            className="domain-bar-fill"
                            style={{ width: `${(ds.score / maxScore) * 100}%` }}
                        />
                    </div>
                    <span className="domain-bar-value">{Math.round(ds.score)}</span>
                    {ds.trend && ds.trend !== 'stable' && (
                        <span className={`tag tag-trend-${ds.trend}`}>
                            {ds.trend === 'rising' ? '↑' : '↓'}
                        </span>
                    )}
                </div>
            ))}
        </div>
    );
}
