const API_BASE = '';
const PLACEHOLDER_IMAGE = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80';

function saveAuth(data) {
  localStorage.setItem('auth', JSON.stringify(data));
}

function getAuth() {
  const raw = localStorage.getItem('auth');
  return raw ? JSON.parse(raw) : null;
}

function clearAuth() {
  localStorage.removeItem('auth');
}

function getToken() {
  const auth = getAuth();
  return auth ? auth.token : null;
}

function toggleHeaderMenus(auth) {
  document.querySelectorAll('[data-guest-only]').forEach(function (el) {
    el.style.display = auth ? 'none' : '';
  });

  document.querySelectorAll('[data-auth-only]').forEach(function (el) {
    el.style.display = auth ? '' : 'none';
  });
}

function renderHeader() {
  const auth = getAuth();
  const userBox = document.getElementById('userBox');

  toggleHeaderMenus(auth);

  if (!userBox) {
    return;
  }

  if (auth) {
    userBox.innerHTML = `
      <div class="user-chip">
        <span class="user-chip-label">${auth.nickname || auth.name || auth.loginId || auth.email}님</span>
        <button class="btn btn-dark" id="logoutBtn" type="button">로그아웃</button>
      </div>
    `;
    const logoutBtn = document.getElementById('logoutBtn');
    logoutBtn.addEventListener('click', function () {
      clearAuth();
      window.location.href = '/';
    });
  } else {
    userBox.innerHTML = '';
  }
}

function showMessage(targetId, message, type) {
  const target = document.getElementById(targetId);
  if (!target) {
    return;
  }
  target.className = `message ${type}`;
  target.textContent = message;
  target.style.display = 'block';
}

async function apiRequest(url, options = {}) {
  const headers = options.headers || {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (!headers['Content-Type'] && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || '요청 처리 중 오류가 발생했습니다.');
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

function getImageUrl(url) {
  return url || PLACEHOLDER_IMAGE;
}

function formatPrice(value) {
  return `${Number(value || 0).toLocaleString()}원`;
}

function getProductDetailUrl(productId) {
  return `/product-detail.html?id=${productId}`;
}

function goToProductDetail(productId) {
  window.location.href = getProductDetailUrl(productId);
}

window.goToProductDetail = goToProductDetail;

function getQueryParam(name) {
  const params = new URLSearchParams(window.location.search);
  return params.get(name);
}

function buildStockBadge(stockQuantity) {
  if (stockQuantity < 1) {
    return '<span class="stock-badge soldout">품절</span>';
  }
  if (stockQuantity < 6) {
    return '<span class="stock-badge limited">수량한정</span>';
  }
  return '<span class="stock-badge normal">판매중</span>';
}

async function loadProducts() {
  const productList = document.getElementById('productList');
  if (!productList) {
    return;
  }

  try {
    const products = await apiRequest('/product-service/product/list', { method: 'GET', headers: {} });
    const countEl = document.getElementById('productCount');
    if (countEl) {
      countEl.textContent = `총 ${products.length}개의 상품`;
    }

    if (!products.length) {
      productList.innerHTML = '<div class="empty">등록된 상품이 없습니다. 첫 상품을 등록해보세요.</div>';
      return;
    }

    productList.innerHTML = products.map(function (product) {
      return `
        <article class="card card-link" onclick="goToProductDetail(${product.id})" role="button" tabindex="0">
          <div class="card-image-wrap">
            <img src="${getImageUrl(product.imageUrl)}" alt="${product.name}">
            ${buildStockBadge(product.stockQuantity)}
          </div>
          <div class="card-body">
            <div class="card-meta-row">
              <span class="card-meta">${product.category || '전체 카테고리'}</span>
            </div>
            <div class="card-title">${product.name}</div>
            <div class="card-price">${formatPrice(product.price)}</div>
            <div class="card-sub">재고 ${product.stockQuantity}개</div>
            <div class="card-description">${product.description || '등록된 상품 설명이 없습니다.'}</div>
          </div>
        </article>
      `;
    }).join('');
  } catch (error) {
    productList.innerHTML = '<div class="empty">상품 목록을 불러오지 못했습니다.</div>';
  }
}

function guardLogin(redirectPath) {
  if (!getToken()) {
    alert('로그인 후 이용해주세요.');
    window.location.href = redirectPath || '/login.html';
    return false;
  }
  return true;
}

async function loadProductDetail() {
  const target = document.getElementById('productDetail');
  if (!target) {
    return;
  }

  const productId = getQueryParam('id');
  if (!productId) {
    target.innerHTML = '<div class="empty">상품 정보가 없습니다.</div>';
    return;
  }

  try {
    const product = await apiRequest(`/product-service/product/${productId}`, { method: 'GET', headers: {} });
    target.innerHTML = `
      <section class="detail-card">
        <div class="detail-image-wrap">
          <img class="detail-image" src="${getImageUrl(product.imageUrl)}" alt="${product.name}">
        </div>
        <div class="detail-content">
          <div class="detail-category">${product.category || '전체 카테고리'}</div>
          <h1 class="detail-title">${product.name}</h1>
          <div class="detail-price">${formatPrice(product.price)}</div>
          <div class="detail-stock" id="detailStock">재고: ${product.stockQuantity}개</div>
          <p class="detail-description">${product.description || '상품 설명이 없습니다.'}</p>
          <div class="detail-actions">
            <button class="btn btn-primary btn-large" id="purchaseBtn" type="button" ${product.stockQuantity < 1 ? 'disabled' : ''}>구매하기</button>
            <a class="btn btn-light btn-large" href="/">메인으로</a>
          </div>
          <div id="purchaseMessage" style="display:none;"></div>
        </div>
      </section>
    `;

    const purchaseBtn = document.getElementById('purchaseBtn');
    if (purchaseBtn) {
      purchaseBtn.addEventListener('click', async function () {
        if (!guardLogin('/login.html')) {
          return;
        }

        if (product.stockQuantity < 1) {
          showMessage('purchaseMessage', '재고가 부족합니다.', 'error');
          return;
        }

        purchaseBtn.disabled = true;
        try {
          await apiRequest('/ordering-service/ordering/create', {
            method: 'POST',
            body: JSON.stringify({
              productId: product.id,
              productCount: 1
            })
          });
          alert('주문이 완료되었습니다.');
          window.location.href = '/';
        } catch (error) {
          purchaseBtn.disabled = false;
          showMessage('purchaseMessage', error.message || '구매에 실패했습니다.', 'error');
        }
      });
    }
  } catch (error) {
    target.innerHTML = '<div class="empty">상품 상세 정보를 불러오지 못했습니다.</div>';
  }
}
