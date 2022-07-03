#!/bin/bash
PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:~/bin
export PATH

curPath=`pwd`

rootPath=$(dirname "$curPath")
rootPath=$(dirname "$rootPath")
rootPath=$(dirname "$rootPath")
rootPath=$(dirname "$rootPath")
serverPath=$(dirname "$rootPath")


action=$1
version=$2


if [ -f /lib/systemd/system/php${version}.service ];then
	systemctl ${action} php${version}
else
	$serverPath/php/init.d/php${version} ${action}
fi