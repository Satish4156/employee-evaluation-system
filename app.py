from flask import Flask, render_template, request, redirect, session, url_for
import pandas as pd
from datetime import datetime
import sqlite3
import secrets
import os
from wsgiref.simple_server import make_server

# =========================================================
# APP
# =========================================================

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# =========================================================
# FILES
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

QUESTIONS_FILE = os.path.join(BASE_DIR, 'questions.xlsx')

DATABASE = os.path.join(BASE_DIR, 'exam.db')

print("DATABASE PATH:", DATABASE)

# =========================================================
# QUESTIONS CACHE
# =========================================================

questions_df = None

# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE,
        check_same_thread=False,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn

# =========================================================
# CREATE DATABASE
# =========================================================

def init_db():

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS answers (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            EmployeeID TEXT,

            QuestionID TEXT,

            Scenario TEXT,

            Answers TEXT,

            Status TEXT,

            Timestamp TEXT


                   
  
                          """)

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS escalations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            EmployeeID TEXT,

            QuestionID TEXT,

            Scenario TEXT,

            Explanation TEXT,

            Timestamp TEXT

           )


                             """)

    conn.commit()

    conn.close()

# =========================================================
# INITIALIZE DATABASE
# =========================================================

init_db()

# =========================================================
# LOGIN
# =========================================================

@app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        employee_id = request.form.get(
            'employee_id',
            ''
        ).strip()

        if employee_id == '':

            return """

            <h3 style='text-align:center;
                       margin-top:50px;
                       color:red;'>

                Employee ID Required

            </h3>

            """

        session['employee_id'] = employee_id

        return redirect(url_for('exam'))

    return render_template('login.html')

# =========================================================
# EXAM
# =========================================================

@app.route('/exam', methods=['GET', 'POST'])
def exam():

    global questions_df

    # =====================================================
    # LOAD QUESTIONS
    # =====================================================

    if questions_df is None:

        try:

            questions_df = pd.read_excel(
                QUESTIONS_FILE,
                dtype=str,
                engine='openpyxl'
            ).fillna('')

        except Exception as e:

            return f"""

            <h2 style='color:red;text-align:center;margin-top:50px;'>

                Excel Loading Error:<br><br>{e}

            </h2>

            """

        questions_df.columns = (
            questions_df.columns
            .str.strip()
        )

        required_columns = [

            'EmployeeID',
            'QuestionID',
            'Scenario',
            'Tags',
            'CorrectAnswer'

        ]

        for col in required_columns:

            if col not in questions_df.columns:

                questions_df[col] = ''

        questions_df['EmployeeID'] = (
            questions_df['EmployeeID']
            .astype(str)
            .str.strip()
        )

        questions_df['QuestionID'] = (
            questions_df['QuestionID']
            .astype(str)
            .str.strip()
        )

        questions_df['Scenario'] = (
            questions_df['Scenario']
            .astype(str)
            .str.strip()
        )

    # =====================================================
    # SESSION CHECK
    # =====================================================

    if 'employee_id' not in session:

        return redirect(url_for('login'))

    employee_id = session['employee_id']

    conn = get_db()

    cursor = conn.cursor()

    # =====================================================
    # COMPLETED IDS
    # =====================================================

    cursor.execute("""

        SELECT QuestionID

        FROM answers

        WHERE EmployeeID = ?

    """, (employee_id,))

    completed_ids = set(

        row['QuestionID']

        for row in cursor.fetchall()

     )
    


    # =====================================================
    # FILTER QUESTIONS
    # =====================================================

    employee_questions = questions_df[

        (
            questions_df['EmployeeID']
            ==
            employee_id
        )

        &

        (
            ~questions_df['QuestionID']
            .isin(completed_ids)
        )

    ]

    # =====================================================
    # COMPLETED PAGE
    # =====================================================

    if employee_questions.empty:

        cursor.execute("""

            SELECT COUNT(*)

            FROM answers

            WHERE EmployeeID = ?

        """, (employee_id,))

        total_answered = cursor.fetchone()[0]

        cursor.execute("""

            SELECT COUNT(*)
 
                       
            FROM answers

            WHERE EmployeeID = ?

            AND Status = 'Correct'

        """), (employee_id,)

        total_correct = cursor.fetchone()[0]

        conn.close()

        return render_template(
            'completed.html',
            score=total_correct,
            total=total_answered
        )

    # =====================================================
    # CURRENT QUESTION
    # =====================================================

    current_question = employee_questions.iloc[0]

    # =====================================================
    # TAGS
    # =====================================================

    raw_tags = str(current_question['Tags'])

    raw_tags = raw_tags.replace('\n', ',')
    raw_tags = raw_tags.replace('|', ',')
    raw_tags = raw_tags.replace(';', ',')

    tags = [

        tag.strip()

        for tag in raw_tags.split(',')

        if tag.strip()

    ]

    tags = sorted(list(dict.fromkeys(tags)))

    # =====================================================
    # POST
    # =====================================================

    if request.method == 'POST':

        action = request.form.get('action')

        # =================================================
        # SUBMIT
        # =================================================

        if action == 'submit':

            selected_answers = request.form.getlist('answers')

            selected_answers = sorted(

                list(

                    dict.fromkeys(

                        [

                            x.strip()

                            for x in selected_answers

                            if x.strip()

                        ]

                    )

                )

            )

            if len(selected_answers) == 0:

                conn.close()

                return """

                <h3 style='text-align:center;
                           margin-top:50px;
                           color:red;'>

                    Please Select At Least One Tag

                </h3>

                """

            # =============================================
            # CORRECT ANSWERS
            # =============================================

            correct_raw = str(
                current_question['CorrectAnswer']
            )

            correct_raw = correct_raw.replace('\n', ',')
            correct_raw = correct_raw.replace('|', ',')
            correct_raw = correct_raw.replace(';', ',')

            correct_answers = sorted(

                list(

                    dict.fromkeys(

                        [

                            x.strip()

                            for x in correct_raw.split(',')

                            if x.strip()

                        ]

                    )

                )

            )

            # =============================================
            # STATUS
            # =============================================

            status = 'Incorrect'

            if selected_answers == correct_answers:

                status = 'Correct'

            # =============================================
            # QUESTION ID
            # =============================================

            question_id = str(
                current_question['QuestionID']
            ).strip()

            # =============================================
            # SCENARIO
            # =============================================

            scenario = str(
                current_question['Scenario']
            ).strip()

            # =============================================
            # DELETE OLD ENTRY
            # =============================================

            cursor.execute("""

                DELETE FROM answers

                WHERE EmployeeID = ?

                AND QuestionID = ?

            """), (

                employee_id,
                question_id

            ))

            # =============================================
            # SAVE ANSWER
            # =============================================

            try:

                cursor.execute("""

                    INSERT INTO answers (

                        EmployeeID,

                        QuestionID,

                        Scenario,

                        Answers,

                        Status,

                        Timestamp

                    )

                    VALUES (?, ?, ?, ?, ?, ?)

                """), (

                    employee_id,

                    question_id,

                    scenario,

                    ', '.join(selected_answers),

                    status,

                    str(datetime.now())

                ))

                conn.commit()

                print("ANSWER SAVED SUCCESSFULLY")

            except Exception as e:

                print("DATABASE ERROR:", e)

                conn.close()

                return f"""

                <h2 style='color:red;text-align:center;margin-top:50px;'>

                    DATABASE ERROR:<br><br>{e}

                </h2>

                """

        # =================================================
        # ESCALATE
        # =================================================

        elif action == 'escalate':

            selected_answers = request.form.getlist(
                'answers'
            )

            selected_answers = [

                x.strip()

                for x in selected_answers

                if x.strip()

            ]

            # BLOCK ESCALATION IF TAGS SELECTED

            if len(selected_answers) > 0:

                conn.close()

                return """

                <h3 style='text-align:center;
                           margin-top:50px;
                           color:red;'>

                    Remove Selected Tags Before Escalation

                </h3>

                """

            explanation = request.form.get(
                'explanation',
                ''
            ).strip()

            if explanation != '':

                try:

                    # SAVE ESCALATION

                    cursor.execute("""

                        INSERT INTO escalations (

                            EmployeeID,

                            QuestionID,

                            Scenario,

                            Explanation,

                            Timestamp

                        )

                        VALUES (?, ?, ?, ?, ?)

                    """, (

                        employee_id,

                        str(current_question['QuestionID']),

                        str(current_question['Scenario']),

                        explanation,

                        str(datetime.now())

                    ))

                    # MARK QUESTION COMPLETED

                    cursor.execute("""

                        INSERT INTO answers (

                            EmployeeID,

                            QuestionID,

                            Scenario,

                            Answers,

                            Status,

                            Timestamp

                        )

                        VALUES (?, ?, ?, ?, ?, ?)

                    """), (

                        employee_id,

                        str(current_question['QuestionID']),

                        str(current_question['Scenario']),

                        'ESCALATED',

                        'Escalated',

                        str(datetime.now())

                    ))

                    conn.commit()

                    print("ESCALATION SAVED")

                except Exception as e:

                    print("ESCALATION ERROR:", e)


        conn.close()

        return redirect(url_for('exam'))

    # =====================================================
    # COUNTS
    # =====================================================

    pending_count = len(employee_questions)

    completed_count = len(completed_ids)

    total_questions = (
        pending_count
        +
        completed_count
    )

    progress_percent = 0

    if total_questions > 0:

        progress_percent = int(

            (
                completed_count
                /
                total_questions
            ) * 100

        )

    conn.close()

    return render_template(

        'exam.html',

        question=current_question,

        tags=tags,

        question_no=completed_count + 1,

        total_questions=total_questions,

        pending_count=pending_count,

        completed_count=completed_count,

        progress_percent=progress_percent

    )
# Admin Dashboard Feature — Copy Paste Code

# =========================================================

# ADMIN DASHBOARD

# =========================================================

@app.route('/admin')
def admin_dashboard():
    conn = get_db()

    cursor = conn.cursor()
    # =============================================
    # TOTAL SUBMISSIONS
    # =============================================
    cursor.execute("""
        SELECT COUNT(*)
        FROM answers
    """)
    total_submissions = cursor.fetchone()[0]

    # =============================================
    # TOTAL ESCALATIONS
    # =============================================
    cursor.execute("""
        SELECT COUNT(*)
        FROM escalations
    """)
    total_escalations = cursor.fetchone()[0]

    # =============================================
    # EMPLOYEE PERFORMANCE
    # =============================================
    cursor.execute("""
        SELECT
            EmployeeID,
            COUNT(*) as total_completed
        FROM answers
        GROUP BY EmployeeID
        ORDER BY total_completed DESC
    """)
    employee_stats = cursor.fetchall()

    # =============================================
    # RECENT SUBMISSIONS
    # =============================================
    cursor.execute("""
        SELECT *
        FROM answers
        ORDER BY id DESC
        LIMIT 20
    """)
    recent_answers = cursor.fetchall()

    conn.close()

    return render_template(
        'admin.html',
        total_submissions=total_submissions,
        total_escalations=total_escalations,
        employee_stats=employee_stats,
        recent_answers=recent_answers
    )

# =========================================================
# LOGOUT
# =========================================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect(url_for('login'))

# =========================================================
# START
# =========================================================

if __name__ == '__main__':

    server = make_server(
        '0.0.0.0',
        5000,
        app
    )

    print("SERVER STARTED")

    server.serve_forever()