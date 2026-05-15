from flask import Flask, render_template, request, redirect, session, url_for
import pandas as pd
from datetime import datetime
import sqlite3
import secrets
from wsgiref.simple_server import make_server
#from waitress import serve

# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.secret_key = secrets.token_hex(16)

# =========================================================
# FILES
# =========================================================

QUESTIONS_FILE = 'questions.xlsx'
DATABASE = 'exam.db'

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

    # =====================================================
    # ANSWERS TABLE
    # =====================================================

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS answers (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            EmployeeID TEXT,

            QuestionID TEXT,

            Answers TEXT,

            Status TEXT,

            Timestamp TEXT

        )

    """)
    try:
       cursor.execute("ALTER TABLE answers ADD COLUMN Scenario TEXT")
    except:
        pass
    # =====================================================
    # ESCALATIONS TABLE
    # =====================================================

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
    # LOAD QUESTIONS ONLY WHEN NEEDED
    # =====================================================

    if questions_df is None:

        print("Loading questions...")

        questions_df = pd.read_excel(

            QUESTIONS_FILE,

            dtype=str,

            engine='openpyxl'

        ).fillna('')

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

        questions_df = questions_df.sort_values(

            by='EmployeeID'

        )

        print("Questions loaded")

    # =====================================================
    # SESSION CHECK
    # =====================================================

    if 'employee_id' not in session:

        return redirect(url_for('login'))

    employee_id = session['employee_id']

    # =====================================================
    # DATABASE
    # =====================================================

    conn = get_db()

    cursor = conn.cursor()

    # =====================================================
    # COMPLETED QUESTIONS
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
    # NO QUESTIONS
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

        """, (employee_id,))

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

    raw_tags = str(

        current_question['Tags']

    )

    raw_tags = raw_tags.replace('\n', ',')
    raw_tags = raw_tags.replace('|', ',')
    raw_tags = raw_tags.replace(';', ',')

    tags = [

        tag.strip()

        for tag in raw_tags.split(',')

        if tag.strip()

    ]

    tags = sorted(

        list(dict.fromkeys(tags))

    )

    # =====================================================
    # POST
    # =====================================================

    if request.method == 'POST':

        action = request.form.get('action')

        # =================================================
        # SUBMIT
        # =================================================

        if action == 'submit':

            selected_answers = request.form.getlist(

                'answers'

            )

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
            # DUPLICATE CHECK
            # =============================================

            question_id = str(

                current_question['QuestionID']

            )

            cursor.execute("""

                SELECT id

                FROM answers

                WHERE EmployeeID = ?

                AND QuestionID = ?

            """, (

                employee_id,

                question_id

            ))

            already_exists = cursor.fetchone()

            # =============================================
            # SAVE
            # =============================================

            if already_exists is None:
                scenario =question.get("Scenario"," ")

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

                """, (

                    employee_id,

                    question_id,

                    scenario,

                    ', '.join(selected_answers),

                    status,

                    str(datetime.now())

                ))

                conn.commit()

        # =================================================
        # ESCALATE
        # =================================================

        elif action == 'escalate':

            explanation = request.form.get(

                'explanation',

                ''

            ).strip()

            if explanation != '':

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

                conn.commit()

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

    # =====================================================
    # RENDER
    # =====================================================

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

    init_db()

    print("Server starting...")

    server = make_server(

        '0.0.0.0',

        5000,

        app

    )

    print("Server running on port 5000")

    server.serve_forever()