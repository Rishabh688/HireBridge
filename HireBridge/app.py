from flask import Flask, render_template, request, redirect, session
from db import get_connection

from flask_bcrypt import Bcrypt  # type: ignore

app = Flask(__name__)

app.secret_key = "hirebridge_secret"
app.config["TEMPLATES_AUTO_RELOAD"] = True

bcrypt = Bcrypt(app)


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# =====================================================
# HOME
# =====================================================


@app.route("/")
def home():
    return render_template("index.html")


# =====================================================
# STUDENT LOGIN
# =====================================================


@app.route("/student_login", methods=["GET", "POST"])
def student_login():

    error = None

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT password, role, linked_id
            FROM users
            WHERE username=%s
            """,
            (username,),
        )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if not user:
            error = "Invalid username or password."

        elif user["role"] != "STUDENT":
            error = "Invalid username or password."
            error = "Invalid username or password."

        else:

            session.clear()

            session["role"] = "STUDENT"
            session["student_id"] = user["linked_id"]

            return redirect("/student_dashboard")

    return render_template("student_login.html", error=error)


# =====================================================
# STUDENT SIGNUP
# =====================================================


@app.route("/student_signup", methods=["GET", "POST"])
def student_signup():

    error = None

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip()
        phone = request.form["phone"].strip()

        cgpa = request.form["cgpa"]
        attendance = request.form["attendance"]

        skills = request.form["skills"].strip()
        year = request.form["year"]

        password = request.form["password"]

        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT user_id
            FROM users
            WHERE username=%s
            """,
            (username,),
        )

        existing = cur.fetchone()

        if existing:

            cur.close()
            conn.close()

            error = "Username already exists."

            return render_template("student_signup.html", error=error)

        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO students
            (
                name,
                email,
                phone,
                cgpa,
                attendance,
                skills,
                year
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                username,
                email,
                phone,
                cgpa,
                attendance,
                skills,
                year,
            ),
        )

        student_id = cur.lastrowid

        # NOTE: original project used bcrypt hashing here (variable name hashed_password)
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        cur.execute(
            """
            INSERT INTO users
            (
                username,
                password,
                role,
                linked_id
            )
            VALUES
            (%s,%s,'STUDENT',%s)
            """,
            (
                username,
                hashed_password,
                student_id,
            ),
        )

        conn.commit()

        cur.close()
        conn.close()

        return redirect("/student_login")

    return render_template("student_signup.html", error=error)


# =====================================================
# STUDENT DASHBOARD
# =====================================================


@app.route("/student_dashboard")
def student_dashboard():

    if session.get("role") != "STUDENT":
        return redirect("/student_login")

    student_id = session["student_id"]

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT
            company_id,
            company_name,
            package,
            location,
            min_cgpa,
            min_attendance
        FROM companies
        """
    )

    companies = cur.fetchall()

    cur.execute(
        """
        SELECT company_id,status
        FROM applications
        WHERE student_id=%s
        """,
        (student_id,),
    )

    rows = cur.fetchall()

    applied = {}

    approved = 0
    rejected = 0

    for row in rows:

        applied[row["company_id"]] = row["status"]

        if row["status"] == "APPROVED":
            approved += 1

        elif row["status"] == "REJECTED":
            rejected += 1

    cur.execute(
        """
        SELECT name
        FROM students
        WHERE student_id=%s
        """,
        (student_id,),
    )

    student = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "student_dashboard.html",
        username=student["name"],
        companies=companies,
        applied=applied,
        open_count=len(companies),
        approved=approved,
        rejected=rejected,
    )


# =====================================================
# APPLY
# =====================================================


@app.route("/apply", methods=["POST"])
def apply():

    if session.get("role") != "STUDENT":
        return redirect("/student_login")

    company_id = request.form["company_id"]

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT IGNORE INTO applications
        (
            student_id,
            company_id,
            status
        )
        VALUES
        (%s,%s,'PENDING')
        """,
        (
            session["student_id"],
            company_id,
        ),
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect("/student_dashboard")


# =====================================================
# RESET APPLICATION
# =====================================================


@app.route("/reset_application", methods=["POST"])
def reset_application():

    if session.get("role") != "STUDENT":
        return redirect("/student_login")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM applications
        WHERE student_id=%s
        AND company_id=%s
        """,
        (
            session["student_id"],
            request.form["company_id"],
        ),
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect("/student_dashboard")


# =====================================================
# COMPANY LOGIN
# =====================================================


@app.route("/company_login", methods=["GET", "POST"])
def company_login():

    error = None

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_connection()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT password,role,linked_id
            FROM users
            WHERE username=%s
            """,
            (username,),
        )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if (
            not user
            or user["role"] != "COMPANY"
            or not bcrypt.check_password_hash(
                user["password"],
                password,
            )
        ):

            error = "Invalid company credentials."

        else:

            session.clear()

            session["role"] = "COMPANY"
            session["company_id"] = user["linked_id"]

            return redirect("/company_dashboard")

    return render_template("company_login.html", error=error)


# =====================================================
# COMPANY DASHBOARD
# =====================================================


@app.route("/company_dashboard")
def company_dashboard():

    if session.get("role") != "COMPANY":
        return redirect("/company_login")

    company_id = session["company_id"]

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT company_name
        FROM companies
        WHERE company_id=%s
        """,
        (company_id,),
    )

    company = cur.fetchone()

    cur.execute(
        """
        SELECT
            a.application_id,
            s.name,
            s.email,
            s.cgpa,
            s.attendance,
            a.status
        FROM applications a
        JOIN students s
        ON a.student_id=s.student_id
        WHERE a.company_id=%s
        """,
        (company_id,),
    )

    applicants = cur.fetchall()

    approved = sum(1 for a in applicants if a["status"] == "APPROVED")

    rejected = sum(1 for a in applicants if a["status"] == "REJECTED")

    cur.close()
    conn.close()

    return render_template(
        "company_dashboard.html",
        company_name=company["company_name"],
        applicants=applicants,
        total=len(applicants),
        approved=approved,
        rejected=rejected,
    )


# =====================================================
# UPDATE APPLICATION
# =====================================================


@app.route("/update_application", methods=["POST"])
def update_application():

    if session.get("role") != "COMPANY":
        return redirect("/company_login")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE applications
        SET status=%s
        WHERE application_id=%s
        """,
        (
            request.form["action"],
            request.form["application_id"],
        ),
    )

    conn.commit()

    cur.close()
    conn.close()

    return redirect("/company_dashboard")


# =====================================================
# LOGOUT
# =====================================================


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000,
    )

