import React from 'react';
import { mockApplications, mockMonthlyTrends, mockRiskDistribution, mockPurposeBreakdown, mockModelMetrics } from '../../utils/mockData';
import { formatCurrency } from '../../utils/formatters';
import TrendLineChart from '../../components/charts/TrendLineChart';
import DonutChart from '../../components/charts/DonutChart';
import BarChartComponent from '../../components/charts/BarChart';
import { Users, DollarSign, Activity, Shield, TrendingUp, BarChart3 } from 'lucide-react';

export default function OverviewDashboard() {
  const totalVolume = mockApplications.reduce((sum, a) => sum + a.loanAmount, 0);

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Admin Overview</h1>
        <p>System-wide metrics, model health, and operational analytics.</p>
      </div>

      {/* Top Stats */}
      <div className="grid grid-4 gap-6" style={{ marginBottom: 32 }}>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(212,175,55,0.15)', color: '#D4AF37' }}><DollarSign size={22} /></div>
          <div className="stat-value">{formatCurrency(totalVolume)}</div>
          <div className="stat-label">Total Loan Volume</div>
          <div className="stat-change positive"><TrendingUp size={12} /> +18% MoM</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(46,204,113,0.15)', color: '#2ECC71' }}><Activity size={22} /></div>
          <div className="stat-value">{(mockModelMetrics.aucRoc * 100).toFixed(1)}%</div>
          <div className="stat-label">Model AUC-ROC</div>
          <div className="stat-change positive"><TrendingUp size={12} /> Excellent</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(52,152,219,0.15)', color: '#3498DB' }}><Users size={22} /></div>
          <div className="stat-value">6</div>
          <div className="stat-label">Active Users</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(91,46,157,0.15)', color: '#7B4FBF' }}><Shield size={22} /></div>
          <div className="stat-value">{mockModelMetrics.driftScore}</div>
          <div className="stat-label">Model Drift</div>
          <div className="stat-change positive"><TrendingUp size={12} /> Within threshold</div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-3 gap-6" style={{ marginBottom: 32 }}>
        <div className="card" style={{ gridColumn: 'span 1' }}>
          <div className="card-header"><h4>Risk Distribution</h4></div>
          <DonutChart data={mockRiskDistribution} height={240} />
        </div>
        <div className="card" style={{ gridColumn: 'span 2' }}>
          <div className="card-header">
            <h4>Monthly Trends</h4>
            <span className="badge badge-gold">6 Months</span>
          </div>
          <TrendLineChart
            data={mockMonthlyTrends}
            lines={[
              { dataKey: 'applications', name: 'Applications', color: '#D4AF37' },
              { dataKey: 'approved', name: 'Approved', color: '#2ECC71' },
              { dataKey: 'avgScore', name: 'Avg Score', color: '#3498DB' },
            ]}
            height={240}
          />
        </div>
      </div>

      {/* Purpose Breakdown */}
      <div className="card">
        <div className="card-header">
          <h4><BarChart3 size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />Loan Purpose Breakdown</h4>
        </div>
        <BarChartComponent data={mockPurposeBreakdown} dataKey="count" nameKey="name" color="#D4AF37" height={260} />
      </div>
    </div>
  );
}
