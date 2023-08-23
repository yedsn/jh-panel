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

# 提示”输入项目所在目录（默认/www/wwwroot/）”
read -p "输入项目所在目录（默认为：/www/wwwroot/）: " project_dir
project_dir=${project_dir:-"/www/wwwroot/"}

# 定义存储迁移信息的json对象（如：migrate_info_project）
migrate_info_project='{"project_list": []}'

# 循环目录下的每个文件夹，获取git地址和所在提交点
for dir in $(ls -d ${project_dir}/*/); do
    pushd ${dir} > /dev/null
    git_url=$(git remote -v | grep "origin" | grep "(push)" | awk '{print $2}')
    git_commit=$(git log -1 --pretty=format:%H)
    project_name=$(basename ${dir})
    project_info=$(jq -n --arg projectName "${project_name}" --arg path "${dir}" --arg gitUrl "${git_url}" --arg gitCommit "${git_commit}" '{projectName: $projectName, path: $path, gitUrl: $gitUrl, gitCommit: $gitCommit}')
    migrate_info_project=$(echo ${migrate_info_project} | jq --argjson project_info "${project_info}" '.project_list += [$project_info]')
    popd > /dev/null
done

# 将每个项目的/config/config.prod.js文件和/upload目录按 目录名称.zip 压缩存到 ${MIGRATE_DIR}/project_files/ 目录下
mkdir -p ${MIGRATE_DIR}/project_files/
for dir in $(ls -d ${project_dir}/*/); do
    pushd ${dir} > /dev/null
    project_name=$(basename ${dir})
    zip -r ${MIGRATE_DIR}/project_files/${project_name}.zip ./config/config.prod.js ./upload
    popd > /dev/null
done

# 在${MIGRATE_DIR}目录生成deploy_project.sh，内容如下：
cat << EOF > ${MIGRATE_DIR}/deploy_project.sh
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

# 提示“输入部署项目目录（默认/www/wwwroot/）”
read -p "请输入部署项目目录（默认/www/wwwroot/）: " deploy_dir
deploy_dir=${deploy_dir:-"/www/wwwroot/"}

# 循环migrate_info_project文件的project_list
while read project_info; do
    project_name=\$(echo \${project_info} | jq -r '.projectName')
    git_url=\$(echo \${project_info} | jq -r '.gitUrl')
    git_commit=\$(echo \${project_info} | jq -r '.gitCommit')
    project_dir=\${deploy_dir}\${project_name}

    # 检查目录是否存在
    if [ -d "\$project_dir" ]; then
        echo "\${project_dir}已存在，跳过"
		continue
    fi

    echo ">>>>>>>>>>>>>>>>>>> Start 部署\${git_url}到\${project_dir}"
    mkdir -p \$project_dir
    pushd \$project_dir > /dev/null
    git clone \${git_url} .
    if [ -f "./project_files/\${project_name}.zip" ]; then
        unzip ./project_files/\${project_name}.zip -d .
    fi
    popd > /dev/null
    echo ">>>>>>>>>>>>>>>>>>> End 部署\${git_url}到\${project_dir}"
done < <(jq -c '.project_list[]' ./migrate_info_project.json)



# 统一安装依赖

jq -c '.project_list[]' ./migrate_info_project.json | while read project_info; do
    project_name=\$(echo \${project_info} | jq -r '.projectName')
    project_dir=\${deploy_dir}\${project_name}

    echo "开始安装依赖：\${project_dir}"
    pushd \$project_dir > /dev/null
    npm i
    popd > /dev/null
done

EOF
chmod +x ${MIGRATE_DIR}/deploy_project.sh

# 把migrate_info_project的内容写入到 ${MIGRATE_DIR}/migrate_info_project.json
echo ${migrate_info_project} > ${MIGRATE_DIR}/migrate_info_project.json
