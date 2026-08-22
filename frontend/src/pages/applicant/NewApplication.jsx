import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LOAN_PURPOSES, EMPLOYMENT_TYPES } from '../../utils/constants';
import { Check, ChevronRight, ChevronLeft } from 'lucide-react';

const STEPS = ['Personal Info', 'Employment', 'Loan Details', 'Review & Submit'];

export default function NewApplication() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    fullName: '', dob: '', phone: '', address: '',
    employer: '', employmentType: '', income: '', yearsEmployed: '',
    loanAmount: '', purpose: '', term: '36', notes: '',
  });

  const update = (field) => (e) => setForm(prev => ({ ...prev, [field]: e.target.value }));

  const nextStep = () => { if (step < STEPS.length - 1) setStep(step + 1); };
  const prevStep = () => { if (step > 0) setStep(step - 1); };

  const handleSubmit = () => {
    alert('Application submitted successfully! You will be redirected to your applications.');
    navigate('/applicant/my-applications');
  };

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>New Loan Application</h1>
        <p>Complete all steps to submit your application for AI-powered risk assessment.</p>
      </div>

      {/* Stepper */}
      <div className="stepper">
        {STEPS.map((s, i) => (
          <React.Fragment key={s}>
            <div className={`stepper-step ${i === step ? 'active' : ''} ${i < step ? 'completed' : ''}`}>
              <div className="stepper-circle">
                {i < step ? <Check size={16} /> : i + 1}
              </div>
              <span className="stepper-label">{s}</span>
            </div>
            {i < STEPS.length - 1 && <div className={`stepper-line ${i < step ? 'completed' : ''}`} />}
          </React.Fragment>
        ))}
      </div>

      <div className="card" style={{ maxWidth: 700, margin: '0 auto' }}>
        {/* Step 0: Personal Info */}
        {step === 0 && (
          <div className="fade-in">
            <h3 style={{ marginBottom: 24 }}>Personal Information</h3>
            <div className="grid grid-2 gap-6">
              <div className="form-group">
                <label>Full Name</label>
                <input className="form-input" placeholder="Sarah Mitchell" value={form.fullName} onChange={update('fullName')} />
              </div>
              <div className="form-group">
                <label>Date of Birth</label>
                <input className="form-input" type="date" value={form.dob} onChange={update('dob')} />
              </div>
              <div className="form-group">
                <label>Phone Number</label>
                <input className="form-input" placeholder="+1 (555) 123-4567" value={form.phone} onChange={update('phone')} />
              </div>
              <div className="form-group">
                <label>Address</label>
                <input className="form-input" placeholder="123 Main St, City, State" value={form.address} onChange={update('address')} />
              </div>
            </div>
          </div>
        )}

        {/* Step 1: Employment */}
        {step === 1 && (
          <div className="fade-in">
            <h3 style={{ marginBottom: 24 }}>Employment Details</h3>
            <div className="grid grid-2 gap-6">
              <div className="form-group">
                <label>Employer Name</label>
                <input className="form-input" placeholder="Acme Corp" value={form.employer} onChange={update('employer')} />
              </div>
              <div className="form-group">
                <label>Employment Type</label>
                <select className="form-input" value={form.employmentType} onChange={update('employmentType')}>
                  <option value="">Select type</option>
                  {EMPLOYMENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Annual Income ($)</label>
                <input className="form-input" type="number" placeholder="78000" value={form.income} onChange={update('income')} />
              </div>
              <div className="form-group">
                <label>Years at Current Employer</label>
                <input className="form-input" type="number" placeholder="5" value={form.yearsEmployed} onChange={update('yearsEmployed')} />
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Loan Details */}
        {step === 2 && (
          <div className="fade-in">
            <h3 style={{ marginBottom: 24 }}>Loan Details</h3>
            <div className="grid grid-2 gap-6">
              <div className="form-group">
                <label>Loan Amount ($)</label>
                <input className="form-input" type="number" placeholder="250000" value={form.loanAmount} onChange={update('loanAmount')} />
              </div>
              <div className="form-group">
                <label>Loan Purpose</label>
                <select className="form-input" value={form.purpose} onChange={update('purpose')}>
                  <option value="">Select purpose</option>
                  {LOAN_PURPOSES.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Loan Term (months)</label>
                <select className="form-input" value={form.term} onChange={update('term')}>
                  <option value="12">12 months</option>
                  <option value="24">24 months</option>
                  <option value="36">36 months</option>
                  <option value="60">60 months</option>
                  <option value="120">120 months</option>
                  <option value="240">240 months</option>
                  <option value="360">360 months</option>
                </select>
              </div>
            </div>
            <div className="form-group" style={{ marginTop: 8 }}>
              <label>Additional Notes</label>
              <textarea className="form-input" placeholder="Any additional information..." value={form.notes} onChange={update('notes')} rows={3} />
            </div>
          </div>
        )}

        {/* Step 3: Review */}
        {step === 3 && (
          <div className="fade-in">
            <h3 style={{ marginBottom: 24 }}>Review Your Application</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px 32px' }}>
              {[
                ['Full Name', form.fullName || '—'],
                ['Date of Birth', form.dob || '—'],
                ['Phone', form.phone || '—'],
                ['Address', form.address || '—'],
                ['Employer', form.employer || '—'],
                ['Employment Type', form.employmentType || '—'],
                ['Annual Income', form.income ? `$${Number(form.income).toLocaleString()}` : '—'],
                ['Years Employed', form.yearsEmployed || '—'],
                ['Loan Amount', form.loanAmount ? `$${Number(form.loanAmount).toLocaleString()}` : '—'],
                ['Purpose', form.purpose || '—'],
                ['Term', `${form.term} months`],
              ].map(([label, value]) => (
                <div key={label} style={{ marginBottom: 8 }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
                  <div style={{ fontWeight: 500 }}>{value}</div>
                </div>
              ))}
            </div>
            {form.notes && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Notes</div>
                <div>{form.notes}</div>
              </div>
            )}
          </div>
        )}

        {/* Navigation Buttons */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 32 }}>
          <button className="btn btn-ghost" onClick={prevStep} disabled={step === 0} style={{ opacity: step === 0 ? 0.3 : 1 }}>
            <ChevronLeft size={16} /> Previous
          </button>
          {step < STEPS.length - 1 ? (
            <button className="btn btn-primary" onClick={nextStep}>
              Next <ChevronRight size={16} />
            </button>
          ) : (
            <button className="btn btn-primary btn-lg" onClick={handleSubmit}>
              Submit Application
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
