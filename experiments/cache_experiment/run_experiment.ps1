# EdgeStream AI — Cache Experiment Script (Windows PowerShell)
# Experiment 1: Edge Cache vs Direct Origin latency comparison
#
# Usage:
#   cd D:\Edgestream\experiments\cache_experiment
#   .\run_experiment.ps1
#
# Prerequisites:
#   - Laptop A (origin) running on 192.168.1.10:8000
#   - Laptop B (edge)   running on 192.168.1.20:80
#   - At least one video processed and in "ready" state
#   - curl installed (built into Windows 10/11)

# ── Configuration — UPDATE THESE ─────────────────────────────────────────────
$ORIGIN_URL  = "http://192.168.1.10:8000"
$EDGE_URL    = "http://192.168.1.20"
$VIDEO_ID    = "REPLACE_WITH_YOUR_VIDEO_ID"      # copy from admin UI
$SEGMENT     = "seg_00001_360p.ts"               # first segment, lowest quality
$TRIALS      = 20
$AI_URL      = "http://192.168.1.30:8001"        # Laptop C

$ResultFile  = ".\results_raw.csv"

Write-Host "EdgeStream AI — Cache Experiment" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host "Origin:  $ORIGIN_URL"
Write-Host "Edge:    $EDGE_URL"
Write-Host "Video:   $VIDEO_ID"
Write-Host "Segment: $SEGMENT"
Write-Host "Trials:  $TRIALS"
Write-Host ""

# ── Warm-up: clear edge cache by restarting Nginx would be ideal.
# ── For now, we note that the first request will always be a MISS.
Write-Host "NOTE: First request through edge will be a MISS (cold cache)." -ForegroundColor Yellow
Write-Host "      Subsequent requests for the same segment will be HITs." -ForegroundColor Yellow
Write-Host ""

# ── Output CSV header ─────────────────────────────────────────────────────────
"trial,condition,latency_ms,cache_status,http_status" | Out-File $ResultFile -Encoding UTF8

# ── Experiment A: Direct origin ───────────────────────────────────────────────
Write-Host "=== Condition A: Direct Origin ===" -ForegroundColor Yellow

$originHits   = 0
$originMisses = 0

for ($i = 1; $i -le $TRIALS; $i++) {
    $url = "$ORIGIN_URL/hls/$VIDEO_ID/$SEGMENT"
    $start = Get-Date

    $result = curl -s -o NUL -w "%{http_code}|%{time_total}" $url
    $elapsed = [math]::Round((Get-Date - $start).TotalMilliseconds, 1)

    $parts  = $result -split "\|"
    $status = $parts[0].Trim()

    Write-Host "  Trial $i : ${elapsed}ms  (HTTP $status)"
    "$i,origin,$elapsed,NONE,$status" | Out-File $ResultFile -Append -Encoding UTF8
}

# ── Experiment B: Via Edge server ─────────────────────────────────────────────
Write-Host ""
Write-Host "=== Condition B: Via Edge Server ===" -ForegroundColor Green

$edgeHits   = 0
$edgeMisses = 0

for ($i = 1; $i -le $TRIALS; $i++) {
    $url = "$EDGE_URL/hls/$VIDEO_ID/$SEGMENT"
    $start = Get-Date

    # -D - dumps headers to stdout; we parse X-Cache-Status from them
    $headers = curl -s -D - -o NUL $url 2>&1
    $elapsed = [math]::Round((Get-Date - $start).TotalMilliseconds, 1)

    # Extract cache status from headers
    $cacheStatus = "UNKNOWN"
    foreach ($line in $headers) {
        if ($line -match "X-Cache-Status:\s*(\w+)") {
            $cacheStatus = $matches[1].Trim()
            break
        }
    }

    if ($cacheStatus -eq "HIT")  { $edgeHits++ }
    if ($cacheStatus -eq "MISS") { $edgeMisses++ }

    Write-Host "  Trial $i : ${elapsed}ms  (Cache: $cacheStatus)"
    "$i,edge,$elapsed,$cacheStatus,200" | Out-File $ResultFile -Append -Encoding UTF8
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan

$data = Import-Csv $ResultFile

$originData = $data | Where-Object { $_.condition -eq "origin" }
$edgeData   = $data | Where-Object { $_.condition -eq "edge" }
$edgeHit    = $data | Where-Object { $_.condition -eq "edge" -and $_.cache_status -eq "HIT" }
$edgeMiss   = $data | Where-Object { $_.condition -eq "edge" -and $_.cache_status -eq "MISS" }

function Get-Percentile($values, $pct) {
    $sorted = $values | Sort-Object { [double]$_ }
    $idx = [math]::Ceiling($pct / 100 * $sorted.Count) - 1
    return [double]$sorted[$idx]
}

$originLatencies = $originData | ForEach-Object { [double]$_.latency_ms }
$edgeLatencies   = $edgeData   | ForEach-Object { [double]$_.latency_ms }
$edgeHitLats     = $edgeHit    | ForEach-Object { [double]$_.latency_ms }

Write-Host ""
Write-Host "Direct Origin:"
Write-Host "  p50: $(Get-Percentile $originLatencies 50) ms"
Write-Host "  p95: $(Get-Percentile $originLatencies 95) ms"
Write-Host ""
Write-Host "Via Edge (all):"
Write-Host "  p50: $(Get-Percentile $edgeLatencies 50) ms"
Write-Host "  p95: $(Get-Percentile $edgeLatencies 95) ms"
Write-Host "  Hits:   $($edgeHit.Count)"
Write-Host "  Misses: $($edgeMiss.Count)"
if ($edgeData.Count -gt 0) {
    $hitRatio = [math]::Round($edgeHit.Count / $edgeData.Count * 100, 1)
    Write-Host "  Hit Ratio: ${hitRatio}%"
}

# ── Send cache stats to AI server for dashboard ───────────────────────────────
$payload = @{
    hits   = $edgeHit.Count
    misses = $edgeMiss.Count
    source = "cache_experiment"
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$AI_URL/cache-stats" -Method POST `
        -ContentType "application/json" -Body $payload | Out-Null
    Write-Host ""
    Write-Host "Cache stats sent to AI dashboard." -ForegroundColor Green
} catch {
    Write-Host "Could not send stats to AI server (non-fatal)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Raw results saved to: $ResultFile"
Write-Host "Copy p50/p95 values and hit ratio into experiments\cache_experiment\results.md"
