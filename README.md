# SSM-DB-Tunnel Setup

A macOS menu-bar app that manages AWS SSM port-forwarding tunnels to MySQL / RDS databases. Click the menu-bar icon, select your endpoints, and connect your local DB client — no terminal required.

---

## How It Works

```
Your Mac  ──SSM tunnel──▶  EC2 Bastion  ──▶  RDS MySQL
localhost:13301                              db-1.rds.amazonaws.com:3306
localhost:13302                              db-2.rds.amazonaws.com:3306
```

The app binds a local port for each RDS endpoint you configure. Your MySQL client connects to `127.0.0.1:<port>` as if the database were local — no VPN needed.

---

## Features

- **One-click tunnels** — start and stop SSM port-forwarding sessions from a browser UI
- **Menu-bar native** — lives quietly in your macOS menu bar via `rumps`
- **Keep-alive** — sends a heartbeat to MySQL every 50 s to prevent idle-connection drops
- **Sleep / wake aware** — automatically resumes tunnels after the Mac wakes from sleep
- **Endpoint manager** — add, edit, and remove RDS hostnames and local port assignments
- **Credential storage** — DB credentials saved locally in `~/Library/Application Support/SsmDbTunnel/`
- **Rotating logs** — up to 5 × 1 MB log files in `~/Library/Logs/SsmDbTunnel/`

---

## Prerequisites

These must be installed on your Mac **before** launching the app. They are **not** bundled in the `.app` (~15 MB DMG).

### 1. Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. AWS CLI

```bash
brew install awscli
```

Verify: `aws --version`

### 3. AWS SSM Session Manager Plugin

This is a **separate** package from the AWS CLI and is required for port-forwarding:

```bash
brew install session-manager-plugin
```

Verify: `session-manager-plugin --version`

### 4. AWS Credentials

Configure an AWS profile with SSM access to the target EC2 bastion and RDS instances:

```bash
aws configure --profile ssm
```

You will be prompted for:

| Prompt | Value |
|---|---|
| AWS Access Key ID | Your key ID |
| AWS Secret Access Key | Your secret key |
| Default region | e.g. `ap-southeast-2` |
| Output format | `json` (or leave blank) |

The profile name `ssm` is the app default. You can change it in the DB Credentials panel.

---

## Installation (from DMG)

1. Double-click `SsmDbTunnel.dmg` to mount it
2. Drag `SsmDbTunnel.app` into `/Applications`
3. Eject the DMG

### First Launch — Bypass Gatekeeper

The app is ad-hoc signed (not notarised with an Apple Developer ID), so macOS will block it on the first open. Do this **once**:

**Option A — Right-click method (easiest)**
1. In Finder, right-click `SsmDbTunnel.app` → **Open**
2. Click **Open** in the security dialog

**Option B — System Settings**
1. Attempt to open normally — it will be blocked
2. Go to **System Settings → Privacy & Security** → click **Open Anyway**

**Option C — Terminal**
```bash
sudo xattr -d com.apple.quarantine /Applications/SsmDbTunnel.app
```

After the first successful open, macOS remembers the exception permanently.

---

## Usage

1. Launch `SsmDbTunnel.app` — a **🗄** icon appears in the menu bar (top-right of screen)
2. Click the icon → the control panel opens in your browser
3. Open **DB Credentials** in the sidebar → enter your details → **Save**:
   - **AWS Profile** — the profile configured in step 4 above (default: `ssm`)
   - **DB User** — your MySQL username
   - **DB Password** — your MySQL password
   - **Database** — default database name
4. Under **Manage Endpoints** → add your RDS hostnames and remote port (`3306`)
5. In **Select Endpoints** → tick the endpoints you want → click **Start Selected**
6. Connect your MySQL client to the local tunnel:

| Field | Value |
|---|---|
| Host | `127.0.0.1` |
| Port | shown in Active Connections (e.g. `13301`) |
| User | your DB username |
| Password | your DB password |
| Database | your database name |

7. Use **Stop All** or stop individual sessions from the Active Connections panel

---

## Configuration

### Environment variables / `.env`

Place a `.env` file at `~/Library/Application Support/SsmDbTunnel/.env` to override defaults:

| Variable | Default | Description |
|---|---|---|
| `SSM_TARGET` | `i-0a47b5db6775690ff` | EC2 bastion instance ID used as the SSM target |
| `SSM_PROFILE` | `ssm` | AWS CLI profile name |

Example:
```env
SSM_TARGET=i-0123456789abcdef0
SSM_PROFILE=my-aws-profile
```

Restart the app after saving.

### Port assignment

The app assigns local forwarding ports starting at `13301`, incrementing per endpoint. These are visible and editable in the **Manage Endpoints** table.

---

## App Data Locations

| Path | Contents |
|---|---|
| `~/Library/Application Support/SsmDbTunnel/hostname_port_map.json` | Endpoint list (hostnames + local ports) |
| `~/Library/Application Support/SsmDbTunnel/db_credentials.json` | Saved DB credentials |
| `~/Library/Application Support/SsmDbTunnel/.env` | Optional config overrides |
| `~/Library/Logs/SsmDbTunnel/app.log` | Application log (rotated, up to 5 × 1 MB) |

---

## Compatibility

| | |
|---|---|
| Apple Silicon (M1 / M2 / M3 / M4) | Supported |
| Intel Mac | Supported |
| Minimum macOS | Monterey 12.0+ recommended |
| Python (bundled) | Not required on recipient's machine |

---

## Troubleshooting

**App doesn't appear in the menu bar**
Check the log for startup errors:
```bash
cat ~/Library/Logs/SsmDbTunnel/app.log
```

**"AWS CLI not found" error**
```bash
brew install awscli
which aws   # should return a path
```

**"session-manager-plugin not found"**
```bash
brew install session-manager-plugin
```

**Gatekeeper blocks the app on every launch**
```bash
sudo xattr -d com.apple.quarantine /Applications/SsmDbTunnel.app
```

**Tunnel starts but MySQL connection is refused**
- Confirm the local port in Active Connections matches what your client uses
- Check that the RDS security group allows inbound connections from the bastion EC2 instance on port `3306`

**Tunnel drops after a few minutes of inactivity**
- The keep-alive runs every 50 s and should prevent this
- If it still drops, check your AWS Session Manager idle timeout setting in the console

---

## Building from Source

> For developers only — end users should use the DMG.

### Requirements

- macOS (Intel or Apple Silicon)
- Python 3.9+
- AWS CLI + SSM Session Manager Plugin (runtime)

### Steps

```bash
# 1. Enter the project directory
cd SsmDbTunnel

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements-dev.txt

# 4. Run from source (dev mode)
python launcher.py

# 5. Build the .app + optional DMG
bash build_macos.sh
# Enter Y when prompted to also create the DMG
```

The build script will:
- Run PyInstaller to produce `dist/SsmDbTunnel.app`
- Ad-hoc sign the bundle with `codesign`
- Optionally wrap it in `dist/SsmDbTunnel.dmg`

---

## Tech Stack

| Component | Library / Tool |
|---|---|
| Menu bar | `rumps` 0.4.0 |
| Web UI server | `Flask` 3.0.0 |
| MySQL driver | `PyMySQL` 1.1.2 |
| Config loading | `python-dotenv` 1.0.0 |
| Input sanitisation | `bleach` 6.1.0 |
| App packaging | `PyInstaller` ≥ 6.0 |
| Tunnelling | AWS CLI + SSM Session Manager Plugin |

---

## Author

**Abhiram** — internal tooling for streamlined local DB access via AWS SSM.
