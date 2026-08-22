import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.[0]) return null;
  const d = payload[0];
  return (
    <div style={{ background: '#1A1240', border: '1px solid #3D1E6D', borderRadius: '8px', padding: '12px 16px', boxShadow: '0 4px 24px rgba(61,30,109,0.4)' }}>
      <p style={{ color: d.payload.color || '#D4AF37', fontWeight: 600, fontSize: '0.875rem' }}>{d.name}</p>
      <p style={{ color: '#FAF7F0', fontSize: '0.8125rem' }}>Value: <strong>{d.value}%</strong></p>
    </div>
  );
};

const COLORS = ['#2ECC71', '#F39C12', '#E74C3C', '#3498DB', '#D4AF37', '#7B4FBF'];

export default function DonutChart({ data, height = 280 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={3}
          dataKey="value"
          stroke="none"
        >
          {data.map((entry, index) => (
            <Cell key={index} fill={entry.color || COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: '0.8125rem', color: '#E8E4DD' }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
