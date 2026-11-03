# Network Throttling Guide — EdgeStream AI Experiments

Use this guide to create controlled degraded-network conditions for data collection.
Collect data under each condition to get a balanced dataset with enough buffering events.

---

## Why Throttle?

On a clean LAN, buffering events are rare (buffer stays at 20–30 seconds).
Without throttling, 95%+ of labels will be 0 (no buffering), making ML training
unreliable. You need deliberate degradation to generate positive labels.

---

## Option A — Windows: NetLimiter (Recommended)

NetLimiter is a GUI tool that limits bandwidth per process or per NIC.

1. Download from: https://www.netlimiter.com/ (free trial)
2. Install on whichever machine is the VIEWER (browser machine)
3. Find the browser process (chrome.exe, firefox.exe)
4. Set download limit per condition:

| Condition | Download Limit | Expected Effect |
|-----------|---------------|-----------------|
| Normal    | Unlimited     | No buffering |
| Mild      | 4 Mbps        | Occasional quality drops |
| Moderate  | 2 Mbps        | Frequent quality drops, some buffering |
| Severe    | 1 Mbps        | Regular buffering at 720p |
| Variable  | Toggle every 30s between 5 Mbps and 0.5 Mbps | Realistic variation |

---

## Option B — Windows: PowerShell QoS Policy

Built into Windows — no extra software needed. Less precise than NetLimiter.

```powershell
# Create a QoS policy to throttle traffic to Laptop B (edge server)
# (replace 192.168.1.20 with real Laptop B IP)

New-NetQosPolicy -Name "EdgeStream-Throttle" `
    -IPDstAddress "192.168.1.20" `
    -IPProtocol TCP `
    -ThrottleRateActionBitsPerSecond 2000000   # 2 Mbps

# Remove throttle when done
Remove-NetQosPolicy -Name "EdgeStream-Throttle" -Confirm:$false
```

---

## Option C — Linux: tc netem (Most Precise)

If the VIEWER or ROUTER machine runs Linux, tc gives precise control.

```bash
# Throttle download to 2 Mbps with 20ms added latency
# (run on viewer machine or router)
sudo tc qdisc add dev eth0 root handle 1: tbf \
    rate 2mbit burst 32kbit latency 400ms

# Remove
sudo tc qdisc del dev eth0 root

# Variable: toggle every 30 seconds in a shell loop
while true; do
    echo "Throttling to 1 Mbps..."
    sudo tc qdisc add dev eth0 root handle 1: tbf \
        rate 1mbit burst 16kbit latency 300ms
    sleep 30
    echo "Removing throttle..."
    sudo tc qdisc del dev eth0 root
    sleep 30
done
```

---

## Data Collection Protocol

Run this sequence to collect a balanced dataset:

| Session Set | Network Condition | Duration  | Expected Buffering |
|-------------|-------------------|-----------|--------------------|
| A (5 runs)  | Normal (no limit) | 5 min each | Rare |
| B (5 runs)  | 2 Mbps throttle  | 5 min each | Occasional |
| C (5 runs)  | 1 Mbps throttle  | 5 min each | Frequent |
| D (3 runs)  | Variable toggle  | 5 min each | Mixed |

**Total target: 18 sessions × ~60 events/session = ~1,080 rows minimum.**

For better ML results, aim for **2,000+ rows with 15–30% positive labels**.

---

## Verifying Throttle is Working

Watch the player's quality selector in the browser — if it drops from 720p to 360p,
the throttle is working. Also watch the buffer stat badge in the player UI.

Check the AI server dashboard — you should see the average buffer dropping
and buffering event count increasing under throttled conditions.

---

## Latency Testing (Experiment 3)

To add network latency (simulating WAN conditions) without reducing bandwidth:

```bash
# Linux: add 100ms RTT latency with 20ms jitter
sudo tc qdisc add dev eth0 root netem delay 100ms 20ms

# Remove
sudo tc qdisc del dev eth0 root
```

Windows alternative: use NetLimiter's "Latency" option or a software router.
