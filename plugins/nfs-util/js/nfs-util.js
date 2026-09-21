var tableData = []; // 表格数据
var addLayer = null; // 添加弹框
var editLayer = null; // 编辑弹框
var logLayer = null; // 日志弹框
var deployLayer = null; // 部署弹框
var editItem = null; // 编辑项
var checkedIds = []; // 已选择的挂载 ID


function projectPanel() {
	refreshTable();
}

function refreshTable() {
    let firstLoad = $('.nfs-util-panel').length == 0;
	var con = '\
    <div class="divtable nfs-util-panel">\
        <div>\
            <button class="btn btn-default btn-sm va0" onclick="openCreateItem();">添加挂载目录</button>\
            <button class="btn btn-default btn-sm va0" data-nfs-batch style="display:none;" onclick="mountBatch();">批量挂载</button>\
            <button class="btn btn-default btn-sm va0" data-nfs-batch style="display:none;" onclick="unmountBatch();">批量卸载</button>\
            <button class="btn btn-default btn-sm va0" data-nfs-batch style="display:none;" onclick="enableAutostartBatch();">批量开启自动挂载</button>\
            <button class="btn btn-default btn-sm va0" data-nfs-batch style="display:none;" onclick="disableAutostartBatch();">批量取消自动挂载</button>\
            <button class="btn btn-danger btn-sm va0" data-nfs-batch style="display:none;" onclick="deleteBatch();">批量删除</button>\
        </div>\
        <table class="table table-hover" style="margin-top: 10px; max-height: 380px; overflow: auto;">\
            <thead><tr>\
                <th width="30"><input class="check nfs-check-all" onclick="checkSelectAll(this);" type="checkbox"></th>\
                <th>名称</th>\
                <th>NFS服务器</th>\
                <th>挂载路径</th>\
                <th>开机自动挂载</th>\
                <th>状态</th>\
                <th>创建时间</th>\
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
		if (!rdata['status']){
            layer.msg(rdata['msg'],{icon:2,time:2000,shade: [0.3, '#000']});
            return;
        }

        var tbody = '';
        var tmp = rdata['data'];
        tableData = tmp;
        var validIds = tmp.map(function(item) { return String(item.id); });
        checkedIds = checkedIds.filter(function(id) { return validIds.includes(String(id)); });
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

            var checked = checkedIds.includes(String(tmp[i].id)) ? 'checked' : '';
            
            tbody += '<tr>\
                        <td><input value="'+tmp[i].id+'" class="check nfs-row-check" onclick="checkSelect();" '+checked+' type="checkbox"></td>\
                        <td style="width: 180px;">'+tmp[i].name+'</td>\
                        <td style="width: 160px;"><div style=" width:160px; overflow: hidden; text-overflow: ellipsis;" title="'+tmp[i].serverIP+':'+tmp[i].mountServerPath+'">'+tmp[i].serverIP+':'+tmp[i].mountServerPath+'</div></td>\
                        <td style="width: 160px;"><div style=" width:160px; overflow: hidden; text-overflow: ellipsis;" title="'+tmp[i].mountPath+'">'+tmp[i].temMountPath+'</div></td>' +
                        '<td style="width: 220px;">'+autostart+'</td>' +
                        '<td style="width: 100px;">'+status+'</td>' +
                        '<td style="width: 180px;">'+tmp[i].createTime+'</td>' +
                        '<td style="text-align: right;width: 280px;">\
                            '+opt+
                            '<a href="javascript:openEditItem(\''+tmp[i].id+'\')" class="btlink">编辑</a> | ' + 
                            '<a href="javascript:deleteItem(\''+tmp[i].id+'\', \''+tmp[i].name+'\')" class="btlink">删除</a>\
                        </td>\
                    </tr>';
        }
        $(".nfs-util-panel .plugin-table-body").html(tbody);
        syncSelectionState();
	});
}

function getSelectedIds() {
    return $('.nfs-util-panel .plugin-table-body input.nfs-row-check:checked').toArray().map(function(item) {
        return String(item.value);
    });
}

function syncSelectionState() {
    var panel = $('.nfs-util-panel');
    var rowChecks = panel.find('.plugin-table-body input.nfs-row-check');
    var selected = panel.find('.plugin-table-body input.nfs-row-check:checked');
    checkedIds = selected.toArray().map(function(item) { return String(item.value); });

    var allSelected = rowChecks.length > 0 && selected.length === rowChecks.length;
    var selectAll = panel.find('thead input.nfs-check-all');
    selectAll.prop('checked', allSelected);
    selectAll.prop('indeterminate', selected.length > 0 && !allSelected);
    panel.find('button[data-nfs-batch]').toggle(selected.length > 0);
}

function checkSelect() {
    setTimeout(syncSelectionState, 5);
}

function checkSelectAll(checkbox) {
    var panel = $('.nfs-util-panel');
    panel.find('.plugin-table-body input.nfs-row-check').prop('checked', !!checkbox.checked);
    syncSelectionState();
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
                  <input id='mountServerPath' class='bt-input-text' name='mountServerPath' placeholder='请输入共享目录' style='width:458px' onchange='handleMountServerPathChange()' />\
                  <div id='mountServerPathQuickFill' style='width:458px;padding: 5px; white-space: pre-wrap; word-wrap: break-word;'/>\
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

async function openEditItem(id) {
    editItem = tableData.find(item => item.id == id) || {};
    if(editItem.status == 'start' || editItem.autostartStatus == 'start') {
        layer.msg('请先卸载挂载目录并关闭开机自动挂载后再进行编辑', { icon: 2 });
        return;
    }
    editLayer = layer.open({
        type: 1,
        skin: 'demo-class',
        area: '640px',
        title: '编辑挂载目录配置',
        closeBtn: 1,
        shift: 0,
        shadeClose: false,
        content: "\
        <form class='bt-form pd20 pb70' id='editForm'>\
            <div class='line'>\
                <span class='tname'>NFS服务器IP</span>\
                <div class='info-r c4'>\
                    <input id='serverIP' class='bt-input-text' type='text' name='serverIP' placeholder='请输入NFS服务器IP，并点击获取共享目录' value='"+editItem.serverIP+"' style='width: 336px' />\
                    <button type='button' class='btn btn-success btn-sm btn-title' onclick=\"getNfsSharePath()\">点击获取共享目录</button>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>共享目录</span>\
                <div class='info-r c4'>\
                  <input id='mountServerPath' class='bt-input-text' type='text' name='mountServerPath' placeholder='请输入共享目录' style='width:458px' value='"+editItem.mountServerPath+"' onchange='handleMountServerPathChange'/>\
                  <div id='mountServerPathQuickFill' style='width:458px;padding: 5px; white-space: pre-wrap; word-wrap: break-word;'/>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>挂载名称</span>\
                <div class='info-r c4'>\
                    <input id='mountName' class='bt-input-text' type='text' name='name' placeholder='挂载名称' style='width:458px' value='"+editItem.name+"' />\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>挂载路径</span>\
                <div class='info-r c4'>\
                    <input onchange='handlePathChange()' id='mountPath' class='bt-input-text mr5' type='text' name='mountPath' value='"+editItem.mountPath+"'  placeholder='请输入挂载路径' style='width:458px' />\
                    <span class='glyphicon glyphicon-folder-open cursor' onclick='changePath(\"mountPath\")'></span>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>备注</span>\
                <div class='info-r c4'>\
                    <textarea id='mountRemark' class='bt-input-text' name='remark' style='width:458px;height:100px;line-height:22px' value='"+editItem.remark+"' /></textarea>\
                </div>\
            </div>" +
            "<div class='bt-form-submit-btn'>\
                <button type='button' class='btn btn-danger btn-sm btn-title' onclick='layer.close(editLayer)'>取消</button>\
                <button type='button' class='btn btn-success btn-sm btn-title' onclick=\"submitEditItem()\">提交</button>\
            </div>\
        </form>",
    });
    // await getNfsSharePath();
    $('#mountServerPath').val(editItem.mountServerPath);
    $('#mountName').val(editItem.name);
    $('#mountPath').val(editItem.mountPath);
    $('#mountRemark').val(editItem.remark);
}

function submitEditItem(){
    var data = $("#editForm").serialize() + '&id=' + editItem.id;

    requestApi('mount_edit', data, function(data){
    	var rdata = $.parseJSON(data.data);
        if(rdata.status) {
            layer.close(editLayer);
            refreshTable();
        }
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
    });
}

function deleteItem(id, name) {
    safeMessage('确认删除挂载[' + name + ']', '删除[' + name + ']挂载只会在挂载列表移除，不会影响挂载的运行！<span style="color: red">如果需要卸载和取消自启动，请先完成对应操作后再删除！<span>', function(){
        var data = "id="+id;
        requestApi('mount_delete', data, function(data){
        	var rdata = $.parseJSON(data.data);
	        layer.msg(rdata.msg,{icon:rdata.status?1:2});
	        refreshTable();
        });
    });
}

function nfsEscapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function deleteBatch() {
    if (!ensureBatchSelection()) {
        return;
    }

    var selectedSet = new Set(checkedIds.map(String));
    var selectedItems = tableData.filter(function(item) {
        return selectedSet.has(String(item.id));
    });
    var nameList = selectedItems.map(function(item) {
        return '<li>' + nfsEscapeHtml(item.name || item.id) + '</li>';
    }).join('');
    var message = '将从管理列表删除以下 <b>' + checkedIds.length + '</b> 个挂载记录：' +
        '<ul style="max-height:180px;overflow:auto;margin:8px 0 8px 20px;">' + nameList + '</ul>' +
        '<span style="color:red;">该操作不会卸载现有挂载、不会清理自动挂载配置，也不会删除本地目录或远端数据。</span>';

    safeMessage('确认批量删除挂载记录', message, function() {
        requestApi('mount_batch_delete', {ids: checkedIds.join(',')}, function(response) {
            var result = parsePluginResponse(response);
            var data = result.data || {};
            var deleted = (data.deleted || []).map(String);
            var missing = (data.missing || []).map(String);
            var removed = new Set(deleted.concat(missing));
            checkedIds = checkedIds.filter(function(id) { return !removed.has(String(id)); });
            layer.msg(result.msg, {icon: result.status ? 1 : 2});
            refreshTable();
        });
    });
}

async function getNfsSharePath() {
    let serverIP = document.getElementById('serverIP').value;
    let data = await requestApi('get_nfs_share_path', {serverIP});
    let rdata = $.parseJSON(data.data);
    if(rdata.status) {
        let list = rdata.data || [];
        // let options = list.map(item => '<option value="' + item.path + '">' + item.path + '</option>').join('');
        // $('#mountServerPath').html(options);

        let quickFillHtml = '<span style="white-space: nowrap;">快捷填充：</span>' + list.map(item => '<a style="margin-right: 5px; color: #337ab7; cursor: pointer;">' + item.path + '</a>').join('');
        $('#mountServerPathQuickFill').html(quickFillHtml);
        $('#mountServerPathQuickFill a').click(function(){
            $('#mountServerPath').val($(this).text());
            handleMountServerPathChange();
        });
        
        handleMountServerPathChange();
    } else {
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
    }
}

function handleMountServerPathChange() {
    let mountServerPath = document.getElementById('mountServerPath').value;
    let mountName = mountServerPath.split('/').pop();
    document.getElementById('mountName').value = mountName;
    document.getElementById('mountPath').value = "/mnt/" + mountName;
}


async function doMount(id) {
    var response = await requestApi('get_mount_script', {id: id});
    var mountScriptData = parsePluginResponse(response);
    if (!mountScriptData.status) {
        layer.msg(mountScriptData.msg,{icon:0,time:2000,shade: [0.3, '#000']});
        return;
    }
    await execScriptAndShowLog('正在挂载...', mountScriptData.data);
    refreshTable();
}

async function doUnMount(id) {
    var response = await requestApi('get_unmount_script', {id: id});
    var unMountScriptData = parsePluginResponse(response);
    if (!unMountScriptData.status) {
        layer.msg(unMountScriptData.msg,{icon:0,time:2000,shade: [0.3, '#000']});
        return;
    }
    await execScriptAndShowLog('正在卸载...', unMountScriptData.data);
    refreshTable();
}

function toggleAutostart(id) {
    requestApi('mount_toggle_autostart', {id}, function(data){
		var rdata = parsePluginResponse(data);
        if(rdata.status) {
            layer.close(addLayer);
        }
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
        refreshTable();
    });
}

function ensureBatchSelection() {
    checkedIds = getSelectedIds();
    if (checkedIds.length === 0) {
        layer.msg('请至少选择一个挂载项', {icon: 0});
        return false;
    }
    return true;
}

function confirmBatchAction(title, message, callback) {
    layer.confirm(message, {icon: 3, title: title, btn: ['确认', '取消']}, function(index) {
        layer.close(index);
        callback();
    });
}

async function runMountBatch(action) {
    if (!ensureBatchSelection()) {
        return;
    }
    var response = await requestApi('get_mount_batch_script', {
        ids: checkedIds.join(','),
        action: action
    });
    var result = parsePluginResponse(response);
    if (!result.status) {
        layer.msg(result.msg, {icon: 2});
        return;
    }
    var actionText = action === 'mount' ? '挂载' : '卸载';
    await execScriptAndShowLog('正在批量' + actionText + '...', result.data);
    refreshTable();
}

function mountBatch() {
    runMountBatch('mount');
}

function unmountBatch() {
    if (!ensureBatchSelection()) {
        return;
    }
    var count = checkedIds.length;
    confirmBatchAction('确认批量卸载', '将卸载已选择的 <b>' + count + '</b> 个挂载项，确认继续？', function() {
        runMountBatch('unmount');
    });
}

function autostartResultMessage(result, fallback) {
    var data = result.data || {};
    var changed = (data.changed || []).length;
    var skipped = (data.skipped || []).length;
    var failed = (data.failed || []).length + (data.missing || []).length;
    if (changed || skipped || failed) {
        return '处理完成：变更' + changed + '项，跳过' + skipped + '项，失败' + failed + '项';
    }
    return fallback;
}

function runAutostartBatch(action) {
    requestApi('mount_batch_autostart', {
        ids: checkedIds.join(','),
        action: action
    }, function(response) {
        var result = parsePluginResponse(response);
        layer.msg(autostartResultMessage(result, result.msg), {icon: result.status ? 1 : 2});
        refreshTable();
    });
}

function confirmAutostartBatch(action) {
    if (!ensureBatchSelection()) {
        return;
    }
    var enable = action === 'enable';
    var actionText = enable ? '开启自动挂载' : '取消自动挂载';
    var count = checkedIds.length;
    confirmBatchAction('确认批量' + actionText, '将为已选择的 <b>' + count + '</b> 个挂载项' + actionText + '，确认继续？', function() {
        runAutostartBatch(action);
    });
}

function enableAutostartBatch() {
    confirmAutostartBatch('enable');
}

function disableAutostartBatch() {
    confirmAutostartBatch('disable');
}

function parsePluginResponse(response) {
    var payload = response && response.data;
    if (typeof payload === 'string') {
        try {
            var parsed = $.parseJSON(payload);
            if (parsed && typeof parsed.status !== 'undefined') {
                return parsed;
            }
        } catch (error) {
            return {status: true, msg: 'ok', data: payload};
        }
    }
    if (payload && typeof payload.status !== 'undefined') {
        return payload;
    }
    return {status: !!(response && response.status), msg: (response && response.msg) || '请求失败', data: payload};
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
        
        var argsObj = {};
        if (typeof(args) == 'string'){
            argsObj = query2Obj(args);
        } else if (args) {
            argsObj = args;
        }
        if(argsObj.showLoading != false && argsObj.showLoading != 'false') {
            var loadT = layer.msg('正在获取中...', { icon: 16, time: 0});
        }
        $.post('/plugins/run', {name:'nfs-util', func:method, args:encodeURIComponent(JSON.stringify(argsObj))}, function(data) {
            layer.close(loadT);
            if (!data.status){
                layer.msg(data.msg,{icon:0,time:2000,shade: [0.3, '#000']});
                resolve(data);
                return;
            }
            resolve(data);
            callback && callback(data);
        },'json'); 
    });
}
