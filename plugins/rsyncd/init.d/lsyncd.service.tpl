[Unit]
Description=Lightweight inotify based sync daemon
ConditionPathExists={$SERVER_PATH}/rsyncd/lsyncd.conf

[Service]
Type=simple
ExecStart={$LSYNCD_BIN} -nodaemon -logfile {$SERVER_PATH}/rsyncd/logs/lsyncd.log {$SERVER_PATH}/rsyncd/lsyncd.conf

[Install]
WantedBy=multi-user.target
