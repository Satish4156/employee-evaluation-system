from flask import Flask, render_template, request, redirect, session
import pandas as pd
from datetime import datetime
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

QUESTIONS_FILE = 'questions.xlsx'
ANSWERS_FILE = 'answers.xlsx'
ESCALATIONS_FILE = 'escalations.xlsx'

# =========================================================
# LOAD EXCEL
# =========================================================

def load_excel(file_name, columns):

    if os.path.exists(file_name):

        try:
            return pd.read_excel(
                file_name,
                engine='openpyxl'
            )

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

        return redirect('/exam')

    return render_template('login.html')

# =========================================================
# EXAM
# =========================================================

@app.route('/exam', methods=['GET', 'POST'])
def exam():

    if 'employee_id' not in session:
        return redirect('/')

    employee_id = str(
        session['employee_id']
    ).strip()

    # =====================================================
    # LOAD QUESTIONS
    # =====================================================

    try:

        questions_df = pd.read_excel(
            QUESTIONS_FILE,
            engine='openpyxl'
        )

    except Exception as e:

        return f"""
        <h3 style='text-align:center;
                   margin-top:50px;
                   color:red;'>
            Error Loading Questions : {e}
        </h3>
        """

    # =====================================================
    # LOAD EMPLOYEE ANSWERS
    # =====================================================

    try:

        answers_df = pd.read_excel(
            ANSWERS_FILE,
            sheet_name=employee_id,
            engine='openpyxl'
        )

    except:

        answers_df = pd.DataFrame(columns=[
            'EmployeeID',
            'QuestionID',
            'Answers',
            'Status',
            'Timestamp'
        ])

    # =====================================================
    # COMPLETED QUESTION IDS
    # =====================================================

    completed_question_ids = []

    if not answers_df.empty:

        completed_question_ids = answers_df[
            'QuestionID'
        ].astype(str).tolist()

    # =====================================================
    # FILTER QUESTIONS
    # =====================================================

    employee_questions = questions_df[

        (
            questions_df['EmployeeID']
            .astype(str)
            .str.strip()
            == employee_id
        )

        &

        (
            ~questions_df['QuestionID']
            .astype(str)
            .isin(completed_question_ids)
        )

    ].reset_index(drop=True)

    # =====================================================
    # COMPLETED PAGE
    # =====================================================

    if employee_questions.empty:

        total_answered = len(answers_df)

        total_correct = len(
            answers_df[
                answers_df['Status'] == 'Correct'
            ]
        )

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

    tags = sorted(
        list(dict.fromkeys(tags))
    )

    # =====================================================
    # FORM SUBMISSION
    # =====================================================

    if request.method == 'POST':

        action = request.form.get(
            'action',
            ''
        )

        selected_answers = request.form.getlist(
            'answers'
        )

        selected_answers = [
            answer.strip()
            for answer in selected_answers
            if answer.strip()
        ]

        selected_answers = sorted(
            list(dict.fromkeys(selected_answers))
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

            correct_raw = str(
                current_question['CorrectAnswer']
            )

            correct_raw = correct_raw.replace('\n', ',')
            correct_raw = correct_raw.replace('|', ',')
            correct_raw = correct_raw.replace(';', ',')

            correct_answers = [
                answer.strip()
                for answer in correct_raw.split(',')
                if answer.strip()
            ]

            correct_answers = sorted(
                list(dict.fromkeys(correct_answers))
            )

            status = 'Incorrect'

            if selected_answers == correct_answers:
                status = 'Correct'

            new_row = pd.DataFrame([{
                'EmployeeID': employee_id,
                'QuestionID': current_question['QuestionID'],
                'Answers': ', '.join(selected_answers),
                'Status': status,
                'Timestamp': datetime.now()
            }])

            answers_df = pd.concat(
                [answers_df, new_row],
                ignore_index=True
            )

            # =============================================
            # SAVE TO EMPLOYEE SHEET
            # =============================================

            if os.path.exists(ANSWERS_FILE):

                with pd.ExcelWriter(
                    ANSWERS_FILE,
                    engine='openpyxl',
                    mode='a',
                    if_sheet_exists='replace'
                ) as writer:

                    answers_df.to_excel(
                        writer,
                        sheet_name=employee_id,
                        index=False
                    )

            else:

                with pd.ExcelWriter(
                    ANSWERS_FILE,
                    engine='openpyxl'
                ) as writer:

                    answers_df.to_excel(
                        writer,
                        sheet_name=employee_id,
                        index=False
                    )

        # =================================================
        # ESCALATION
        # =================================================

        elif action == 'escalate':

            # =============================================
            # DO NOT ALLOW ESCALATION IF TAGS SELECTED
            # =============================================

            if len(selected_answers) > 0:

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

            new_row = pd.DataFrame([{
                'EmployeeID': employee_id,
                'QuestionID': current_question['QuestionID'],
                'Scenario': current_question['Scenario'],
                'Explanation': explanation,
                'Timestamp': datetime.now()
            }])

            escalation_df = pd.concat(
                [escalation_df, new_row],
                ignore_index=True
            )

            escalation_df.to_excel(
                ESCALATIONS_FILE,
                index=False
            )

        return redirect('/exam')

    # =====================================================
    # COUNTS
    # =====================================================

    pending_count = len(employee_questions)

    completed_count = len(completed_question_ids)

    total_questions = (
        pending_count + completed_count
    )

    progress_percent = 0

    if total_questions > 0:

        progress_percent = int(
            (
                completed_count /
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

    return redirect('/')

# =========================================================
# RUN
# =========================================================

if __name__ == '__main__':

    app.run(
        debug=False,
        host='0.0.0.0',
        port=5000
    )

