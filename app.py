from flask import Flask, render_template, request, redirect, session
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "secret123"

# =====================================================
# FILES
# =====================================================

QUESTIONS_FILE = "questions.xlsx"
ANSWERS_FILE = "answers.xlsx"
ESCALATIONS_FILE = "escalations.xlsx"

# =====================================================
# LOAD QUESTIONS
# =====================================================

questions_df = pd.read_excel(QUESTIONS_FILE)

questions_df = questions_df.fillna("")

questions = questions_df.to_dict(orient="records")

# =====================================================
# TAGS
# =====================================================

tags = [
    "#Issue > Account > Registration > Account Creation Failure",
    "#Issue > Banking > Payment > Transaction Failure",
    "#Issue > Technical > Server > Downtime",
    "#Issue > Healthcare > Billing > Invoice Error",
    "#Issue > Education > Upload > File Missing",
    "#Issue > Telecom > Network > Slow Internet"
]

# =====================================================
# LOGIN
# =====================================================

@app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        employee_id = request.form.get('employee_id')

        if employee_id:

            session['employee_id'] = employee_id

            return redirect('/exam')

    return render_template('login.html')

# =====================================================
# EXAM
# =====================================================

@app.route('/exam', methods=['GET', 'POST'])
def exam():

    if 'employee_id' not in session:
        return redirect('/')

    employee_id = session['employee_id']

    # =================================================
    # LOAD COMPLETED QUESTIONS
    # =================================================

    completed_questions = set()

    if os.path.exists(ANSWERS_FILE):

        try:

            excel_file = pd.ExcelFile(ANSWERS_FILE)

            if employee_id in excel_file.sheet_names:

                employee_answers = pd.read_excel(
                    ANSWERS_FILE,
                    sheet_name=employee_id
                )

                completed_questions = set(
                    employee_answers["task_id"].astype(str)
                )

        except:
            pass

    # =================================================
    # FILTER EMPLOYEE QUESTIONS
    # =================================================

    remaining_questions = []

    for q in questions:

        task_id = str(q.get("task_id", "")).strip()

        assigned_employee = str(
            q.get("EmployeeID", "")
        ).strip()

        # ONLY EMPLOYEE QUESTIONS
        if assigned_employee != employee_id:
            continue

        # REMOVE COMPLETED QUESTIONS
        if task_id in completed_questions:
            continue

        remaining_questions.append(q)

    # =================================================
    # COUNTS
    # =================================================

    employee_total_questions = [

        q for q in questions

        if str(q.get("EmployeeID", "")).strip()
        == employee_id

    ]

    total_questions = len(employee_total_questions)

    completed_count = len(completed_questions)

    pending_count = total_questions - completed_count

    progress_percent = 0

    if total_questions > 0:

        progress_percent = int(
            (completed_count / total_questions) * 100
        )

    # =================================================
    # ALL COMPLETED
    # =================================================

    if len(remaining_questions) == 0:

        return render_template(
            'completed.html',
            employee_id=employee_id
        )

    # =================================================
    # CURRENT QUESTION
    # =================================================

    current_question = remaining_questions[0]

    # =================================================
    # POST
    # =================================================

    if request.method == 'POST':

        action = request.form.get('action')

        selected_tags = request.form.getlist('tags')

        # =============================================
        # ESCALATE
        # =============================================

        if action == "escalate":

            if len(selected_tags) > 0:

                return render_template(
                    'exam.html',
                    question=current_question,
                    tags=tags,
                    question_no=completed_count + 1,
                    total_questions=total_questions,
                    pending_count=pending_count,
                    completed_count=completed_count,
                    progress_percent=progress_percent,
                    error_message="Remove selected tags before escalation"
                )

            escalation_data = {

                "employee_id": employee_id,
                "task_id": current_question["task_id"],
                "question": current_question["Scenario"],
                "status": "Escalated"

            }

            escalation_df = pd.DataFrame([escalation_data])

            if os.path.exists(ESCALATIONS_FILE):

                old_df = pd.read_excel(
                    ESCALATIONS_FILE
                )

                escalation_df = pd.concat(
                    [old_df, escalation_df],
                    ignore_index=True
                )

            escalation_df.to_excel(
                ESCALATIONS_FILE,
                index=False
            )

            return redirect('/exam')

        # =============================================
        # SAVE ANSWER
        # =============================================

        answer_data = {

            "employee_id": employee_id,
            "task_id": current_question["task_id"],
            "question": current_question["Scenario"],
            "selected_tags": ", ".join(selected_tags),
            "status": "Completed"

        }

        employee_sheet = pd.DataFrame([answer_data])

        try:

            if os.path.exists(ANSWERS_FILE):

                with pd.ExcelWriter(
                    ANSWERS_FILE,
                    engine="openpyxl",
                    mode="a",
                    if_sheet_exists="overlay"
                ) as writer:

                    try:

                        existing_df = pd.read_excel(
                            ANSWERS_FILE,
                            sheet_name=employee_id
                        )

                        updated_df = pd.concat(
                            [existing_df, employee_sheet],
                            ignore_index=True
                        )

                    except:

                        updated_df = employee_sheet

                    updated_df.to_excel(
                        writer,
                        sheet_name=employee_id,
                        index=False
                    )

            else:

                with pd.ExcelWriter(
                    ANSWERS_FILE,
                    engine="openpyxl"
                ) as writer:

                    employee_sheet.to_excel(
                        writer,
                        sheet_name=employee_id,
                        index=False
                    )

        except Exception as e:

            return f"Excel Save Error: {e}"

        return redirect('/exam')

    # =================================================
    # GET
    # =================================================

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

# =====================================================
# LOGOUT
# =====================================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

# =====================================================
# RUN
# =====================================================

if __name__ == '__main__':

    app.run(

        debug=False,

        host='0.0.0.0',

        port=5000

    )