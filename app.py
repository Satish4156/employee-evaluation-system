from flask import Flask, render_template, request, redirect, session, url_for
import pandas as pd
from datetime import datetime
import os
import secrets

app = Flask(__name__)

# =========================================================
# SECRET KEY
# =========================================================

app.secret_key = secrets.token_hex(16)

# =========================================================
# FILES
# =========================================================

QUESTIONS_FILE = 'questions.xlsx'
ANSWERS_FILE = 'answers.xlsx'
ESCALATIONS_FILE = 'escalations.xlsx'

# =========================================================
# LOAD / CREATE EXCEL
# =========================================================

def load_excel(file_name, columns):

    if os.path.exists(file_name):

        try:

            return pd.read_excel(file_name)

        except:

            return pd.DataFrame(columns=columns)

    return pd.DataFrame(columns=columns)

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
        session['start_time'] = str(datetime.now())

        return redirect(url_for('exam'))

    return render_template('login.html')

# =========================================================
# EXAM
# =========================================================

@app.route('/exam', methods=['GET', 'POST'])
def exam():

    # =====================================================
    # SESSION VALIDATION
    # =====================================================

    if 'employee_id' not in session:

        return redirect(url_for('login'))

    employee_id = str(
        session['employee_id']
    ).strip()

    # =====================================================
    # LOAD QUESTIONS
    # =====================================================

    try:

        questions_df = pd.read_excel(
            QUESTIONS_FILE
        )

    except Exception as e:

        return f"""
        <h3 style='text-align:center;
                   margin-top:50px;
                   color:red;'>

            Error Loading questions.xlsx : {e}

        </h3>
        """

    # =====================================================
    # LOAD ANSWERS
    # =====================================================

    answers_df = load_excel(

        ANSWERS_FILE,

        [
            'EmployeeID',
            'QuestionID',
            'Answers',
            'Status',
            'Timestamp'
        ]

    )

    # =====================================================
    # GET COMPLETED QUESTION IDS
    # =====================================================

    completed_question_ids = []

    if not answers_df.empty:

        completed_question_ids = answers_df[

            answers_df['EmployeeID']
            .astype(str)
            .str.strip()

            ==

            employee_id

        ]['QuestionID'].astype(str).tolist()

    # =====================================================
    # FILTER ONLY PENDING QUESTIONS
    # =====================================================

    employee_questions = questions_df[

        (
            questions_df['EmployeeID']
            .astype(str)
            .str.strip()

            ==

            employee_id
        )

        &

        (
            ~questions_df['QuestionID']
            .astype(str)
            .isin(completed_question_ids)
        )

    ].reset_index(drop=True)

    # =====================================================
    # NO QUESTIONS
    # =====================================================

    if employee_questions.empty:

        total_answered = len(

            answers_df[

                answers_df['EmployeeID']
                .astype(str)
                .str.strip()

                ==

                employee_id

            ]

        )

        total_correct = len(

            answers_df[

                (
                    answers_df['EmployeeID']
                    .astype(str)
                    .str.strip()

                    ==

                    employee_id
                )

                &

                (
                    answers_df['Status']
                    ==

                    'Correct'
                )

            ]

        )

        return render_template(

            'completed.html',

            score=total_correct,

            total=total_answered

        )

    # =====================================================
    # ALWAYS FIRST PENDING QUESTION
    # =====================================================

    question_index = 0

    # =====================================================
    # CURRENT QUESTION
    # =====================================================

    current_question = employee_questions.iloc[
        question_index
    ]

    # =====================================================
    # TAGS
    # =====================================================

    raw_tags = str(
        current_question['Tags']
    ).strip()

    raw_tags = raw_tags.replace(
        '\n',
        ','
    )

    raw_tags = raw_tags.replace(
        '|',
        ','
    )

    raw_tags = raw_tags.replace(
        ';',
        ','
    )

    tags = [

        tag.strip()

        for tag in raw_tags.split(',')

        if tag.strip()

    ]

    tags = list(
        dict.fromkeys(tags)
    )

    tags = sorted(tags)

    # =====================================================
    # FORM SUBMIT
    # =====================================================

    if request.method == 'POST':

        action = request.form.get(
            'action',
            ''
        )

        # =================================================
        # SELECTED ANSWERS
        # =================================================

        selected_answers = request.form.getlist(
            'answers'
        )

        selected_answers = [

            answer.strip()

            for answer in selected_answers

            if answer.strip()

        ]

        selected_answers = list(
            dict.fromkeys(selected_answers)
        )

        # =================================================
        # SUBMIT ANSWER
        # =================================================

        if action == 'submit':

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

            correct_raw = correct_raw.replace(
                '\n',
                ','
            )

            correct_raw = correct_raw.replace(
                '|',
                ','
            )

            correct_raw = correct_raw.replace(
                ';',
                ','
            )

            correct_answers = [

                answer.strip()

                for answer in correct_raw.split(',')

                if answer.strip()

            ]

            correct_answers = list(
                dict.fromkeys(correct_answers)
            )

            # =============================================
            # SORT
            # =============================================

            selected_answers_sorted = sorted(
                selected_answers
            )

            correct_answers_sorted = sorted(
                correct_answers
            )

            # =============================================
            # STATUS
            # =============================================

            status = 'Incorrect'

            if (
                selected_answers_sorted
                ==
                correct_answers_sorted
            ):

                status = 'Correct'

            # =============================================
            # PREVENT DUPLICATE SAVE
            # =============================================

            already_exists = answers_df[

                (
                    answers_df['EmployeeID']
                    .astype(str)
                    .str.strip()

                    ==

                    employee_id
                )

                &

                (
                    answers_df['QuestionID']
                    .astype(str)

                    ==

                    str(current_question['QuestionID'])
                )

            ]

            if already_exists.empty:

                # =========================================
                # SAVE ANSWER
                # =========================================

                new_row = pd.DataFrame([{

                    'EmployeeID':
                    employee_id,

                    'QuestionID':
                    current_question['QuestionID'],

                    'Answers':
                    ', '.join(selected_answers_sorted),

                    'Status':
                    status,

                    'Timestamp':
                    datetime.now()

                }])

                answers_df = pd.concat(

                    [answers_df, new_row],

                    ignore_index=True

                )

                answers_df.to_excel(

                    ANSWERS_FILE,

                    index=False

                )

        # =================================================
        # ESCALATION
        # =================================================

        elif action == 'escalate':

            explanation = request.form.get(
                'explanation',
                ''
            ).strip()

            if explanation == '':

                return """
                <h3 style='text-align:center;
                           margin-top:50px;
                           color:red;'>

                    Escalation Explanation Required

                </h3>
                """

            escalation_df = load_excel(

                ESCALATIONS_FILE,

                [
                    'EmployeeID',
                    'QuestionID',
                    'Scenario',
                    'Explanation',
                    'Timestamp'
                ]

            )

            # =============================================
            # PREVENT DUPLICATE ESCALATION
            # =============================================

            already_escalated = escalation_df[

                (
                    escalation_df['EmployeeID']
                    .astype(str)
                    .str.strip()

                    ==

                    employee_id
                )

                &

                (
                    escalation_df['QuestionID']
                    .astype(str)

                    ==

                    str(current_question['QuestionID'])
                )

            ]

            if already_escalated.empty:

                new_row = pd.DataFrame([{

                    'EmployeeID':
                    employee_id,

                    'QuestionID':
                    current_question['QuestionID'],

                    'Scenario':
                    current_question['Scenario'],

                    'Explanation':
                    explanation,

                    'Timestamp':
                    datetime.now()

                }])

                escalation_df = pd.concat(

                    [escalation_df, new_row],

                    ignore_index=True

                )

                escalation_df.to_excel(

                    ESCALATIONS_FILE,

                    index=False

                )

        # =================================================
        # LOAD NEXT PENDING QUESTION
        # =================================================

        return redirect(url_for('exam'))

    # =====================================================
    # COUNTS
    # =====================================================

    pending_count = len(employee_questions)

    completed_count = len(completed_question_ids)

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
# RUN
# =========================================================

if __name__ == '__main__':

    app.run(

        debug=True,

        host='0.0.0.0',

        port=5000

    )