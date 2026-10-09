# Server setup (IONOS VPS, Ubuntu 24.04)

One-time setup of the production host. No secrets in this file.

## 1. Access and updates (as root)
    ssh-copy-id root@SERVER_IP
    ssh root@SERVER_IP
    apt update && apt upgrade -y

## 2. Docker
    curl -fsSL https://get.docker.com | sh

## 3. Non-root deploy user (key-only)
    adduser --disabled-password --gecos "" deploy
    usermod -aG docker deploy
    mkdir -p /home/deploy/.ssh
    cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
    chown -R deploy:deploy /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys

## 4. Firewall (only 22, 80, 443)
    ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp
    ufw --force enable

## 5. Disable password login
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
    systemctl restart ssh

## 6. Run f1-mcp (as deploy)
    git clone https://github.com/JuanEliasLaraSoto/f1-mcp.git && cd f1-mcp
    echo "DOMAIN=SERVER-IP-WITH-DASHES.sslip.io" > .env
    docker compose up -d --build
    curl https://SERVER-IP-WITH-DASHES.sslip.io/health
