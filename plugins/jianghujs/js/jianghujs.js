var tableData = []; // 表格数据
var addLayer = null; // 添加弹框
var editLayer = null; // 编辑弹框
var logLayer = null; // 日志弹框
var deployLayer = null; // 部署弹框
var editItem = null; // 编辑项
var refreshTableTask = null;
var jianghujsPreheatTaskName = 'JianghuJS管理器项目预备';
var jianghujsLogCleanTaskName = 'JianghuJS管理器日志清理';


function projectPanel() {
	refreshTable();
	startRefreshTableTask();
}

function serviceConfigPanel() {
    clearRefreshTableTask();
    var content = '\
    <div class="safe container-fluid jianghujs-service-config" style="overflow:hidden;">\
        <style>\
            .jianghujs-service-config .card { padding: 18px 20px; }\
            .jianghujs-service-config .jianghujs-task-heading { display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap; }\
            .jianghujs-service-config .jianghujs-task-description { line-height:20px; }\
            .jianghujs-service-config .jianghujs-task-field { display:flex; align-items:center; gap:10px; margin-bottom:14px; flex-wrap:wrap; }\
            .jianghujs-service-config .jianghujs-task-label { min-width:42px; color:#555; }\
            .jianghujs-service-config .jianghujs-task-time { display:flex; align-items:center; gap:6px; }\
            .jianghujs-service-config .jianghujs-task-minute-n { display:flex; align-items:center; gap:6px; }\
            .jianghujs-service-config .jianghujs-task-rules { gap:8px; line-height:32px; }\
            .jianghujs-service-config .jianghujs-task-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }\
            .jianghujs-service-config .jianghujs-task-actions .btn { margin:0; }\
            @media (max-width: 700px) { .jianghujs-service-config .card { padding:15px; } .jianghujs-service-config .jianghujs-task-label { min-width:auto; } }\
        </style>\
        <div class="card mb10" id="jianghujs-preheat-task">\
            <div class="jianghujs-task-heading"><b>项目依赖预备</b><span class="c9 jianghujs-task-description">仅备用机启用；仅处理存在 package-lock.json 的项目，按登记顺序执行 npm ci。</span></div>\
            <div class="jianghujs-task-field jianghujs-task-period">\
                <input type="hidden" name="id" value="">\
                <span class="jianghujs-task-label">周期</span>\
                <select class="bt-input-text" name="period" style="width:100px;">\
                    <option value="day">每天</option>\
                    <option value="minute-n">N分钟</option>\
                </select>\
                <span class="task-day-time jianghujs-task-time"><input class="bt-input-text" type="number" name="hour" min="0" max="23" value="2" style="width:58px;"><span>:</span><input class="bt-input-text" type="number" name="minute" min="0" max="59" value="0" style="width:58px;"></span>\
                <span class="task-minute-n jianghujs-task-minute-n" style="display:none;"><span>每</span><input class="bt-input-text" type="number" name="minute-n" min="1" value="60" style="width:65px;"><span>分钟</span></span>\
            </div>\
            <div class="jianghujs-task-actions">\
                <button class="btn btn-success btn-sm task-create" onclick="saveJianghujsServiceTask(\'preheat\')">创建</button>\
                <button class="btn btn-success btn-sm task-update" style="display:none" onclick="saveJianghujsServiceTask(\'preheat\')">修改</button>\
                <button class="btn btn-danger btn-sm task-delete" style="display:none" onclick="deleteJianghujsServiceTask(\'preheat\')">删除</button>\
            </div>\
        </div>\
        <div class="card" id="jianghujs-log-clean-task">\
            <div class="jianghujs-task-heading"><b>项目日志清理</b><span class="c9 jianghujs-task-description">只清理项目中已开启“自动清理日志”的 logs 目录。</span></div>\
            <div class="jianghujs-task-field jianghujs-task-period">\
                <input type="hidden" name="id" value="">\
                <span class="jianghujs-task-label">周期</span>\
                <select class="bt-input-text" name="period" style="width:100px;">\
                    <option value="day">每天</option>\
                    <option value="minute-n">N分钟</option>\
                </select>\
                <span class="task-day-time jianghujs-task-time"><input class="bt-input-text" type="number" name="hour" min="0" max="23" value="1" style="width:58px;"><span>:</span><input class="bt-input-text" type="number" name="minute" min="0" max="59" value="0" style="width:58px;"></span>\
                <span class="task-minute-n jianghujs-task-minute-n" style="display:none;"><span>每</span><input class="bt-input-text" type="number" name="minute-n" min="1" value="60" style="width:65px;"><span>分钟</span></span>\
            </div>\
            <div class="jianghujs-task-field jianghujs-task-rules">\
                <span class="jianghujs-task-label">保留规则</span>\
                <span><input class="bt-input-text" type="number" name="saveAllDay" min="1" value="3" style="width:58px;"> 天内全部保留，其余只保留</span>\
                <span><input class="bt-input-text" type="number" name="saveOther" min="0" value="1" style="width:58px;"> 份，最长保留</span>\
                <span><input class="bt-input-text" type="number" name="saveMaxDay" min="1" value="30" style="width:58px;"> 天</span>\
            </div>\
            <div class="jianghujs-task-actions">\
                <button class="btn btn-success btn-sm task-create" onclick="saveJianghujsServiceTask(\'log_clean\')">创建</button>\
                <button class="btn btn-success btn-sm task-update" style="display:none" onclick="saveJianghujsServiceTask(\'log_clean\')">修改</button>\
                <button class="btn btn-danger btn-sm task-delete" style="display:none" onclick="deleteJianghujsServiceTask(\'log_clean\')">删除</button>\
                <button class="btn btn-default btn-sm task-migrate" style="display:none" onclick="migrateJianghujsLegacyLogCleanTasks()">迁移旧项目任务</button>\
            </div>\
        </div>\
    </div>';
    $('.soft-man-con').html(content);
    $('.jianghujs-task-period select[name="period"]').off('change.jianghujsTask').on('change.jianghujsTask', function() {
        toggleJianghujsTaskPeriod($(this).closest('.card'));
    });
    loadJianghujsServiceTasks();
}

function toggleJianghujsTaskPeriod(card) {
    var isMinuteN = card.find('select[name="period"]').val() === 'minute-n';
    card.find('.task-day-time').toggle(!isMinuteN);
    card.find('.task-minute-n').toggle(isMinuteN);
}

function fillJianghujsServiceTask(card, task, defaults, legacyTasks) {
    task = task || null;
    card.find('input[name="id"]').val(task ? task.id : '');
    card.find('select[name="period"]').val(task && task.type === 'minute-n' ? 'minute-n' : 'day');
    card.find('input[name="hour"]').val(task && task.where_hour !== '' ? task.where_hour : defaults.hour);
    card.find('input[name="minute"]').val(task && task.where_minute !== '' ? task.where_minute : defaults.minute);
    card.find('input[name="minute-n"]').val(task && task.where1 ? task.where1 : defaults.minuteN);
    if (defaults.logClean) {
        card.find('input[name="saveAllDay"]').val(task && task.saveAllDay !== '' ? task.saveAllDay : 3);
        card.find('input[name="saveOther"]').val(task && task.saveOther !== '' ? task.saveOther : 1);
        card.find('input[name="saveMaxDay"]').val(task && task.saveMaxDay !== '' ? task.saveMaxDay : 30);
    }
    card.find('.task-create').toggle(!task);
    card.find('.task-update,.task-delete').toggle(!!task);
    card.find('.task-migrate').toggle(!!task && defaults.logClean && (legacyTasks || []).length > 0);
    toggleJianghujsTaskPeriod(card);
}

function loadJianghujsServiceTasks() {
    requestApi('get_service_task_config', {showLoading: false}, function(data) {
        var result = $.parseJSON(data.data);
        if (!result.status) {
            layer.msg(result.msg || '读取服务配置失败', {icon: 2});
            return;
        }
        var tasks = result.data || {};
        fillJianghujsServiceTask($('#jianghujs-preheat-task'), tasks.preheat, {hour: 2, minute: 0, minuteN: 60});
        fillJianghujsServiceTask($('#jianghujs-log-clean-task'), tasks.log_clean, {hour: 1, minute: 0, minuteN: 60, logClean: true}, tasks.legacy_log_clean_tasks);
    });
}

function buildJianghujsServiceTask(type) {
    var isLogClean = type === 'log_clean';
    var card = isLogClean ? $('#jianghujs-log-clean-task') : $('#jianghujs-preheat-task');
    var period = card.find('select[name="period"]').val();
    var minuteN = parseInt(card.find('input[name="minute-n"]').val(), 10) || 1;
    var task = {id: card.find('input[name="id"]').val(), name: isLogClean ? jianghujsLogCleanTaskName : jianghujsPreheatTaskName, type: period, week: '', where1: period === 'minute-n' ? minuteN : '', hour: period === 'day' ? card.find('input[name="hour"]').val() : '', minute: period === 'day' ? card.find('input[name="minute"]').val() : '', sType: 'toShell', sName: '', backupTo: 'localhost', backup_to: 'localhost'};
    if (isLogClean) {
        task.saveAllDay = card.find('input[name="saveAllDay"]').val();
        task.saveOther = card.find('input[name="saveOther"]').val();
        task.saveMaxDay = card.find('input[name="saveMaxDay"]').val();
        task.sBody = 'python3 /www/server/jh-panel/plugins/jianghujs/index.py project_log_clean_all \'{"saveAllDay":"' + task.saveAllDay + '","saveOther":"' + task.saveOther + '","saveMaxDay":"' + task.saveMaxDay + '"}\'';
    } else {
        task.sBody = "python3 /www/server/jh-panel/plugins/jianghujs/index.py project_preheat_all '{}'";
    }
    return task;
}

function saveJianghujsServiceTask(type) {
    var task = buildJianghujsServiceTask(type);
    var creating = !task.id;
    addOrUpdateCron(task).then(function(result) {
        layer.msg(result.msg, {icon: result.status ? 1 : 2});
        if (!result.status) return;
        if (creating && type === 'log_clean') {
            migrateJianghujsLegacyLogCleanTasks();
            return;
        }
        loadJianghujsServiceTasks();
    });
}

function migrateJianghujsLegacyLogCleanTasks() {
    requestApi('migrate_legacy_log_clean_tasks', {showLoading: false}, function(data) {
        var migration = $.parseJSON(data.data);
        layer.msg(migration.msg, {icon: migration.status ? 1 : 2});
        loadJianghujsServiceTasks();
    });
}

function deleteJianghujsServiceTask(type) {
    var card = type === 'log_clean' ? $('#jianghujs-log-clean-task') : $('#jianghujs-preheat-task');
    var id = card.find('input[name="id"]').val();
    if (!id) return;
    safeMessage('确认删除', '确定删除该计划任务吗？删除后不会修改项目的日志清理参与状态。', function() {
        delCron({id: id}).then(function(result) {
            layer.msg(result.msg, {icon: result.status ? 1 : 2});
            if (result.status) loadJianghujsServiceTasks();
        });
    });
}

function refreshTable() {
    let firstLoad = $('.jianghujs-panel').length == 0;
	var con = '\
    <div class="divtable jianghujs-panel">\
        <div style="display: flex; justify-content: space-between;">\
            <div>\
                <button class="btn btn-success btn-sm va0" onclick="openDeployItem();">部署项目</button>\
                <button class="btn btn-default btn-sm va0" onclick="openCreateItem();">导入项目</button>\
                <button class="btn btn-default btn-sm va0" batch="false" style="display: none;" onclick="projectStartBatch();">批量启动</button>\
                <button class="btn btn-default btn-sm va0" batch="false" style="display: none;" onclick="projectReloadBatch();">批量重启</button>\
                <button class="btn btn-default btn-sm va0" batch="false" style="display: none;" onclick="projectStopBatch();">批量停止</button>\
                <button class="btn btn-default btn-sm va0" batch="false" style="display: none;" onclick="projectEnableStartBatch();">批量开启自启</button>\
                <button class="btn btn-default btn-sm va0" batch="false" style="display: none;" onclick="projectDisableStartBatch();">批量取消自启</button>\
            </div>\
            <div>\
                <input type="text" id="jianghujsSearchInput" class="search ser-text pull-left" placeholder="请输入关键词" onkeydown="handleSearch()"/>\
            </div>\
        </div>\
        <table class="table table-hover" style="margin-top: 10px; max-height: 380px; overflow: auto;">\
            <thead>\
                <th width="30"><input class="check" onclick="checkSelectAll();" type="checkbox"></th>\
                <th>目录</th>\
                <th>名称</th>' +
                '<th>开机自启</th>' +
                '<th>状态</th>\
                <th style="text-align: right;" width="280">操作</th></tr>\
            </thead>\
            <tbody class="plugin-table-body"></tbody>\
            <tfoot>\
              <span>共 <b class="project-count">0</b> 个项目</span>\
            </tfoot>\
        </table>\
    </div>';
    
    if(firstLoad) {
	    $(".soft-man-con").html(con);
    }

	requestApi('project_list',{showLoading: firstLoad, search: $("#jianghujsSearchInput").val()}, function(data){
		let rdata = $.parseJSON(data.data);
		// console.log(rdata);
		if (!rdata['status']){
            layer.msg(rdata['msg'],{icon:2,time:2000,shade: [0.3, '#000']});
            return;
        }

        var tmp = rdata['data'];
        tableData = tmp;
        renderTableData();
	});
}

// 选中的 id
let checkedIds = []
// 点击选中
function checkSelect() {
    setTimeout(function () {
        var list = $('.plugin-table-body input[type="checkbox"].check:checked');
        checkedIds = list.toArray().map(o => o.value)
        var num = list.length
        // console.log(num);
        if (num == 1) {
            $('button[batch="true"]').hide();
            $('button[batch="false"]').show();
        }else if (num>1){
            $('button[batch="true"]').show();
            $('button[batch="false"]').show();
        }else{
            $('button[batch="true"]').hide();
            $('button[batch="false"]').hide();
        }
    },5)
}
// 点击全选
function checkSelectAll() {
    setTimeout(function () {
        var num = $('thead input[type="checkbox"].check:checked').length;
        if (num > 0) {
            // 全选
            $('.plugin-table-body input[type="checkbox"].check').prop('checked', true);;
        } else {
            // 取消全选
            $('.plugin-table-body input[type="checkbox"].check').prop('checked', false);;
        }
        checkSelect()
    },5)
}

function renderTableData() {
    let tmp = tableData;
    
    let search = $("#jianghujsSearchInput").val();
    if (search) {
        tmp = tableData.filter(x => x.name.indexOf(search) > -1);
    }
    
    var tbody = '';
    for(var i=0;i<tmp.length;i++){
        var opt = '';
        if(!tmp[i].loadingStatus) {
            if(tmp[i].status != 'start'){
                opt += '<a href="javascript:projectScriptExcute(\'start\', \''+tmp[i].id+'\')" class="btlink">启动</a> | ';
            }else{
                opt += '<a href="javascript:projectScriptExcute(\'stop\', \''+tmp[i].id+'\')" class="btlink">停止</a> | ';
                opt += '<a href="javascript:projectScriptExcute(\'reload\', \''+tmp[i].id+'\')" class="btlink">重启</a> | ';
            }
        }

        const path = tmp[i].path.replace('//','')
        tmp[i].path = path
        tmp[i].temPath = '<a class="jhlink" href="javascript:openNewWindowPath(\'' + path + '\')">' + path + '</a>';
        
        var status = '';
        if(tmp[i].loadingStatus) {
            status = '<span style="color:#cecece;">' + tmp[i].loadingStatus + '</span>';
        } else {
            if(tmp[i].status != 'start'){
                status = '<span style="color:rgb(255, 0, 0);" class="glyphicon glyphicon-pause"></span>';
            } else {
                status = '<span style="color:rgb(92, 184, 92)" class="glyphicon glyphicon-play"></span>';
            }
        }
        

        var autostart = '';
        var autostartChecked = tmp[i].autostartStatus == 'start'? 'checked' : '';
        autostart = '<div class="autostart-item">\
            <input class="btswitch btswitch-ios" id="autostart_' + tmp[i].id + '" type="checkbox" ' + autostartChecked + '>\
            <label class="btswitch-btn" for="autostart_' + tmp[i].id + '" onclick="toggleAutostart(\'' + tmp[i].id + '\')"></label></div>';

        var checked = ''
        if (checkedIds.includes(tmp[i]['id'])) {
            checked = 'checked'
        }
        
        tbody += '<tr>\
                    <td><input value="'+tmp[i]['id']+'" class="check" onclick="checkSelect();" ' + checked +' type="checkbox"></td>\
                    <td style="width: 180px;">'+tmp[i].temPath+'</td>\
                    <td style="width: 180px;">'+tmp[i].name+'<span style="display: none">'+tmp[i].echo+'</span>'+'</td>' +
                    '<td style="width: 100px;">'+autostart+'</td>' +
                    '<td style="width: 100px;" id="S' + tmp[i].id + '">' + status + '</td>\
                    <td style="text-align: right;">\
                        <div style="width: 200px; float: right;">\
                            '+opt+
                            '<a href="javascript:projectUpdate(\''+tmp[i].path+'\')" class="btlink">git pull</a> | ' + 
                            // '<a style="display: none;" href="javascript:openProjectLogs(\''+tmp[i].id+'\')" class="btlink">日志</a> | ' + 
                            '<a href="javascript:openEditItem(\''+tmp[i].id+'\')" class="btlink">编辑</a> | ' + 
                            '<a href="javascript:deleteItem(\''+tmp[i].id+'\', \''+tmp[i].name+'\')" class="btlink">删除</a>\
                        </div>\
                    </td>\
                </tr>';
    }
    $(".project-count").text(tmp.length);
    $(".plugin-table-body").html(tbody);
}

function clearRefreshTableTask() {
    if(refreshTableTask != null) {
        clearInterval(refreshTableTask);
        refreshTableTask = null;
    }
}

function startRefreshTableTask() {
    clearRefreshTableTask();
    refreshTableTask = setInterval(function(){
        if($('.jianghujs-panel').length == 0) {
            clearRefreshTableTask();
            return;
        }
        refreshTable();
    }, 5000);
}

function handleSearch() {
    setTimeout(() => {
        renderTableData();
    }, 0)
}

// 绑定关闭事件
$(document).on('jianghujsPluginClose', function(e){
    clearRefreshTableTask();
});

function toggleAutostart(id) {
    requestApi('project_toggle_autostart', {id}, function(data){
    	var rdata = $.parseJSON(data.data);
        if(rdata.status) {
            layer.close(addLayer);
        }
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
        refreshTable();
    });
}

function openCreateItem() {
    addLayer = layer.open({
        type: 1,
        skin: 'demo-class',
        area: '640px',
        title: '添加项目',
        closeBtn: 1,
        shift: 0,
        shadeClose: false,
        content: "\
        <form class='bt-form pd20 pb70' id='addForm'>\
            <div class='line'>\
                <span class='tname'>项目根目录</span>\
                <div class='info-r c4'>\
                    <input onchange='handlePathChange()' id='projectPath' class='bt-input-text mr5' type='text' name='path' value='"+'/www/wwwroot'+"/' placeholder='"+'/www/wwwroot'+"' style='width:458px' />\
                    <span class='glyphicon glyphicon-folder-open cursor' onclick='changePath(\"projectPath\")'></span>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>项目名称</span>\
                <div class='info-r c4'>\
                    <input id='projectName' class='bt-input-text' type='text' name='name' placeholder='项目名称' style='width:458px' />\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>启动脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectStartScript' class='bt-input-text' name='startScript' style='width:458px;height:100px;line-height:22px' /></textarea>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>重启脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectReloadScript' class='bt-input-text' name='reloadScript' style='width:458px;height:100px;line-height:22px' /></textarea>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>停止脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectStopScript' class='bt-input-text' name='stopScript' style='width:458px;height:100px;line-height:22px' /></textarea>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>自启动脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectAutostartScript' class='bt-input-text' name='autostartScript' style='width:458px;height:100px;line-height:22px'/></textarea>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>自动清理日志</span>\
                <div class='info-r c4'>\
                    <div class='clean-switch'>\
                        <input class='btswitch btswitch-ios' name='logClean' id='projectLogClean' type='checkbox' checked>\
                        <label class='btswitch-btn' for='projectLogClean'></label>\
                    </div>\
                </div>\
            </div>\
            <div class='bt-form-submit-btn'>\
                <button type='button' class='btn btn-danger btn-sm btn-title' onclick='layer.close(addLayer)'>取消</button>\
                <button type='button' class='btn btn-success btn-sm btn-title' onclick=\"submitCreateItem()\">提交</button>\
            </div>\
        </form>",
        success: function() {}
    });
}

async function submitCreateItem(){
    // 添加项目
    var form = $("#addForm").serialize();

    let name = $('#projectName').val();
    await checkProjectNameExist(name);

    layer.msg('正在添加,请稍候...',{icon:16,time:0,shade: [0.3, '#000']});
    let data = await requestApi('project_add', form);
    let rdata = $.parseJSON(data.data);
    if(!rdata.status) {
        layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
    }
    layer.close(addLayer);
    refreshTable();
}

async function openEditItem(id) {
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
            </div>\
            <div class='line'>\
                <span class='tname'>自启动脚本</span>\
                <div class='info-r c4'>\
                    <textarea id='projectAutostartScript' class='bt-input-text' name='autostartScript' style='width:458px;height:100px;line-height:22px'/></textarea>\
                </div>\
            </div>\
            <div class='line'>\
                <span class='tname'>自动清理日志</span>\
                <div class='info-r c4'>\
                    <div class='clean-switch'>\
                        <input class='btswitch btswitch-ios' name='logClean' id='projectLogClean' type='checkbox' checked>\
                        <label class='btswitch-btn' for='projectLogClean'></label>\
                    </div>\
                </div>\
            </div>\
            <div class='bt-form-submit-btn'>\
                <button type='button' class='btn btn-danger btn-sm btn-title' onclick='layer.close(editLayer)'>取消</button>\
                <button type='button' class='btn btn-success btn-sm btn-title' onclick=\"submitEditItem()\">提交</button>\
            </div>\
        </form>",
        success: function() {}
    });
    
    $('#projectStartScript').val(editItem.start_script);
    $('#projectReloadScript').val(editItem.reload_script);
    $('#projectStopScript').val(editItem.stop_script);
    $('#projectAutostartScript').val(editItem.autostart_script);
    $('#projectLogClean').prop('checked', !!editItem.log_clean_enabled);
}

async function submitEditItem(){
    let form = $("#editForm").serialize() + '&id=' + editItem.id;

    let data = await requestApi('project_edit', form);
    let rdata = $.parseJSON(data.data);
    if(rdata.status) {
        layer.close(editLayer);
        refreshTable();
    }
    layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
    
}

function deleteItem(id, name) {
    safeMessage('确认删除项目[' + name + ']', '删除[' + name + ']项目只会在管理页面移除项目，不会影响项目的运行', function(){
        var data = "id="+id;
        requestApi('project_delete', data, function(data){
        	var rdata = $.parseJSON(data.data);
	        layer.msg(rdata.msg,{icon:rdata.status?1:2});
	        refreshTable();
        });
    });
}



async function openDeployItem() {
    deployLayer = layer.open({
        type: 1,
        skin: 'demo-class',
        area: '640px',
        title: '部署项目',
        closeBtn: 1,
        shift: 0,
        shadeClose: false,
        content: "\
        <form class='bt-form pd20 pb70' id='deployForm'>\
            <div class='step1'>\
                <div class='line'>\
                    <span class='tname'>项目Git地址</span>\
                    <div class='info-r c4'>\
                        <input oninput='handleGitUrlChange()' id='projectGitUrl' class='bt-input-text' type='text' name='gitUrl' placeholder='项目Git地址' style='width:458px' />\
                    </div>\
                </div>\
                <div class='line'>\
                    <span class='tname'>项目根目录</span>\
                    <div class='info-r c4'>\
                        <input onchange='handlePathChange()' id='projectPath' class='bt-input-text mr5' type='text' name='path' value='"+'/www/wwwroot'+"/' placeholder='"+'/www/wwwroot'+"' style='width:458px' />\
                        <span class='glyphicon glyphicon-folder-open cursor' onclick='changePath(\"projectPath\")'></span>\
                    </div>\
                </div>\
                <div class='line'>\
                    <span class='tname'>项目名称</span>\
                    <div class='info-r c4'>\
                        <input id='projectName' class='bt-input-text' type='text' name='name' placeholder='项目名称' style='width:458px' />\
                    </div>\
                </div>\
                <div class='line'>\
                    <span class='tname'></span>\
                    <div class='info-r c4 flex'>\
                        <input id='isLinkUpload' name='isLinkUpload' type='checkbox' style='margin: 2px; margin-right: 5px;'></input><label for='isLinkUpload' style='font-weight: normal; margin-top: 3px;'>自动链接「项目目录下的upload目录」到「/www/wwwstorage/项目名称/upload/」</label>\
                    </div>\
                </div>\
            </div>\
            <div class='step2' hidden>\
                <div class='line'>\
                    <span class='tname'>部署脚本</span>\
                    <div class='info-r c4'>\
                        <textarea id='projectDeployScript' class='bt-input-text' name='deployScript' style='width:458px;height:100px;line-height:22px' /></textarea>\
                    </div>\
                </div>\
                <div class='line'>\
                    <span class='tname'>启动脚本</span>\
                    <div class='info-r c4'>\
                        <textarea id='projectStartScript' class='bt-input-text' name='startScript' style='width:458px;height:100px;line-height:22px' /></textarea>\
                    </div>\
                </div>\
                <div class='line'>\
                    <span class='tname'>重启脚本</span>\
                    <div class='info-r c4'>\
                        <textarea id='projectReloadScript' class='bt-input-text' name='reloadScript' style='width:458px;height:100px;line-height:22px' /></textarea>\
                    </div>\
                </div>\
                <div class='line'>\
                    <span class='tname'>停止脚本</span>\
                    <div class='info-r c4'>\
                        <textarea id='projectStopScript' class='bt-input-text' name='stopScript' style='width:458px;height:100px;line-height:22px' /></textarea>\
                    </div>\
                </div>\
                <div class='line'>\
                    <span class='tname'>自启动脚本</span>\
                    <div class='info-r c4'>\
                        <textarea id='projectAutostartScript' class='bt-input-text' name='autostartScript' style='width:458px;height:100px;line-height:22px'/></textarea>\
                    </div>\
                </div>\
                <div class='line'>\
                    <span class='tname'>自动清理日志</span>\
                    <div class='info-r c4'>\
                        <div class='clean-switch'>\
                            <input class='btswitch btswitch-ios' name='logClean' id='projectLogClean' type='checkbox' checked>\
                            <label class='btswitch-btn' for='projectLogClean'></label>\
                        </div>\
                    </div>\
                </div>\
            </div>\
            <div class='bt-form-submit-btn'>\
                <button type='button' class='btn btn-danger btn-sm btn-title' onclick='layer.close(deployLayer)'>取消</button>\
                <button type='button' class='step1-btn btn btn-success btn-sm btn-title' onclick=\"submitDeployItemStep1(deployLayer)\">拉取&下一步</button>\
                <button type='button' class='step2-back-btn btn btn-success btn-sm btn-title' onclick=\"deployItemBackStep1()\">上一步</button>\
                <button type='button' class='step2-btn btn btn-success btn-sm btn-title' onclick=\"submitDeployItem()\">部署</button>\
            </div>\
        </form>",
        success: function() {
            $("#deployForm .step2, #deployForm .step2-btn, #deployForm .step2-back-btn").hide();
        }
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

function projectUpdate(path) {
    var data = "path="+path;
    requestApi('project_update', data, function(data){
        var rdata = $.parseJSON(data.data);
        refreshTable();
        layer.msg(rdata.msg,{icon:rdata.status?1:2});
        messageBox({timeout: 300, autoClose: true, toLogAfterComplete: true});
    });
}

function projectStartBatch() {
    var list = $('.plugin-table-body input[type="checkbox"].check:checked');
    checkedIds = list.toArray().map(o => o.value)
    projectScriptExcute('start', checkedIds.join(','))
}

function projectReloadBatch() {
    var list = $('.plugin-table-body input[type="checkbox"].check:checked');
    checkedIds = list.toArray().map(o => o.value)
    projectScriptExcute('reload', checkedIds.join(','))
}

function projectStopBatch() {
    var list = $('.plugin-table-body input[type="checkbox"].check:checked');
    checkedIds = list.toArray().map(o => o.value)
    projectScriptExcute('stop', checkedIds.join(','))
}
function projectStartExcute(action, id) {
    var data = "id="+id+"&action="+action;

    setTimeout(function() {
        refreshTable()
    }, 10)
    requestApi('project_start_excute', data, function(data){
        var rdata = $.parseJSON(data.data);
        refreshTable();
        layer.msg(rdata.msg,{icon:rdata.status?1:2});
        messageBox({timeout: 300, autoClose: true, toLogAfterComplete: true});
    });
}

function projectEnableStartBatch() {
    var list = $('.plugin-table-body input[type="checkbox"].check:checked');
    checkedIds = list.toArray().map(o => o.value)
    projectStartExcute('enable', checkedIds.join(','))
}
function projectDisableStartBatch() {
    var list = $('.plugin-table-body input[type="checkbox"].check:checked');
    checkedIds = list.toArray().map(o => o.value)
    projectStartExcute('disable', checkedIds.join(','))
}

function handleGitUrlChange() {
    let gitUrl = document.getElementById('projectGitUrl').value;
    const regex = /^(?:https?:\/\/|git@)(?:[^@\/]+@)?(?:www\.)?([^:\/\s]+)(?:\/|:)([^\/\s]+)\/([^\/\s]+?)(?:\.git)?$/;
    const matches = gitUrl.match(regex);
    if(!matches) {
        layer.msg('git地址格式不正确',{icon:2, time:2000});
        return;
    }
    let path = '/www/wwwroot/' + matches[3];
    let name = matches[3];
    $('#projectPath').val(path);
    $('#projectName').val(name);
}


async function submitDeployItem() {
    var deployForm = $("#deployForm").serialize();
    let deployScript = $('#projectDeployScript').val();
    let projectPath = $('#projectPath').val();
    await execScriptAndShowLog('正在部署项目...', deployScript);

    let data = await requestApi('project_add', deployForm);
    
    let rdata = $.parseJSON(data.data);
    if(rdata.status) {
        layer.close(deployLayer);
        refreshTable();
        openTimoutLayer('部署完毕，需要打开项目配置目录吗？', () => {
            openNewWindowPath(projectPath + '/config')
        }, { confirmBtn: '打开配置目录', timeout: -1 })
        return
    }
    layer.msg(rdata.msg, { icon: rdata.status ? 1 : 2 });
    
}

async function checkPathExist(path) {
    return new Promise(function(resolve, reject) {
        $.post('/files/check_exist_path',{path},function(rdata){
            if(rdata.data) {
                safeMessage('目录已存在','<a style="color:red;">目录['+path+']已存在，要删除目录重新部署吗？</a>删除后将无法恢复,请谨慎操作。<br/>确认请输入结果:',function(){
                    resolve(true);
                });
            } else {
                resolve(false);
            }
        },'json');
    });
}

async function submitDeployItemStep1(deployLayer) {
    const form = $("#deployForm").serialize() + '&showLoading=false';
    const gitUrl = $("#projectGitUrl").val();
    const path = $("#projectPath").val();
    const name = $("#projectName").val();

    if (!gitUrl) {
        layer.msg('项目Git地址不能为空',{icon:2, time:2000});
        return;
    }
    await checkProjectNameExist(name);
    await checkPathExist(path);

    let addKnownHostsScriptData = await requestApi('get_add_known_hosts_script', { gitUrl: encodeURIComponent(gitUrl) });
    if (addKnownHostsScriptData.data) {
        await execScriptAndShowLog('正在添加git地址到已知主机列表...', addKnownHostsScriptData.data, {logWindowSuccessTimeout: -1});
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    let cloneScriptData = await requestApi('get_clone_script', { gitUrl: encodeURIComponent(gitUrl), path: encodeURIComponent(path) });
    await execScriptAndShowLog('正在拉取代码...', cloneScriptData.data);

    requestApi('get_project_deploy_file', form, function(rdata) {
        defaultDeployScript = `
# 安装依赖
cd ${path}
npm i --loglevel verbose
echo "|- 安装依赖完成✅"
# 复制配置文件
pushd ${path}/config > /dev/null
cp config.prod.example.js config.prod.js
echo "|- 复制配置文件完成✅"
popd > /dev/null`;
        if ($("#isLinkUpload").prop('checked')) {
            defaultDeployScript += `
# 建立upload软链
if [ -d "${path}/upload/" ]; then
    rm -rf ${path}/upload/
    echo "|- 已删除${path}/upload/"
fi
if [ ! -d "/www/wwwstorage/${name}/upload/" ]; then
    mkdir -p /www/wwwstorage/${name}/upload/
    echo "|- 已创建/www/wwwstorage/${name}/upload/"
fi
ln -s /www/wwwstorage/${name}/upload/ upload
echo "|- 建立upload软链完成✅"`
        }

        deployScript = rdata.data || defaultDeployScript;
        $('#projectDeployScript').val(deployScript);
    })
    handlePathChange()
    $("#projectName").val(name);

    $("#deployForm .step1, #deployForm .step1-btn").hide();
    $("#deployForm .step2, #deployForm .step2-btn").show();
    refreshLayerCenter(deployLayer);
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
npm i\n\
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

function checkProjectNameExist(projectName) {
    return new Promise(function(resolve, reject) {
        requestApi('check_project_name_exist', { name: projectName }, function(data){
            var rdata = $.parseJSON(data.data);
            let isExist = rdata.data;
            if(isExist) {
                layer.msg('项目名称已存在',{icon:2, time:2000});
                return;
            }
            resolve();
        });
    });
}


/*** 计划任务相关 start ***/
// 添加或者更新计划任务
function addOrUpdateCron(data) {
	return new Promise((resolve, reject) => {
		let url = data.id? '/crontab/modify_crond' : '/crontab/add'
		$.post(url, { ...data, stype: data.sType, sname: data.sName, sbody: data.sBody },function(rdata){
			resolve(rdata)
		},'json');
	});
}
// 获取计划任务
function getCron(data) {
	return new Promise((resolve, reject) => {
		$.post('/crontab/get', { ...data },function(rdata){
			resolve(rdata)
		},'json');
	});
}
// 删除计划任务
function delCron(data) {
	return new Promise((resolve, reject) => {
        $.post('/crontab/del', { ...data },function(rdata){
            resolve(rdata)
        },'json');
	});
}
/*** 计划任务相关 end ***/




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
        $.post('/plugins/run', {name:'jianghujs', func:method, args:JSON.stringify(argsObj)}, function(data) {
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
