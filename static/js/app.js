// ===== GLOBAL STATE =====
let currentView = 'dashboard';
let currentDetailLink = null;
let isEditMode = false;
let editingLinkData = null;

// ===== NAVIGATION =====
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initMobileMenu();
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

      // Close mobile menu
      closeMobileMenu();
    });
  });
}

function initMobileMenu() {
  const menuBtn = document.getElementById('mobileMenuBtn');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('mobileOverlay');

  if (!menuBtn) return;

  // Toggle menu
  menuBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
  });

  // Close menu when clicking overlay
  overlay.addEventListener('click', () => {
    closeMobileMenu();
  });
}

function closeMobileMenu() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('mobileOverlay');
  if (sidebar) {
    sidebar.classList.remove('open');
  }
  if (overlay) {
    overlay.classList.remove('active');
  }
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
  const addQueryBtn = document.getElementById('addQueryBtn');
  const addAcqBtn = document.getElementById('addAcqBtn');
  const copyBtn = document.getElementById('copyBtn');

  addQueryBtn.addEventListener('click', addQueryRow);
  addAcqBtn.addEventListener('click', addAcqRow);

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await createLink();
  });

  copyBtn.addEventListener('click', () => {
    const url = document.getElementById('resultUrl').textContent;
    copyToClipboard(url);
  });
}

function addQueryRow() {
  const wrapper = document.querySelector('.query-input-wrapper');
  const newRow = document.createElement('div');
  newRow.className = 'single-input-row';
  newRow.innerHTML = `
    <input type="text" class="query-input" placeholder="예: 청소기 추천" required>
    <button type="button" class="btn-remove-single" onclick="removeQueryRow(this)">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
    </button>
  `;
  wrapper.appendChild(newRow);
}

function addAcqRow() {
  const wrapper = document.querySelector('.acq-input-wrapper');
  const newRow = document.createElement('div');
  newRow.className = 'single-input-row';
  newRow.innerHTML = `
    <input type="text" class="acq-input" placeholder="예: 청소기 인기" required>
    <button type="button" class="btn-remove-single" onclick="removeAcqRow(this)">
      <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
    </button>
  `;
  wrapper.appendChild(newRow);
}

function removeQueryRow(button) {
  const rows = document.querySelectorAll('.query-input-wrapper .single-input-row');
  if (rows.length > 1) {
    button.closest('.single-input-row').remove();
  } else {
    showToast('최소 1개의 Query가 필요합니다', 'error');
  }
}

function removeAcqRow(button) {
  const rows = document.querySelectorAll('.acq-input-wrapper .single-input-row');
  if (rows.length > 1) {
    button.closest('.single-input-row').remove();
  } else {
    showToast('최소 1개의 Acq가 필요합니다', 'error');
  }
}

async function createLink() {
  const productName = document.getElementById('productName').value.trim();

  // Collect all queries
  const queryInputs = document.querySelectorAll('.query-input-wrapper .query-input');
  const queries = [];
  queryInputs.forEach(input => {
    const value = input.value.trim();
    if (value) {
      queries.push(value);
    }
  });

  // Collect all acqs
  const acqInputs = document.querySelectorAll('.acq-input-wrapper .acq-input');
  const acqs = [];
  acqInputs.forEach(input => {
    const value = input.value.trim();
    if (value) {
      acqs.push(value);
    }
  });

  if (queries.length === 0 || acqs.length === 0) {
    showToast('Query와 Acq를 각각 최소 1개씩 입력해주세요', 'error');
    return;
  }

  showLoading(true);

  try {
    const response = await fetch('/api/links', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ productName, queries, acqs })
    });

    const data = await response.json();

    if (response.ok) {
      showCreateResult(data);
      showToast('링크가 생성되었습니다!', 'success');

      // Reset form
      document.getElementById('createForm').reset();
      document.querySelectorAll('.query-input-wrapper .single-input-row').forEach((row, index) => {
        if (index > 0) row.remove();
      });
      document.querySelectorAll('.acq-input-wrapper .single-input-row').forEach((row, index) => {
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

  let html = '<div style="margin-bottom:12px;"><strong>Query 목록:</strong></div>';
  html += data.queries.map((q, i) => `<div>${i + 1}. ${q}</div>`).join('');
  html += '<div style="margin-top:16px;margin-bottom:12px;"><strong>Acq 목록:</strong></div>';
  html += data.acqs.map((a, i) => `<div>${i + 1}. ${a}</div>`).join('');
  html += '<div style="margin-top:16px;color:#666;font-size:13px;">💡 각 클릭마다 Query와 Acq가 랜덤 조합됩니다!</div>';

  keywordList.innerHTML = html;

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

  editingLinkData = link;
  isEditMode = false;

  document.getElementById('detailLinkCode').textContent = `링크: ${link.code}`;
  document.getElementById('detailFullUrl').textContent = fullUrl;
  document.getElementById('detailClicks').textContent = link.clicks;
  document.getElementById('detailCreated').textContent = formatDate(link.createdAt);

  // Support both old format (keywords) and new format (queries/acqs)
  const queries = link.queries || [];
  const acqs = link.acqs || [];
  const keywordCount = queries.length + acqs.length;

  document.getElementById('detailKeywordCount').textContent = keywordCount;

  renderKeywordList(link);

  // Setup buttons
  document.getElementById('detailCopyBtn').onclick = () => copyToClipboard(fullUrl);
  document.getElementById('detailEditBtn').onclick = () => toggleEditMode();
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

function renderKeywordList(link) {
  const tbody = document.querySelector('#detailKeywordsTable tbody');
  const queries = link.queries || [];
  const acqs = link.acqs || [];

  if (queries.length > 0 && acqs.length > 0) {
    // New format - show queries and acqs separately
    let html = '<tr><td colspan="4" style="background:#f0f9ff;font-weight:600;color:#1e40af;">Query 목록</td></tr>';

    queries.forEach((q, i) => {
      if (isEditMode) {
        html += `
          <tr>
            <td>${i + 1}</td>
            <td colspan="2">
              <input type="text" class="edit-input" id="query-${i}" value="${q}" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;">
            </td>
            <td style="text-align:center;">
              <button class="btn-edit-action" onclick="updateQuery(${i})" title="저장">
                <svg viewBox="0 0 24 24" fill="currentColor" style="width:16px;height:16px;"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              </button>
              <button class="btn-edit-action delete" onclick="deleteQueryItem(${i})" title="삭제">
                <svg viewBox="0 0 24 24" fill="currentColor" style="width:16px;height:16px;"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
              </button>
            </td>
          </tr>
        `;
      } else {
        html += `
          <tr>
            <td>${i + 1}</td>
            <td colspan="3">${q}</td>
          </tr>
        `;
      }
    });

    if (isEditMode) {
      html += `
        <tr>
          <td></td>
          <td colspan="3">
            <button class="btn btn-secondary btn-sm" onclick="showAddQueryInput()" style="width:100%;">+ Query 추가</button>
          </td>
        </tr>
      `;
    }

    html += '<tr><td colspan="4" style="background:#f0f9ff;font-weight:600;color:#1e40af;">Acq 목록</td></tr>';

    acqs.forEach((a, i) => {
      if (isEditMode) {
        html += `
          <tr>
            <td>${i + 1}</td>
            <td colspan="2">
              <input type="text" class="edit-input" id="acq-${i}" value="${a}" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;">
            </td>
            <td style="text-align:center;">
              <button class="btn-edit-action" onclick="updateAcq(${i})" title="저장">
                <svg viewBox="0 0 24 24" fill="currentColor" style="width:16px;height:16px;"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              </button>
              <button class="btn-edit-action delete" onclick="deleteAcqItem(${i})" title="삭제">
                <svg viewBox="0 0 24 24" fill="currentColor" style="width:16px;height:16px;"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
              </button>
            </td>
          </tr>
        `;
      } else {
        html += `
          <tr>
            <td>${i + 1}</td>
            <td colspan="3">${a}</td>
          </tr>
        `;
      }
    });

    if (isEditMode) {
      html += `
        <tr>
          <td></td>
          <td colspan="3">
            <button class="btn btn-secondary btn-sm" onclick="showAddAcqInput()" style="width:100%;">+ Acq 추가</button>
          </td>
        </tr>
      `;
    }

    html += '<tr><td colspan="4" style="color:#666;font-size:12px;text-align:center;">💡 각 클릭마다 Query와 Acq가 랜덤 조합됩니다</td></tr>';
    tbody.innerHTML = html;
  } else if (link.keywords && link.keywords.length > 0) {
    // Old format - show keyword pairs
    tbody.innerHTML = link.keywords.map((k, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${k.query}</td>
        <td>${k.acq}</td>
        <td><a href="#" class="preview-btn" onclick="previewUrl('${k.query}', '${k.acq}'); return false;">미리보기</a></td>
      </tr>
    `).join('');
  } else {
    tbody.innerHTML = '<tr><td colspan="4" class="no-data">키워드가 없습니다</td></tr>';
  }
}

function toggleEditMode() {
  isEditMode = !isEditMode;
  const editBtn = document.getElementById('detailEditBtn');
  editBtn.textContent = isEditMode ? '편집 완료' : '편집';
  editBtn.className = isEditMode ? 'btn btn-primary' : 'btn btn-secondary';
  renderKeywordList(editingLinkData);
}

async function updateQuery(index) {
  const input = document.getElementById(`query-${index}`);
  const newValue = input.value.trim();

  if (!newValue) {
    showToast('Query를 입력해주세요', 'error');
    return;
  }

  showLoading(true);

  try {
    const response = await fetch(`/api/links/${currentDetailLink}/queries/${index}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: newValue })
    });

    const data = await response.json();

    if (response.ok) {
      showToast('Query가 수정되었습니다', 'success');
      editingLinkData.queries = data.queries;
      renderKeywordList(editingLinkData);
    } else {
      showToast(data.error || '수정 실패', 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('오류가 발생했습니다', 'error');
  } finally {
    showLoading(false);
  }
}

async function deleteQueryItem(index) {
  if (!confirm('이 Query를 삭제하시겠습니까?')) {
    return;
  }

  showLoading(true);

  try {
    const response = await fetch(`/api/links/${currentDetailLink}/queries/${index}`, {
      method: 'DELETE'
    });

    const data = await response.json();

    if (response.ok) {
      showToast('Query가 삭제되었습니다', 'success');
      editingLinkData.queries = data.queries;
      renderKeywordList(editingLinkData);
    } else {
      showToast(data.error || '삭제 실패', 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('오류가 발생했습니다', 'error');
  } finally {
    showLoading(false);
  }
}

async function showAddQueryInput() {
  const query = prompt('새 Query를 입력하세요:');
  if (!query || !query.trim()) {
    return;
  }

  showLoading(true);

  try {
    const response = await fetch(`/api/links/${currentDetailLink}/queries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query.trim() })
    });

    const data = await response.json();

    if (response.ok) {
      showToast('Query가 추가되었습니다', 'success');
      editingLinkData.queries = data.queries;
      renderKeywordList(editingLinkData);
    } else {
      showToast(data.error || '추가 실패', 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('오류가 발생했습니다', 'error');
  } finally {
    showLoading(false);
  }
}

async function updateAcq(index) {
  const input = document.getElementById(`acq-${index}`);
  const newValue = input.value.trim();

  if (!newValue) {
    showToast('Acq를 입력해주세요', 'error');
    return;
  }

  showLoading(true);

  try {
    const response = await fetch(`/api/links/${currentDetailLink}/acqs/${index}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acq: newValue })
    });

    const data = await response.json();

    if (response.ok) {
      showToast('Acq가 수정되었습니다', 'success');
      editingLinkData.acqs = data.acqs;
      renderKeywordList(editingLinkData);
    } else {
      showToast(data.error || '수정 실패', 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('오류가 발생했습니다', 'error');
  } finally {
    showLoading(false);
  }
}

async function deleteAcqItem(index) {
  if (!confirm('이 Acq를 삭제하시겠습니까?')) {
    return;
  }

  showLoading(true);

  try {
    const response = await fetch(`/api/links/${currentDetailLink}/acqs/${index}`, {
      method: 'DELETE'
    });

    const data = await response.json();

    if (response.ok) {
      showToast('Acq가 삭제되었습니다', 'success');
      editingLinkData.acqs = data.acqs;
      renderKeywordList(editingLinkData);
    } else {
      showToast(data.error || '삭제 실패', 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('오류가 발생했습니다', 'error');
  } finally {
    showLoading(false);
  }
}

async function showAddAcqInput() {
  const acq = prompt('새 Acq를 입력하세요:');
  if (!acq || !acq.trim()) {
    return;
  }

  showLoading(true);

  try {
    const response = await fetch(`/api/links/${currentDetailLink}/acqs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ acq: acq.trim() })
    });

    const data = await response.json();

    if (response.ok) {
      showToast('Acq가 추가되었습니다', 'success');
      editingLinkData.acqs = data.acqs;
      renderKeywordList(editingLinkData);
    } else {
      showToast(data.error || '추가 실패', 'error');
    }
  } catch (error) {
    console.error('Error:', error);
    showToast('오류가 발생했습니다', 'error');
  } finally {
    showLoading(false);
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
