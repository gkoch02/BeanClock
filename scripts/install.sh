#!/usr/bin/env bash
# Idempotent installer for the kidage e-paper appliance.
# Run on a fresh Raspberry Pi OS Lite (Bookworm) as root: sudo bash scripts/install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/opt/kidage"
CONFIG_DIR="/etc/kidage"

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo." >&2
    exit 1
fi

echo "==> Enabling SPI"
if command -v raspi-config >/dev/null; then
    raspi-config nonint do_spi 0
else
    echo "(raspi-config not found; assuming SPI is already enabled)"
fi

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3-venv python3-pip python3-dev \
    libopenjp2-7 libtiff6 libjpeg62-turbo

echo "==> Creating service user"
if ! id kidage >/dev/null 2>&1; then
    useradd --system --home "$INSTALL_DIR" --shell /usr/sbin/nologin \
            --groups spi,gpio kidage
fi

echo "==> Syncing source to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
    "$REPO_DIR"/ "$INSTALL_DIR"/

# Record the source revision so `kidage --version` (and ad-hoc inspection of
# /opt/kidage/VERSION) can answer "what is deployed here?". Must run after
# rsync --delete or it would wipe the file. --dirty surfaces uncommitted
# edits, which is the most likely failure mode of this rsync deploy model
# (someone edits /opt/kidage in place, or installs from a clone with local
# changes). If the source isn't a git checkout, write "unknown" rather than
# failing the install.
echo "==> Recording deployed revision"
if VERSION_STR="$(git -C "$REPO_DIR" describe --always --dirty --tags 2>/dev/null)"; then
    echo "$VERSION_STR" > "$INSTALL_DIR/VERSION"
else
    echo "unknown" > "$INSTALL_DIR/VERSION"
fi

echo "==> Creating virtualenv and installing"
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    python3 -m venv "$INSTALL_DIR/.venv"
fi
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet "$INSTALL_DIR[pi]"

chown -R kidage:kidage "$INSTALL_DIR"

echo "==> Installing config template (preserves existing)"
mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    cp "$REPO_DIR/config.example.toml" "$CONFIG_DIR/config.toml"
    echo "    wrote $CONFIG_DIR/config.toml — edit it before starting the service."
fi
chown -R kidage:kidage "$CONFIG_DIR"

echo "==> Installing systemd units"
install -m 0644 "$REPO_DIR/systemd/kidage.service" /etc/systemd/system/kidage.service
install -m 0644 "$REPO_DIR/systemd/kidage.timer"   /etc/systemd/system/kidage.timer
systemctl daemon-reload
systemctl enable --now kidage.timer

cat <<EOF

Done.

  1. Edit your config:    sudo \$EDITOR $CONFIG_DIR/config.toml
  2. Refresh the panel:   sudo systemctl start kidage.service
  3. Watch the timer:     systemctl list-timers kidage.timer
  4. Tail the logs:       journalctl -u kidage.service -f

EOF
