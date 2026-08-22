import React, { useState } from 'react';
import { Upload, FileText, CheckCircle, X, File } from 'lucide-react';

export default function DocumentUpload() {
  const [files, setFiles] = useState([
    { id: 1, name: 'bank_statement_2024.pdf', size: '2.4 MB', status: 'Uploaded', type: 'Bank Statement', date: '2024-08-15' },
    { id: 2, name: 'tax_return_2023.pdf', size: '1.8 MB', status: 'Verified', type: 'Tax Return', date: '2024-08-14' },
  ]);

  const requiredDocs = [
    { type: 'Government ID', desc: 'Valid passport or driver\'s license', uploaded: false },
    { type: 'Bank Statement', desc: 'Last 3 months of bank statements', uploaded: true },
    { type: 'Tax Return', desc: 'Most recent tax return', uploaded: true },
    { type: 'Pay Stubs', desc: 'Last 2 months of pay stubs', uploaded: false },
    { type: 'Proof of Address', desc: 'Utility bill or lease agreement', uploaded: false },
  ];

  const handleDrop = (e) => {
    e.preventDefault();
    const newFiles = Array.from(e.dataTransfer?.files || []).map((f, i) => ({
      id: Date.now() + i,
      name: f.name,
      size: `${(f.size / (1024 * 1024)).toFixed(1)} MB`,
      status: 'Uploaded',
      type: 'Other',
      date: new Date().toISOString().split('T')[0],
    }));
    setFiles(prev => [...prev, ...newFiles]);
  };

  const handleFileInput = (e) => {
    const newFiles = Array.from(e.target.files || []).map((f, i) => ({
      id: Date.now() + i,
      name: f.name,
      size: `${(f.size / (1024 * 1024)).toFixed(1)} MB`,
      status: 'Uploaded',
      type: 'Other',
      date: new Date().toISOString().split('T')[0],
    }));
    setFiles(prev => [...prev, ...newFiles]);
  };

  const removeFile = (id) => setFiles(prev => prev.filter(f => f.id !== id));

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Document Upload</h1>
        <p>Upload required documents for your loan application.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24 }}>
        <div>
          {/* Upload Zone */}
          <div
            className="file-upload-zone"
            onDrop={handleDrop}
            onDragOver={e => e.preventDefault()}
            onClick={() => document.getElementById('file-input').click()}
            style={{ marginBottom: 24 }}
          >
            <Upload size={40} />
            <p><span className="upload-cta">Click to upload</span> or drag and drop</p>
            <p style={{ fontSize: '0.75rem', marginTop: 4 }}>PDF, JPG, PNG up to 10MB</p>
            <input id="file-input" type="file" multiple hidden onChange={handleFileInput} accept=".pdf,.jpg,.jpeg,.png" />
          </div>

          {/* Uploaded Files */}
          <div className="card">
            <h4 style={{ marginBottom: 16 }}>Uploaded Documents</h4>
            {files.length === 0 ? (
              <p style={{ color: 'var(--color-ivory-muted)', textAlign: 'center', padding: 24 }}>No documents uploaded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {files.map(f => (
                  <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', background: 'rgba(61,30,109,0.1)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                    <FileText size={20} color="#D4AF37" />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{f.name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)' }}>{f.size} • {f.date}</div>
                    </div>
                    <span className={`badge ${f.status === 'Verified' ? 'badge-emerald' : 'badge-gold'}`}>
                      {f.status === 'Verified' && <CheckCircle size={12} />} {f.status}
                    </span>
                    <button onClick={() => removeFile(f.id)} style={{ background: 'none', border: 'none', color: 'var(--color-ivory-muted)', cursor: 'pointer', padding: 4 }}>
                      <X size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Required Documents Checklist */}
        <div className="card" style={{ height: 'fit-content' }}>
          <h4 style={{ marginBottom: 16 }}>Required Documents</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {requiredDocs.map((doc, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 0', borderBottom: i < requiredDocs.length - 1 ? '1px solid var(--border-subtle)' : 'none' }}>
                {doc.uploaded ? (
                  <CheckCircle size={18} color="#2ECC71" style={{ marginTop: 2, flexShrink: 0 }} />
                ) : (
                  <File size={18} color="#E8E4DD" style={{ marginTop: 2, flexShrink: 0, opacity: 0.5 }} />
                )}
                <div>
                  <div style={{ fontWeight: 500, fontSize: '0.875rem', color: doc.uploaded ? 'var(--color-emerald)' : 'var(--color-ivory)' }}>{doc.type}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-ivory-muted)' }}>{doc.desc}</div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, padding: '10px 12px', background: 'rgba(243,156,18,0.08)', border: '1px solid rgba(243,156,18,0.2)', borderRadius: 'var(--radius-sm)', fontSize: '0.8125rem', color: 'var(--color-amber)' }}>
            ⚠️ 3 documents still required
          </div>
        </div>
      </div>
    </div>
  );
}
