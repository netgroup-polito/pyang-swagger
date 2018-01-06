#!/bin/bash

_pwd=$(pwd)

#set -x

DIR="$( cd "$( dirname "$0" )" && pwd )"
cd $DIR

GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
GIT_COMMIT_HASH="$(git log -1 --format=%h)"

sudo pip install -r requirements.txt
sudo rm -rf /tmp/pyang-swagger
mkdir /tmp/pyang-swagger

wget https://github.com/mbj4668/pyang/archive/pyang-1.7.2.tar.gz -O /tmp/pyang-swagger/pyang.tar.gz
mkdir /tmp/pyang-swagger/pyang
tar -zxf /tmp/pyang-swagger/pyang.tar.gz -C /tmp/pyang-swagger/pyang/ --strip-components=1

#git clone https://github.com/sebymiano/pyang-swagger.git
cp $(pwd)/pyang/plugins/swagger.py /tmp/pyang-swagger/pyang/pyang/plugins/

cd /tmp/pyang-swagger/pyang
sudo pip install -r requirements.txt
sudo python setup.py install

CONFIG_PATH=$HOME/.config/iovnetctl/
FILE_NAME=pyang-swagger.yaml

DATE=`date '+%Y-%m-%d %H:%M:%S'`

#echo $FILE_CONTENT

mkdir -p $CONFIG_PATH

cat > $CONFIG_PATH$FILE_NAME << EOF
git-info: ${GIT_BRANCH}/${GIT_COMMIT_HASH}
install-date: ${DATE}
EOF

cd $_pwd
