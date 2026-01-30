/**
 * 🏪 Marketplace Page JavaScript
 *
 * Handles strategy marketplace functionality:
 * - Browse and search strategies
 * - Publish strategies
 * - Download strategies
 * - Reviews and ratings
 *
 * @version 1.0.0
 * @date 2026-01-27
 */

const API_BASE = "/api/v1";

// State
let currentPage = 1;
let totalPages = 1;
let selectedStrategyId = null;
let selectedRating = 0;
let strategies = [];

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener("DOMContentLoaded", () => {
  loadStrategies();
  loadStats();
  setupEventListeners();
});

function setupEventListeners() {
  // Search & Filters
  document
    .getElementById("searchInput")
    .addEventListener("input", debounce(loadStrategies, 300));
  document
    .getElementById("categoryFilter")
    .addEventListener("change", loadStrategies);
  document.getElementById("sortBy").addEventListener("change", loadStrategies);
  document
    .getElementById("timeframeFilter")
    .addEventListener("change", loadStrategies);
  document
    .getElementById("verifiedOnly")
    .addEventListener("change", loadStrategies);

  // View toggle
  document.querySelectorAll(".view-toggle button").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      document
        .querySelectorAll(".view-toggle button")
        .forEach((b) => b.classList.remove("active"));
      e.target.closest("button").classList.add("active");
      const view = e.target.closest("button").dataset.view;
      toggleView(view);
    });
  });

  // Rating stars
  document.querySelectorAll(".rating-star").forEach((star) => {
    star.addEventListener("click", (e) => {
      selectedRating = parseInt(e.currentTarget.dataset.value);
      updateRatingStars(selectedRating);
    });
    star.addEventListener("mouseenter", (e) => {
      const val = parseInt(e.currentTarget.dataset.value);
      highlightStars(val);
    });
  });

  document.querySelector(".rating-input").addEventListener("mouseleave", () => {
    updateRatingStars(selectedRating);
  });
}

// ============================================
// API CALLS
// ============================================

async function loadStrategies() {
  const search = document.getElementById("searchInput").value;
  const category = document.getElementById("categoryFilter").value;
  const sortBy = document.getElementById("sortBy").value;
  const timeframe = document.getElementById("timeframeFilter").value;
  const verifiedOnly = document.getElementById("verifiedOnly").checked;

  const params = new URLSearchParams({
    page: currentPage,
    limit: 12,
    ...(search && { search }),
    ...(category && { category }),
    ...(sortBy && { sort_by: sortBy }),
    ...(timeframe && { timeframe }),
    ...(verifiedOnly && { verified_only: "true" }),
  });

  showLoading();

  try {
    const response = await fetch(
      `${API_BASE}/marketplace/strategies?${params}`,
    );
    const data = await response.json();

    strategies = data.strategies || data || [];
    totalPages = data.total_pages || 1;

    renderStrategies(strategies);
    renderPagination();
    document.getElementById("resultsCount").textContent =
      data.total || strategies.length;

    // Load featured
    if (currentPage === 1 && !search && !category) {
      loadFeaturedStrategies();
    } else {
      document.getElementById("featuredSection").style.display = "none";
    }
  } catch (error) {
    console.error("Failed to load strategies:", error);
    showError("Failed to load strategies. Please try again.");
  }
}

async function loadFeaturedStrategies() {
  try {
    const response = await fetch(
      `${API_BASE}/marketplace/strategies?sort_by=rating&limit=3`,
    );
    const data = await response.json();
    const featured = data.strategies || data || [];

    if (featured.length > 0) {
      document.getElementById("featuredSection").style.display = "block";
      renderFeaturedStrategies(featured);
    } else {
      document.getElementById("featuredSection").style.display = "none";
    }
  } catch (error) {
    console.error("Failed to load featured:", error);
    document.getElementById("featuredSection").style.display = "none";
  }
}

async function loadStats() {
  try {
    const response = await fetch(`${API_BASE}/marketplace/stats`);
    const stats = await response.json();

    document.getElementById("totalStrategies").textContent =
      stats.total_strategies || 0;
    document.getElementById("totalDownloads").textContent = formatNumber(
      stats.total_downloads || 0,
    );
    document.getElementById("avgRating").textContent = (
      stats.average_rating || 0
    ).toFixed(1);
  } catch (error) {
    console.error("Failed to load stats:", error);
  }
}

async function downloadStrategy(id) {
  try {
    const response = await fetch(
      `${API_BASE}/marketplace/strategies/${id}/download`,
      {
        method: "POST",
      },
    );

    if (!response.ok) throw new Error("Download failed");

    const data = await response.json();
    showToast("Success", "Strategy downloaded successfully!", "success");

    // Refresh stats
    loadStats();

    // Ask if user wants to view the strategy
    if (
      confirm(
        "Strategy downloaded! Would you like to view it in My Strategies?",
      )
    ) {
      window.location.href = "strategies.html";
    }
  } catch (error) {
    console.error("Download failed:", error);
    showToast("Error", "Failed to download strategy", "error");
  }
}

async function toggleLike(id) {
  try {
    const response = await fetch(
      `${API_BASE}/marketplace/strategies/${id}/like`,
      {
        method: "POST",
      },
    );

    if (!response.ok) throw new Error("Like failed");

    const data = await response.json();

    // Update UI
    const btn = document.querySelector(`[data-strategy-id="${id}"] .btn-like`);
    if (btn) {
      btn.classList.toggle("liked", data.liked);
      const countSpan = btn.querySelector(".like-count");
      if (countSpan) {
        countSpan.textContent = data.total_likes || "";
      }
    }
  } catch (error) {
    console.error("Like failed:", error);
  }
}

async function publishStrategy() {
  const name = document.getElementById("pubName").value;
  const category = document.getElementById("pubCategory").value;
  const description = document.getElementById("pubDescription").value;
  const strategyType = document.getElementById("pubStrategyType").value;
  const timeframe = document.getElementById("pubTimeframe").value;
  const paramsStr = document.getElementById("pubParams").value;
  const tags = document.getElementById("pubTags").value;
  const visibility = document.getElementById("pubVisibility").value;

  // Validate
  if (!name || !category || !description || !strategyType) {
    showToast("Error", "Please fill in all required fields", "error");
    return;
  }

  // Parse params
  let params = {};
  if (paramsStr) {
    try {
      params = JSON.parse(paramsStr);
    } catch (e) {
      showToast("Error", "Invalid JSON in parameters", "error");
      return;
    }
  }

  // Build payload
  const payload = {
    name,
    category,
    description,
    strategy_type: strategyType,
    timeframe,
    parameters: params,
    tags: tags ? tags.split(",").map((t) => t.trim()) : [],
    visibility,
    performance: {
      win_rate: parseFloat(document.getElementById("pubWinRate").value) || null,
      sharpe_ratio:
        parseFloat(document.getElementById("pubSharpe").value) || null,
      max_drawdown:
        parseFloat(document.getElementById("pubDrawdown").value) || null,
      total_return:
        parseFloat(document.getElementById("pubReturn").value) || null,
    },
  };

  try {
    const response = await fetch(`${API_BASE}/marketplace/strategies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Publish failed");
    }

    const data = await response.json();

    showToast("Success", "Strategy published successfully!", "success");

    // Close modal and refresh
    bootstrap.Modal.getInstance(document.getElementById("publishModal")).hide();
    document.getElementById("publishForm").reset();
    loadStrategies();
    loadStats();
  } catch (error) {
    console.error("Publish failed:", error);
    showToast("Error", error.message || "Failed to publish strategy", "error");
  }
}

async function submitReview() {
  if (!selectedStrategyId || selectedRating === 0) {
    showToast("Error", "Please select a rating", "error");
    return;
  }

  const text = document.getElementById("reviewText").value;

  try {
    const response = await fetch(
      `${API_BASE}/marketplace/strategies/${selectedStrategyId}/review`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rating: selectedRating,
          comment: text,
        }),
      },
    );

    if (!response.ok) throw new Error("Review failed");

    showToast("Success", "Review submitted!", "success");
    bootstrap.Modal.getInstance(document.getElementById("reviewModal")).hide();

    // Reset
    selectedRating = 0;
    updateRatingStars(0);
    document.getElementById("reviewText").value = "";

    loadStrategies();
  } catch (error) {
    console.error("Review failed:", error);
    showToast("Error", "Failed to submit review", "error");
  }
}

// ============================================
// RENDERING
// ============================================

function renderStrategies(items) {
  const container = document.getElementById("strategiesGrid");

  if (!items || items.length === 0) {
    container.innerHTML = `
            <div class="col-12">
                <div class="empty-state">
                    <i class="bi bi-inbox"></i>
                    <h5>No strategies found</h5>
                    <p>Try adjusting your filters or be the first to publish a strategy!</p>
                </div>
            </div>
        `;
    return;
  }

  container.innerHTML = items
    .map((strategy) => renderStrategyCard(strategy))
    .join("");
}

function renderFeaturedStrategies(items) {
  const container = document.getElementById("featuredStrategies");
  container.innerHTML = items
    .map((strategy) => renderStrategyCard(strategy, true))
    .join("");
}

function renderStrategyCard(strategy, featured = false) {
  const badges = [];
  if (strategy.verified)
    badges.push(
      '<span class="strategy-badge badge-verified"><i class="bi bi-patch-check-fill"></i> Verified</span>',
    );
  if (featured)
    badges.push(
      '<span class="strategy-badge badge-featured"><i class="bi bi-star-fill"></i> Featured</span>',
    );
  if (isNew(strategy.created_at))
    badges.push('<span class="strategy-badge badge-new">New</span>');

  const tags = (strategy.tags || [])
    .slice(0, 3)
    .map((t) => `<span class="strategy-tag">${escapeHtml(t)}</span>`)
    .join("");

  const winRate = strategy.performance?.win_rate;
  const sharpe = strategy.performance?.sharpe_ratio;
  const drawdown = strategy.performance?.max_drawdown;

  return `
        <div class="col-md-6 col-lg-4" data-strategy-id="${strategy.id}">
            <div class="strategy-card ${featured ? "featured" : ""}">
                <div class="strategy-card-header">
                    <div>
                        <h5 class="strategy-name" onclick="openStrategyDetail('${strategy.id}')">${escapeHtml(strategy.name)}</h5>
                        <div class="strategy-author">by ${escapeHtml(strategy.author || "Anonymous")}</div>
                    </div>
                    <div>${badges.join(" ")}</div>
                </div>
                
                <p class="strategy-description">${escapeHtml(strategy.description || "No description")}</p>
                
                ${tags ? `<div class="strategy-tags">${tags}</div>` : ""}
                
                <div class="strategy-metrics">
                    <div class="metric-item">
                        <div class="metric-value ${winRate >= 50 ? "positive" : "negative"}">${winRate ? winRate.toFixed(1) + "%" : "-"}</div>
                        <div class="metric-label">Win Rate</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value ${sharpe >= 1 ? "positive" : ""}">${sharpe ? sharpe.toFixed(2) : "-"}</div>
                        <div class="metric-label">Sharpe</div>
                    </div>
                    <div class="metric-item">
                        <div class="metric-value negative">${drawdown ? drawdown.toFixed(1) + "%" : "-"}</div>
                        <div class="metric-label">Max DD</div>
                    </div>
                </div>
                
                <div class="strategy-footer">
                    <div class="strategy-rating">
                        ${renderStars(strategy.rating || 0)}
                        <span class="rating-value">${(strategy.rating || 0).toFixed(1)}</span>
                        <span class="rating-count">(${strategy.review_count || 0})</span>
                    </div>
                    <div class="strategy-actions">
                        <button class="btn-like ${strategy.liked ? "liked" : ""}" onclick="toggleLike('${strategy.id}')" title="Like">
                            <i class="bi bi-heart${strategy.liked ? "-fill" : ""}"></i>
                            <span class="like-count">${strategy.like_count || ""}</span>
                        </button>
                        <button class="btn-download" onclick="downloadStrategy('${strategy.id}')" title="Download">
                            <i class="bi bi-download"></i> Download
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function renderStars(rating) {
  const full = Math.floor(rating);
  const half = rating % 1 >= 0.5;
  const empty = 5 - full - (half ? 1 : 0);

  let html = "";
  for (let i = 0; i < full; i++) html += '<i class="bi bi-star-fill"></i>';
  if (half) html += '<i class="bi bi-star-half"></i>';
  for (let i = 0; i < empty; i++) html += '<i class="bi bi-star"></i>';

  return html;
}

function renderPagination() {
  const container = document.getElementById("pagination").querySelector("ul");

  if (totalPages <= 1) {
    container.innerHTML = "";
    return;
  }

  let html = `
        <li class="page-item ${currentPage === 1 ? "disabled" : ""}">
            <a class="page-link" href="#" onclick="goToPage(${currentPage - 1})">&laquo;</a>
        </li>
    `;

  for (let i = 1; i <= totalPages; i++) {
    if (
      i === 1 ||
      i === totalPages ||
      (i >= currentPage - 2 && i <= currentPage + 2)
    ) {
      html += `
                <li class="page-item ${i === currentPage ? "active" : ""}">
                    <a class="page-link" href="#" onclick="goToPage(${i})">${i}</a>
                </li>
            `;
    } else if (i === currentPage - 3 || i === currentPage + 3) {
      html +=
        '<li class="page-item disabled"><span class="page-link">...</span></li>';
    }
  }

  html += `
        <li class="page-item ${currentPage === totalPages ? "disabled" : ""}">
            <a class="page-link" href="#" onclick="goToPage(${currentPage + 1})">&raquo;</a>
        </li>
    `;

  container.innerHTML = html;
}

// ============================================
// MODALS
// ============================================

function openPublishModal() {
  const modal = new bootstrap.Modal(document.getElementById("publishModal"));
  modal.show();
}

function openStrategyDetail(id) {
  selectedStrategyId = id;
  const strategy = strategies.find((s) => s.id === id);

  if (!strategy) {
    // Fetch from API
    fetch(`${API_BASE}/marketplace/strategies/${id}`)
      .then((r) => r.json())
      .then((data) => showDetailModal(data))
      .catch((err) =>
        showToast("Error", "Failed to load strategy details", "error"),
      );
    return;
  }

  showDetailModal(strategy);
}

function showDetailModal(strategy) {
  document.getElementById("detailModalTitle").textContent = strategy.name;
  document.getElementById("btnDownloadStrategy").onclick = () =>
    downloadStrategy(strategy.id);

  const body = document.getElementById("detailModalBody");
  body.innerHTML = `
        <div class="row">
            <div class="col-md-8">
                <h6 class="text-muted mb-2">Description</h6>
                <p>${escapeHtml(strategy.description || "No description")}</p>
                
                <h6 class="text-muted mb-2 mt-4">Strategy Type</h6>
                <p><span class="badge bg-primary">${strategy.strategy_type || "Custom"}</span></p>
                
                ${
                  strategy.parameters
                    ? `
                    <h6 class="text-muted mb-2 mt-4">Parameters</h6>
                    <pre class="bg-dark p-3 rounded"><code>${JSON.stringify(strategy.parameters, null, 2)}</code></pre>
                `
                    : ""
                }
                
                ${
                  strategy.tags?.length
                    ? `
                    <h6 class="text-muted mb-2 mt-4">Tags</h6>
                    <div>${strategy.tags.map((t) => `<span class="badge bg-secondary me-1">${escapeHtml(t)}</span>`).join("")}</div>
                `
                    : ""
                }
            </div>
            <div class="col-md-4">
                <div class="card bg-secondary bg-opacity-25 mb-3">
                    <div class="card-body">
                        <h6 class="card-title">Performance</h6>
                        <div class="d-flex justify-content-between mb-2">
                            <span class="text-muted">Win Rate</span>
                            <span class="${strategy.performance?.win_rate >= 50 ? "text-success" : "text-danger"}">${strategy.performance?.win_rate?.toFixed(1) || "-"}%</span>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <span class="text-muted">Sharpe Ratio</span>
                            <span>${strategy.performance?.sharpe_ratio?.toFixed(2) || "-"}</span>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <span class="text-muted">Max Drawdown</span>
                            <span class="text-danger">${strategy.performance?.max_drawdown?.toFixed(1) || "-"}%</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span class="text-muted">Total Return</span>
                            <span class="${strategy.performance?.total_return >= 0 ? "text-success" : "text-danger"}">${strategy.performance?.total_return?.toFixed(1) || "-"}%</span>
                        </div>
                    </div>
                </div>
                
                <div class="card bg-secondary bg-opacity-25">
                    <div class="card-body">
                        <div class="d-flex justify-content-between mb-2">
                            <span class="text-muted">Rating</span>
                            <span>${renderStars(strategy.rating || 0)} (${strategy.review_count || 0})</span>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <span class="text-muted">Downloads</span>
                            <span>${formatNumber(strategy.download_count || 0)}</span>
                        </div>
                        <div class="d-flex justify-content-between mb-2">
                            <span class="text-muted">Author</span>
                            <span>${escapeHtml(strategy.author || "Anonymous")}</span>
                        </div>
                        <div class="d-flex justify-content-between">
                            <span class="text-muted">Published</span>
                            <span>${formatDate(strategy.created_at)}</span>
                        </div>
                    </div>
                </div>
                
                <button class="btn btn-outline-primary w-100 mt-3" onclick="openReviewModal('${strategy.id}')">
                    <i class="bi bi-chat-dots"></i> Write a Review
                </button>
            </div>
        </div>
    `;

  const modal = new bootstrap.Modal(
    document.getElementById("strategyDetailModal"),
  );
  modal.show();
}

function openReviewModal(id) {
  selectedStrategyId = id;
  selectedRating = 0;
  updateRatingStars(0);
  document.getElementById("reviewText").value = "";

  // Close detail modal if open
  const detailModal = bootstrap.Modal.getInstance(
    document.getElementById("strategyDetailModal"),
  );
  if (detailModal) detailModal.hide();

  const modal = new bootstrap.Modal(document.getElementById("reviewModal"));
  modal.show();
}

// ============================================
// HELPERS
// ============================================

function showLoading() {
  document.getElementById("strategiesGrid").innerHTML = `
        <div class="col-12 text-center py-5" id="loadingState">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="text-muted mt-2">Loading strategies...</p>
        </div>
    `;
}

function showError(message) {
  document.getElementById("strategiesGrid").innerHTML = `
        <div class="col-12">
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> ${escapeHtml(message)}
            </div>
        </div>
    `;
}

function showToast(title, message, type = "info") {
  const container = document.getElementById("toastContainer");
  const id = "toast-" + Date.now();

  const bgClass =
    type === "success"
      ? "bg-success"
      : type === "error"
        ? "bg-danger"
        : "bg-primary";

  const html = `
        <div id="${id}" class="toast ${bgClass} text-white" role="alert">
            <div class="toast-header ${bgClass} text-white">
                <strong class="me-auto">${escapeHtml(title)}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">${escapeHtml(message)}</div>
        </div>
    `;

  container.insertAdjacentHTML("beforeend", html);

  const toastEl = document.getElementById(id);
  const toast = new bootstrap.Toast(toastEl);
  toast.show();

  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

function toggleView(view) {
  const grid = document.getElementById("strategiesGrid");
  if (view === "list") {
    grid.classList.add("list-view");
  } else {
    grid.classList.remove("list-view");
  }
}

function goToPage(page) {
  if (page < 1 || page > totalPages) return;
  currentPage = page;
  loadStrategies();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateRatingStars(rating) {
  document.querySelectorAll(".rating-star").forEach((star) => {
    const val = parseInt(star.dataset.value);
    star.classList.toggle("active", val <= rating);
    star.querySelector("i").className =
      val <= rating ? "bi bi-star-fill" : "bi bi-star";
  });
}

function highlightStars(rating) {
  document.querySelectorAll(".rating-star").forEach((star) => {
    const val = parseInt(star.dataset.value);
    star.querySelector("i").className =
      val <= rating ? "bi bi-star-fill" : "bi bi-star";
  });
}

function isNew(dateStr) {
  if (!dateStr) return false;
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now - date;
  return diff < 7 * 24 * 60 * 60 * 1000; // 7 days
}

function formatNumber(num) {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return num.toString();
}

function formatDate(dateStr) {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleDateString();
}

function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
