# Edge Server Setup — Laptop B

This machine runs Nginx as a caching reverse proxy between browsers and the origin server.

**Laptop B IP:** `192.168.1.20` (update in nginx.conf if different)
**Origin IP:**   `192.168.1.10:8000` (update `proxy_pass` in nginx.conf)

---

## Option A — Linux (Recommended)

```bash
# Install Nginx
sudo apt update && sudo apt install -y nginx

# Copy config
sudo cp nginx.conf /etc/nginx/nginx.conf

# Create cache directory
sudo mkdir -p /var/cache/nginx/edgestream
sudo chown -R www-data:www-data /var/cache/nginx/edgestream

# Test configuration
sudo nginx -t

# Start / restart
sudo systemctl enable nginx
sudo systemctl restart nginx

# Verify
curl -s http://localhost/edge-health
```

---

## Option B — Windows (Docker Desktop)

```powershell
# Prerequisite: Docker Desktop is running

cd D:\Edgestream\edge-server

# Start edge server in background
docker compose up -d

# Verify
curl http://localhost/edge-health

# View logs
docker compose logs -f nginx-edge
```

---

## Verify Cache is Working

```bash
# First request — should return X-Cache-Status: MISS
curl -I http://192.168.1.20/hls/{VIDEO_ID}/seg_00001_360p.ts

# Second request — should return X-Cache-Status: HIT
curl -I http://192.168.1.20/hls/{VIDEO_ID}/seg_00001_360p.ts
```

Replace `{VIDEO_ID}` with an actual video ID from the admin UI on Laptop A.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| CORS error in browser | Verify CORS headers in nginx.conf; check `add_header Access-Control-Allow-Origin '*'` |
| 502 Bad Gateway | Origin server (Laptop A) is not running or IP is wrong in nginx.conf |
| Cache never shows HIT | Check `proxy_no_cache` directive; master.m3u8 intentionally never caches |
| Connection refused on port 80 | Firewall is blocking port 80 — allow it on Laptop B |

---

## Firewall (Windows Laptop B with Docker)

```powershell
# Allow inbound port 80 from LAN
New-NetFirewallRule -DisplayName "EdgeStream Edge Port 80" `
    -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
```

## Firewall (Linux Laptop B)

```bash
sudo ufw allow 80/tcp
sudo ufw reload
```
