import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload) return null;
  return (
    <div style={{ background: '#1A1240', border: '1px solid #3D1E6D', borderRadius: '8px', padding: '12px 16px', boxShadow: '0 4px 24px rgba(61,30,109,0.4)' }}>
      <p style={{ color: '#D4AF37', fontWeight: 600, marginBottom: 6, fontFamily: 'Playfair Display' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontSize: '0.8125rem', margin: '2px 0' }}>
          {p.name}: <strong>{p.value}</strong>
        </p>
      ))}
    </div>
  );
};

export default function TrendLineChart({ data, lines = [], height = 300 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2A1854" />
        <XAxis dataKey="month" stroke="#E8E4DD" fontSize={12} tickLine={false} />
        <YAxis stroke="#E8E4DD" fontSize={12} tickLine={false} />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: '0.8125rem', color: '#E8E4DD' }} />
        {lines.map((line, i) => (
          <Line
            key={line.dataKey}
            type="monotone"
            dataKey={line.dataKey}
            name={line.name}
            stroke={line.color || ['#D4AF37', '#2ECC71', '#3498DB', '#F39C12'][i % 4]}
            strokeWidth={2}
            dot={{ r: 4, fill: line.color || '#D4AF37' }}
            activeDot={{ r: 6 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
