#!/bin/bash
# this script is used for deployment app to dev instance
# it can be used from local machine too

set -a
source .env
set +a

apt-get -y install sshpass

sshpass -p $DEV_PASSWORD ssh -o StrictHostKeyChecking=no $DEV_LOGIN@$DEV_PROXY_IP -p 60001<<EOF
set -euo pipefail
echo "Updating repository"
if [ -d "$REPOSITORY_NAME" ]; then
  cd $REPOSITORY_NAME
  git fetch --all
  git reset --hard origin/main
else
  git clone $BITBUCKET_GIT_SSH_ORIGIN
  cd $REPOSITORY_NAME
fi
echo "Setting environment variables"
cat << ENV > .env
OPENAI_API_KEY=$OPENAI_API_KEY_BAL
GOOGLE_API_KEY=$GOOGLE_API_KEY
USER=$USER
PASSWORD=$PASSWORD
ENV
ls -la
make down
make build
# RUN sudo chown fszmid:fszmid /home/fszmid/ml/data/cma/logs/processed_rows/
make up
make venv
sleep 10
make test-integration
EOF
