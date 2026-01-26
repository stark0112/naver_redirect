// ===== GLOBAL STATE =====
let currentView = 'dashboard';
let currentDetailLink = null;

// ===== NAVIGATION =====
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initCreateForm();
  loadDashboard();
});

function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const view = item.getAttribute('data-view');
      switchView(view);

      // Update active state
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');
    });
  });
}

function switchView(view) {
  currentView = view;

  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

  // Show selected view
  const viewElement = document.getElementById(view + 'View');
  if (viewElement) {
    viewElement.classList.add('active');
  }

  // Load data for view
  if (view === 'dashboard') {
    loadDashboard();
  } else if (view === 'links') {
    loadLinks();
  }
}

// ===== CREATE FORM =====
function initCreateForm() {
  const form = document.getElementById('createForm');
  const addKeywordBtn = document.getElementById('addKeywordBtn');
  const copyBtn = document.getElementById('copyBtn');

  addKeywordBtn.addEventListener('click', addKeywordRow);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await createLink();
  });

  copyBtn.addEventListener('click', () => {
    const url = document.getElementById('resultUrl').textContent;
    copyToClipboard(url);
  });
}

function addKeywordRow() {
  const wrapper = document.querySelector('.keyword-input-wrapper');
  const newRow = document.createElement('div');
  newRow.className = 'keyword-row';
  newRow.innerHTML = `
    <input type="text" class="query-input" placeholder="Query (검색어)" required>
    <input type="text" class="acq-input" placeholder="Acq (자동완성 검색어)" required>
    <button type="button" class="btn-remove" onclick="removeKeywordRow(this)">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
    </button>
  `;
  wrapper.appendChild(newRow);
}

function removeKeywordRow(button) {
  const rows = document.querySelectorAll('.keyword-row');
  if (rows.length > 1) {
    button.closest('.keyword-row').remove();
  } else {
    showToast('최소 1개의 키워드가 필요합니다', 'error');
  }
}

async function createLink() {
  const productName = document.getElementById('productName').value.trim();
  const keywordRows = document.querySelectorAll('.keyword-row');

  const keywords = [];
  keywordRows.forEach(row => {
    const query = row.querySelector('.query-input').value.trim();
    const acq = row.querySelector('.acq-input').value.trim();
    if (query && acq) {
      keywords.push({ query, acq });
    }
  });

  if (keywords.length === 0) {
    showToast('최소 1개의 키워드를 입력해주세요', 'error');
    return;
  }

  showLoading(true);

  try {
    const response = await fetch('/api/links', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ productName, keywords })
    });

    const data = await response.json();

    if (response.ok) {
      showCreateResult(data);
      showToast('링크가 생성되었습니다!', 'success');

      // Reset form
      document.getElementById('createForm').reset();
      document.querySelectorAll('.keyword-row').forEach((row, index) => {
        if (index > 0) row.remove();
      });
    } else {
      showToast(data.error || '링크 생성 실패', 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('서버 오류가 발생했습니다', 'error');
  } finally {
    showLoading(false);
  }
}

function showCreateResult(data) {
  const resultSection = document.getElementById('createResult');
  const resultUrl = document.getElementById('resultUrl');
  const keywordList = document.getElementById('keywordList');

  const fullUrl = `${window.location.origin}/r/${data.code}`;
  resultUrl.textContent = fullUrl;

  keywordList.innerHTML = data.keywords.map((k, i) =>
    `<div><strong>${i + 1}.</strong> Query: "${k.query}" / Acq: "${k.acq}"</div>`
  ).join('');

  resultSection.style.display = 'block';
  resultSection.scrollIntoView({ behavior: 'smooth' });
}

// ===== DASHBOARD =====
async function loadDashboard() {
  try {
    const response = await fetch('/api/stats');
    const data = await response.json();

    document.getElementById('totalLinks').textContent = data.totalLinks || 0;
    document.getElementById('totalKeywords').textContent = data.totalKeywords || 0;
    document.getElementById('totalClicks').textContent = data.totalClicks || 0;
    document.getElementById('todayClicks').textContent = data.todayClicks || 0;

    // Load recent links
    loadRecentLinks(data.recentLinks || []);
  } catch (error) {
    console.error('Error loading dashboard:', error);
  }
}

function loadRecentLinks(links) {
  const tbody = document.querySelector('#recentLinksTable tbody');

  if (links.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="no-data">생성된 링크가 없습니다</td></tr>';
    return;
  }

  tbody.innerHTML = links.map(link => `
    <tr onclick="viewLinkDetail('${link.code}')">
      <td><span class="link-code">${link.code}</span></td>
      <td>${link.keywordCount}개</td>
      <td>${link.clicks}회</td>
      <td>${formatDate(link.createdAt)}</td>
    </tr>
  `).join('');
}

// ===== LINKS MANAGEMENT =====
async function loadLinks() {
  try {
    const response = await fetch('/api/links');
    const data = await response.json();

    const tbody = document.querySelector('#linksTable tbody');

    if (data.links.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="no-data">생성된 링크가 없습니다</td></tr>';
      return;
    }

    tbody.innerHTML = data.links.map(link => `
      <tr>
        <td><span class="link-code">${link.code}</span></td>
        <td>${link.productName || '-'}</td>
        <td>${link.keywordCount}개</td>
        <td>${link.clicks}회</td>
        <td>${formatDate(link.createdAt)}</td>
        <td>
          <button class="btn btn-sm btn-secondary" onclick="viewLinkDetail('${link.code}')">상세</button>
          <button class="btn btn-sm btn-danger" onclick="deleteLink('${link.code}')">삭제</button>
        </td>
      </tr>
    `).join('');
  } catch (error) {
    console.error('Error loading links:', error);
  }
}

async function viewLinkDetail(code) {
  currentDetailLink = code;

  try {
    const response = await fetch(`/api/links/${code}`);
    const data = await response.json();

    if (response.ok) {
      showLinkDetail(data);
    } else {
      showToast('링크를 찾을 수 없습니다', 'error');
    }
  } catch (error) {
    console.error('Error loading link detail:', error);
    showToast('오류가 발생했습니다', 'error');
  }
}

function showLinkDetail(link) {
  const detailSection = document.getElementById('linkDetail');
  const fullUrl = `${window.location.origin}/r/${link.code}`;

  document.getElementById('detailLinkCode').textContent = `링크: ${link.code}`;
  document.getElementById('detailFullUrl').textContent = fullUrl;
  document.getElementById('detailClicks').textContent = link.clicks;
  document.getElementById('detailCreated').textContent = formatDate(link.createdAt);
  document.getElementById('detailKeywordCount').textContent = link.keywords.length;

  const tbody = document.querySelector('#detailKeywordsTable tbody');
  tbody.innerHTML = link.keywords.map((k, i) => `
    <tr>
      <td>${i + 1}</td>
      <td>${k.query}</td>
      <td>${k.acq}</td>
      <td><a href="#" class="preview-btn" onclick="previewUrl('${k.query}', '${k.acq}'); return false;">미리보기</a></td>
    </tr>
  `).join('');

  // Setup buttons
  document.getElementById('detailCopyBtn').onclick = () => copyToClipboard(fullUrl);
  document.getElementById('detailDeleteBtn').onclick = () => deleteLink(link.code);

  detailSection.style.display = 'block';
  detailSection.scrollIntoView({ behavior: 'smooth' });

  // Switch to links view if not already there
  if (currentView !== 'links') {
    switchView('links');
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelector('[data-view="links"]').classList.add('active');
  }
}

async function deleteLink(code) {
  if (!confirm('정말 이 링크를 삭제하시겠습니까?')) {
    return;
  }

  showLoading(true);

  try {
    const response = await fetch(`/api/links/${code}`, {
      method: 'DELETE'
    });

    if (response.ok) {
      showToast('링크가 삭제되었습니다', 'success');
      document.getElementById('linkDetail').style.display = 'none';
      loadLinks();
      loadDashboard();
    } else {
      showToast('삭제 실패', 'error');
    }
  } catch (error) {
    console.error('Error deleting link:', error);
    showToast('오류가 발생했습니다', 'error');
  } finally {
    showLoading(false);
  }
}

function previewUrl(query, acq) {
  const ackey = generateAckey();
  const acr = Math.floor(Math.random() * 11);
  const url = `https://m.search.naver.com/search.naver?sm=mtp_sug.top&where=m&query=${encodeURIComponent(query)}&ackey=${ackey}&acq=${encodeURIComponent(acq)}&acr=${acr}&qdt=0`;
  window.open(url, '_blank');
}

// ===== UTILITIES =====
function generateAckey() {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < 8; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

function formatDate(dateString) {
  const date = new Date(dateString);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('클립보드에 복사되었습니다!', 'success');
  }).catch(() => {
    showToast('복사 실패', 'error');
  });
}

function showLoading(show) {
  const overlay = document.getElementById('loadingOverlay');
  overlay.style.display = show ? 'flex' : 'none';
}

function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast ${type} show`;

  setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}
