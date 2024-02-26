
# 节流池文件
debounce_commands_pool_file = 'data/debounce_commands_pool.json'

# 读取节流池
def read_debounce_commands_pool():
    with open(debounce_commands_pool_file, 'r') as file:
        return json.load(file)

# 写入节流池
def write_debounce_commands_pool(debounce_commands_pool):
    with open(debounce_commands_pool_file, 'w') as file:
        json.dump(debounce_commands_pool, file)
 
# 添加节流命令
def add_debounce_commands(command, debounce_time):
    debounce_commands_pool = read_debounce_commands_pool()
    debounce_commands_pool.append({
        'command': command,
        'seconds_to_run': debounce_time,
        'time': time.time()
    })
    write_debounce_commands_pool(debounce_commands_pool)
    
