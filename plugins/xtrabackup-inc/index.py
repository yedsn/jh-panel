# coding:utf-8

import sys
import io
import os
import time
import re
from urllib.parse import unquote

sys.path.append(os.getcwd() + "/class/core")
import mw

app_debug = False
if mw.isAppleSystem():
    app_debug = True

def getPluginName():
    return 'xtrabackup-inc'  

def getPluginDir():
    return mw.getPluginDir() + '/' + getPluginName()

def getServerDir():
    return mw.getServerDir() + '/' + getPluginName()

def runLog():
    return getServerDir() + '/xtrabackup.log'  

def initdInstall():
    updateCurrentMysqlPswInScript()
    return 'ok'

# 更新脚本中的配置
def updateScriptConfig(config):
    port = config.get('port', None)
    user = config.get('user', None)
    password = config.get('password', None)
    port_rep = '--port\s*=\s*(.*?) '
    user_rep = '--user\s*=\s*(.*?) '
    password_rep = '--password\s*=\s*(.*?) '
    # 更新全量备份脚本
    full_script_file = getFullScriptFile()
    full_script_content = mw.readFile(full_script_file)
    if port is not None:
        full_script_content = re.sub(port_rep, '--port=' + port + ' ', full_script_content)
    if user is not None:
        full_script_content = re.sub(user_rep, '--user=' + user + ' ', full_script_content)
    if password is not None:
        full_script_content = re.sub(password_rep, '--password=' + password + ' ', full_script_content)

    mw.writeFile(full_script_file, full_script_content)

    # 更新增量备份脚本
    inc_script_file = getIncScriptFile()
    inc_script_content = mw.readFile(inc_script_file)
    password_rep = '--password\s*=\s*(.*?) '
    if port is not None:
        inc_script_content = re.sub(port_rep, '--port=' + port + ' ', inc_script_content)
    if user is not None:
        inc_script_content = re.sub(user_rep, '--user=' + user + ' ', inc_script_content)
    if password is not None:
        inc_script_content = re.sub(password_rep, '--password=' + password + ' ', inc_script_content)
    mw.writeFile(inc_script_file, inc_script_content)

def updateCurrentMysqlPswInScript():
    try:
        mysqlConn = mw.M('config').dbPos(mw.getServerDir() + '/mysql-apt', 'mysql')
        password = mysqlConn.where(
            'id=?', (1,)).getField('mysql_root')
        updateScriptConfig({
            "password": password
        })
    except Exception as e:
        return str(e)

def status():
    return 'start'

def getArgs():
    args = sys.argv[2:]
    tmp = {}
    args_len = len(args)

    if args_len == 1:
        t = args[0].strip('{').strip('}')
        t = t.split(':')
        tmp[t[0]] = t[1]
    elif args_len > 1:
        for i in range(len(args)):
            t = args[i].split(':')
            tmp[t[0]] = t[1]

    return tmp

def checkArgs(data, ck=[]):
    for i in range(len(ck)):
        if not ck[i] in data:
            return (False, mw.returnJson(False, '参数:(' + ck[i] + ')没有!'))
    return (True, mw.returnJson(True, 'ok'))


def getConf():
    path = getServerDir() + "/xtrabackup.sh"
    return path

def getFullScriptFile():
    path = getServerDir() + "/xtrabackup-full.sh"
    return path

def getIncScriptFile():
    path = getServerDir() + "/xtrabackup-inc.sh"
    return path

def getSetting():
    file = getFullScriptFile()
    content = mw.readFile(file)
    port_rep = '--port\s*=\s*(.*?) '
    port_tmp = re.search(port_rep, content).groups()[0].strip()
    user_rep = '--user\s*=\s*(.*?) '
    user_tmp = re.search(user_rep, content).groups()[0].strip()
    password_rep = '--password\s*=\s*(.*?) '
    password_tmp = re.search(password_rep, content).groups()[0].strip()
    return mw.returnJson(True, 'ok', {
        'port': port_tmp,
        'user': user_tmp,
        'password': password_tmp
    })

def changeSetting():
    args = getArgs()
    data = checkArgs(args, ['password'])
    if not data[0]:
        return data[1]

    updateScriptConfig(args)
    return mw.returnJson(True, '编辑成功!')

def testSetting():
    args = getArgs()
    data = checkArgs(args, ['port', 'user', 'password'])
    if not data[0]:
        return data[1]

    port = args['port']
    user = args['user']
    password = args['password']
    db = mw.getMyORM()
    db.setPort(port)
    # db.setSocket(getSocketFile())
    db.setPwd(password)
    mysqlMsg = str(db.query('show databases'))
    if mysqlMsg != None:
        if "1045" in mysqlMsg:
            return mw.returnJson(False, '连接错误!')
    return mw.returnJson(True, '连接成功!')

def getBaseBackupPathConf():
    return getServerDir() + '/base-backup-path.conf'

def getBaseBackupPath():
    path = mw.readFile(getBaseBackupPathConf())
    if(path == False):
        path = '/www/backup/xtrabackup_data_base'
    else:
        path = path.strip()
    return path

def getIncBackupPathConf():
    return getServerDir() + '/inc-backup-path.conf'

def getIncBackupPath():
    path = mw.readFile(getIncBackupPathConf())
    if(path == False):
        path = '/www/backup/xtrabackup_data_incremental'
    else:
        path = path.strip()
    return path

def doMysqlBackup():
    args = getArgs()
    content = mw.readFile(getConf())

    if args['content'] is not None:
        content = unquote(str(args['content']), 'utf-8').replace("\\n", "\n")

    # 写入临时文件用于执行
    tempFilePath = getServerDir() + '/xtrabackup_temp.sh'
    mw.writeFile(tempFilePath, '%(content)s\nrm -f %(tempFilePath)s' % {'content': content, 'tempFilePath': tempFilePath})
    mw.execShell('chmod 750 ' + tempFilePath)
    # 执行脚本
    log_file = runLog()
    mw.execShell('echo $(date "+%Y-%m-%d %H:%M:%S") "备份开始" >> ' + log_file)
    
    # sync the backup path to the backup script
    # mw.execShell("BACKUP_PATH=%(backupPath)s sh %(tempFilePath)s >> %(logFile)s" % {'backupPath':getBackupPath(), 'tempFilePath': tempFilePath, 'logFile': log_file })
    mw.addAndTriggerTask(
        name = '执行Xtrabackup命令[备份]',
        execstr = 'sh %(tempFilePath)s >> %(logFile)s' % {'tempFilePath': tempFilePath, 'logFile': log_file }
    )
    
    execResult = mw.execShell("tail -n 1 " + log_file)
    
    # if "备份成功" in execResult[0]:
    #     return mw.returnJson(True, execResult[0])

    # Tip: 兼容 老版本的 xtrabackup.sh; 未来可以删除
    if os.path.exists(os.path.join(getBackupPath(), 'mysql')):
        return mw.returnJson(True, '备份成功')    
        
    return mw.returnJson(True, execResult[0])


def backupList():
    result = []
    xtrabackup_data_history_path = '/www/backup/xtrabackup_data_history'
    for d_walk in os.walk(xtrabackup_data_history_path):
        for d_list in d_walk[2]:
            if mw.getFileSuffix(d_list) == 'zip': 
                filepath = '%s/%s' % (xtrabackup_data_history_path, d_list)
                result.append({
                    'filename': d_list,
                    'size': mw.getPathSize(filepath),
                    'sizeTxt': mw.toSize(mw.getPathSize(filepath)),
                    'createTime': os.path.getctime(filepath)
                })
    return mw.returnJson(True, 'ok', result)

def getRecoveryBackupScript():
    args = getArgs()
    data = checkArgs(args, ['filename'])
    if not data[0]:
        return data[1]
    filename = args['filename']

    # 获取的mysql目录
    mysqlDir = ''
    if os.path.exists('/www/server/mysql-apt'):
        mysqlDir = '/www/server/mysql-apt/data'
    elif os.path.exists('/www/server/mysql'):
        mysqlDir = '/www/server/mysql/data'
    else :
        return mw.returnJson(False, '未检测到安装的mysql插件!')

    recoveryScript = '#!/bin/bash\n'
    recoveryScript += ('timestamp=$(date +%Y%m%d_%H%M%S)\n')
    recoveryScript += ('LOG_DIR=/www/server/xtrabackup/logs\n')
    if os.path.exists('/www/server/mysql-apt'):
        recoveryScript += ('systemctl stop mysql-apt\n')
    elif os.path.exists('/www/server/mysql'):
        recoveryScript += ('systemctl stop mysql\n')

    recoveryScript += ('mv %s %s_%s\n' % (mysqlDir, mysqlDir, time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))))
    recoveryScript += ('rm -rf /www/backup/xtrabackup_data_restore\n')
    recoveryScript += ('mkdir -p /www/server/xtrabackup/logs\n')
    recoveryScript += ('unzip -d /www/backup/xtrabackup_data_restore /www/backup/xtrabackup_data_history/%s\n' % (filename))
    recoveryScript += ('xtrabackup --prepare --target-dir=/www/backup/xtrabackup_data_restore &>> $LOG_DIR/recovery_$timestamp.log\n')
    recoveryScript += ('xtrabackup --copy-back --target-dir=/www/backup/xtrabackup_data_restore &>> $LOG_DIR/recovery_$timestamp.log\n')
    recoveryScript += ('chown -R mysql:mysql %s \n' % (mysqlDir))
    recoveryScript += ('chmod -R 755 ' + mysqlDir + '\n')
    if os.path.exists('/www/server/mysql-apt'):
        recoveryScript += ('systemctl start mysql-apt\n')
    elif os.path.exists('/www/server/mysql'):
        recoveryScript += ('systemctl start mysql\n')
    recoveryScript += ('python3 /www/server/jh-panel/scripts/clean.py $LOG_DIR\n')
    return mw.returnJson(True, 'ok', recoveryScript)

def doRecoveryBackup():
    args = getArgs()
    content = mw.readFile(getConf())

    if args['content'] is not None:
        content = unquote(str(args['content']), 'utf-8').replace("\\n", "\n")

    # 写入临时文件用于执行
    tempFilePath = getServerDir() + '/recovery_temp.sh'
    mw.writeFile(tempFilePath, '%(content)s\nrm -f %(tempFilePath)s\necho 恢复成功' % {'content': content, 'tempFilePath': tempFilePath})
    mw.execShell('chmod 750 ' + tempFilePath)
    # 执行脚本
    log_file = runLog()
    mw.execShell('echo $(date "+%Y-%m-%d %H:%M:%S") "恢复开始" >> ' + log_file)
    
    # mw.execShell("sh %(tempFilePath)s >> %(logFile)s" % {'tempFilePath': tempFilePath, 'logFile': log_file })
    mw.addAndTriggerTask(
        name = '执行Xtrabackup命令[恢复]',
        execstr = "sh %(tempFilePath)s >> %(logFile)s" % {'tempFilePath': tempFilePath, 'logFile': log_file }
    )
    
    execResult = mw.execShell("tail -n 1 " + log_file)
    
    # if "恢复成功" in execResult[0]:
    #     return mw.returnJson(True, '恢复成功; 请前往Mysql插件 <br/>- "从服务器获取"  <br/>- 如果ROOT密码有变动👉"修复ROOT密码" <br/>Tip: 若无法找回密码, 可以使用无密码模式启动mysql, 然后再使用mysql的sql脚本设置密码。')
    
    return mw.returnJson(True, execResult[0])

def doDeleteBackup():
    args = getArgs()
    data = checkArgs(args, ['filename'])
    if not data[0]:
        return data[1]
    filename = args['filename']
    mw.execShell('rm -f /www/backup/xtrabackup_data_history/' + filename)
    return mw.returnJson(True, '删除成功!')


def getXtrabackupCron():
    args = getArgs()
    data = checkArgs(args, ['xtrabackupCronName'])
    if not data[0]:
        return data[1]
    xtrabackupCronName = args['xtrabackupCronName']
    cronCount = mw.M('crontab').where('name=?', (xtrabackupCronName,)).count()
    cronList = mw.M('crontab').where('name=?', (xtrabackupCronName,)).field('id,name,type,where_hour,where_minute,saveAllDay,saveOther,saveMaxDay').select()
    if cronCount > 0:
        return mw.returnJson(True,  xtrabackupCronName + ' 已存在', { 
            'id': cronList[0]['id'],
            'name': cronList[0]['name'],
            'type': cronList[0]['type'],
            'hour': cronList[0]['where_hour'],
            'minute': cronList[0]['where_minute'],
            'saveAllDay': cronList[0]['saveAllDay'],
            'saveOther': cronList[0]['saveOther'],
            'saveMaxDay': cronList[0]['saveMaxDay']
        })
    return mw.returnJson(False, xtrabackupCronName + ' 不存在')    


def getBackupPath():
    return mw.returnJson(True, 'ok',  {
        "base": getBaseBackupPath(),
        "inc": getIncBackupPath()
    })

def setBackupPath():
    args = getArgs()
    data = checkArgs(args, ['base', 'inc'])
    if not data[0]:
        return data[1]

    base = args['base']
    inc = args['inc']
    mw.writeFile(getBaseBackupPathConf(), base)
    mw.writeFile(getIncBackupPathConf(), inc)
    return mw.returnJson(True, '修改成功!')

def getFullBackupScript():
    backupScript = 'echo "正在备份..." \nBACKUP_BASE_PATH=%(baseBackupPath)s\nBACKUP_INC_PATH=%(incBackupPath)s\nset -x\n %(script)s' % {'baseBackupPath':getBaseBackupPath(), 'incBackupPath':getIncBackupPath(), 'script': mw.readFile(getFullScriptFile()) } 
    return mw.returnJson(True, 'ok',  backupScript)

def getIncBackupScript():
    backupScript = 'echo "正在备份..." \nBACKUP_BASE_PATH=%(baseBackupPath)s\nBACKUP_INC_PATH=%(incBackupPath)s\nset -x\n %(script)s' % {'baseBackupPath':getBaseBackupPath(), 'incBackupPath':getIncBackupPath(), 'script': mw.readFile(getIncScriptFile()) } 
    return mw.returnJson(True, 'ok',  backupScript)

def getFullBackupCronScript():
    # cron中直接执行脚本文件
    backupCronScript = 'echo "正在备份..." \nBACKUP_BASE_PATH=%(baseBackupPath)s\nBACKUP_INC_PATH=%(incBackupPath)s\nset -x\n bash %(scriptFile)s' % {'baseBackupPath':getBaseBackupPath(), 'incBackupPath':getIncBackupPath(), 'scriptFile': getFullScriptFile() } 
    return mw.returnJson(True, 'ok',  backupCronScript)

if __name__ == "__main__":
    func = sys.argv[1]
    if func == 'status':
        print(status())
    elif func == 'run_log':
        print(runLog())
    elif func == 'initd_install':
        print(initdInstall())
    elif func == 'conf':
        print(getConf()) 
    elif func == 'get_backup_path':
        print(getBackupPath())
    elif func == 'set_backup_path':
        print(setBackupPath())
    elif func == 'full_backup_script':
        print(getFullBackupScript())
    elif func == 'full_backup_cron_script':
        print(getFullBackupCronScript())
    elif func == 'inc_backup_script':
        print(getIncBackupScript())
    elif func == 'get_xtrabackup_cron':
        print(getXtrabackupCron())
    elif func == 'get_setting':
        print(getSetting())     
    elif func == 'change_setting':
        print(changeSetting())   
    elif func == 'test_setting':
        print(testSetting())     
    elif func == 'do_mysql_backup':
        print(doMysqlBackup())
    elif func == 'backup_list':
        print(backupList())
    elif func == 'get_recovery_backup_script':
        print(getRecoveryBackupScript())
    elif func == 'do_recovery_backup':
        print(doRecoveryBackup())
    elif func == 'do_delete_backup':
        print(doDeleteBackup())
    else:
        print('error')
