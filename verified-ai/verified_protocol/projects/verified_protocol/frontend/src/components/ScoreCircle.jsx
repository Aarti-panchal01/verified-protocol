/**
 * ScoreCircle — Animated radial score display
 */
export default function ScoreCircle({ score, size = 120, label = 'Score' }) {
    const radius = (size - 12) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;

    const tierColor = score >= 90 ? 'var(--tier-exceptional)'
        : score >= 70 ? 'var(--tier-strong)'
            : score >= 50 ? 'var(--tier-moderate)'
                : score >= 30 ? 'var(--tier-developing)'
                    : 'var(--tier-minimal)';

    const tierLabel = score >= 90 ? 'Exceptional'
        : score >= 70 ? 'Strong'
            : score >= 50 ? 'Moderate'
                : score >= 30 ? 'Developing'
                    : 'Minimal';

    return (
        <div className="score-circle" style={{ width: size, height: size }}>
            <svg viewBox={`0 0 ${size} ${size}`}>
                <circle
                    className="score-circle-bg"
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                />
                <circle
                    className="score-circle-fill"
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    stroke={tierColor}
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    style={{ filter: `drop-shadow(0 0 6px ${tierColor})` }}
                />
            </svg>
            <div className="score-circle-value">
                <span className="score-number" style={{ color: tierColor }}>{score}</span>
                <span className="score-label">{label}</span>
            </div>
        </div>
    );
}
