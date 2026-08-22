import React from 'react';

/**
 * RiskGauge — SVG semi-circular gauge showing risk score 0-850
 */
export default function RiskGauge({ score = 0, size = 220 }) {
  const maxScore = 850;
  const pct = Math.min(score / maxScore, 1);
  const cx = size / 2;
  const cy = size / 2 + 10;
  const r = size / 2 - 20;
  const startAngle = Math.PI;
  const endAngle = 0;
  const sweepAngle = startAngle - (startAngle - endAngle) * pct;

  const arcX = cx + r * Math.cos(sweepAngle);
  const arcY = cy - r * Math.sin(sweepAngle);
  const startX = cx + r * Math.cos(startAngle);
  const startY = cy - r * Math.sin(startAngle);

  // Background arc (full semi-circle)
  const bgEndX = cx + r * Math.cos(endAngle);
  const bgEndY = cy - r * Math.sin(endAngle);

  const getColor = () => {
    if (score >= 700) return '#2ECC71';
    if (score >= 550) return '#F39C12';
    return '#E74C3C';
  };

  const getLabel = () => {
    if (score >= 700) return 'Low Risk';
    if (score >= 550) return 'Moderate';
    return 'High Risk';
  };

  return (
    <div className="risk-gauge-container">
      <svg width={size} height={size / 2 + 40} className="risk-gauge-svg" viewBox={`0 0 ${size} ${size / 2 + 40}`}>
        {/* Background track */}
        <path
          d={`M ${startX} ${startY} A ${r} ${r} 0 0 1 ${bgEndX} ${bgEndY}`}
          fill="none"
          stroke="#2A1854"
          strokeWidth="14"
          strokeLinecap="round"
        />
        {/* Score arc */}
        {score > 0 && (
          <path
            d={`M ${startX} ${startY} A ${r} ${r} 0 ${pct > 0.5 ? 1 : 0} 1 ${arcX} ${arcY}`}
            fill="none"
            stroke={getColor()}
            strokeWidth="14"
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 8px ${getColor()}40)` }}
          />
        )}
        {/* Needle */}
        <circle cx={arcX} cy={arcY} r="8" fill="#D4AF37" style={{ filter: 'drop-shadow(0 0 6px #D4AF3780)' }} />
        <circle cx={arcX} cy={arcY} r="4" fill="#1A1240" />
        {/* Center dot */}
        <circle cx={cx} cy={cy} r="5" fill="#D4AF37" />
        {/* Scale labels */}
        <text x={startX - 5} y={cy + 24} fill="#E8E4DD" fontSize="11" textAnchor="middle" fontFamily="Inter">0</text>
        <text x={cx} y={cy - r - 8} fill="#E8E4DD" fontSize="11" textAnchor="middle" fontFamily="Inter">425</text>
        <text x={bgEndX + 5} y={cy + 24} fill="#E8E4DD" fontSize="11" textAnchor="middle" fontFamily="Inter">850</text>
      </svg>
      <div className="risk-gauge-label">
        <div className="risk-gauge-score">{score}</div>
        <div className="risk-gauge-text" style={{ color: getColor() }}>{getLabel()}</div>
      </div>
    </div>
  );
}
