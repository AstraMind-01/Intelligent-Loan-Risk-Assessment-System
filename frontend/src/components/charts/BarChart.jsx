import React from 'react';
import { BarChart as ReBarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload) return null;
  return (
    <div style={{ background: '#1A1240', border: '1px solid #3D1E6D', borderRadius: '8px', padding: '12px 16px', boxShadow: '0 4px 24px rgba(61,30,109,0.4)' }}>
      <p style={{ color: '#D4AF37', fontWeight: 600, marginBottom: 4, fontFamily: 'Playfair Display' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontSize: '0.8125rem' }}>
          {p.name}: <strong>{p.value}</strong>
        </p>
      ))}
    </div>
  );
};

export default function BarChartComponent({ data, dataKey = 'count', nameKey = 'name', color = '#D4AF37', height = 300 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ReBarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2A1854" />
        <XAxis dataKey={nameKey} stroke="#E8E4DD" fontSize={11} tickLine={false} angle={-20} textAnchor="end" height={60} />
        <YAxis stroke="#E8E4DD" fontSize={12} tickLine={false} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} maxBarSize={40} />
      </ReBarChart>
    </ResponsiveContainer>
  );
}
