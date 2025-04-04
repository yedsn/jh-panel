#!/bin/bash

# 检查/usr/bin/jq是否存在
if ! [ -x "/usr/bin/jq" ]; then
    echo "/usr/bin/jq不存在，正在尝试自动安装..."
    apt-get update
    apt-get install jq -y
    hash -r
    if ! [ -x "/usr/bin/jq" ]; then
        echo "安装jq失败，请手动安装后再运行脚本。"
        exit 1
    fi
fi

# 从环境变量中获取MIGRATE_DIR值
MIGRATE_DIR=${MIGRATE_DIR:-"/www/migrate/"}

# 从环境变量中获取PROJECT_DIR值
project_dir=${PROJECT_DIR:-""}
if [ -z "$project_dir" ]; then
    default_project_dir="/www/wwwroot/"
    if [ -d "/appdata/wwwroot/" ]; then
        default_project_dir="/appdata/wwwroot/"
    fi
    read -p "输入项目所在目录（默认为：${default_project_dir}）: " project_dir
    project_dir=${project_dir:-${default_project_dir}}
fi

# 定义存储迁移信息的json对象（如：migrate_info_plugin）
migrate_info_plugin='{"project_dir": "'${project_dir}'"}'

# 创建${MIGRATE_DIR}/plugin_files目录
mkdir -p ${MIGRATE_DIR}/plugin_files/

if [ -d "/www/server/jianghujs" ]; then
    # 打包/www/server/jianghujs目录下的data和script目录到${MIGRATE_DIR}/jianghujs.zip
    pushd /www/server/jianghujs/ > /dev/null
    zip -r ${MIGRATE_DIR}/plugin_files/jianghujs.zip .
    popd > /dev/null
fi

if [ -d "/www/server/docker" ]; then
    # 打包/www/server/docker目录下的data和script目录到${MIGRATE_DIR}/docker.zip
    pushd /www/server/docker/ > /dev/null
    zip -r ${MIGRATE_DIR}/plugin_files/docker.zip .
    popd > /dev/null
fi

# 在${MIGRATE_DIR}生成deploy_plugin.sh
cat << EOF > ${MIGRATE_DIR}/deploy_plugin.sh
#!/bin/bash

read -p "恢复后原插件数据将丢失，确定要这样做吗？（默认y）[y/n]: " confirm
confirm=\${confirm:-"y"}

if [ "\$confirm" != "y" ]; then
    echo "操作已取消"
    exit 1
fi

# 从环境变量中获取DEPLOY_DIR值
DEPLOY_DIR=\${DEPLOY_DIR:-"/www/wwwroot/"}



if [ -d "/www/server/jianghujs" ]; then
    if [ -f "./plugin_files/jianghujs.zip" ]; then
        # 删除/www/server/jianghujs目录
        rm -rf /www/server/jianghujs

        # 解压./plugin_files/jianghujs.zip到/www/server/jianghujs
        unzip -o ./plugin_files/jianghujs.zip -d /www/server/jianghujs
        
        # 在/www/server/jianghujs/目录下执行以下脚本替换项目目录
        pushd /www/server/jianghujs/ > /dev/null
        find . -type f -print0 | while read -d \$'\0' file
        do
        echo "正在替换\${file}"
        sed -i "s#${project_dir}#\${DEPLOY_DIR}#g" "\$file"
        done
        popd > /dev/null
    fi


fi


if [ -d "/www/server/docker" ]; then
    if [ -f "./plugin_files/docker.zip" ]; then
        # 删除/www/server/docker目录
        rm -rf /www/server/docker

        # 解压./plugin_files/docker.zip到/www/server/docker
        unzip -o ./plugin_files/docker.zip -d /www/server/docker

            
        # 在/www/server/docker/目录下执行以下脚本替换项目目录
        pushd /www/server/docker/ > /dev/null
        find . -type f -print0 | while read -d \$'\0' file
        do
        echo "正在替换\${file}"
        sed -i "s#${project_dir}#\${DEPLOY_DIR}#g" "\$file"
        done
        popd > /dev/null
    fi
fi


EOF
chmod +x ${MIGRATE_DIR}/deploy_plugin.sh

# 将migrate_info_plugin的内容写入到 ${MIGRATE_DIR}/migrate_info_plugin.json
echo ${migrate_info_plugin} > ${MIGRATE_DIR}/migrate_info_plugin.json
