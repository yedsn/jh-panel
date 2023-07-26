var tableData = []; // 表格数据
var addLayer = null; // 添加弹框
var editLayer = null; // 编辑弹框
var logLayer = null; // 日志弹框
var deployLayer = null; // 部署弹框
var editItem = null; // 编辑项


function projectPanel() {
	refreshTable();
}

function refreshTable() {
    let firstLoad = $('.nfs-util-panel').length == 0;
	var con = '\
    <div class="divtable nfs-util-panel">\
    <button class="btn btn-default btn-sm va0" onclick="openCreateItem();">添加挂载目录</button>\
        <table class="table table-hover" style="margin-top: 10px; max-height: 380px; overflow: auto;">\
            <thead>\
                <th>名称</th>\
                <th>NFS服务器</th>\
                <th>挂载路径</th>\
                <th>开机自动挂载</th>\
                <th>状态</th>\
                <th style="text-align: right;" width="150">操作</th></tr>\
            </thead>\
            <tbody class="plugin-table-body"></tbody>\
        </table>\
    </div>';
    
    if(firstLoad) {
	    $(".soft-man-con").html(con);
    }

	requestApi('mount_list',{showLoading: firstLoad}, function(data){
		let rdata = $.parseJSON(data.data);
		// console.log(rdata);
		if (!rdata['status']){
            layer.msg(rdata['msg'],{icon:2,time:2000,shade: [0.3, '#000']});
            return;
        }

        var tbody = '';
        var tmp = rdata['data'];
        tableData = tmp;
        for(var i=0;i<tmp.length;i++){
            var opt = '';
            if(tmp[i].status != 'start'){
                opt += '<a href="javascript:doMount(\''+tmp[i].id+'\')" class="btlink">挂载</a> | ';
            }else{
                opt += '<a href="javascript:doUnMount(\''+tmp[i].id+'\')" class="btlink">卸载</a> | ';
            }

            const mountPath = tmp[i].mountPath.replace('//','')
            tmp[i].mountPath = mountPath
            tmp[i].temMountPath = '<a class="jhlink" href="javascript:openNewWindowPath(\'' + mountPath + '\')">' + mountPath + '</a>';
            
            var status = '';
            if(tmp[i].status != 'start'){
                status = '<span style="color:rgb(255, 0, 0);" class="glyphicon glyphicon-pause"></span>';
            } else {
                status = '<span style="color:rgb(92, 184, 92)" class="glyphicon glyphicon-play"></span>';
            }
            

            var autostart = '';
            var autostartChecked = tmp[i].autostartStatus == 'start'? 'checked' : '';
            autostart = '<div class="autostart-item">\
                <input class="btswitch btswitch-ios" id="autostart_' + tmp[i].id + '" type="checkbox" ' + autostartChecked + '>\
                <label class="btswitch-btn" for="autostart_' + tmp[i].id + '" onclick="toggleAutostart(\'' + tmp[i].id + '\')"></label></div>';
            
            tbody += '<tr>\
                        <td style="width: 180px;">'+tmp[i].name+'</td>\
                        <td style="width: 180px;">'+tmp[i].serverIp+':'+tmp[i].mountServerPath+'</td>\
                        <td style="width: 180px;">'+tmp[i].temMountPath+'</td>' +
                        '<td style="width: 180px;">'+autostart+'</td>' +
                        '<td style="width: 100px;">'+status+'</td>' +
                        '<td style="text-align: right;width: 280px;">\
                            '+opt+
                            '<a href="javascript:openEditItem(\''+tmp[i].id+'\')" class="btlink">编辑</a> | ' + 
                            '<a href="javascript:deleteItem(\''+tmp[i].id+'\', \''+tmp[i].name+'\')" class="btlink">删除</a>\
                        </td>\
                    </tr>';
        }
        $(".plugin-table-body").html(tbody);
	});
}

function openCreateItem() {
    addLayer = layer.open({
        type: 1,
        skin: 'demo-class',
        area: '640px',
        title: '添加挂载目录配置',
        closeBtn: 1,
        shift: 0,
        shadeClose: false,
        content: "\
        <form class='bt-form pd20 pb70' id='addForm'>\
            <div class='line'>\
                <span class='tname'>NFS服务器IP</span>\
                <div class='info-r c4'>\
                    <input id='serverIP' class='bt-input-text' type='text' name='serverIP' placeholder='请输入NFS服务器IP，并点击获取共享目录' style='width: 336px' />\
                    <button type='button' class='btn btn-success btn-sm btn-title' onclick=\"getNfsSharePath()\">点击获取共享目录</button>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>共享目录</span>\
                <div class='info-r c4'>\
                <select id='mountServerPath' class='bt-input-text c5 mr5' name='mountServerPath' placeholder='请选择共享目录' style='width:458px' onchange='handleMountServerPathChange'>\
                    <option>无数据</option>\
                </select>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>挂载名称</span>\
                <div class='info-r c4'>\
                    <input id='mountName' class='bt-input-text' type='text' name='name' placeholder='挂载名称' style='width:458px' />\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>挂载路径</span>\
                <div class='info-r c4'>\
                    <input onchange='handlePathChange()' id='mountPath' class='bt-input-text mr5' type='text' name='mountPath' value='' placeholder='请输入挂载路径' style='width:458px' />\
                    <span class='glyphicon glyphicon-folder-open cursor' onclick='changePath(\"mountPath\")'></span>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>备注</span>\
                <div class='info-r c4'>\
                    <textarea id='mountRemark' class='bt-input-text' name='remark' style='width:458px;height:100px;line-height:22px'/></textarea>\
                </div>\
            </div>" +
            "<div class='bt-form-submit-btn'>\
                <button type='button' class='btn btn-danger btn-sm btn-title' onclick='layer.close(addLayer)'>取消</button>\
                <button type='button' class='btn btn-success btn-sm btn-title' onclick=\"submitCreateItem()\">提交</button>\
            </div>\
        </form>",
    });
}

function submitCreateItem(){
    var data = $("#addForm").serialize();
    requestApi('mount_add', data, function(data){
    	var rdata = $.parseJSON(data.data);
        if(rdata.status) {
            layer.close(addLayer);
            refreshTable();
        }
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
    });
}

function openEditItem(id) {
    editItem = tableData.find(item => item.id == id) || {};

    editLayer = layer.open({
        type: 1,
        skin: 'demo-class',
        area: '640px',
        title: '编辑项目',
        closeBtn: 1,
        shift: 0,
        shadeClose: false,
        content: "\
        <form class='bt-form pd20 pb70' id='editForm'>\
            <div class='line'>\
                <span class='tname'>项目根目录</span>\
                <div class='info-r c4'>\
                    <input onchange='handlePathChange()' id='projectPath' class='bt-input-text mr5' type='text' name='path' value='"+editItem.path+"' placeholder='"+editItem.path+"' style='width:458px' />\
                    <span class='glyphicon glyphicon-folder-open cursor' onclick='changePath(\"projectPath\")'></span>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>项目名称</span>\
                <div class='info-r c4'>\
                    <input id='projectName' class='bt-input-text' type='text' name='name' placeholder='项目名称' style='width:458px' value='" + editItem.name + "'/>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>启动脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectStartScript' class='bt-input-text' name='startScript' style='width:458px;height:100px;line-height:22px'/></textarea>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>重启脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectReloadScript' class='bt-input-text' name='reloadScript' style='width:458px;height:100px;line-height:22px'/></textarea>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>停止脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectStopScript' class='bt-input-text' name='stopScript' style='width:458px;height:100px;line-height:22px'/></textarea>\
                </div>\
            </div>" +  
            "<div class='line'>\
                <span class='tname'>自启动脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectAutostartScript' class='bt-input-text' name='autostartScript' style='width:458px;height:100px;line-height:22px'/></textarea>\
                </div>\
            </div>" +
            "<div class='bt-form-submit-btn'>\
                <button type='button' class='btn btn-danger btn-sm btn-title' onclick='layer.close(editLayer)'>取消</button>\
                <button type='button' class='btn btn-success btn-sm btn-title' onclick=\"submitEditItem()\">提交</button>\
            </div>\
        </form>",
    });
    
    $('#projectStartScript').val(editItem.start_script);
    $('#projectReloadScript').val(editItem.reload_script);
    $('#projectStopScript').val(editItem.stop_script);
    $('#projectAutostartScript').val(editItem.autostart_script);
}

function submitEditItem(){
    var data = $("#editForm").serialize() + '&id=' + editItem.id;

    requestApi('project_edit', data, function(data){
    	var rdata = $.parseJSON(data.data);
        if(rdata.status) {
            layer.close(editLayer);
            refreshTable();
        }
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
    });
}

function deleteItem(id, name) {
    safeMessage('确认删除挂载[' + name + ']', '删除[' + name + ']挂载只会在挂载列表移除，不会挂载的运行', function(){
        var data = "id="+id;
        requestApi('mount_delete', data, function(data){
        	var rdata = $.parseJSON(data.data);
	        layer.msg(rdata.msg,{icon:rdata.status?1:2});
	        refreshTable();
        });
    });
}

function getNfsSharePath() {
    let serverIP = document.getElementById('serverIP').value;
    requestApi('get_nfs_share_path', {serverIP}, function(data){
        let rdata = $.parseJSON(data.data);
        if(rdata.status) {
            let list = rdata.data || [];
            let options = list.map(item => '<option value="' + item.path + '">' + item.path + '</option>').join('');
            $('#mountServerPath').html(options);
            handleMountServerPathChange();
        } else {
            layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
        }
    });
    
}

function handleMountServerPathChange() {
    let mountServerPath = document.getElementById('mountServerPath').value;
    document.getElementById('mountName').value = mountServerPath.split('/').pop();;
    document.getElementById('mountPath').value = mountServerPath;
}


async function doMount(id) {
    var mountScriptData = await requestApi('get_mount_script', "id="+id);
    if (!mountScriptData.status){
        layer.msg(mountScriptData.msg,{icon:0,time:2000,shade: [0.3, '#000']});
        return;
    }
    await execScriptAndShowLog('正在挂载...', mountScriptData.data);
    refreshTable();
}

async function doUnMount(id) {
    var unMountScriptData = await requestApi('get_unmount_script', "id="+id);
    if (!unMountScriptData.status){
        layer.msg(unMountScriptData.msg,{icon:0,time:2000,shade: [0.3, '#000']});
        return;
    }
    await execScriptAndShowLog('正在卸载...', unMountScriptData.data);
    refreshTable();
}

function toggleAutostart(id) {
    requestApi('mount_toggle_autostart', {id}, function(data){
    	var rdata = $.parseJSON(data.data);
        if(rdata.status) {
            layer.close(addLayer);
        }
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
        refreshTable();
    });
}

function projectScriptExcute(scriptKey, id) {
    var data = "id="+id+"&scriptKey="+scriptKey;

    if (scriptKey === 'stop') {
        var status = '<span style="color:rgb(255, 0, 0);" class="glyphicon glyphicon-pause"></span>';
        $("#S" + id).html(status);
    }

    setTimeout(function() {
        refreshTable()
    }, 10)
    requestApi('project_script_excute', data, function(data){
        var rdata = $.parseJSON(data.data);
        refreshTable();
        layer.msg(rdata.msg,{icon:rdata.status?1:2});
        messageBox({timeout: 300, autoClose: true, toLogAfterComplete: true});
    });
}

function projectStart(path) {
    var data = "path="+path;
    requestApi('project_start', data, function(data){
        var rdata = $.parseJSON(data.data);
        layer.msg(rdata.msg,{icon:rdata.status?1:2});
        refreshTable();
    });
}

function projectStop(path) {
    var data = "path="+path;
    requestApi('project_stop', data, function(data){
        var rdata = $.parseJSON(data.data);
        layer.msg(rdata.msg,{icon:rdata.status?1:2});
        refreshTable();
    });
}

function projectUpdate(path) {
    var data = "path="+path;
    requestApi('project_update', data, function(data){
        var rdata = $.parseJSON(data.data);
        refreshTable();
        layer.msg(rdata.msg,{icon:rdata.status?1:2});
        messageBox({timeout: 300, autoClose: true, toLogAfterComplete: true});
    });
}

function handlePathChange() {
    let path = document.getElementById('projectPath').value;
    let name = (path || '').split('/').pop();
    let startScript = 'cd ' + path + '\nnpm i --loglevel verbose\nnpm start';
    let reloadScript = 'cd ' + path + '\nnpm stop\nnpm start';
    let stopScript = 'cd ' + path + '\nnpm stop';
    let autostartScript = '\
#! /bin/bash\n\
### BEGIN INIT INFO\n\
# Provides: OnceDoc\n\
# Required-Start: $network $remote_fs $local_fs\n\
# Required-Stop: $network $remote_fs $local_fs\n\
# Default-Start: 2 3 4 5\n\
# Default-Stop: 0 1 6\n\
# Short-Description: start and stop node\n\
# Description: OnceDoc\n\
### END INIT INFO\n\
if [ -e "/www/server/nodejs/fnm" ];then\n\
  export PATH="/www/server/nodejs/fnm:$PATH"\n\
  eval "$(fnm env --use-on-cd --shell bash)"\n\
fi\n\
if ! command -v npm > /dev/null;then\n\
  echo "No npm"\n\
  exit 1\n\
fi\n\
WEB_DIR=' + path + '\n\
cd $WEB_DIR\n\
npm start\n\
    ';
    $('#projectName').val(name);
    $('#projectStartScript').val(startScript);
    $('#projectReloadScript').val(reloadScript);
    $('#projectStopScript').val(stopScript);
    $('#projectAutostartScript').val(autostartScript);
}

function deployItemBackStep1() {
    $("#deployForm .step1, #deployForm .step1-btn").show();
    $("#deployForm .step2, #deployForm .step2-btn, #deployForm .step2-back-btn").show();
}

function openProjectLogs(id){
	layer.msg('正在获取,请稍候...',{icon:16,time:0,shade: [0.3, '#000']});
	var data='&id='+id;
    requestApi('project_logs', data, function(data){
        var rdata = $.parseJSON(data.data);
        if(!rdata.status) {
			layer.msg(rdata.msg,{icon:2, time:2000});
			return;
		};
		logLayer = layer.open({
			type:1,
			title:lan.crontab.task_log_title,
			area: ['60%','500px'], 
			shadeClose:false,
			closeBtn:1,
			content:'<div class="setchmod bt-form pd20 pb70">'
				+'<pre id="project-log" style="overflow: auto; border: 0px none; line-height:23px;padding: 15px; margin: 0px; white-space: pre-wrap; height: 405px; background-color: rgb(51,51,51);color:#f1f1f1;border-radius:0px;font-family:"></pre>'
				+'<div class="bt-form-submit-btn" style="margin-top: 0px;">'
				+'<button type="button" class="btn btn-success btn-sm" onclick="projectLogsClear('+id+')">清空</button>'
				+'<button type="button" class="btn btn-danger btn-sm" onclick="layer.close(logLayer)">关闭</button>'
			    +'</div>'
			+'</div>'
		});

		setTimeout(function(){
			$("#project-log").html(rdata.msg);
		},200);
    });
}

function projectLogsClear(id) {
    var data = "id="+id;
    requestApi('project_logs_clear', data, function(data){
        var rdata = $.parseJSON(data.data);
        layer.msg(rdata.msg,{icon:rdata.status?1:2});
        layer.close(logLayer);
    });
}


function query2Obj(str){
    var data = {};
    kv = str.split('&');
    for(i in kv){
        v = kv[i].split('=');
        data[v[0]] = v[1];
    }
    return data;
}

async function requestApi(method,args,callback){
    return new Promise(function(resolve, reject) {
        
        var argsObj = null;
        if (typeof(args) == 'string'){
            argsObj = query2Obj(args);
        } else {
            argsObj = args;
        }
        if(argsObj.showLoading != false && argsObj.showLoading != 'false') {
            var loadT = layer.msg('正在获取中...', { icon: 16, time: 0});
        }
        $.post('/plugins/run', {name:'nfs-util', func:method, args:JSON.stringify(argsObj)}, function(data) {
            layer.close(loadT);
            if (!data.status){
                layer.msg(data.msg,{icon:0,time:2000,shade: [0.3, '#000']});
                return;
            }
            resolve(data);
            callback && callback(data);
        },'json'); 
    });
}