# Restaurant POS — Digital Ocean Deployment Guide

Flask + SQLite app, production ke liye tayyar. Ye folder wohi POS hai, sirf
server wali files ke sath — Windows junk (venv, run.bat, screenshots, demo DB) hata diya hai.

## Architecture (multi-tenant — Sep 2026)

Har account ki **apni alag database file** hai — kisi client ka data doosre ko kabhi nahi dikhta:

| File | Kya hai |
|---|---|
| `pos.db` | CENTRAL — sirf `users` table (logins, roles) |
| `tenants/u1.db` | Admin (main account) ka pura restaurant data |
| `tenants/u3.db` | Client (e.g. KFC) ka apna data — menu/orders/settings |
| `tenants/u<id>.db` | Har naye client account ke sath khud ban jati hai |

- `schema.sql` = tenant schema (restaurant tables). Users ka schema app.py me inline hai (`USERS_SCHEMA`).
- Client account banate hi uski data file banti hai; account delete karo to file bhi delete.
- **Admin "Open Dashboard"** (Users & Clients page) se kisi bhi client ka data khol kar uske
  liye menu/settings set kar sakta hai — yellow bar dikhti hai, "Back to my account" se wapas.
- Dashboard/branding: login page generic "Restaurant POS" — restaurant name tenant ke settings se.
- DB connections hamesha close hote hain (`db()` context manager — sqlite3 ka `with` close nahi karta).
- Deploy-time migration script: `deploy/migrate_tenant.py` (legacy shared data → admin tenant).
- Backup cron (raat 3 baje): `pos.db` + `tenants/` dono ka tar.gz → `backups/`, 7 din retention.

## Kya-kya hai

| File | Kaam |
|---|---|
| `app.py` | Application (WAL + busy_timeout patched — multi-worker safe) |
| `schema.sql` | Tables (first run pe khud ban jati hain) |
| `wsgi.py` | Gunicorn entry point — DB + admin login khud banata hai |
| `requirements.txt` | flask + gunicorn |
| `templates/`, `static/` | UI + CSS |
| `deploy/restaurant-pos.service` | systemd unit (server restart pe khud start) |
| `deploy/nginx-restaurant-pos.conf` | Optional — domain/HTTPS ke liye |

Pehli baar run pe app khud `pos.db` banayegi aur **admin** login create karega
(seed_admin default: `admin123` — sirf tab jab users table bilkul khali ho).
**Live server ka current password: `restaurant2026`** (deployment ke waqt change kiya gaya tha).
Demo data (Tandoori House wala) server pe NAHI hai — client apna restaurant naam,
address, tables aur menu UI se add karega (Settings → Tables → Menu).

---

## Step 1 — Droplet banao (Digital Ocean)

1. [cloud.digitalocean.com](https://cloud.digitalocean.com) → **Create → Droplet**
2. Image: **Ubuntu 24.04 LTS**, Plan: **Basic, $6/mo** (1 GB RAM kaafi hai)
3. Region: client ke qareeb (Lahore/restaurant ke liye **Singapore** sab se behtar latency)
4. Authentication: **SSH key** (password bhi chalega, SSH key safer)
5. **Create Droplet** → IP note kar lo

## Step 2 — Files server pe pahunchao

Windows me is folder me right-click → **Open Git Bash here**, phir (IP apni daalo):

```bash
scp -r C:/Users/Jadoon/Desktop/restaurant-pos-deploy/. root@YOUR_DROPLET_IP:/opt/restaurant-pos
```

(SSH key use ki hai to password nahi puchhega. Password login hai to har baar password.

## Step 3 — Server setup (SSH karke in commands run karo)

```bash
# 1. Server update + Python tools
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv nginx

# 2. App ke liye dedicated user (files + DB isi ke paas)
sudo useradd -r -s /usr/sbin/nologin pos
sudo chown -R pos:pos /opt/restaurant-pos

# 3. Python environment
cd /opt/restaurant-pos
sudo -u pos python3 -m venv venv
sudo -u pos venv/bin/pip install -r requirements.txt

# 4. Pehli baar DB + admin login banao (test ke liye)
sudo -u pos venv/bin/python -c "import wsgi"   # pos.db ban jayegi

# 5. Secret key set karo (service file me bhi change karo)
sudo nano /opt/restaurant-pos/deploy/restaurant-pos.service
#   Environment=SECRET_KEY= line me koi lambi random string daalo
#   (ya: python -c "import secrets; print(secrets.token_hex(32))")

# 6. systemd service enable karo
sudo cp /opt/restaurant-pos/deploy/restaurant-pos.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now restaurant-pos

# 7. Check — koi error nahi hona chahiye
sudo systemctl status restaurant-pos
```

## Step 4 — Firewall + Test

```bash
sudo ufw allow OpenSSH
sudo ufw allow 5001
sudo ufw enable
```

Ab browser me: **http://168.144.155.135** → login **admin / restaurant2026**

Client ko dena: URL + ye login. Client **Password change** kare (Settings → password page) aur Settings me
apna restaurant name/address/phone daale. Uske baad admin password badal kar
client ko de do.

## Step 5 — Domain + HTTPS (optional, recommend kiya jata hai)

Droplet pe domain point karo, phir:

```bash
sudo cp /opt/restaurant-pos/deploy/nginx-restaurant-pos.conf /etc/nginx/sites-available/restaurant-pos
sudo nano /etc/nginx/sites-available/restaurant-pos    # server_name apna domain daalo
sudo ln -s /etc/nginx/sites-available/restaurant-pos /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo ufw allow 'Nginx Full'
sudo ufw delete allow 5001
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com    # free HTTPS
```

## Backup (zaroori!)

DB ek file hai: `/opt/restaurant-pos/pos.db`. Roz backup ke liye:

```bash
sudo crontab -e
# niche line add karo (raat 3 baje backup + 7 din purane delete)
0 3 * * * cp /opt/restaurant-pos/pos.db /opt/restaurant-pos/backups/pos-$(date +\%F).db && find /opt/restaurant-pos/backups -name '*.db' -mtime +7 -delete
```

Client ka data isi file me hai — iska backup zaroor chalu rakhna.

---

## Trouble

- **502 / page nahi khulti** → `sudo systemctl status restaurant-pos` + `sudo journalctl -u restaurant-pos -n 30`
- **"database is locked"** → service me `--workers 2` ko `--workers 1` kar do (chhoti app ke liye 1 worker bhi kaafi)
- **Port 5001 khulta nahi** → `sudo ufw status` check; Digital Ocean dashboard → Firewall me bhi 5001/TCP allow
- Login bhool gaye → `sudo -u pos sqlite3 /opt/restaurant-pos/pos.db "UPDATE users SET password_hash='x' WHERE id=1"` — asan tariqa: DB delete kar ke `python -c "import wsgi"` dobara chalao (sirf fresh install pe)
