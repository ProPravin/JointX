/* Shared helpers used across all JointX pages. */
window.JointX = (function () {
  async function api(path, method = 'GET', body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
    };
    if (body !== null && method !== 'GET') {
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    let data;
    try {
      data = await res.json();
    } catch (e) {
      data = { success: false, error: 'Invalid server response' };
    }
    return data;
  }

  let _lastSyncStatus = null;

  function renderSyncIndicator() {
    const label = document.getElementById('connLabel');
    const pill = document.getElementById('conn-pill');
    if (!label || !_lastSyncStatus) return;
    const t = window.JointXI18n ? window.JointXI18n.t : (k) => k;
    label.textContent = t(_lastSyncStatus.online ? 'conn.online' : 'conn.offline');
    if (pill) pill.classList.toggle('off', !_lastSyncStatus.online);
  }

  async function refreshSyncIndicator() {
    if (!document.getElementById('connLabel')) return;
    try {
      const res = await api('/api/sync/status', 'GET');
      if (res.success) {
        _lastSyncStatus = res.data;
        renderSyncIndicator();
      }
    } catch (e) {
      // Silently ignore — offline-first, sync indicator is a nicety only.
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async () => {
        await api('/api/auth/logout', 'POST', {});
        window.location.href = '/login';
      });
    }
    refreshSyncIndicator();
  });

  return { api, refreshSyncIndicator, renderSyncIndicator };
})();
