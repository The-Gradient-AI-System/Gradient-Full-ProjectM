const LOCAL_API_URL = 'http://127.0.0.1:8000';

const isLocalFrontend = () => {
  if (typeof window === 'undefined') {
    return process.env.NODE_ENV === 'development';
  }
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1';
};

/**
 * Local dev (localhost:3000) → local backend.
 * Production (Vercel) → REACT_APP_API_URL from build env (set in Vercel dashboard).
 */
const resolveApiUrl = () => {
  if (isLocalFrontend()) {
    return LOCAL_API_URL;
  }

  const fromEnv = process.env.REACT_APP_API_URL?.trim();
  if (fromEnv) {
    return fromEnv.replace(/\/$/, '');
  }

  return LOCAL_API_URL;
};

const API_URL = resolveApiUrl();

export const getApiUrl = () => API_URL;

export const resolveAvatarUrl = (url) => {
  if (!url) return '';
  if (
    url.startsWith('data:') ||
    url.startsWith('blob:') ||
    url.startsWith('http://') ||
    url.startsWith('https://')
  ) {
    return url;
  }
  if (url.startsWith('/')) {
    return `${API_URL}${url}`;
  }
  return `${API_URL}/${url}`;
};



let authToken = null;



const getSessionStorage = () => {

  if (typeof window === 'undefined') return null;

  try {

    return window.sessionStorage;

  } catch (error) {

    console.warn('Session storage unavailable:', error);

    return null;

  }

};



export const loadAuthToken = () => {

  const storage = getSessionStorage();

  authToken = storage?.getItem('authToken') || null;

  return authToken;

};



export const setAuthToken = token => {

  authToken = token;

  const storage = getSessionStorage();

  if (!storage) return;



  if (token) {

    storage.setItem('authToken', token);

  } else {

    storage.removeItem('authToken');

  }

};



export const clearAuthToken = () => setAuthToken(null);



const parseJsonSafely = async response => {

  const text = await response.text();

  if (!text) return null;

  try {

    return JSON.parse(text);

  } catch (error) {

    throw new Error(text || response.statusText);

  }

};



const parseErrorDetail = (detail) => {
  if (!detail) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'string' ? item : item?.msg || JSON.stringify(item)))
      .join(', ');
  }
  if (typeof detail === 'object') {
    return detail.msg || detail.message || JSON.stringify(detail);
  }
  return String(detail);
};

const request = async (path, options = {}) => {
  const headers = new Headers(options.headers || {});
  const isFormData =
    typeof FormData !== 'undefined' && options?.body && options.body instanceof FormData;
  // For FormData we must NOT set Content-Type manually (browser adds proper boundary).
  if (!isFormData) {
    headers.set('Content-Type', 'application/json');
  }

  if (!authToken) {
    loadAuthToken();
  }

  if (authToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });



  if (!response.ok) {

    const errorBody = await parseJsonSafely(response).catch(() => null);

    const detail = parseErrorDetail(errorBody?.detail || errorBody?.message);

    if (response.status === 401) {
      clearAuthToken();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('auth:session-expired', { detail }));
      }
    }

    throw new Error(detail || response.statusText || 'Request failed');

  }



  if (response.status === 204) {

    return null;

  }



  return parseJsonSafely(response);

};



export const loginRequest = credentials =>

  request('/auth/login', {

    method: 'POST',

    body: JSON.stringify(credentials),

  });



export const logoutRequest = () =>

  request('/auth/logout', {

    method: 'POST',

  });



export const registerRequest = payload =>

  request('/auth/register', {

    method: 'POST',

    body: JSON.stringify(payload),

  });



export const postGmailSync = () =>

  request('/gmail/sync', {

    method: 'POST',

  });

export const getGmailLeads = (rangeDays = null, { lightweight = false } = {}) => {
  const params = new URLSearchParams();
  if (rangeDays != null && rangeDays !== '') {
    params.set('range_days', String(rangeDays));
  }
  if (lightweight) {
    params.set('lightweight', 'true');
  }
  const qs = params.toString() ? `?${params.toString()}` : '';
  return request(`/gmail/leads${qs}`);
};

export const postLeadInsights = (payload) =>

  request('/gmail/lead-insights', {

    method: 'POST',

    body: JSON.stringify(payload),

  });



export const getLeadProfile = (email) => request(`/gmail/lead-profile?email=${encodeURIComponent(email)}`);

export const getStatusHistory = (gmail_id) => request(`/gmail/status-history?gmail_id=${encodeURIComponent(gmail_id)}`);

export const postLeadStatus = (payload) =>
  request('/gmail/lead-status', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const postEmailAction = (msgId, action) =>
  request(`/emails/${encodeURIComponent(msgId)}/action`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  });

export const assignLead = (gmail_id) =>
  request('/leads/assign', {
    method: 'POST',
    body: JSON.stringify({ gmail_id }),
  });

export const deleteLead = (gmail_id) =>
  request(`/leads/delete?gmail_id=${encodeURIComponent(gmail_id)}`, {
    method: 'DELETE',
  });



export const postGenerateReplies = (payload) =>

  request('/gmail/generate-replies', {

    method: 'POST',

    body: JSON.stringify(payload),

  });



export const getReplyPrompts = () => request('/settings/reply-prompts');



export const updateReplyPrompts = (payload) =>
  request('/settings/reply-prompts', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });

export const getManagers = () => request('/admin/managers');

export const getManagersStatus = () => request('/users/managers/status');

export const createManager = (payload) =>
  request('/admin/managers', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const setManagerStatus = (managerId, payload) =>
  request(`/admin/managers/${encodeURIComponent(managerId)}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const resetManagerPassword = (managerId, payload) =>
  request(`/admin/managers/${encodeURIComponent(managerId)}/reset-password`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const deleteManager = (managerId, confirmUsername) =>
  request(
    `/admin/managers/${encodeURIComponent(managerId)}?confirm_username=${encodeURIComponent(
      confirmUsername || ''
    )}`,
    {
    method: 'DELETE',
    }
  );

export const assignManagerAsAdmin = (userId) =>
  request(`/users/${encodeURIComponent(userId)}/assign-admin`, {
    method: 'POST',
  });

export const updateManagerRole = (managerId, role) =>
  request(`/admin/managers/${encodeURIComponent(managerId)}/role`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  });

export const getMyProfile = () => request('/profile/me');

export const updateMyProfile = (payload) =>
  request('/profile/me', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });

export const updateMyUsername = (payload) =>
  request('/profile/me/username', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const updateMyEmail = (payload) =>
  request('/profile/me/email', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const updateMyPassword = (payload) =>
  request('/profile/me/password', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });

export const updateMyAvatar = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return request('/users/avatar', {
    method: 'POST',
    body: formData,
  });
};

export const forgotPassword = (payload) =>
  request('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const resetPassword = (payload) =>
  request('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const sendEmailWithAttachments = (payload) => {
  const formData = new FormData();

  // Add text fields
  Object.keys(payload).forEach(key => {
    if (key !== 'attachments') {
      formData.append(key, payload[key]);
    }
  });

  // Add files
  if (payload.attachments) {
    payload.attachments.forEach(file => {
      formData.append('attachments', file);
    });
  }

  return request('/email/send', {
    method: 'POST',
    body: formData,
    headers: {}, // Let browser set Content-Type for FormData
  });
};
