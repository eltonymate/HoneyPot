# Cowrie Honeypot on DigitalOcean

A step-by-step log of setting up an SSH/Telnet honeypot exposed to the public internet, used to capture and analyze real automated attack traffic (bots, brute-force attempts, worm propagation) for a PrinceLab YouTube video.

## Architecture

```
Internet → Droplet (public IPv4)
             ├── Port 22   → redirected to Cowrie (honeypot, port 2222)
             └── Port 2200 → real SSH, for management, restricted to my own IP
```

## 1. Create the droplet

- Provider: **DigitalOcean**
- Image: Ubuntu 24.04 LTS
- Plan: Basic, 1 vCPU / 1GB RAM ($6/mo tier) — enough for Cowrie
- Auth: SSH key
- Hostname: neutral (not "honeypot"), to avoid tipping off automated scanners

## 2. Initial access & hardening

Connected via the public IPv4:

```bash
ssh root@<droplet_ip>
```

Created a non-root user for management:

```bash
adduser <username>
usermod -aG sudo <username>
```

Moved the **real** SSH management port off 22, since 22 is reserved for the honeypot:

```bash
nano /etc/ssh/sshd_config
# Port 2200
sshd -t              # validate syntax before restarting
systemctl restart ssh # service is "ssh" on Ubuntu, not "sshd"
```

> Kept the original session open until the new port was confirmed working, to avoid getting locked out.

## 3. Firewall

Restricted the management port to my own IP and left port 22 open to the world (that's the bait):

- DigitalOcean Networking → Firewalls → allow TCP 2200 from my IP only
- TCP 22 left open to all — this is what needs to attract bot traffic

## 4. Install Cowrie

```bash
apt install -y git python3-venv python3-pip libssl-dev libffi-dev build-essential authbind
adduser --disabled-password cowrie
su - cowrie
git clone https://github.com/cowrie/cowrie.git
cd cowrie
python3 -m venv cowrie-env
source cowrie-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .        # makes the `cowrie` command available directly
```

## 5. Configure Cowrie

```bash
cp etc/cowrie.cfg.dist etc/cowrie.cfg
nano etc/cowrie.cfg
```

Key settings:
```ini
[honeypot]
hostname = srvv-01

[ssh]
listen_endpoints = tcp:2222:interface=0.0.0.0
```

## 6. Redirect port 22 → 2222

Cowrie listens on 2222 (non-privileged port); public bots need to hit 22:

```bash
iptables -t nat -A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 2222
apt install -y iptables-persistent
netfilter-persistent save
```

## 7. Start Cowrie

```bash
cowrie start
cowrie status   # → "Cowrie is running"
```

## 8. Watch it work

```bash
tail -f var/log/cowrie/cowrie.log     # human-readable
tail -f var/log/cowrie/cowrie.json    # structured, one JSON event per line
```

First scan/connection attempt arrived within minutes of exposing port 22. First successful brute-force login within hours.

## 9. Let it collect data

Left the honeypot exposed for **24 hours** before pulling results.

## 10. Analyze the logs

Wrote a Python script to parse `cowrie.json` and produce an aggregate summary:

- Counts connection events per source IP
- Geolocates each IP via a batch IP-geolocation API
- Counts frequency of every command the attackers typed

Output (`honeypot_summary.json`):
- **525** total events
- **127** unique IPs
- **36** distinct countries
- Top command: `echo xsec` (137 times) — a canary command used by automated botnets to verify remote command execution before deploying a real payload
- 1 flagged high-severity event: an attacker attempted to drop a fake SSH private key and pull/execute a remote payload (self-propagating worm behavior)

## 11. Build the dashboard

Built a self-contained HTML dashboard (IT and EN versions) showing:
- A real choropleth world map (actual country borders, from Natural Earth boundary data) colored by attack volume per country
- A ranked list of top attacking countries
- A categorized table of the most-used attacker commands (recon / canary test / malicious payload / other)

## Security notes

- The honeypot runs as the unprivileged `cowrie` user, never as root.
- Management access is isolated on a non-standard port, restricted by IP.
- Everything the "attacker" sees inside Cowrie is a simulated filesystem/shell — no real system is ever exposed.
- This setup is for research/educational purposes on infrastructure I own; exposing SSH intentionally like this is only safe when fully isolated as described above.
