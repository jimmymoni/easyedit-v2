import React from 'react';
import { LogIn, LogOut, User } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const AuthButton: React.FC = () => {
  const { isAuthenticated, user, login, logout, isLoading, error } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 text-gray-500">
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-900"></div>
        <span className="text-sm">Loading...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex items-center space-x-3">
        {error && (
          <span className="text-sm text-red-600">{error}</span>
        )}
        <button
          onClick={login}
          disabled={isLoading}
          className="flex items-center space-x-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
        >
          <LogIn className="h-4 w-4" />
          <span>Get Demo Token</span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center space-x-3">
      <div className="flex items-center space-x-2 text-gray-700">
        <User className="h-4 w-4" />
        <span className="text-sm font-medium">{user?.email}</span>
        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
          {user?.role}
        </span>
      </div>
      <button
        onClick={logout}
        className="flex items-center space-x-1 text-gray-600 hover:text-gray-900 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors"
      >
        <LogOut className="h-4 w-4" />
        <span className="text-sm">Logout</span>
      </button>
    </div>
  );
};

export default AuthButton;