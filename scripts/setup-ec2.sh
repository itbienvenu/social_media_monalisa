#!/bin/bash
set -e

echo "=== System Update & Prerequisites Installation ==="
sudo apt-get update -y
sudo apt-get install -y curl git rsync jq gnupg lsb-release

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo "=== Installing Docker ==="
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
    
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
      
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

# Make sure docker group exists and user ubuntu is in it
if ! groups ubuntu | grep -q "\bdocker\b"; then
    echo "=== Adding ubuntu user to docker group ==="
    sudo usermod -aG docker ubuntu
    echo "WARNING: Docker group permissions updated. You may need to restart the shell or system if running commands directly."
fi

# Install docker-compose standalone V2 if not already present or alias it
if ! command -v docker-compose &> /dev/null; then
    echo "=== Creating docker-compose alias/link ==="
    # Docker Compose V2 is installed via docker-compose-plugin, so "docker compose" works.
    # We can create a symlink so "docker-compose" works too.
    sudo ln -s /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose || true
fi

# Ensure target deployment directory exists
sudo mkdir -p /home/ubuntu/app
sudo chown -R ubuntu:ubuntu /home/ubuntu/app

echo "=== EC2 Setup Completed successfully! ==="
