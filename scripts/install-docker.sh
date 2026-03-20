#!/bin/bash
# Install Docker Engine on Ubuntu (WSL2 compatible)
# Usage: sudo bash scripts/install-docker.sh

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo bash $0"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"

echo "=== Installing Docker Engine on Ubuntu ==="

apt-get update
apt-get install -y ca-certificates curl

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

usermod -aG docker "$REAL_USER"
service docker start

echo ""
echo "=== Docker installed successfully ==="
docker --version
echo "User '$REAL_USER' added to docker group."
echo "Open a new terminal (or run 'newgrp docker') to use docker without sudo."
