#!/bin/sh

_pwd=$(pwd)

mkdir /tmp/pyang-swagger

wget https://github.com/mbj4668/pyang/archive/pyang-1.7.1.tar.gz -O /tmp/pyang-swagger/pyang.tar.gz
mkdir /tmp/pyang-swagger/pyang
tar -zxf /tmp/pyang-swagger/pyang.tar.gz -C /tmp/pyang-swagger/pyang/ --strip-components=1

#git clone https://github.com/sebymiano/pyang-swagger.git
cp ./pyang-swagger/pyang/plugins/swagger.py /tmp/pyang-swagger/pyang/pyang/plugins/

cd /tmp/pyang-swagger/pyang
python setup.py

cd $_pwd