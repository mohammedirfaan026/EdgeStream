/**
 * player.js — Initialises hls.js, loads the video stream from the edge server,
 * manages the quality selector, and exposes shared state for metrics.js.
 *
 * All video requests use the EDGE server URL (Laptop B) so they pass through
 * the Nginx cache.  The AI server URL is used only by metrics.js for telemetry.
 */

// ── Configuration — UPDATE THESE IPs ─────────────────────────────────────────
const EDGE_URL   = "http://192.168.1.20";       // Laptop B — all HLS requests
const ORIGIN_URL = "http://192.168.1.10:8000";  // Laptop A — metadata only

// ── DOM references ────────────────────────────────────────────────────────────
const videoEl         = document.getElementById("videoEl");
const qualitySelect   = document.getElementById("quality-select");
const statQuality     = document.getElementById("stat-quality");
const statBuffer      = document.getElementById("stat-buffer");
const statBitrate     = document.getElementById("stat-bitrate");
const statCache       = document.getElementById("stat-cache");
const titleEl         = document.getElementById("video-title");
const descCard        = document.getElementById("desc-card");
const descEl          = document.getElementById("video-description");
const bufferingSpinner = document.getElementById("buffering-spinner");

// ── Read video ID from URL query string ───────────────────────────────────────
const params  = new URLSearchParams(window.location.search);
const videoId = params.get("id");

if (!videoId) {
  document.body.innerHTML = '<p style="color:#f87171;padding:2rem">No video ID specified. <a href="index.html">Go back</a></p>';
  throw new Error("No video ID");
}

// ── Shared state (read by metrics.js) ─────────────────────────────────────────
window.edgeStream = {
  videoId,
  hls: null,
  sessionId: crypto.randomUUID(),
  lastFragDuration: 0,     // seconds — last segment download time
  lastFragSpeed: 0,        // kbps — last segment download throughput
};

// ── Load video metadata ────────────────────────────────────────────────────────
async function loadVideoMeta() {
  try {
    const res = await fetch(`${ORIGIN_URL}/videos/${videoId}`,
                            { signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error("Not found");
    const meta = await res.json();
    document.title = `${meta.title} — EdgeStream AI`;
    titleEl.textContent = meta.title;
    if (meta.description) {
      descEl.textContent = meta.description;
      descCard.style.display = "block";
    }
  } catch (_) {
    titleEl.textContent = "Video";
  }
}

// ── Initialise hls.js ─────────────────────────────────────────────────────────
function initPlayer() {
  const hlsUrl = `${EDGE_URL}/hls/${videoId}/master.m3u8`;

  if (!Hls.isSupported()) {
    // Safari supports HLS natively
    if (videoEl.canPlayType("application/vnd.apple.mpegurl")) {
      videoEl.src = hlsUrl;
      return;
    }
    alert("Your browser does not support HLS playback.");
    return;
  }

  const hls = new Hls({
    // Start at the lowest quality to fill buffer quickly
    startLevel: 0,
    // Enable ABR (automatic bitrate selection by hls.js)
    autoLevelEnabled: true,
    // Use aggressive buffer-filling strategy
    maxBufferLength: 30,
    maxMaxBufferLength: 60,
    // Bandwidth estimate persistence
    abrEwmaDefaultEstimate: 500000,    // 500 kbps initial estimate
  });

  window.edgeStream.hls = hls;

  hls.loadSource(hlsUrl);
  hls.attachMedia(videoEl);

  // ── Event: HLS manifest loaded → populate quality selector ────────────────
  hls.on(Hls.Events.MANIFEST_PARSED, (event, data) => {
    const levels = hls.levels;
    qualitySelect.innerHTML = '<option value="-1">Auto (ABR)</option>';

    levels.forEach((level, idx) => {
      const label = level.name || `${Math.round(level.bitrate / 1000)} kbps`;
      const opt   = document.createElement("option");
      opt.value   = idx;
      opt.textContent = label;
      qualitySelect.appendChild(opt);
    });

    // Show risk indicator now that player is ready
    document.getElementById("risk-indicator").style.display = "flex";
  });

  // ── Event: Level (quality) changed ────────────────────────────────────────
  hls.on(Hls.Events.LEVEL_SWITCHED, (event, data) => {
    const level = hls.levels[data.level];
    if (level) {
      statQuality.textContent = `Quality: ${level.name || data.level}`;
      statBitrate.textContent = `Bitrate: ${Math.round(level.bitrate / 1000)} kbps`;
    }
    // Sync dropdown (auto mode may have selected a specific level)
    if (qualitySelect.value === "-1") {
      // Stay on Auto — don't change dropdown
    }
  });

  // ── Event: Fragment loaded → compute download speed ───────────────────────
  hls.on(Hls.Events.FRAG_LOADED, (event, data) => {
    const stats = data.frag.stats;
    if (stats && stats.loaded && stats.tload > stats.tfirst) {
      const durationMs = stats.tload - stats.tfirst;
      const bytes      = stats.loaded;
      window.edgeStream.lastFragDuration = durationMs;
      window.edgeStream.lastFragSpeed    = (bytes * 8) / durationMs;  // kbps
      statCache.textContent = "Cache: —";   // can't read cache header from hls.js
    }
  });

  // ── Event: Buffering / stalled ────────────────────────────────────────────
  hls.on(Hls.Events.ERROR, (event, data) => {
    if (data.details === Hls.ErrorDetails.BUFFER_STALLED_ERROR ||
        data.details === Hls.ErrorDetails.BUFFER_NUDGE_ON_STALL) {
      bufferingSpinner.style.display = "flex";
    }
    if (data.fatal) {
      console.error("Fatal hls.js error:", data.type, data.details);
    }
  });

  videoEl.addEventListener("playing", () => {
    bufferingSpinner.style.display = "none";
  });

  videoEl.addEventListener("waiting", () => {
    bufferingSpinner.style.display = "flex";
  });

  // ── Live stat update loop ─────────────────────────────────────────────────
  setInterval(() => {
    if (!videoEl.duration) return;

    // Buffer length = how many seconds of video are buffered ahead of playhead
    let bufferAhead = 0;
    for (let i = 0; i < videoEl.buffered.length; i++) {
      if (videoEl.buffered.start(i) <= videoEl.currentTime &&
          videoEl.currentTime  <= videoEl.buffered.end(i)) {
        bufferAhead = videoEl.buffered.end(i) - videoEl.currentTime;
        break;
      }
    }

    statBuffer.textContent = `Buffer: ${bufferAhead.toFixed(1)}s`;

    const bw = hls.bandwidthEstimate;
    if (bw) statBitrate.textContent = `Bitrate: ${Math.round(bw / 1000)} kbps`;

  }, 1000);
}

// ── Quality selector change handler ───────────────────────────────────────────
qualitySelect.addEventListener("change", () => {
  const hls = window.edgeStream.hls;
  if (!hls) return;
  const val = parseInt(qualitySelect.value, 10);
  hls.currentLevel = val;   // -1 = auto, 0..n = specific level
  statQuality.textContent = val === -1 ? "Quality: Auto" : `Quality: Level ${val}`;
});

// ── Boot ─────────────────────────────────────────────────────────────────────
loadVideoMeta();
initPlayer();
