/** The officer portal API (/api/v1/admin/). The server checks every permission again. */
import { api } from './client';

const get = (url, params) => api.get(url, { params }).then((r) => r.data);
const post = (url, data) => api.post(url, data).then((r) => r.data);
const patch = (url, data) => api.patch(url, data).then((r) => r.data);
const put = (url, data) => api.put(url, data).then((r) => r.data);
const del = (url) => api.delete(url).then((r) => r.data);
const blob = (url, params) => api.get(url, { params, responseType: 'blob' });
const form = (data) => {
  const body = new FormData();
  Object.entries(data).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') body.append(key, value);
  });
  return body;
};

/** List/retrieve/create/update plus detail actions for a router collection such as "/admin/members/". */
const resource = (path) => ({
  list: (params) => get(path, params),
  get: (id) => get(`${path}${id}/`),
  create: (data) => post(path, data),
  update: (id, data) => patch(`${path}${id}/`, data),
  action: (id, name, data) => post(`${path}${id}/${name}/`, data),
  sub: (id, name, params) => get(`${path}${id}/${name}/`, params),
});

export const adminApi = {
  dashboard: () => get('/admin/dashboard/'),

  members: {
    ...resource('/admin/members/'),
    uploadDocument: (id, data) => post(`/admin/members/${id}/documents/`, form(data)),
    verifyDocument: (id, docId) => post(`/admin/members/${id}/documents/${docId}/verify/`),
    removeDocument: (id, docId) => del(`/admin/members/${id}/documents/${docId}/`),
    downloadDocument: (id, docId) => blob(`/admin/members/${id}/documents/${docId}/download/`),
    photo: (id) => blob(`/admin/members/${id}/photo/`),
    uploadPhoto: (id, file) => put(`/admin/members/${id}/photo/`, form({ photo: file })),
    addNextOfKin: (id, data) => post(`/admin/members/${id}/next-of-kin/`, data),
    removeNextOfKin: (id, kinId) => del(`/admin/members/${id}/next-of-kin/${kinId}/`),
  },
  memberImports: {
    list: (params) => get('/admin/members/imports/', params),
    get: (id) => get(`/admin/members/imports/${id}/`),
    upload: (file) => post('/admin/members/imports/', form({ file })),
    commit: (id, sendActivation) => post(`/admin/members/imports/${id}/commit/`, { send_activation: sendActivation }),
    template: () => blob('/admin/members/imports/template/'),
  },
  closures: { ...resource('/admin/closure-requests/'), attachment: (id) => blob(`/admin/closure-requests/${id}/attachment/`) },

  savingsProducts: resource('/admin/savings/products/'),
  savingsCycles: resource('/admin/savings/cycles/'),
  savingsAccounts: resource('/admin/savings/accounts/'),
  contribute: (data) => post('/admin/savings/contributions/', data),
  withdraw: (data) => post('/admin/savings/withdrawals/', data),
  deductionSchedule: (params) => get('/admin/savings/deduction-schedule/', params),
  downloadDeductionSchedule: (params) => blob('/admin/savings/deduction-schedule/download/', params),

  loanProducts: resource('/admin/loans/products/'),
  loanApplications: {
    ...resource('/admin/loans/applications/'),
    downloadDocument: (id, docId) => blob(`/admin/loans/applications/${id}/documents/${docId}/download/`),
  },
  loans: {
    ...resource('/admin/loans/'),
    overdue: (params) => get('/admin/loans/overdue/', params),
    eligibility: (params) => get('/admin/loans/eligibility/', params),
  },

  investmentProducts: resource('/admin/investments/products/'),
  investmentAccounts: resource('/admin/investments/accounts/'),
  investmentReturns: resource('/admin/investments/returns/'),

  dividendCycles: resource('/admin/dividends/cycles/'),

  transactions: {
    ...resource('/admin/transactions/'),
    pending: (params) => get('/admin/transactions/pending/', params),
    adjust: (data) => post('/admin/transactions/adjustments/', data),
    summary: (params) => get('/admin/transactions/summary/', params),
  },
  batches: {
    ...resource('/admin/batches/'),
    upload: (data) => post('/admin/batches/', form(data)),
    template: (type) => blob('/admin/batches/template/', { type }),
  },

  departments: resource('/admin/departments/'),
  officers: { ...resource('/admin/officers/'), setRoles: (id, roles) => put(`/admin/officers/${id}/roles/`, { roles }) },
  roles: { ...resource('/admin/roles/'), remove: (id) => del(`/admin/roles/${id}/`) },
  permissions: () => get('/admin/permissions/'),
  settings: { get: () => get('/admin/settings/'), update: (data) => patch('/admin/settings/', data) },
  auditLogs: { list: (params) => get('/admin/audit-logs/', params), actions: () => get('/admin/audit-logs/actions/') },

  reports: {
    catalogue: () => get('/admin/reports/'),
    run: (key, params) => get(`/admin/reports/${key}/`, params),
    export: (key, params, format) => blob(`/admin/reports/${key}/`, { ...params, format }),
  },
  announcements: resource('/admin/announcements/'),
  messages: resource('/admin/messages/'),
};

/** Fetch every page of a small reference list (products, departments, roles) for drop-downs. */
export async function allPages(fetcher, params = {}) {
  const first = await fetcher({ ...params, page_size: 100 });
  return Array.isArray(first) ? first : first.results;
}
