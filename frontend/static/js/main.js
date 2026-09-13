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

  async function refreshSyncIndicator() {
    const el = document.getElementById('sync-indicator');
    if (!el) return;
    try {
      const res = await api('/api/sync/status', 'GET');
      if (res.success) {
        const d = res.data;
        el.textContent = d.online
          ? `Online — ${d.pending_count} pending`
          : `Offline — ${d.pending_count} pending`;
        el.className = 'pill ' + (d.online ? '' : 'pill-muted');
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

  return { api, refreshSyncIndicator };
})();
