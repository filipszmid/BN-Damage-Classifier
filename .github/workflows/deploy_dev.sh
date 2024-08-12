#!/bin/bash

# Load environment variables
set -a  # automatically export all variables
source .env
set +a

#echo "Installing GlobalProtect VPN..."
#sudo dpkg -i data/global_protect/PanGPLinux-6.2.0-c10/GlobalProtect_focal_deb-6.2.0.1-265.deb

ls -l /opt/paloaltonetworks/globalprotect

chmod +x /opt/paloaltonetworks/globalprotect

GP_PATH=$(find / -type f -name globalprotect 2>/dev/null | head -n 1)

if [ -z "$GP_PATH" ]; then
    echo "GlobalProtect executable not found, exiting."
    exit 1
fi

# Extract the directory from GP_PATH and add to PATH
GP_DIR=$(dirname "$GP_PATH")
export PATH=$PATH:$GP_DIR
echo "GlobalProtect directory added to PATH: $GP_DIR"

"$GP_PATH" help

globalprotect help

echo "Configuring VPN..."
globalprotect connect --portal $VPN_IP_GATEWAY --username $VPN_LOGIN --password "$VPN_PASSWORD"
sleep 3

echo "Checking VPN status..."
globalprotect show --status

#sudo apt-get install sshpass

echo "Establishing SSH connection..."
sshpass -p $DEV_PASSWORD ssh -o StrictHostKeyChecking=no $DEV_LOGIN@$DEV_IP <<EOF
set -euo pipefail
echo "Deleting old dir"
sshpass -p $DEV_PASSWORD sudo rm -rf $REPOSITORY_NAME
git clone $BITBUCKET_GIT_SSH_ORIGIN
cd $REPOSITORY_NAME
echo OPENAI_API_KEY=$OPENAI_API_KEY_BAL >> .env
echo GOOGLE_API_KEY=$GOOGLE_API_KEY >> .env
ls -la
make down
make build
make up
make test-integration
EOF
