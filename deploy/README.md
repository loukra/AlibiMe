# Running the backend on a server

The backend is one API process, one worker and a Postgres database. It can share
a server with other apps, behind nginx, with its own user, folder, port (8010,
loopback only) and domain. What is still
open before going live is in [`DEPLOY-CHECKLIST.md`](DEPLOY-CHECKLIST.md).

| File | Goes to |
|---|---|
| `alibime-api.service`, `alibime-worker.service` | `/etc/systemd/system/` |
| `alibime-backup.service`, `alibime-backup.timer` | `/etc/systemd/system/` |
| `nginx-alibime.conf` | `/etc/nginx/sites-available/alibime`, linked from `sites-enabled/` |
| `alibime.env.example` | `/opt/alibime/backend/.env`, filled in, mode 600 |
| `backup-alibime.sh` | stays in `/opt/alibime/deploy/` |

## First setup

As root, with the API domain's DNS already pointing at the server:

```bash
adduser --system --group --home /opt/alibime alibime
git clone https://github.com/loukra/AlibiMe /opt/alibime
chown -R alibime:alibime /opt/alibime
mkdir -p /opt/alibime/secrets /var/backups/alibime
chown alibime:alibime /opt/alibime/secrets /var/backups/alibime
chmod 700 /opt/alibime/secrets /var/backups/alibime

# Postgres
apt install postgresql
sudo -u postgres createuser alibime
sudo -u postgres createdb -O alibime alibime

# Python
cd /opt/alibime/backend
sudo -u alibime python3.11 -m venv .venv
sudo -u alibime .venv/bin/pip install -e ".[postgres,appstore]"
sudo -u alibime cp ../deploy/alibime.env.example .env && chmod 600 .env
# fill in .env, then:
sudo -u alibime .venv/bin/alembic upgrade head
sudo -u alibime .venv/bin/python -m app.seeds.seed

# Services
cp ../deploy/alibime-*.service ../deploy/alibime-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now alibime-api alibime-worker alibime-backup.timer

# nginx and TLS
cp ../deploy/nginx-alibime.conf /etc/nginx/sites-available/alibime
ln -s /etc/nginx/sites-available/alibime /etc/nginx/sites-enabled/alibime
nginx -t && systemctl reload nginx
certbot --nginx -d <api domain>
```

If the API doesn't come up, `journalctl -u alibime-api -n 50` says why; a
setting that still points at a mock is listed by name.

## Updating

```bash
cd /opt/alibime && sudo -u alibime git pull
cd backend && sudo -u alibime .venv/bin/pip install -e ".[postgres,appstore]"
sudo -u alibime .venv/bin/alembic upgrade head
systemctl restart alibime-api alibime-worker
```
