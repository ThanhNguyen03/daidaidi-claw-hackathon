'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2, ToggleLeft, ToggleRight, Edit3, Save, X, Users, BookOpen, ShieldCheck } from 'lucide-react';
import { getApiBaseUrl } from '../lib/api';
import type { OrgRule, User, UserRole } from '../lib/types';

interface AdminPanelProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: User;
}

type AdminTab = 'rules' | 'users';

const ROLE_LABELS: Record<UserRole, string> = {
  admin: '🛡️ Admin',
  account_manager: '💼 Account Manager',
  sales_rep: '🎯 Sales Rep',
};

const SCOPE_OPTIONS = [
  { value: 'all', label: 'Tất cả Agent' },
  { value: 'market_strategy', label: 'Market Strategy' },
  { value: 'product_solution', label: 'Product Solution' },
  { value: 'compliance', label: 'Compliance' },
  { value: 'client_simulator', label: 'Client Simulator' },
];

function authHeader(user: User) {
  return { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' };
}

export function AdminPanel({ isOpen, onClose, currentUser }: AdminPanelProps) {
  const [tab, setTab] = useState<AdminTab>('rules');
  const [rules, setRules] = useState<OrgRule[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New rule form state
  const [showNewRule, setShowNewRule] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newScope, setNewScope] = useState('all');

  // Edit rule state
  const [editId, setEditId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [editScope, setEditScope] = useState('all');

  const base = getApiBaseUrl();

  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${base}/api/admin/rules`, { headers: authHeader(currentUser) });
      const data = await res.json();
      setRules(data.rules ?? []);
    } catch { setError('Không tải được danh sách quy tắc'); }
    finally { setLoading(false); }
  }, [base, currentUser]);

  const loadUsers = useCallback(async () => {
    try {
      const res = await fetch(`${base}/api/admin/users`, { headers: authHeader(currentUser) });
      const data = await res.json();
      setUsers(data.users ?? []);
    } catch { setError('Không tải được danh sách user'); }
  }, [base, currentUser]);

  useEffect(() => {
    if (!isOpen) return;
    loadRules();
    loadUsers();
  }, [isOpen, loadRules, loadUsers]);

  const createRule = async () => {
    if (!newTitle.trim() || !newContent.trim()) return;
    try {
      await fetch(`${base}/api/admin/rules`, {
        method: 'POST',
        headers: authHeader(currentUser),
        body: JSON.stringify({ title: newTitle, content: newContent, scope: newScope }),
      });
      setNewTitle(''); setNewContent(''); setNewScope('all'); setShowNewRule(false);
      await loadRules();
    } catch { setError('Không tạo được quy tắc'); }
  };

  const saveEdit = async () => {
    if (editId === null) return;
    const rule = rules.find(r => r.id === editId);
    if (!rule) return;
    try {
      await fetch(`${base}/api/admin/rules/${editId}`, {
        method: 'PUT',
        headers: authHeader(currentUser),
        body: JSON.stringify({ title: editTitle, content: editContent, scope: editScope, is_active: !!rule.is_active }),
      });
      setEditId(null);
      await loadRules();
    } catch { setError('Không lưu được thay đổi'); }
  };

  const toggleRule = async (id: number) => {
    try {
      await fetch(`${base}/api/admin/rules/${id}/toggle`, {
        method: 'PATCH',
        headers: authHeader(currentUser),
      });
      await loadRules();
    } catch { setError('Không thay đổi được trạng thái'); }
  };

  const deleteRule = async (id: number) => {
    if (!confirm('Xóa quy tắc này?')) return;
    try {
      await fetch(`${base}/api/admin/rules/${id}`, {
        method: 'DELETE',
        headers: authHeader(currentUser),
      });
      await loadRules();
    } catch { setError('Không xóa được quy tắc'); }
  };

  const changeRole = async (userId: number, role: string) => {
    try {
      await fetch(`${base}/api/admin/users/role`, {
        method: 'PUT',
        headers: authHeader(currentUser),
        body: JSON.stringify({ user_id: userId, role }),
      });
      await loadUsers();
    } catch { setError('Không đổi được quyền'); }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-scrim items-start p-4">
      <div className="w-full max-w-3xl rounded-2xl my-8 modal-card">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-text">
            <ShieldCheck size={18} className="text-accent" />
            Admin Panel
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-2 text-text-muted">
            <X size={16} />
          </button>
        </header>

        {/* Tabs */}
        <div className="flex border-b border-border px-6">
          <button
            onClick={() => setTab('rules')}
            className={`admin-tab ${tab === 'rules' ? 'admin-tab--active' : ''}`}
          >
            <BookOpen size={14} />
            Quy tắc Agent ({rules.length})
          </button>
          <button
            onClick={() => setTab('users')}
            className={`admin-tab ${tab === 'users' ? 'admin-tab--active' : ''}`}
          >
            <Users size={14} />
            Quản lý User ({users.length})
          </button>
        </div>

        <div className="p-6">
          {error && (
            <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-xs">
              {error}
              <button className="ml-2 underline" onClick={() => setError(null)}>Đóng</button>
            </div>
          )}

          {/* Rules Tab */}
          {tab === 'rules' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between mb-4">
                <p className="text-xs text-text-muted">
                  Quy tắc bật sẽ được inject vào mọi cuộc trò chuyện của Agent. Tắt để tạm dừng.
                </p>
                <button
                  onClick={() => setShowNewRule(!showNewRule)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity"
                >
                  <Plus size={13} />
                  Thêm quy tắc
                </button>
              </div>

              {/* New Rule Form */}
              {showNewRule && (
                <div className="admin-rule-form">
                  <input
                    className="admin-input"
                    placeholder="Tên quy tắc (ví dụ: Ưu tiên Zalo Mini App)"
                    value={newTitle}
                    onChange={e => setNewTitle(e.target.value)}
                  />
                  <textarea
                    className="admin-input admin-textarea"
                    placeholder="Nội dung quy tắc sẽ được inject vào system prompt của Agent..."
                    value={newContent}
                    onChange={e => setNewContent(e.target.value)}
                    rows={3}
                  />
                  <div className="flex gap-2 items-center">
                    <select className="admin-select" value={newScope} onChange={e => setNewScope(e.target.value)}>
                      {SCOPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                    <button onClick={createRule} className="admin-btn-primary flex items-center gap-1">
                      <Save size={13} /> Lưu
                    </button>
                    <button onClick={() => setShowNewRule(false)} className="admin-btn-ghost">
                      Hủy
                    </button>
                  </div>
                </div>
              )}

              {loading ? (
                <div className="text-center py-8 text-text-muted text-sm">Đang tải...</div>
              ) : rules.length === 0 ? (
                <div className="text-center py-8 text-text-muted text-sm">
                  Chưa có quy tắc nào. Bấm &quot;Thêm quy tắc&quot; để bắt đầu dạy Agent.
                </div>
              ) : (
                rules.map(rule => (
                  <div key={rule.id} className={`admin-rule-card ${rule.is_active ? 'admin-rule-card--active' : 'admin-rule-card--inactive'}`}>
                    {editId === rule.id ? (
                      <div className="space-y-2">
                        <input
                          className="admin-input"
                          value={editTitle}
                          onChange={e => setEditTitle(e.target.value)}
                        />
                        <textarea
                          className="admin-input admin-textarea"
                          value={editContent}
                          onChange={e => setEditContent(e.target.value)}
                          rows={2}
                        />
                        <div className="flex gap-2">
                          <select className="admin-select" value={editScope} onChange={e => setEditScope(e.target.value)}>
                            {SCOPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                          </select>
                          <button onClick={saveEdit} className="admin-btn-primary flex items-center gap-1">
                            <Save size={13} /> Lưu
                          </button>
                          <button onClick={() => setEditId(null)} className="admin-btn-ghost">Hủy</button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start gap-3">
                        <button
                          onClick={() => toggleRule(rule.id)}
                          className={`mt-0.5 shrink-0 transition-colors ${rule.is_active ? 'text-green-600 dark:text-green-400' : 'text-text-muted'}`}
                          title={rule.is_active ? 'Đang bật — bấm để tắt' : 'Đang tắt — bấm để bật'}
                        >
                          {rule.is_active ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                        </button>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="text-sm font-medium text-text">{rule.title}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded-sm bg-bg text-text-muted border border-border">
                              {SCOPE_OPTIONS.find(o => o.value === rule.scope)?.label ?? rule.scope}
                            </span>
                          </div>
                          <p className="text-xs text-text-muted line-clamp-2">{rule.content}</p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            onClick={() => { setEditId(rule.id); setEditTitle(rule.title); setEditContent(rule.content); setEditScope(rule.scope); }}
                            className="p-1.5 rounded-sm hover:bg-surface-2 text-text-muted hover:text-text transition-colors"
                            title="Chỉnh sửa"
                          >
                            <Edit3 size={13} />
                          </button>
                          <button
                            onClick={() => deleteRule(rule.id)}
                            className="p-1.5 rounded-sm hover:bg-red-500/10 text-text-muted hover:text-red-600 dark:hover:text-red-400 transition-colors"
                            title="Xóa"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* Users Tab */}
          {tab === 'users' && (
            <div className="space-y-2">
              <p className="text-xs text-text-muted mb-4">
                Quản lý phân quyền. Tài khoản Admin có thể truy cập Admin Panel và quản lý quy tắc Agent.
              </p>
              {users.map(u => (
                <div key={u.id} className="flex items-center gap-3 px-4 py-3 rounded-xl bg-bg border border-border">
                  <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-accent text-sm font-bold shrink-0">
                    {u.full_name?.[0]?.toUpperCase() ?? '?'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text truncate">{u.full_name}</p>
                    <p className="text-xs text-text-muted truncate">@{u.username}</p>
                  </div>
                  {u.id === currentUser.id ? (
                    <span className="text-xs text-text-muted">{ROLE_LABELS[u.role as UserRole] ?? u.role}</span>
                  ) : (
                    <select
                      className="admin-select text-xs"
                      value={u.role}
                      onChange={e => changeRole(u.id, e.target.value)}
                    >
                      <option value="admin">🛡️ Admin</option>
                      <option value="account_manager">💼 Account Manager</option>
                      <option value="sales_rep">🎯 Sales Rep</option>
                    </select>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
