import os
import sys

# === 配置部分 ===
TARGET_APP_FILE = 'app.py'  # 后端文件名
DB_FILENAME = 'Sample.accdb' # 你的数据库文件名

def update_db_path():
    # 1. 获取当前工作目录
    current_dir = os.getcwd()
    db_full_path = os.path.join(current_dir, DB_FILENAME)

    # 2. 检查数据库是否存在
    if not os.path.exists(db_full_path):
        print(f"[错误] 找不到数据库文件: {DB_FILENAME}")
        print(f"请确保数据库文件就在当前文件夹下: {current_dir}")
        return False

    # 3. 检查 app.py 是否存在
    if not os.path.exists(TARGET_APP_FILE):
        print(f"[错误] 找不到后端文件: {TARGET_APP_FILE}")
        return False

    print(f"[检测] 数据库路径锁定为: {db_full_path}")

    # 4. 读取 app.py 并替换路径
    try:
        with open(TARGET_APP_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        modified = False
        
        for line in lines:
            # 寻找定义 DB_PATH 的那一行 (忽略空格)
            if line.strip().startswith("DB_PATH ="):
                # 替换为新的绝对路径，注意转义反斜杠
                new_line = f"DB_PATH = r'{db_full_path}' \n"
                new_lines.append(new_line)
                modified = True
                print("[更新] 已自动修改 app.py 中的数据库路径。")
            else:
                new_lines.append(line)

        if not modified:
            print("[警告] 在 app.py 中没找到 'DB_PATH =' 这一行，请检查代码。")
            return False

        # 5. 写回 app.py
        with open(TARGET_APP_FILE, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
            
        return True

    except Exception as e:
        print(f"[异常] 修改文件失败: {e}")
        return False

if __name__ == "__main__":
    if update_db_path():
        print("[成功] 系统配置就绪。")
        sys.exit(0) # 成功退出码
    else:
        sys.exit(1) # 失败退出码