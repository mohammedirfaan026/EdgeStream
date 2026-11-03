/**
 * metrics.js — Collects hls.js playback telemetry and sends it to the
 * AI & Monitoring server (Laptop C) at a configurable interval.
 *
 * Key design decisions:
 *   1. ALL network errors to the AI server are caught silently.
 *      Video playback must never be interrupted by monitoring failures.
 *   2. Metrics are batched — one POST per interval, not one per event.
 *   3. The response from the AI server carries a buffering risk score.
 *      If risk is HIGH, a warning overlay is shown in the player.
 *   4. The AI server URL is the only IP reference in this file.
 *
 * Depends on player.js — must be loaded after player.js (see player.html).
 */

// ── Configuration — UPDATE AI server IP ──────────────────────────────────────
const AI_SERVER          = "http://192.168.1.30:8001";   // Laptop C
const REPORT_INTERVAL_MS = 5000;                          // send every 5 seconds
const HIGH_RISK_THRESHOLD = 0.6;                          // show warning above this

// ── DOM references ────────────────────────────────────────────────────────────
const warningEl  = document.getElementById("buffering-warning");
const riskBar    = document.getElementById("risk-bar");
const riskScore  = document.getElementById("risk-score");
const riskIndic  = document.getElementById("risk-indicator");

// ── Grab shared state from player.js ─────────────────────────────────────────
// window.edgeStream is populated by player.js before this script runs.
const { sessionId, videoId } = window.edgeStream;

/**
 * Compute how many seconds of video are buffered ahead of the current playhead.
 * Reads from the video element's buffered TimeRanges object.
 */
function getBufferAhead(videoEl) {
  for (let i = 0; i < videoEl.buffered.length; i++) {
    if (videoEl.buffered.start(i) <= videoEl.currentTime &&
        videoEl.currentTime       <= videoEl.buffered.end(i)) {
      return videoEl.buffered.end(i) - videoEl.currentTime;
    }
  }
  return 0;
}

/**
 * Build the metrics payload object to send to the AI server.
 * Only includes data that is reliably available from hls.js and the HTMLVideoElement.
 */
function buildPayload(videoEl, hls) {
  const bufferAhead  = getBufferAhead(videoEl);
  const isBuffering  = videoEl.readyState < 3 && !videoEl.paused;
  const bitrateKbps  = hls ? Math.round((hls.bandwidthEstimate || 0) / 1000) : 0;
  const currentLevel = hls ? hls.currentLevel : -1;

  return {
    session_id:       sessionId,
    video_id:         videoId,
    timestamp:        new Date().toISOString(),
    playback_time_s:  parseFloat(videoEl.currentTime.toFixed(2)),
    buffer_duration_s: parseFloat(bufferAhead.toFixed(3)),
    bitrate_kbps:     bitrateKbps,
    dl_speed_kbps:    parseFloat((window.edgeStream.lastFragSpeed || 0).toFixed(1)),
    dl_time_ms:       parseFloat((window.edgeStream.lastFragDuration || 0).toFixed(0)),
    is_buffering:     isBuffering,
    quality_level:    currentLevel,
  };
}

/**
 * Update the risk indicator UI based on the AI server's response.
 * @param {number} riskScoreVal  — float 0.0 to 1.0
 * @param {boolean} warning      — true if risk exceeds threshold
 */
function updateRiskUI(riskScoreVal, warning) {
  const pct = Math.round(riskScoreVal * 100);

  riskBar.style.width = `${pct}%`;
  riskScore.textContent = `${pct}%`;

  // Colour the bar: green → yellow → red
  if (riskScoreVal < 0.4) {
    riskBar.style.background = "var(--success)";
  } else if (riskScoreVal < 0.7) {
    riskBar.style.background = "var(--warning)";
  } else {
    riskBar.style.background = "var(--danger)";
  }

  // Show/hide the warning banner
  warningEl.style.display = warning ? "block" : "none";
}

/**
 * Main telemetry loop — fires every REPORT_INTERVAL_MS.
 * Sends metrics to AI server, updates risk UI from response.
 * Any error is caught and logged; playback continues unaffected.
 */
async function sendMetrics() {
  const videoEl = document.getElementById("videoEl");
  const hls     = window.edgeStream?.hls;

  // Don't send metrics if video hasn't started
  if (!videoEl || videoEl.readyState < 1) return;

  const payload = buildPayload(videoEl, hls);

  try {
    const res = await fetch(`${AI_SERVER}/metrics/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      // Fail fast — 3 second timeout so we never block the browser event loop
      signal: AbortSignal.timeout(3000),
    });

    if (res.ok) {
      const data = await res.json();
      const score   = typeof data.buffering_risk_score === "number"
                      ? data.buffering_risk_score : 0;
      const warning = data.warning === true;

      updateRiskUI(score, warning);
      riskIndic.style.display = "flex";
    }
  } catch (err) {
    // AI server is unreachable or slow — this is non-fatal
    // Hide the warning (can't confirm risk) but don't interrupt playback
    console.debug("[metrics] AI server unavailable:", err.message);
  }
}

// ── Start the telemetry interval ──────────────────────────────────────────────
// Wait a moment for player.js to fully initialise hls.js before starting.
setTimeout(() => {
  sendMetrics();  // first call immediately
  setInterval(sendMetrics, REPORT_INTERVAL_MS);
}, 1500);
