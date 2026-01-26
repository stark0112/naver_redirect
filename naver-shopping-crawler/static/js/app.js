// State
let currentKeywordId = null;

// DOM Elements
const loadingOverlay = document.getElementById('loadingOverlay');

// Initialize
document.addEventListener('DOMContentLoaded', init);

function init() {
  setupNavigation();
  setupSearchForm();
  setupRankingForm();
  loadDashboard();
}

// ===== Navigation =====
function setupNavigation() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      const view = item.dataset.view;
      switchView(view);
    });
  });
}

function switchView(view) {
  // Update nav
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === view);
  });

  // Update views
  document.querySelectorAll('.view').forEach(v => {
    v.classList.remove('active');
  });
  document.getElementById(view + 'View').classList.add('active');

  // Load data
  switch (view) {
    case 'dashboard':
      loadDashboard();
      break;
    case 'keywords':
      loadKeywords();
      break;
    case 'ranking':
      loadKeywordsForRanking();
      break;
  }
}

// ===== Dashboard =====
async function loadDashboard() {
  try {
    const response = await fetch('/api/stats');
    const data = await response.json();

    document.getElementById('totalKeywords').textContent = data.total_keywords;
    document.getElementById('totalProducts').textContent = data.total_products;
    document.getElementById('phoneSuccess').textContent = data.phone_success;
    document.getElementById('phoneFailed').textContent = data.phone_failed;
    document.getElementById('todayCrawled').textContent = data.today_crawled;
  } catch (error) {
    console.error('Dashboard load error:', error);
  }
}

// ===== Search =====
function setupSearchForm() {
  const form = document.getElementById('searchForm');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await performSearch();
  });

  document.getElementById('exportBtn').addEventListener('click', () => {
    if (currentKeywordId) {
      window.location.href = `/api/keywords/${currentKeywordId}/export`;
    }
  });
}

async function performSearch() {
  const keyword = document.getElementById('keyword').value.trim();
  const startPage = parseInt(document.getElementById('startPage').value);
  const endPage = parseInt(document.getElementById('endPage').value);
  const crawlPhone = document.getElementById('crawlPhone').checked;

  if (!keyword) {
    alert('검색어를 입력하세요');
    return;
  }

  showLoading();

  try {
    const response = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        keyword,
        start_page: startPage,
        end_page: endPage,
        crawl_phone: crawlPhone
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || '검색 실패');
    }

    const data = await response.json();
    currentKeywordId = data.keyword_id;

    // 결과 표시
    displaySearchResults(data.products);
    document.getElementById('resultCount').textContent = data.total_products;
    document.getElementById('searchResult').style.display = 'block';

    if (crawlPhone) {
      alert('전화번호 크롤링이 백그라운드에서 진행됩니다.\n잠시 후 새로고침하면 결과를 확인할 수 있습니다.');
    }
  } catch (error) {
    alert('오류: ' + error.message);
  } finally {
    hideLoading();
  }
}

function displaySearchResults(products) {
  const tbody = document.querySelector('#resultTable tbody');
  tbody.innerHTML = '';

  products.forEach(product => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${product.current_rank || '-'}</td>
      <td><a href="${product.product_url}" target="_blank">${truncate(product.product_name, 40)}</a></td>
      <td>${product.store_name || '-'}</td>
      <td class="${getPhoneClass(product)}">${product.phone_number || getPhoneStatus(product)}</td>
      <td>${formatPrice(product.price)}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ===== Keywords =====
async function loadKeywords() {
  try {
    const response = await fetch('/api/keywords');
    const keywords = await response.json();

    const tbody = document.querySelector('#keywordsTable tbody');
    tbody.innerHTML = '';

    keywords.forEach(kw => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><a href="#" class="keyword-link" data-id="${kw.id}">${kw.keyword}</a></td>
        <td>${kw.product_count}건</td>
        <td>${formatDate(kw.created_at)}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="exportKeyword(${kw.id})">엑셀</button>
          <button class="btn btn-danger btn-sm" onclick="deleteKeyword(${kw.id})">삭제</button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // 키워드 클릭 이벤트
    document.querySelectorAll('.keyword-link').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        loadKeywordProducts(parseInt(link.dataset.id), link.textContent);
      });
    });
  } catch (error) {
    console.error('Keywords load error:', error);
  }
}

async function loadKeywordProducts(keywordId, keyword) {
  currentKeywordId = keywordId;
  document.getElementById('detailKeyword').textContent = keyword;

  try {
    const response = await fetch(`/api/keywords/${keywordId}/products`);
    const products = await response.json();

    const tbody = document.querySelector('#detailTable tbody');
    tbody.innerHTML = '';

    products.forEach(product => {
      const tr = document.createElement('tr');
      const rankChange = formatRankChange(product.rank_change);

      tr.innerHTML = `
        <td>${product.current_rank || '-'}</td>
        <td class="${rankChange.class}">${rankChange.text}</td>
        <td><a href="${product.product_url}" target="_blank">${truncate(product.product_name, 35)}</a></td>
        <td>${product.store_name || '-'}</td>
        <td class="${getPhoneClass(product)}">${product.phone_number || getPhoneStatus(product)}</td>
        <td>${formatPrice(product.price)}</td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById('keywordDetail').style.display = 'block';

    // 엑셀 다운로드 버튼
    document.getElementById('detailExportBtn').onclick = () => {
      exportKeyword(keywordId);
    };
  } catch (error) {
    console.error('Products load error:', error);
  }
}

function exportKeyword(keywordId) {
  window.location.href = `/api/keywords/${keywordId}/export`;
}

async function deleteKeyword(keywordId) {
  if (!confirm('정말 삭제하시겠습니까?')) return;

  try {
    await fetch(`/api/keywords/${keywordId}`, { method: 'DELETE' });
    loadKeywords();
    document.getElementById('keywordDetail').style.display = 'none';
  } catch (error) {
    alert('삭제 실패');
  }
}

// ===== Ranking =====
async function loadKeywordsForRanking() {
  try {
    const response = await fetch('/api/keywords');
    const keywords = await response.json();

    const select = document.getElementById('rankingKeyword');
    select.innerHTML = '<option value="">선택하세요</option>';

    keywords.forEach(kw => {
      const option = document.createElement('option');
      option.value = kw.id;
      option.textContent = kw.keyword;
      select.appendChild(option);
    });
  } catch (error) {
    console.error('Keywords load error:', error);
  }
}

function setupRankingForm() {
  document.getElementById('findDropsBtn').addEventListener('click', findRankingDrops);
}

async function findRankingDrops() {
  const keywordId = document.getElementById('rankingKeyword').value;
  const minDrop = parseInt(document.getElementById('minDrop').value);

  if (!keywordId) {
    alert('키워드를 선택하세요');
    return;
  }

  showLoading();

  try {
    const response = await fetch(`/api/ranking/drops?keyword_id=${keywordId}&min_drop=${minDrop}`);
    const drops = await response.json();

    const tbody = document.querySelector('#dropsTable tbody');
    tbody.innerHTML = '';

    // 첫 번째 항목의 시간으로 헤더 업데이트
    if (drops.length > 0) {
      const first = drops[0];
      document.getElementById('timeHeader1').textContent = first.time_1 || '-';
      document.getElementById('timeHeader2').textContent = first.time_2;
      document.getElementById('timeHeader3').textContent = first.time_3;
    }

    drops.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${truncate(item.product_name, 30)}</td>
        <td>${item.store_name || '-'}</td>
        <td>${item.phone_number || '-'}</td>
        <td>${item.rank_1 ? `<strong>${item.rank_1}위</strong>` : '-'}</td>
        <td><strong>${item.rank_2}위</strong></td>
        <td><strong>${item.rank_3}위</strong></td>
        <td class="rank-down">▼${item.drop}</td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById('dropsCount').textContent = drops.length;
    document.getElementById('dropsResult').style.display = 'block';
  } catch (error) {
    alert('조회 실패');
  } finally {
    hideLoading();
  }
}

// ===== Utilities =====
function showLoading() {
  loadingOverlay.style.display = 'flex';
}

function hideLoading() {
  loadingOverlay.style.display = 'none';
}

function truncate(str, len) {
  if (!str) return '-';
  return str.length > len ? str.substring(0, len) + '...' : str;
}

function formatPrice(price) {
  if (!price) return '-';
  return price.toLocaleString() + '원';
}

function formatDate(dateStr) {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function formatRankChange(change) {
  if (change === null || change === undefined) {
    return { text: '-', class: '' };
  }
  if (change > 0) {
    return { text: `▲${change}`, class: 'rank-up' };
  }
  if (change < 0) {
    return { text: `▼${Math.abs(change)}`, class: 'rank-down' };
  }
  return { text: '-', class: '' };
}

function getPhoneClass(product) {
  if (product.phone_number) return 'phone-success';
  if (product.phone_crawled === 0) return 'phone-pending';
  return 'phone-failed';
}

function getPhoneStatus(product) {
  if (product.phone_crawled === 0) return '크롤링 중...';
  if (product.phone_crawled === -1) return '없음';
  return '-';
}
