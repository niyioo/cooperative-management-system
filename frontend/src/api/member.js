/** The member portal API (/api/v1/me/). Every call is scoped to the signed-in member by the server. */
import { api } from './client';

const get = (url, params) => api.get(url, { params }).then((r) => r.data);
const post = (url, data, config) => api.post(url, data, config).then((r) => r.data);
const patch = (url, data) => api.patch(url, data).then((r) => r.data);

export const memberApi = {
  dashboard: () => get('/me/dashboard/'),
  profile: () => get('/me/profile/'),
  updateProfile: (data) => patch('/me/profile/', data),

  savings: () => get('/me/savings/'),
  christmas: (year) => get('/me/savings/christmas/', year ? { year } : undefined),
  savingsTransactions: (accountId, page = 1) => get(`/me/savings/accounts/${accountId}/transactions/`, { page }),

  loanProducts: () => get('/me/loan-products/'),
  loanQuote: (productId, amount, termMonths) => get(`/me/loan-products/${productId}/quote/`, { amount, term_months: termMonths }),
  applications: () => get('/me/loan-applications/'),
  application: (id) => get(`/me/loan-applications/${id}/`),
  createApplication: (data) => post('/me/loan-applications/', data),
  updateApplication: (id, data) => patch(`/me/loan-applications/${id}/`, data),
  submitApplication: (id) => post(`/me/loan-applications/${id}/submit/`),
  cancelApplication: (id, reason) => post(`/me/loan-applications/${id}/cancel/`, { reason }),
  uploadApplicationDocument: (id, title, file) => {
    const form = new FormData();
    form.append('title', title);
    form.append('file', file);
    return post(`/me/loan-applications/${id}/documents/`, form);
  },
  lookupGuarantor: (membershipNumber) => get('/me/guarantor-lookup/', { membership_number: membershipNumber }),
  addGuarantor: (applicationId, membershipNumber) => post(`/me/loan-applications/${applicationId}/guarantors/`, { membership_number: membershipNumber }),
  removeGuarantor: (applicationId, guaranteeId) => api.delete(`/me/loan-applications/${applicationId}/guarantors/${guaranteeId}/`).then((r) => r.data),
  guaranteeRequests: (params) => get('/me/guarantee-requests/', params),
  acceptGuarantee: (id) => post(`/me/guarantee-requests/${id}/accept/`),
  declineGuarantee: (id, reason) => post(`/me/guarantee-requests/${id}/decline/`, { reason }),

  loans: () => get('/me/loans/'),
  loan: (id) => get(`/me/loans/${id}/`),
  loanRepayments: (id) => get(`/me/loans/${id}/repayments/`),

  investments: () => get('/me/investments/'),
  investmentTransactions: (accountId) => get(`/me/investments/${accountId}/transactions/`),
  dividends: () => get('/me/dividends/'),

  transactions: (params) => get('/me/transactions/', params),
  statement: (params) => api.get('/me/transactions/statement/', { params, responseType: 'blob' }),

  closureRequests: () => get('/me/closure-requests/'),
  requestClosure: (data) => {
    const form = new FormData();
    Object.entries(data).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') form.append(key, value);
    });
    return post('/me/closure-requests/', form);
  },
  withdrawClosure: (id) => post(`/me/closure-requests/${id}/withdraw/`),

  notifications: (page = 1) => get('/me/notifications/', { page }),
  unreadCount: () => get('/me/notifications/unread-count/'),
  markRead: (id) => post(`/me/notifications/${id}/read/`),
  markAllRead: () => post('/me/notifications/read-all/'),
  announcements: () => get('/me/announcements/'),
};
