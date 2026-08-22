import React, { useState, useMemo } from 'react';
import RiskGauge from '../../components/charts/RiskGauge';
import { formatCurrency } from '../../utils/formatters';
import { Calculator, RotateCcw } from 'lucide-react';

export default function EligibilitySimulator() {
  const [income, setIncome] = useState(75000);
  const [loanAmount, setLoanAmount] = useState(200000);
  const [creditScore, setCreditScore] = useState(720);
  const [dti, setDti] = useState(25);
  const [yearsEmployed, setYearsEmployed] = useState(5);

  // Simulated risk score calculation
  const riskScore = useMemo(() => {
    let score = 400;
    score += Math.min(creditScore / 850, 1) * 200;
    score += Math.max(0, (36 - dti) / 36) * 100;
    score += Math.min(yearsEmployed / 10, 1) * 50;
    const lti = loanAmount / income;
    score += Math.max(0, (5 - lti) / 5) * 80;
    score += income > 60000 ? 20 : 0;
    return Math.round(Math.min(Math.max(score, 0), 850));
  }, [income, loanAmount, creditScore, dti, yearsEmployed]);

  const getEligibility = () => {
    if (riskScore >= 700) return { text: 'Likely Eligible', color: 'var(--color-emerald)', desc: 'Based on your inputs, you have a strong profile for loan approval.' };
    if (riskScore >= 550) return { text: 'Potentially Eligible', color: 'var(--color-amber)', desc: 'Your profile shows moderate risk. Consider reducing your DTI or loan amount.' };
    return { text: 'May Need Improvement', color: 'var(--color-ruby)', desc: 'Your current profile suggests higher risk. Improving credit score or reducing debt would help.' };
  };

  const eligibility = getEligibility();

  const reset = () => { setIncome(75000); setLoanAmount(200000); setCreditScore(720); setDti(25); setYearsEmployed(5); };

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Eligibility Simulator</h1>
        <p>Adjust the sliders to see how changes in your profile affect your estimated risk score.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Controls */}
        <div className="card">
          <div className="card-header">
            <h4><Calculator size={18} style={{ marginRight: 8, verticalAlign: 'middle' }} />Adjust Parameters</h4>
            <button className="btn btn-ghost btn-sm" onClick={reset}><RotateCcw size={14} /> Reset</button>
          </div>

          <div className="slider-container">
            <div className="slider-header">
              <label style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)' }}>Annual Income</label>
              <span className="slider-value">{formatCurrency(income)}</span>
            </div>
            <input className="slider-input" type="range" min="20000" max="300000" step="5000" value={income} onChange={e => setIncome(Number(e.target.value))} />
          </div>

          <div className="slider-container">
            <div className="slider-header">
              <label style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)' }}>Loan Amount</label>
              <span className="slider-value">{formatCurrency(loanAmount)}</span>
            </div>
            <input className="slider-input" type="range" min="5000" max="1000000" step="5000" value={loanAmount} onChange={e => setLoanAmount(Number(e.target.value))} />
          </div>

          <div className="slider-container">
            <div className="slider-header">
              <label style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)' }}>Credit Score</label>
              <span className="slider-value">{creditScore}</span>
            </div>
            <input className="slider-input" type="range" min="300" max="850" step="5" value={creditScore} onChange={e => setCreditScore(Number(e.target.value))} />
          </div>

          <div className="slider-container">
            <div className="slider-header">
              <label style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)' }}>Debt-to-Income Ratio (%)</label>
              <span className="slider-value">{dti}%</span>
            </div>
            <input className="slider-input" type="range" min="0" max="60" step="1" value={dti} onChange={e => setDti(Number(e.target.value))} />
          </div>

          <div className="slider-container">
            <div className="slider-header">
              <label style={{ fontSize: '0.8125rem', color: 'var(--color-ivory-muted)' }}>Years at Current Employer</label>
              <span className="slider-value">{yearsEmployed} yrs</span>
            </div>
            <input className="slider-input" type="range" min="0" max="30" step="1" value={yearsEmployed} onChange={e => setYearsEmployed(Number(e.target.value))} />
          </div>
        </div>

        {/* Results */}
        <div>
          <div className="card card-highlight" style={{ marginBottom: 16 }}>
            <h4 style={{ marginBottom: 8, textAlign: 'center' }}>Estimated Risk Score</h4>
            <RiskGauge score={riskScore} size={200} />
          </div>
          <div className="card" style={{ borderLeft: `3px solid ${eligibility.color}` }}>
            <h4 style={{ color: eligibility.color, marginBottom: 8 }}>{eligibility.text}</h4>
            <p style={{ color: 'var(--color-ivory-muted)', fontSize: '0.875rem' }}>{eligibility.desc}</p>
            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={{ padding: '8px 12px', background: 'rgba(61,30,109,0.2)', borderRadius: 'var(--radius-sm)' }}>
                <div className="label-caps" style={{ marginBottom: 4 }}>Loan-to-Income</div>
                <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)' }}>{(loanAmount / income).toFixed(1)}x</div>
              </div>
              <div style={{ padding: '8px 12px', background: 'rgba(61,30,109,0.2)', borderRadius: 'var(--radius-sm)' }}>
                <div className="label-caps" style={{ marginBottom: 4 }}>Monthly Payment Est.</div>
                <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)', color: 'var(--color-gold)' }}>{formatCurrency(Math.round(loanAmount / 360 * 1.05))}/mo</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
