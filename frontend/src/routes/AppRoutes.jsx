import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './ProtectedRoute';

// Layouts
import ApplicantLayout from '../layouts/ApplicantLayout';
import OfficerLayout from '../layouts/OfficerLayout';
import AdminLayout from '../layouts/AdminLayout';

// Auth Pages
import Login from '../pages/auth/Login';
import Signup from '../pages/auth/Signup';

// Applicant Pages
import ApplicantHome from '../pages/applicant/Home';
import NewApplication from '../pages/applicant/NewApplication';
import MyApplications from '../pages/applicant/MyApplications';
import RiskReport from '../pages/applicant/RiskReport';
import EligibilitySimulator from '../pages/applicant/EligibilitySimulator';
import DocumentUpload from '../pages/applicant/DocumentUpload';
import ChatSupport from '../pages/applicant/ChatSupport';

// Officer Pages
import OfficerDashboard from '../pages/officer/Dashboard';
import ApplicantQueue from '../pages/officer/ApplicantQueue';
import RiskAnalysis from '../pages/officer/RiskAnalysis';
import ReportsHistory from '../pages/officer/ReportsHistory';

// Admin Pages
import OverviewDashboard from '../pages/admin/OverviewDashboard';
import ManageUsers from '../pages/admin/ManageUsers';
import ModelMonitor from '../pages/admin/ModelMonitor';
import AuditLogs from '../pages/admin/AuditLogs';
import Settings from '../pages/admin/Settings';

export default function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      {/* Applicant Routes */}
      <Route path="/applicant" element={
        <ProtectedRoute allowedRoles={['applicant', 'officer', 'admin']}>
          <ApplicantLayout />
        </ProtectedRoute>
      }>
        <Route index element={<ApplicantHome />} />
        <Route path="new-application" element={<NewApplication />} />
        <Route path="my-applications" element={<MyApplications />} />
        <Route path="risk-report" element={<RiskReport />} />
        <Route path="simulator" element={<EligibilitySimulator />} />
        <Route path="documents" element={<DocumentUpload />} />
        <Route path="chat" element={<ChatSupport />} />
      </Route>

      {/* Officer Routes */}
      <Route path="/officer" element={
        <ProtectedRoute allowedRoles={['officer', 'admin']}>
          <OfficerLayout />
        </ProtectedRoute>
      }>
        <Route index element={<OfficerDashboard />} />
        <Route path="queue" element={<ApplicantQueue />} />
        <Route path="risk-analysis" element={<RiskAnalysis />} />
        <Route path="reports" element={<ReportsHistory />} />
      </Route>

      {/* Admin Routes */}
      <Route path="/admin" element={
        <ProtectedRoute allowedRoles={['admin']}>
          <AdminLayout />
        </ProtectedRoute>
      }>
        <Route index element={<OverviewDashboard />} />
        <Route path="users" element={<ManageUsers />} />
        <Route path="model-monitor" element={<ModelMonitor />} />
        <Route path="audit-logs" element={<AuditLogs />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      {/* Redirect root to login */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
