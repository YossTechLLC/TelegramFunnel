# Virtual Environment Setup for PGP_v1

## Environment Information

### Production VM (pgp-final)
- **Hostname**: `pgp-final`
- **Username**: `kingslavxxx`
- **Path**: `/home/kingslavxxx/TelegramFunnel/NOVEMBER/PGP_v1/`

### Development Environment
- **Username**: `user`
- **Path**: `/home/user/TelegramFunnel/NOVEMBER/PGP_v1/`

---

## Setup Instructions

### On pgp-final VM (Production)

1. **Navigate to the PGP_v1 directory:**
   ```bash
   cd /home/kingslavxxx/TelegramFunnel/NOVEMBER/PGP_v1/
   ```

2. **Run the setup script:**
   ```bash
   ./setup_venv.sh
   ```

3. **Activate the virtual environment:**
   ```bash
   source activate_venv.sh
   # OR
   source .venv/bin/activate
   ```

### On Development Machine

1. **Navigate to the PGP_v1 directory:**
   ```bash
   cd /home/user/TelegramFunnel/NOVEMBER/PGP_v1/
   ```

2. **Run the setup script:**
   ```bash
   ./setup_venv.sh
   ```

3. **Activate the virtual environment:**
   ```bash
   source activate_venv.sh
   # OR
   source .venv/bin/activate
   ```

---

## Virtual Environment Location

The virtual environment is **always created at**:
```
<CURRENT_DIRECTORY>/.venv
```

This means:
- On `pgp-final`: `/home/kingslavxxx/TelegramFunnel/NOVEMBER/PGP_v1/.venv`
- On development: `/home/user/TelegramFunnel/NOVEMBER/PGP_v1/.venv`

---

## Installed Packages

The setup script automatically installs:

### Core Google Cloud & Database
- flask
- google-cloud-secret-manager
- cloud-sql-python-connector
- pg8000
- psycopg2-binary
- python-dotenv
- google-cloud-tasks
- google-cloud-logging

### Additional Common Packages
- sqlalchemy
- flask-cors
- flask-jwt-extended
- python-telegram-bot
- gunicorn
- pydantic
- bcrypt
- redis
- sendgrid
- httpx
- pytz
- nest-asyncio

---

## Quick Commands

### Setup (First Time)
```bash
cd ~/TelegramFunnel/NOVEMBER/PGP_v1/
./setup_venv.sh
```

### Activate
```bash
source ~/TelegramFunnel/NOVEMBER/PGP_v1/activate_venv.sh
```

### Deactivate
```bash
deactivate
```

### Check Python Version
```bash
source .venv/bin/activate
python --version
```

### List Installed Packages
```bash
source .venv/bin/activate
pip list
```

---

## Notes

- The `.venv` directory is **git-ignored** (see `.gitignore`)
- The setup script uses **relative paths** so it works in any environment
- Both `setup_venv.sh` and `activate_venv.sh` are executable scripts
- Python 3.11+ is required

---

## Troubleshooting

### Virtual environment already exists
The setup script will prompt you to recreate or keep the existing venv.

### Permission denied
Make sure the scripts are executable:
```bash
chmod +x setup_venv.sh activate_venv.sh
```

### Python not found
Ensure Python 3.11+ is installed:
```bash
python3 --version
```
