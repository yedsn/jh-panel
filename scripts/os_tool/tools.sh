
# 下载并执行脚本的函数
download_and_run() {
    local script_name=$1
    if [ "$USE_PANEL_SCRIPT" == "true" ]; then 
      # echo "|- 正在运行  $SCRIPT_BASE/${script_name}..."
      bash $SCRIPT_BASE/${script_name} ${@:2}
    else
      # echo "|- 正在下载并运行  ${URLBase}/${script_name}..."
      wget -nv -O /tmp/vm_${script_name} ${URLBase}/${script_name}
      bash /tmp/vm_${script_name} ${@:2}
    fi    
}

download_and_run_node() {
    local script_name=$1
    local script_path=""
    if [ "$USE_PANEL_SCRIPT" == "true" ]; then 
      pushd $SCRIPT_BASE > /dev/null
      script_path=$SCRIPT_BASE/${script_name}
    else
      wget -nv -O /tmp/package.json ${URLBase}/package.json
      pushd /tmp/ > /dev/null
      script_path=/tmp/vm_${script_name}
      wget -nv -O $script_path ${URLBase}/${script_name}
    fi    
    
    # echo "|- 正在运行  $script_path..."
    source /root/.bashrc

    # 检查依赖是否安装
    package_json_current_checksum=$(md5sum "package.json" | awk '{print $1}')
    package_json_old_checksum=""
    if [ -f "package.json.checksum" ]; then
      package_json_old_checksum=$(cat "package.json.checksum")
    fi

    if [ ! -d "node_modules" ] || [ "$package_json_current_checksum" != "$package_json_old_checksum" ]; then
      echo "正在运行 npm install..."
      npm install
      echo $package_json_current_checksum > "package.json.checksum"
    else
      echo "跳过 npm install。"
    fi

    node ${script_path} ${@:2}
    popd > /dev/null
}