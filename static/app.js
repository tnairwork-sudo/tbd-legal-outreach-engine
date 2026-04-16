const body = document.getElementById('targetsBody');
const toast = document.getElementById('toast');
const busy = document.getElementById('busy');
const dailyCountEl = document.getElementById('dailyCount');

function setBusy(on) {
  busy.classList.toggle('hidden', !on);
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 1800);
}

function statusSelect(target) {
  const options = ['Pending', 'Contacted', 'Replied', 'Meeting Booked', 'Retained'];
  return `<select data-action="status" data-id="${target.id}">${options
    .map((s) => `<option value="${s}" ${target.status === s ? 'selected' : ''}>${s}</option>`)
    .join('')}</select>`;
}

function scoreClass(score) {
  const val = Number(score || 0);
  if (val >= 80) return 'score-green';
  if (val >= 60) return 'score-yellow';
  return '';
}

function renderRows(targets) {
  body.innerHTML = targets
    .map(
      (t) => `<tr>
        <td>${t.name || ''}</td>
        <td>${t.company || ''}</td>
        <td class="${scoreClass(t.fit_score)}">${t.fit_score ?? ''}</td>
        <td>${t.decision_driver || ''}</td>
        <td>${t.intelligence_hook || ''}</td>
        <td>${statusSelect(t)}</td>
        <td>
          <button data-action="messages" data-id="${t.id}">View Messages</button>
          <button data-action="send" data-id="${t.id}">Send</button>
          <button data-action="generate" data-id="${t.id}">Generate</button>
          <div id="messages-${t.id}" class="messages hidden"></div>
        </td>
      </tr>`
    )
    .join('');
}

async function loadDailyCount() {
  const res = await fetch('/api/daily-count');
  const data = await res.json();
  dailyCountEl.textContent = `${data.count} / ${data.limit} today`;
  dailyCountEl.classList.toggle('warning', !!data.warning);
}

async function loadTargets() {
  const res = await fetch('/api/targets');
  const data = await res.json();
  renderRows(data);
  await loadDailyCount();
}

async function showMessages(id) {
  const holder = document.getElementById(`messages-${id}`);
  holder.classList.remove('hidden');
  if (holder.dataset.loaded === '1') {
    holder.classList.toggle('hidden');
    return;
  }
  const res = await fetch(`/api/messages/${id}`);
  const data = await res.json();
  const entries = [
    ['connection', 'LinkedIn Connection Request'],
    ['followup', 'LinkedIn Follow-up'],
    ['email', 'Email Outreach'],
  ];
  holder.innerHTML = entries
    .map(([key, label]) => {
      const content = data[key] || '';
      return `<div class="message-block"><strong>${label}</strong><pre>${content}</pre><button data-copy="${encodeURIComponent(content)}">Copy</button></div>`;
    })
    .join('');
  holder.dataset.loaded = '1';
}

body.addEventListener('click', async (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  const action = btn.dataset.action;
  const id = btn.dataset.id;

  try {
    if (action === 'messages') {
      await showMessages(id);
      return;
    }
    if (action === 'generate') {
      setBusy(true);
      await fetch(`/api/generate/${id}`, { method: 'POST' });
      showToast('Profile + messages generated');
      await loadTargets();
      return;
    }
    if (action === 'send') {
      const res = await fetch(`/api/send/${id}`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        showToast(data.error || 'Send failed');
        return;
      }
      if (data.linkedin_url) {
        window.open(data.linkedin_url, '_blank');
      }
      showToast('Marked as contacted');
      await loadTargets();
    }
  } finally {
    setBusy(false);
  }
});

body.addEventListener('change', async (e) => {
  const sel = e.target.closest('select[data-action="status"]');
  if (!sel) return;
  const id = sel.dataset.id;
  await fetch(`/api/update-status/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: sel.value }),
  });
  showToast('Status updated');
  await loadDailyCount();
});

body.addEventListener('click', async (e) => {
  const copyBtn = e.target.closest('button[data-copy]');
  if (!copyBtn) return;
  const text = decodeURIComponent(copyBtn.dataset.copy || '');
  await navigator.clipboard.writeText(text);
  showToast('Copied');
});

document.getElementById('runDiscoveryBtn').addEventListener('click', async () => {
  setBusy(true);
  await fetch('/api/run-discovery', { method: 'POST' });
  showToast('Discovery started in background');
  setTimeout(loadTargets, 1500);
  setBusy(false);
});

document.getElementById('addTargetForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  setBusy(true);
  const payload = Object.fromEntries(new FormData(e.target).entries());
  const res = await fetch('/api/add-target', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || 'Add failed');
  } else {
    showToast('Target added');
    e.target.reset();
    await loadTargets();
  }
  setBusy(false);
});

document.getElementById('csvForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  setBusy(true);
  const formData = new FormData(e.target);
  const res = await fetch('/api/upload-csv', { method: 'POST', body: formData });
  const data = await res.json();
  if (!res.ok) {
    showToast(data.error || 'Upload failed');
  } else {
    showToast(`Uploaded ${data.inserted} targets`);
    e.target.reset();
    await loadTargets();
  }
  setBusy(false);
});

document.getElementById('exportBtn').addEventListener('click', () => {
  window.location.href = '/api/export';
});

loadTargets();
