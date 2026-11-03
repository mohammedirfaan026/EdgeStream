/**
 * dashboard.js — Polls the AI server for metrics and updates all dashboard panels.
 *
 * Polling interval: 5 seconds (configurable below).
 * Uses Chart.js for the buffer duration line chart and cache doughnut chart.
 * All DOM updates are non-destructive — charts are updated in place, not rebuilt.
 */

const POLL_INTERVAL_MS = 5000;

// ── Chart instances (created once, updated on each poll) ──────────────────────
let bufferChart = null;
let cacheChart  = null;

function initCharts() {
  const bufCtx = document.getElementById("bufferChart").getContext("2d");
  const cacheCtx = document.getElementById("cacheChart").getContext("2d");

  bufferChart = new Chart(bufCtx, {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        label: "Buffer (s)",
        data: [],
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59,130,246,0.08)",
        fill: true,
        tension: 0.3,
        pointRadius: 0,
      }],
    },
    options: {
      animation: false,
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: { mode: "index", intersect: false },
      },
      scales: {
        x: {
          ticks: { color: "#888", maxTicksLimit: 8 },
          grid:  { color: "#2a2d3a" },
        },
        y: {
          min: 0,
          ticks: { color: "#888" },
          grid:  { color: "#2a2d3a" },
          title: { display: true, text: "seconds", color: "#888" },
        },
      },
    },
  });

  cacheChart = new Chart(cacheCtx, {
    type: "doughnut",
    data: {
      labels: ["Hits", "Misses"],
      datasets: [{
        data: [0, 0],
        backgroundColor: ["#4ade80", "#f87171"],
        borderColor: "#1a1d27",
        borderWidth: 3,
      }],
    },
    options: {
      animation: false,
      responsive: true,
      plugins: {
        legend: {
          labels: { color: "#888", font: { size: 11 } },
        },
      },
    },
  });
}

// ── Poll and render ───────────────────────────────────────────────────────────
async function fetchAndRender() {
  try {
    const [dataRes, statusRes] = await Promise.all([
      fetch("/dashboard/data"),
      fetch("/predict/status"),
    ]);

    const data   = await dataRes.json();
    const status = await statusRes.json();

    renderKPIs(data, status);
    renderBufferChart(data.streaming.recent_buffer_series);
    renderCacheChart(data.cache);
    renderPredictionsTable(data.ai.recent_predictions);

    document.getElementById("last-update").textContent =
      "Last updated: " + new Date().toLocaleTimeString();

    document.getElementById("model-badge").textContent =
      status.model_loaded ? "Model: ML Active" : "Model: Baseline";

  } catch (err) {
    console.warn("[dashboard] Failed to fetch data:", err.message);
  }
}

function renderKPIs(data, status) {
  const s = data.streaming;
  const c = data.cache;
  const a = data.ai;

  document.getElementById("kpi-active").textContent    = s.active_sessions;
  document.getElementById("kpi-total").textContent     = s.total_sessions;
  document.getElementById("kpi-buffer").textContent    = s.avg_buffer_s.toFixed(1) + "s";
  document.getElementById("kpi-buf-events").textContent = s.total_buffering_events;
  document.getElementById("kpi-hit-ratio").textContent =
    c.total > 0 ? (c.hit_ratio * 100).toFixed(1) + "%" : "—";
  document.getElementById("kpi-alerts").textContent    = a.high_risk_count;
}

function renderBufferChart(series) {
  if (!series || series.length === 0) return;

  // Keep the last 60 data points on the chart
  const recent = series.slice(-60);
  const labels = recent.map(pt => {
    const d = new Date(pt.t);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  });
  const values = recent.map(pt => pt.v);

  bufferChart.data.labels          = labels;
  bufferChart.data.datasets[0].data = values;
  bufferChart.update("none");  // "none" = no animation for live updates
}

function renderCacheChart(cache) {
  cacheChart.data.datasets[0].data = [cache.hits, cache.misses];
  cacheChart.update("none");
}

function renderPredictionsTable(predictions) {
  const tbody = document.getElementById("pred-tbody");
  if (!predictions || predictions.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-row">No predictions yet.</td></tr>';
    return;
  }

  tbody.innerHTML = predictions.map(p => {
    const isHigh = p.predicted_label === 1;
    const t = new Date(p.predicted_at).toLocaleTimeString();
    return `
      <tr>
        <td>${t}</td>
        <td>${(p.risk_score * 100).toFixed(1)}%</td>
        <td class="${isHigh ? "label-high" : "label-low"}">${isHigh ? "HIGH" : "LOW"}</td>
        <td>${p.model_version || "—"}</td>
      </tr>`;
  }).join("");
}

// ── Boot ─────────────────────────────────────────────────────────────────────
initCharts();
fetchAndRender();
setInterval(fetchAndRender, POLL_INTERVAL_MS);
