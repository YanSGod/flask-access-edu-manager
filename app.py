import pyodbc
import datetime
import csv
import io
import os
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================= 数据库配置 (相对路径) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = r'C:\Users\YanSGod\YanSGod\.git\Sample.accdb' 
# print(f"正在连接数据库: {DB_PATH}") 

CONN_STR = (r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};' f'DBQ={DB_PATH};')

def get_db_connection():
    try:
        return pyodbc.connect(CONN_STR)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

# ================= 🛠️ 工具函数 =================
def safe_date_str(val, fmt='%Y-%m-%d'):
    if not val: return ""
    try:
        if isinstance(val, (datetime.datetime, datetime.date)):
            return val.strftime(fmt)
        s = str(val)
        return s[:10] if fmt == '%Y-%m-%d' else s[:16]
    except: return ""

# ================= 1. 基础接口 =================

@app.route('/api/login', methods=['POST'])
def login():
    d = request.json
    conn = get_db_connection()
    if not conn: return jsonify({"status":"error", "message":"数据库连接失败"}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 密码, 角色, 姓名 FROM [T-Account] WHERE 用户ID = ?", (d['userID'],))
        row = cursor.fetchone()
        if row and str(row[0]) == str(d['password']) and row[1] == d['role']:
            return jsonify({"status":"success", "name":row[2], "role":row[1], "id":d['userID']})
        return jsonify({"status":"error", "message":"账号或密码错误"}), 401
    except Exception as e:
        return jsonify({"status":"error", "message":str(e)}), 500
    finally: conn.close()

@app.route('/api/change_password', methods=['POST'])
def change_password():
    d = request.json
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT 密码 FROM [T-Account] WHERE 用户ID=?", (d['userID'],))
        row = cursor.fetchone()
        if not row: return jsonify({"status":"error", "message":"用户不存在"})
        if str(row[0]) != str(d['oldPwd']): return jsonify({"status":"error", "message":"旧密码错误"})
        
        cursor.execute("UPDATE [T-Account] SET 密码=? WHERE 用户ID=?", (d['newPwd'], d['userID']))
        conn.commit()
        return jsonify({"status":"success", "message":"密码修改成功，请重新登录"})
    except Exception as e: return jsonify({"status":"error", "message":str(e)})
    finally: conn.close()

@app.route('/api/teacher/courses', methods=['GET'])
def get_teacher_courses():
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT 课程ID, 课程名称, 班级ID FROM [T-Course] WHERE 教师ID = ?", (request.args.get('teacherID'),))
        return jsonify([{"id":r[0], "name":r[1], "class_id":r[2]} for r in cursor.fetchall()])
    except: return jsonify([])
    finally: conn.close()

@app.route('/api/class/students', methods=['GET'])
def get_class_students():
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT 学生ID, 姓名 FROM [T-Student] WHERE 班级ID = ?", (request.args.get('classID'),))
        return jsonify([{"id":r[0], "name":r[1]} for r in cursor.fetchall()])
    except: return jsonify([])
    finally: conn.close()

@app.route('/api/course/exams', methods=['GET'])
def get_course_exams():
    course_id = request.args.get('courseID')
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT 考试名称, 满分 FROM [T-Score] WHERE 课程ID=?", (course_id,))
        exams = [{"name": r[0], "full": r[1] if r[1] else 100} for r in cursor.fetchall()]
        return jsonify(exams)
    except: return jsonify([])
    finally: conn.close()

@app.route('/api/teacher/dashboard_stats', methods=['GET'])
def get_teacher_stats():
    tid = request.args.get('teacherID')
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM [T-Communication] WHERE 教师ID=? AND 状态=1", (tid,))
        unread_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT TOP 20 s.考试名称, s.学生ID, s.分数, c.课程名称, s.满分, s.考试日期
            FROM [T-Score] s, [T-Course] c 
            WHERE s.课程ID = c.课程ID AND c.教师ID = ? 
            ORDER BY s.考试日期 DESC
        """, (tid,))
        
        warning_list = []
        rows = cursor.fetchall()
        for r in rows:
            exam, sid, score, course_name, full, date = r
            full_score = full if (full and full > 0) else 100
            if score < full_score * 0.6:
                s_name = "未知学生"
                try:
                    cursor.execute("SELECT 姓名 FROM [T-Student] WHERE 学生ID=?", (str(sid),))
                    s_res = cursor.fetchone()
                    if s_res: s_name = s_res[0]
                except: pass

                if len(warning_list) < 10: 
                    warning_list.append({
                        "exam": exam, "student": s_name, 
                        "score": f"{score}/{full_score}", "course": course_name
                    })
        return jsonify({"status": "success", "unread_msgs": unread_count, "warnings": warning_list})
    except Exception as e: 
        return jsonify({"status": "error", "message": str(e), "warnings": []})
    finally: conn.close()

# ================= 2. 数据查询接口 =================

@app.route('/api/homework', methods=['GET'])
def get_homework():
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        sql = "SELECT h.作业ID, c.课程名称, h.作业内容, h.布置日期, h.截止日期 FROM [T-Homework] h, [T-Course] c WHERE h.课程ID=c.课程ID AND c.教师ID=?"
        params = [request.args.get('teacherID')]
        if request.args.get('courseID'): sql += " AND h.课程ID=?"; params.append(request.args.get('courseID'))
        cursor.execute(sql + " ORDER BY h.布置日期 DESC", tuple(params))
        res = []
        for row in cursor.fetchall():
            res.append({
                "作业ID": row[0], "课程名称": row[1], "作业内容": row[2],
                "布置日期": safe_date_str(row[3]),
                "截止日期": safe_date_str(row[4])
            })
        return jsonify(res)
    except: return jsonify([])
    finally: conn.close()

@app.route('/api/course/attendance', methods=['GET'])
def get_course_attendance():
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT 出勤ID, 学生ID, 日期, 状态 FROM [T-Attendance] WHERE 课程ID=? ORDER BY 日期 DESC", (request.args.get('courseID'),))
        rows = cursor.fetchall()
        res = []
        for r in rows:
            att_id, sid, date_val, status = r
            s_name = "未知"
            try:
                cursor.execute("SELECT 姓名 FROM [T-Student] WHERE 学生ID=?", (str(sid),))
                s_row = cursor.fetchone()
                if s_row: s_name = s_row[0]
            except: pass
            res.append({"date":safe_date_str(date_val), "name":s_name, "status":status, "id":att_id})
        return jsonify(res)
    except: return jsonify([])
    finally: conn.close()

@app.route('/api/course/scores', methods=['GET'])
def get_course_scores():
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT 成绩ID, 学生ID, 考试名称, 分数, 考试日期, 满分 FROM [T-Score] WHERE 课程ID=? ORDER BY 考试日期 DESC", (request.args.get('courseID'),))
        rows = cursor.fetchall()
        res = []
        for r in rows:
            sc_id, sid, exam, score, date_val, full = r
            s_name = "未知"
            try:
                cursor.execute("SELECT 姓名 FROM [T-Student] WHERE 学生ID=?", (str(sid),))
                s_row = cursor.fetchone()
                if s_row: s_name = s_row[0]
            except: pass

            res.append({
                "exam":exam, "name":s_name, "score":score, "id":sc_id, 
                "date": safe_date_str(date_val), 
                "full": full if full else 100
            })
        return jsonify(res)
    finally: conn.close()

# ================= 3. 操作接口 =================

@app.route('/api/add_homework', methods=['POST'])
def add_homework():
    d = request.json; conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO [T-Homework] (课程ID, 作业内容, 布置日期, 截止日期) VALUES (?, ?, ?, ?)", (d['courseID'], d['content'], d['assignDate'], d['dueDate']))
        conn.commit(); return jsonify({"status":"success", "message":"作业发布成功"})
    except Exception as e: return jsonify({"status":"error", "message":str(e)})
    finally: conn.close()

@app.route('/api/add_score', methods=['POST'])
def add_score():
    d = request.json; conn = get_db_connection(); cursor = conn.cursor()
    try:
        try: 
            cursor.execute("INSERT INTO [T-Score] (学生ID, 课程ID, 分数, 考试名称, 考试日期, 满分) VALUES (?, ?, ?, ?, ?, ?)", 
                           (d['studentID'], d['courseID'], d['score'], d['examName'], d['examDate'], d['fullScore']))
        except:
            cursor.execute("SELECT MAX(成绩ID) FROM [T-Score]")
            row = cursor.fetchone(); new_id = int(row[0]) + 1 if (row and row[0]) else 901
            cursor.execute("INSERT INTO [T-Score] (成绩ID, 学生ID, 课程ID, 分数, 考试名称, 考试日期, 满分) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                           (new_id, d['studentID'], d['courseID'], d['score'], d['examName'], d['examDate'], d['fullScore']))
        conn.commit(); return jsonify({"status":"success", "message":"成绩录入成功"})
    except Exception as e: return jsonify({"status":"error", "message":str(e)})
    finally: conn.close()

@app.route('/api/delete_item', methods=['POST'])
def delete_item():
    d = request.json; conn = get_db_connection(); cursor = conn.cursor()
    try:
        if d['type'] == 'homework': cursor.execute("DELETE FROM [T-Homework] WHERE 作业ID=?", (d['id'],))
        elif d['type'] == 'attendance': cursor.execute("DELETE FROM [T-Attendance] WHERE 出勤ID=?", (d['id'],))
        elif d['type'] == 'score': cursor.execute("DELETE FROM [T-Score] WHERE 成绩ID=?", (d['id'],))
        conn.commit(); return jsonify({"status":"success", "message":"删除成功"})
    except Exception as e: return jsonify({"status":"error", "message":str(e)})
    finally: conn.close()

@app.route('/api/update_item', methods=['POST'])
def update_item():
    d = request.json; conn = get_db_connection(); cursor = conn.cursor()
    try:
        if d['type'] == 'homework': cursor.execute("UPDATE [T-Homework] SET 作业内容=?, 截止日期=? WHERE 作业ID=?", (d['content'], d['dueDate'], d['id']))
        elif d['type'] == 'score': cursor.execute("UPDATE [T-Score] SET 分数=?, 考试日期=? WHERE 成绩ID=?", (d['score'], d['date'], d['id']))
        elif d['type'] == 'attendance': cursor.execute("UPDATE [T-Attendance] SET 状态=? WHERE 出勤ID=?", (d['status'], d['id']))
        conn.commit(); return jsonify({"status":"success", "message":"修改成功"})
    except Exception as e: return jsonify({"status":"error", "message":str(e)})
    finally: conn.close()

@app.route('/api/add_attendance', methods=['POST'])
def add_attendance():
    d = request.json; conn = get_db_connection(); cursor = conn.cursor()
    try:
        try:
            cursor.execute("INSERT INTO [T-Attendance] (学生ID, 课程ID, 日期, 状态) VALUES (?, ?, ?, ?)", (d['studentID'], d['courseID'], d['date'], d['status']))
        except Exception:
            cursor.execute("SELECT MAX(出勤ID) FROM [T-Attendance]")
            row = cursor.fetchone()
            new_id = int(row[0]) + 1 if (row and row[0]) else 1
            cursor.execute("INSERT INTO [T-Attendance] (出勤ID, 学生ID, 课程ID, 日期, 状态) VALUES (?, ?, ?, ?, ?)", (new_id, d['studentID'], d['courseID'], d['date'], d['status']))
        conn.commit()
        return jsonify({"status":"success", "message":"考勤录入成功"})
    except Exception as e:
        print(f"Add Attendance Error: {e}")
        return jsonify({"status":"error", "message":f"录入失败: {str(e)}"})
    finally: conn.close()

# ================= 4. 家长端 & 消息系统 (含新算法) =================

@app.route('/api/parent/dashboard', methods=['GET'])
def get_parent_dashboard():
    pid = request.args.get('parentID'); conn = get_db_connection(); cursor = conn.cursor()
    try:
        # 1. 基础信息
        cursor.execute("SELECT 学生ID FROM [T-Parent] WHERE 家长ID=?", (pid,)); sid = cursor.fetchone()[0]
        cursor.execute("SELECT 姓名 FROM [T-Account] WHERE 用户ID=?", (pid,)); pname = cursor.fetchone()[0]
        
        cursor.execute("SELECT 姓名, 学生ID, 班级ID FROM [T-Student] WHERE 学生ID=?", (str(sid),))
        s_row = cursor.fetchone()
        student_name = s_row[0]; class_id = s_row[2]
        
        class_full_name = "未知班级"
        try:
            cursor.execute("SELECT 班级名称 FROM [T-Class] WHERE 班级ID=?", (class_id,))
            c_row = cursor.fetchone()
            if c_row: class_full_name = str(c_row[0])
        except: pass

        # 2. 作业 (不参与计算)
        cursor.execute("SELECT h.作业内容, c.课程名称, h.布置日期, h.截止日期 FROM [T-Homework] h, [T-Course] c WHERE h.课程ID=c.课程ID AND c.班级ID=? ORDER BY h.截止日期 DESC", (class_id,))
        hw_all, active_hw_count, today = [], 0, datetime.date.today()
        for r in cursor.fetchall():
            due_val = r[3]; is_expired = False
            try:
                if isinstance(due_val, datetime.datetime): is_expired = due_val.date() < today
                elif isinstance(due_val, datetime.date): is_expired = due_val < today
                elif isinstance(due_val, str): is_expired = datetime.datetime.strptime(due_val[:10], '%Y-%m-%d').date() < today
            except: pass
            if not is_expired: active_hw_count += 1 
            hw_all.append({"content": r[0], "course": r[1], "assign_date": safe_date_str(r[2]), "due_date": safe_date_str(r[3]), "is_expired": is_expired})
        
        # 3. 成绩查询 + 🟢 算法准备：计算平均百分制成绩
        cursor.execute("SELECT s.考试名称, c.课程名称, s.分数, s.考试日期, c.课程ID, s.满分 FROM [T-Score] s LEFT JOIN [T-Course] c ON s.课程ID=c.课程ID WHERE s.学生ID=? ORDER BY s.考试日期 DESC", (sid,))
        rows = cursor.fetchall()
        all_scores = []
        
        total_score_percent = 0  # 累加百分制成绩 (得分/满分 * 100)
        valid_exams_count = 0    # 有效考试次数

        for r in rows:
            exam_name = r[0]; course_id = r[4]; student_score = r[2]
            full_score = r[5] if r[5] else 100
            
            # 计算单科折合分供综合评价使用
            if full_score > 0:
                score_ratio = (student_score / full_score) * 100
                total_score_percent += score_ratio
                valid_exams_count += 1

            # 班级平均分查询
            avg_score = 0
            try:
                cursor.execute("SELECT AVG(分数) FROM [T-Score] WHERE 课程ID=? AND 考试名称=?", (course_id, exam_name))
                avg_res = cursor.fetchone()
                if avg_res and avg_res[0] is not None: avg_score = round(avg_res[0], 1)
            except: pass

            all_scores.append({
                "exam": exam_name, "course_name": r[1], "score": student_score, 
                "date": safe_date_str(r[3]), "course_id": course_id, "full": full_score, "class_avg": avg_score
            })

        # 4. 考勤 & 🟢 算法准备：计算出勤率
        cursor.execute("SELECT a.日期, c.课程名称, a.状态 FROM [T-Attendance] a LEFT JOIN [T-Course] c ON a.课程ID=c.课程ID WHERE a.学生ID=? ORDER BY a.日期 DESC", (sid,))
        att_rows = cursor.fetchall()
        att = [{"date":safe_date_str(r[0]), "course":r[1], "status":r[2]} for r in att_rows]

        total_att = len(att)
        absent_count = sum(1 for item in att if item['status'] == '缺勤')
        
        att_rate_val = 100.0 # 默认满勤
        if total_att > 0:
            att_rate_val = ((total_att - absent_count) / total_att) * 100
        
        att_rate_str = f"{int(att_rate_val)}%"

        # 🟢 [核心修改] 综合评价算法实现
        # 权重设置：成绩 70% + 出勤 30%
        # 如果没有成绩记录，暂时完全由出勤决定
        
        avg_academic_score = 0
        if valid_exams_count > 0:
            avg_academic_score = total_score_percent / valid_exams_count
        
        # 计算综合分
        if valid_exams_count == 0:
            # 无成绩时，只看出勤（或者给一个基础分，这里选择只看出勤）
            comp_val = att_rate_val
        else:
            comp_val = (avg_academic_score * 0.7) + (att_rate_val * 0.3)
        
        # 如果是完全新用户（无考勤无成绩），给个默认值 100
        if valid_exams_count == 0 and total_att == 0:
            comp_val = 100

        comp_val = int(comp_val)
        
        # 评级逻辑
        if comp_val >= 90: comp_status = "优秀"
        elif comp_val >= 80: comp_status = "良好"
        elif comp_val >= 60: comp_status = "及格"
        else: comp_status = "需努力"

        return jsonify({
            "status":"success", "parent_name":pname, 
            "student_info":{"name":student_name, "class_id":class_id, "class_name": class_full_name},
            "attendance":att, "homework":hw_all, "scores":all_scores,
            "stats": {
                "att_rate": att_rate_str, 
                "hw_count": active_hw_count, 
                "last_score": all_scores[0]['score'] if all_scores else 0, 
                "comp_val": comp_val,       # 🟢 返回计算后的综合分
                "comp_status": comp_status  # 🟢 返回评级
            }
        })
    except Exception as e: 
        print(f"Parent Dashboard Error: {e}")
        return jsonify({"status":"error", "message":f"查询失败: {str(e)}"})
    finally: conn.close()

@app.route('/api/teacher/messages', methods=['GET'])
def get_msgs():
    tid = request.args.get('teacherID')
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT 沟通ID, 学生ID, 日期 FROM [T-Communication] WHERE 教师ID=? AND 状态=1", (tid,))
        rows = cursor.fetchall()
        res = []
        for r in rows:
            sid = r[1]; s_name = "未知学生"
            try:
                cursor.execute("SELECT 姓名 FROM [T-Student] WHERE 学生ID=?", (str(sid),))
                s_row = cursor.fetchone()
                if s_row: s_name = s_row[0]
            except: pass
            res.append({"id": r[0], "text": f"家长请求沟通 (学生:{s_name})", "date": safe_date_str(r[2], '%Y-%m-%d %H:%M')})
        return jsonify(res)
    except Exception as e: return jsonify([{"id": 0, "text": f"系统报错: {str(e)}", "date": "请截图"}])
    finally: conn.close()

@app.route('/api/parent/messages', methods=['GET'])
def get_parent_msgs():
    pid = request.args.get('parentID'); conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT 日期, 状态 FROM [T-Communication] WHERE 家长ID=? ORDER BY 日期 DESC", (pid,))
        res = []
        for r in cursor.fetchall():
            status_val = r[1]
            is_read = (str(status_val) == '0' or status_val == 0 or status_val is False)
            res.append({"date": safe_date_str(r[0], '%Y-%m-%d %H:%M'), "is_read": is_read})
        return jsonify(res)
    except: return jsonify([])
    finally: conn.close()

@app.route('/api/parent/send_msg', methods=['POST'])
def p_send():
    d = request.json; conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT 学生ID FROM [T-Parent] WHERE 家长ID=?", (d['pid'],)); sid = cursor.fetchone()[0]
        cursor.execute("SELECT 班级ID FROM [T-Student] WHERE 学生ID=?", (str(sid),)); class_id = cursor.fetchone()[0]
        cursor.execute("SELECT 班主任ID FROM [T-Class] WHERE 班级ID=?", (class_id,)); tid = cursor.fetchone()[0]
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try: cursor.execute("INSERT INTO [T-Communication] (学生ID,家长ID,教师ID,日期,状态) VALUES (?,?,?,?,1)", (sid, d['pid'], tid, now))
        except: cursor.execute("INSERT INTO [T-Communication] (沟通ID,学生ID,家长ID,教师ID,日期,状态) VALUES (?,?,?,?,?,1)", (int(datetime.datetime.now().timestamp()), sid, d['pid'], tid, now))
        conn.commit(); return jsonify({"status":"success", "message":"沟通请求已发送"})
    except Exception as e: return jsonify({"status":"error", "message":f"发送失败: {str(e)}"})
    finally: conn.close()

@app.route('/api/teacher/read_msg', methods=['POST'])
def read_msg():
    conn = get_db_connection(); cursor = conn.cursor()
    try:
        cursor.execute("UPDATE [T-Communication] SET 状态=0 WHERE 沟通ID=?", (request.json['msgID'],))
        conn.commit(); return jsonify({"status":"success"})
    finally: conn.close()

@app.route('/api/teacher/export', methods=['GET'])
def export_file():
    export_type = request.args.get('type'); teacher_id = request.args.get('teacherID'); course_id = request.args.get('courseID')
    conn = get_db_connection(); cursor = conn.cursor(); output = io.StringIO(); writer = csv.writer(output); 
    try:
        if export_type == 'homework':
            writer.writerow(['ID', '课程', '内容', '布置日期', '截止日期'])
            cursor.execute("SELECT h.作业ID, c.课程名称, h.作业内容, h.布置日期, h.截止日期 FROM [T-Homework] h, [T-Course] c WHERE h.课程ID=c.课程ID AND c.教师ID=? ORDER BY h.布置日期 DESC", (teacher_id,))
            for r in cursor.fetchall(): writer.writerow([r[0], r[1], r[2], safe_date_str(r[3]), safe_date_str(r[4])])
        elif export_type == 'score':
            writer.writerow(['日期', '考试', '姓名', '分数', '满分'])
            cursor.execute("SELECT sc.考试日期, sc.考试名称, s.姓名, sc.分数, sc.满分 FROM [T-Score] sc, [T-Student] s WHERE sc.学生ID=s.学生ID AND sc.课程ID=? ORDER BY sc.考试日期 DESC", (course_id,))
            for r in cursor.fetchall(): writer.writerow([safe_date_str(r[0]), r[1], r[2], r[3], r[4]])
        elif export_type == 'attendance':
             writer.writerow(['日期', '姓名', '状态'])
             cursor.execute("SELECT a.日期, s.姓名, a.状态 FROM [T-Attendance] a, [T-Student] s WHERE a.学生ID=s.学生ID AND a.课程ID=? ORDER BY a.日期 DESC", (course_id,))
             for r in cursor.fetchall(): writer.writerow([safe_date_str(r[0]), r[1], r[2]])
        return Response("\ufeff" + output.getvalue(), mimetype="text/csv", headers={"Content-disposition": f"attachment; filename={export_type}.csv"})
    except Exception as e: return Response(f"导出失败: {str(e)}", status=500)
    finally: conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)