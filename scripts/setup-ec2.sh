#!/bin/bash
set -e

echo "=== System Update & Prerequisites Installation ==="
sudo apt-get update -y
sudo apt-get install -y curl git rsync jq gnupg lsb-release

# Detect OS ID and codename from /etc/os-release — always present on
# systemd-based distros, avoids hardcoding 'ubuntu' and removes the
# dependency on lsb_release (which may not be installed at this point).
. /etc/os-release

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo "=== Installing Docker (distro: $ID $VERSION_CODENAME) ==="
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/$ID/gpg" \
        | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$ID $VERSION_CODENAME stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

# Make sure docker group exists and the deploy user is in it
# ${SUDO_USER:-$USER} resolves to the actual login user even when the script is run via sudo
DEPLOY_USER="${SUDO_USER:-$USER}"
if ! groups "$DEPLOY_USER" | grep -q "\bdocker\b"; then
    echo "=== Adding $DEPLOY_USER to docker group ==="
    sudo usermod -aG docker "$DEPLOY_USER"
    echo "WARNING: Docker group permissions updated. You may need to restart the shell or system if running commands directly."
fi

# Install docker-compose standalone V2 if not already present or alias it
if ! command -v docker-compose &> /dev/null; then
    echo "=== Creating docker-compose alias/link ==="
    # Docker Compose V2 is installed via docker-compose-plugin, so "docker compose" works.
    # We can create a symlink so "docker-compose" works too.
    sudo ln -s /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose || true
fi

# Ensure target deployment directory exists and is owned by the deploy user.
# Use getent passwd to resolve the home directory from /etc/passwd — this is
# the authoritative lookup and works correctly even when run via sudo (unlike
# eval/tilde expansion, which may resolve to root's home instead).
DEPLOY_HOME="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
if [ -z "$DEPLOY_HOME" ]; then
    echo "❌ ERROR: Could not resolve home directory for user '$DEPLOY_USER'. Aborting."
    exit 1
fi
APP_DIR="$DEPLOY_HOME/app"
sudo mkdir -p "$APP_DIR"
sudo chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"

echo "=== EC2 Setup Completed successfully! ==="
