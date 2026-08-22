import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    // Redirect to the user's own portal if they try to access a role they don't have
    const roleHome = user?.role === 'admin' ? '/admin' : user?.role === 'officer' ? '/officer' : '/applicant';
    return <Navigate to={roleHome} replace />;
  }

  return children;
}
