#!/usr/bin/env bash
# Idempotent installer for the beanclock e-paper appliance.
# Run on a fresh Raspberry Pi OS Lite (Bookworm) as root: sudo bash scripts/install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/opt/beanclock"
CONFIG_DIR="/etc/beanclock"

if [[ $EUID -ne 0 ]]; then
    echo "Run with sudo." >&2
    exit 1
fi

# Pre-rename installs used "kidage" for the unit, user, and paths. Retire the
# old units and carry config/state over so the device keeps its settings.
if [[ -e /etc/systemd/system/kidage.timer || -d /opt/kidage ]]; then
    echo "==> Migrating from kidage install"
    systemctl disable --now kidage.timer 2>/dev/null || true
    rm -f /etc/systemd/system/kidage.service /etc/systemd/system/kidage.timer
    systemctl daemon-reload
    if [[ -d /etc/kidage && ! -e "$CONFIG_DIR" ]]; then
        mv /etc/kidage "$CONFIG_DIR"
    fi
    if [[ -d /var/lib/kidage && ! -e /var/lib/beanclock ]]; then
        mv /var/lib/kidage /var/lib/beanclock
    fi
    rm -rf /opt/kidage
    userdel kidage 2>/dev/null || true
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
if ! id beanclock >/dev/null 2>&1; then
    # spi/gpio exist on Raspberry Pi OS but not everywhere; only request the
    # ones present so useradd doesn't abort the install on other hosts.
    hw_groups="$(getent group spi gpio 2>/dev/null | cut -d: -f1 | paste -sd, - || true)"
    useradd --system --home "$INSTALL_DIR" --shell /usr/sbin/nologin \
            ${hw_groups:+--groups "$hw_groups"} beanclock
fi

echo "==> Syncing source to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
    "$REPO_DIR"/ "$INSTALL_DIR"/

# Must run after rsync --delete (which would otherwise wipe the file).
echo "==> Recording deployed revision"
VERSION_STR="$(git -C "$REPO_DIR" describe --always --dirty --tags 2>/dev/null || echo unknown)"
echo "$VERSION_STR" > "$INSTALL_DIR/VERSION"

echo "==> Creating virtualenv and installing"
if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
    python3 -m venv "$INSTALL_DIR/.venv"
fi
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet "$INSTALL_DIR[pi]"

chown -R beanclock:beanclock "$INSTALL_DIR"

echo "==> Installing config template (preserves existing)"
mkdir -p "$CONFIG_DIR"
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    cp "$REPO_DIR/config.example.toml" "$CONFIG_DIR/config.toml"
    echo "    wrote $CONFIG_DIR/config.toml — edit it before starting the service."
fi
chown -R beanclock:beanclock "$CONFIG_DIR"

echo "==> Installing systemd units"
install -m 0644 "$REPO_DIR/systemd/beanclock.service" /etc/systemd/system/beanclock.service
install -m 0644 "$REPO_DIR/systemd/beanclock.timer"   /etc/systemd/system/beanclock.timer
systemctl daemon-reload
systemctl enable --now beanclock.timer

cat <<EOF

Done.

  1. Edit your config:    sudo \$EDITOR $CONFIG_DIR/config.toml
  2. Refresh the panel:   sudo systemctl start beanclock.service
  3. Watch the timer:     systemctl list-timers beanclock.timer
  4. Tail the logs:       journalctl -u beanclock.service -f

EOF
