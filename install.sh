#!/bin/bash

_pwd=$(pwd)

#set -x

DIR="$( cd "$( dirname "$0" )" && pwd )"
cd $DIR

GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
GIT_COMMIT_HASH="$(git log -1 --format=%h)"

if pyang -v | grep -q '1.7.3'; then
  	echo "Pyang version 1.7.3 is already installed"
  	sudo cp $(pwd)/pyang/plugins/swagger.py /usr/local/lib/python2.7/dist-packages/pyang-1.7.3-py2.7.egg/pyang/plugins/swagger.py
else
	sudo pip install -r requirements.txt
	sudo rm -rf /tmp/pyang-swagger
	mkdir /tmp/pyang-swagger

	wget https://github.com/mbj4668/pyang/archive/pyang-1.7.3.tar.gz -O /tmp/pyang-swagger/pyang.tar.gz
	mkdir /tmp/pyang-swagger/pyang
	tar -zxf /tmp/pyang-swagger/pyang.tar.gz -C /tmp/pyang-swagger/pyang/ --strip-components=1

	#git clone https://github.com/sebymiano/pyang-swagger.git
	cp $(pwd)/pyang/plugins/swagger.py /tmp/pyang-swagger/pyang/pyang/plugins/

	cd /tmp/pyang-swagger/pyang
	sudo pip install -r requirements.txt
	sudo python setup.py install
fi

CONFIG_PATH=$HOME/.config/iovnet/
FILE_NAME=pyang-swagger.yaml

DATE=`date '+%Y-%m-%d %H:%M:%S'`

#echo $FILE_CONTENT

mkdir -p $CONFIG_PATH

cat > $CONFIG_PATH$FILE_NAME << EOF
git-info: ${GIT_BRANCH}/${GIT_COMMIT_HASH}
install-date: ${DATE}
EOF

echo "PYANG-SWAGGER installed successfully"

cd $_pwd
