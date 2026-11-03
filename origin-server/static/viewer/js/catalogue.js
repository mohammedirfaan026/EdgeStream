/**
 * catalogue.js — Fetches the video list from the origin server and renders
 * the video catalogue grid on index.html.
 *
 * Requests go through the EDGE server (Laptop B) so the response is cached.
 * If the edge server is unreachable, falls back to direct origin.
 */

// ── Configuration ─────────────────────────────────────────────────────────────
// UPDATE these IPs to match your actual network setup.
const EDGE_URL   = "http://192.168.1.20";        // Laptop B — edge server
const ORIGIN_URL = "http://192.168.1.10:8000";   // Laptop A — direct fallback

// ── Fetch and render video list ───────────────────────────────────────────────
async function loadCatalogue() {
  const grid     = document.getElementById("video-grid");
  const errorMsg = document.getElementById("error-msg");

  let videos = null;

  // Try edge first, fall back to origin
  for (const base of [EDGE_URL, ORIGIN_URL]) {
    try {
      const res = await fetch(`${base}/videos`, { signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        videos = await res.json();
        break;
      }
    } catch (_) {
      // Try next endpoint
    }
  }

  if (videos === null) {
    grid.innerHTML = "";
    errorMsg.textContent = "Could not reach the video server. Check that Laptop A and Laptop B are running.";
    errorMsg.style.display = "block";
    return;
  }

  if (videos.length === 0) {
    grid.innerHTML = '<p class="loading-msg">No videos available yet. Upload one via the admin interface.</p>';
    return;
  }

  grid.innerHTML = videos.map(v => renderCard(v)).join("");
}

/**
 * Build an HTML card for a single video.
 * The card links to player.html with the video ID in the URL query string.
 */
function renderCard(video) {
  const durationStr = video.duration_s
    ? formatDuration(video.duration_s)
    : "";

  const resStr = Array.isArray(video.resolutions)
    ? video.resolutions.join(", ")
    : "";

  return `
    <a class="video-card" href="player.html?id=${encodeURIComponent(video.video_id)}">
      <div class="video-thumb">🎬</div>
      <div class="video-card-body">
        <div class="video-card-title">${escHtml(video.title)}</div>
        <div class="video-card-meta">
          ${durationStr ? durationStr + " &nbsp;·&nbsp; " : ""}
          ${resStr}
        </div>
      </div>
    </a>`;
}

/** Format seconds as mm:ss */
function formatDuration(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/** Escape HTML special characters to prevent XSS */
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Start ─────────────────────────────────────────────────────────────────────
loadCatalogue();
