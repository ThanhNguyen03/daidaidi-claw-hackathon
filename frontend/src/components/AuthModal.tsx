'use client';

import React, { useState } from 'react';
import { Eye, EyeOff, LogIn, UserPlus, Sparkles, Shield } from 'lucide-react';
import { getApiBaseUrl } from '../lib/api';
import type { User } from '../lib/types';

interface AuthModalProps {
  onSuccess: (user: User) => void;
}

type Tab = 'login' | 'register';

export function AuthModal({ onSuccess }: AuthModalProps) {
  const [tab, setTab] = useState<Tab>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const endpoint = tab === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body: Record<string, string> = { username, password };
      if (tab === 'register') body.full_name = fullName;

      const res = await fetch(`${getApiBaseUrl()}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Đã xảy ra lỗi');

      // Persist token to localStorage
      localStorage.setItem('auth_token', data.token);
      localStorage.setItem('auth_user', JSON.stringify(data));
      onSuccess(data as User);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đã xảy ra lỗi');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-modal-overlay tf-stage">
      <span className="tf-orb tf-orb--1" />
      <span className="tf-orb tf-orb--2" />
      <div className="auth-modal-card tf-card overflow-hidden">
        {/* Header */}
        <div className="auth-modal-header">
          <div className="auth-modal-logo tf-mark">
            <Sparkles size={28} />
          </div>
          <h1 className="auth-modal-title">Z-PreSales Agent</h1>
          <p className="auth-modal-subtitle">Multi-Agent Sales Assistant</p>
        </div>

        {/* Tab Switcher */}
        <div className="auth-tab-row">
          <button
            className={`auth-tab ${tab === 'login' ? 'auth-tab--active' : ''}`}
            onClick={() => { setTab('login'); setError(null); }}
          >
            <LogIn size={14} />
            Đăng nhập
          </button>
          <button
            className={`auth-tab ${tab === 'register' ? 'auth-tab--active' : ''}`}
            onClick={() => { setTab('register'); setError(null); }}
          >
            <UserPlus size={14} />
            Đăng ký
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-form">
          {tab === 'register' && (
            <div className="auth-field">
              <label className="auth-label">Họ và tên</label>
              <input
                className="auth-input"
                type="text"
                placeholder="Nguyễn Văn A"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                autoFocus
              />
            </div>
          )}

          <div className="auth-field">
            <label className="auth-label">Tên đăng nhập</label>
            <input
              className="auth-input"
              type="text"
              placeholder="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus={tab === 'login'}
              autoComplete="username"
            />
          </div>

          <div className="auth-field">
            <label className="auth-label">Mật khẩu</label>
            <div className="auth-input-wrapper">
              <input
                className="auth-input"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              />
              <button
                type="button"
                className="auth-eye-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label="Toggle password visibility"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="auth-error">{error}</div>
          )}

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span className="auth-spinner" />
            ) : tab === 'login' ? (
              <><LogIn size={16} /> Đăng nhập</>
            ) : (
              <><UserPlus size={16} /> Tạo tài khoản</>
            )}
          </button>
        </form>

        {tab === 'register' && (
          <p className="auth-admin-hint">
            <Shield size={12} />
            Tài khoản đầu tiên đăng ký sẽ tự động là <strong>Admin</strong>
          </p>
        )}
      </div>
    </div>
  );
}
