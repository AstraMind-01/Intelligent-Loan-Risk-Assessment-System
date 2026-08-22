import React, { createContext, useContext, useState } from 'react';
import { mockUsers } from '../utils/mockData';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const login = (email, password, role = 'applicant') => {
    // Mock login — in production this calls authService
    const mockUser = mockUsers[role] || mockUsers.applicant;
    setUser({ ...mockUser, role });
    setIsAuthenticated(true);
    localStorage.setItem('user', JSON.stringify({ ...mockUser, role }));
    return { success: true, user: mockUser };
  };

  const signup = (name, email, password) => {
    const newUser = { id: 'u-new', name, email, role: 'applicant', avatar: name.split(' ').map(n => n[0]).join('') };
    setUser(newUser);
    setIsAuthenticated(true);
    localStorage.setItem('user', JSON.stringify(newUser));
    return { success: true };
  };

  const logout = () => {
    setUser(null);
    setIsAuthenticated(false);
    localStorage.removeItem('user');
  };

  const switchRole = (role) => {
    const mockUser = mockUsers[role];
    if (mockUser) {
      setUser({ ...mockUser, role });
      localStorage.setItem('user', JSON.stringify({ ...mockUser, role }));
    }
  };

  // Auto-restore session
  React.useEffect(() => {
    const stored = localStorage.getItem('user');
    if (stored) {
      const parsed = JSON.parse(stored);
      setUser(parsed);
      setIsAuthenticated(true);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, login, signup, logout, switchRole }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

export default AuthContext;
