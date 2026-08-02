from dotenv import load_dotenv
load_dotenv()

from playsound import playsound
import threading
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
import os
import cv2
import face_recognition
import numpy as np
from datetime import datetime, timedelta
import calendar
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import io
from PIL import Image

app = Flask(__name__)

# ---------------- SECRETS (from environment) ----------------
# All secrets now come from environment variables instead of being
# hardcoded. See .env.example for the variables you need to set.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-fallback-key")

# ---------------- EMAIL CONFIG ----------------
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# ---------------- WEBCAM FEATURE FLAG ----------------
# A cloud server has no physical webcam and no display, so the live
# recognition loop (cv2.VideoCapture + cv2.imshow) can only run on a
# machine that actually has a camera and a screen — i.e. locally.
# Deployed instances keep everything else (login, student CRUD,
# attendance reports) fully working; only this route is gated.
ENABLE_WEBCAM = os.environ.get("ENABLE_WEBCAM", "false").lower() == "true"
print("DEBUG: ENABLE_WEBCAM =", ENABLE_WEBCAM, "| raw env value =", os.environ.get("ENABLE_WEBCAM"))

# ---------------- DATABASE ----------------
# No hardcoded fallback on purpose — if DATABASE_URL isn't set, the
# app should fail loudly instead of silently connecting somewhere
# unexpected with a credential baked into the source code.
DATABASE_URL = os.environ.get("DATABASE_URL")
DB_SSLMODE = os.environ.get("DB_SSLMODE", "require")


def get_db_connection():
    """
    Returns a new Postgres connection. Most hosted Postgres providers
    (Render, Railway, Supabase, etc.) give you a single DATABASE_URL
    connection string — put it in your environment and everything
    else here just works.
    """
    return psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE)


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # ---------------- ADMIN TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # ---------------- STUDENTS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER,
        name TEXT,
        roll_no TEXT,
        email TEXT,
        branch TEXT,
        year TEXT,
        UNIQUE(admin_id, roll_no)
    )
    """)

    # Postgres supports IF NOT EXISTS on ADD COLUMN directly —
    # no need for the try/except OperationalError dance SQLite needed.
    cursor.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS email TEXT")

    # ---------------- ATTENDANCE TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        admin_id INTEGER,
        roll_no TEXT,
        date TEXT,
        time TEXT
    )
    """)

    conn.commit()
    cursor.close()
    conn.close()


init_db()

# ---------------- LOGIN REQUIRED ----------------
from functools import wraps


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


# ---------------- HOME ----------------

@app.route("/")
def home():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM admin")
    count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    if count == 0:
        return redirect(url_for("signup"))

    return redirect(url_for("login"))


# ---------------- SIGNUP ----------------

@app.route("/signup", methods=["GET", "POST"])
def signup():

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        cursor.execute(
            "SELECT id FROM admin WHERE username=%s",
            (username,)
        )

        if cursor.fetchone():

            cursor.close()
            conn.close()

            return render_template(
                "signup.html",
                error="Username already exists."
            )

        password = generate_password_hash(password)

        cursor.execute(
            "INSERT INTO admin(username,password) VALUES(%s,%s)",
            (username, password)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for("login"))

    cursor.close()
    conn.close()

    return render_template("signup.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id,password FROM admin WHERE username=%s",
            (username,)
        )

        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row and check_password_hash(row[1], password):

            session["admin_id"] = row[0]
            session["username"] = username

            return redirect(url_for("dashboard"))

        error = "Invalid Username or Password"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():

    admin_id = session["admin_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM students WHERE admin_id=%s",
        (admin_id,)
    )

    total_students = cursor.fetchone()[0]

    today = datetime.now().strftime("%d-%m-%Y")

    cursor.execute(
        """
        SELECT COUNT(DISTINCT roll_no)
        FROM attendance
        WHERE admin_id=%s AND date=%s
        """,
        (admin_id, today)
    )

    today_attendance = cursor.fetchone()[0]

    absent_students = total_students - today_attendance

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        total_students=total_students,
        today_attendance=today_attendance,
        absent_students=absent_students,
        username=session["username"]
    )


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
@login_required
def register():

    if request.method == "POST":

        name = request.form["name"]
        roll_no = request.form["roll_no"]
        email = request.form["email"]
        branch = request.form["branch"]
        year = request.form["year"]

        image = request.files["image"]

        admin_id = session["admin_id"]
        username = session["username"]

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO students
                (admin_id,name,roll_no,email,branch,year)
                VALUES(%s,%s,%s,%s,%s,%s)
                """,
                (
                    admin_id,
                    name,
                    roll_no,
                    email,
                    branch,
                    year
                )
            )

            conn.commit()

        except psycopg2.errors.UniqueViolation:

            # A failed statement leaves a Postgres transaction in an
            # aborted state until it's rolled back — SQLite doesn't
            # need this, but Postgres does.
            conn.rollback()
            cursor.close()
            conn.close()

            return "Roll Number already exists."

        cursor.close()
        conn.close()

        os.makedirs(
            f"dataset/{username}/{roll_no}",
            exist_ok=True
        )

        image.save(
            f"dataset/{username}/{roll_no}/{image.filename}"
        )

        return redirect(url_for("dashboard"))

    return render_template("register.html")


# ---------------- MANAGE STUDENTS ----------------

@app.route('/manage_students')
@login_required
def manage_students():

    admin_id = session["admin_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            name,
            roll_no,
            email,
            branch,
            year
        FROM students
        WHERE admin_id=%s
        ORDER BY name
    """, (admin_id,))

    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_students.html",
        students=students
    )


# ---------------- EDIT STUDENT ----------------

@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):

    admin_id = session["admin_id"]
    username = session["username"]

    conn = get_db_connection()
    cursor = conn.cursor()

    # ---------------- DELETE ----------------
    if request.method == "POST" and request.form.get("action") == "delete":

        cursor.execute(
            "SELECT roll_no FROM students WHERE id=%s AND admin_id=%s",
            (student_id, admin_id)
        )

        student = cursor.fetchone()

        if student:

            roll_no = student[0]

            cursor.execute(
                "DELETE FROM attendance WHERE admin_id=%s AND roll_no=%s",
                (admin_id, roll_no)
            )

            cursor.execute(
                "DELETE FROM students WHERE id=%s AND admin_id=%s",
                (student_id, admin_id)
            )

            conn.commit()

            import shutil

            folder = os.path.join(
                "dataset",
                username,
                roll_no
            )

            if os.path.exists(folder):
                shutil.rmtree(folder)

        cursor.close()
        conn.close()
        return redirect(url_for("manage_students"))

    # ---------------- UPDATE ----------------
    if request.method == "POST":

        new_name = request.form["name"]
        new_roll = request.form["roll_no"]
        new_email = request.form["email"]
        new_branch = request.form["branch"]
        new_year = request.form["year"]

        cursor.execute(
            "SELECT roll_no FROM students WHERE id=%s AND admin_id=%s",
            (student_id, admin_id)
        )

        old_roll = cursor.fetchone()[0]

        cursor.execute("""
            UPDATE students
            SET
                name=%s,
                roll_no=%s,
                email=%s,
                branch=%s,
                year=%s
            WHERE id=%s AND admin_id=%s
        """, (
            new_name,
            new_roll,
            new_email,
            new_branch,
            new_year,
            student_id,
            admin_id
        ))

        conn.commit()
        cursor.close()
        conn.close()

        if old_roll != new_roll:

            old_path = os.path.join(
                "dataset",
                username,
                old_roll
            )

            new_path = os.path.join(
                "dataset",
                username,
                new_roll
            )

            if os.path.exists(old_path):
                os.rename(old_path, new_path)

        return redirect(url_for("manage_students"))

    cursor.execute("""
        SELECT
            id,
            name,
            roll_no,
            email,
            branch,
            year
        FROM students
        WHERE id=%s AND admin_id=%s
    """, (student_id, admin_id))

    student = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "edit_student.html",
        student=student
    )
# ---------------- BROWSER ATTENDANCE ----------------
@app.route("/browser_attendance")
@login_required
def browser_attendance():
    return render_template("browser_attendance.html")
@app.route("/recognize", methods=["POST"])
@login_required
def recognize():

    data = request.get_json()

    if not data or "image" not in data:
        return {
            "success": False,
            "message": "No image received."
        }

    try:

        image_data = data["image"].split(",")[1]

        image = Image.open(
            io.BytesIO(base64.b64decode(image_data))
        )

        frame = cv2.cvtColor(
            np.array(image),
            cv2.COLOR_RGB2BGR
        )

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

    username = session["username"]

    known_encodings, known_rolls = load_known_faces(username)

    if len(known_encodings) == 0:

        return {
            "success": False,
            "message": "No registered students."
        }

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    locations = face_recognition.face_locations(rgb)

    encodings = face_recognition.face_encodings(
        rgb,
        locations
    )

    if len(encodings) == 0:

        return {
            "success": False,
            "message": "No face detected."
        }

    face_encoding = encodings[0]

    distances = face_recognition.face_distance(
        known_encodings,
        face_encoding
    )

    best = np.argmin(distances)

    if distances[best] >= 0.45:

        return {
            "success": False,
            "message": "Unknown Face"
        }

    roll_no = known_rolls[best]

    today = datetime.now().strftime("%d-%m-%Y")

    attendance_marked = mark_attendance(
    roll_no,
    today
         )
     

    conn = get_db_connection()

    cursor = conn.cursor()

    cursor.execute(
    """
    SELECT name, roll_no
    FROM students
    WHERE admin_id=%s
    AND roll_no=%s
    """,
    (
        session["admin_id"],
        roll_no
    )
)

    result = cursor.fetchone()

    cursor.close()

    conn.close()

    if result:
     student_name = result[0]
     student_roll = result[1]
    else:
     student_name = roll_no
     student_roll = roll_no

    current_time = datetime.now().strftime("%H:%M:%S")

    if attendance_marked:
     return {
        "success": True,
        "message": f"""✅ Attendance Marked Successfully

👤 Name : {student_name}

🆔 Roll No : {student_roll}

🕒 Time : {current_time}"""
    }
    else:
      return {
        "success": False,
        "message": f"""⚠ Attendance already marked today.

👤 Name : {student_name}

🆔 Roll No : {student_roll}"""
    }
# ---------------- ATTENDANCE ----------------

@app.route('/attendance')
@login_required
def attendance():

    if not ENABLE_WEBCAM:
        return (
            "<h2>Live webcam attendance is disabled on this deployment.</h2>"
            "<p>A cloud server has no physical camera, so this feature only "
            "runs locally. Set the environment variable "
            "<code>ENABLE_WEBCAM=true</code> and run the app on a machine "
            "with a webcam to use it.</p>"
            f"<p><a href='{url_for('dashboard')}'>Back to dashboard</a></p>"
        )

    start_attendance()
    return redirect(url_for('view_attendance'))
# ---------------- LOAD KNOWN FACES ----------------
def load_known_faces(username):
    known_encodings = []
    known_rolls = []

    base_folder = f"dataset/{username}"

    if not os.path.exists(base_folder):
        return known_encodings, known_rolls

    for roll in os.listdir(base_folder):
        folder = os.path.join(base_folder, roll)

        if not os.path.isdir(folder):
            continue

        for img in os.listdir(folder):
            img_path = os.path.join(folder, img)

            try:
                image = face_recognition.load_image_file(img_path)
                encodings = face_recognition.face_encodings(image)

                if encodings:
                    known_encodings.append(encodings[0])
                    known_rolls.append(roll)

            except Exception:
                continue

    return known_encodings, known_rolls

def start_attendance():
    username = session['username']
    known_encodings = []
    known_rolls = []

    base_folder = f"dataset/{username}"

    if not os.path.exists(base_folder):
        return

    # Load all registered student faces
    for roll in os.listdir(base_folder):
        folder = os.path.join(base_folder, roll)

        for img in os.listdir(folder):
            img_path = os.path.join(folder, img)

            image = face_recognition.load_image_file(img_path)
            encodings = face_recognition.face_encodings(image)

            if len(encodings) > 0:
                known_encodings.append(encodings[0])
                known_rolls.append(roll)

    if len(known_encodings) == 0:
        return

    cap = cv2.VideoCapture(0)

    today = datetime.now().strftime("%d-%m-%Y")

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb)
        face_encodings = face_recognition.face_encodings(rgb, face_locations)

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):

            distances = face_recognition.face_distance(
                known_encodings,
                face_encoding
            )

            if len(distances) == 0:
                continue

            best = np.argmin(distances)

            if distances[best] < 0.45:

                roll_no = known_rolls[best]

                # Get student name
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT name
                    FROM students
                    WHERE admin_id=%s AND roll_no=%s
                    """,
                    (session["admin_id"], roll_no)
                )

                result = cursor.fetchone()
                cursor.close()
                conn.close()

                if result:
                    student_name = result[0]
                else:
                    student_name = roll_no

                # Mark attendance
                mark_attendance(roll_no, today)

                # Draw rectangle
                cv2.rectangle(
                    frame,
                    (left, top),
                    (right, bottom),
                    (0, 255, 0),
                    2
                )

                # Filled rectangle for text
                cv2.rectangle(
                    frame,
                    (left, top - 35),
                    (right, top),
                    (0, 255, 0),
                    cv2.FILLED
                )

                # Display Name
                cv2.putText(
                    frame,
                    student_name,
                    (left + 6, top - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )

                # Present message
                cv2.putText(
                    frame,
                    "Attendance Marked",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )

            else:

                cv2.rectangle(
                    frame,
                    (left, top),
                    (right, bottom),
                    (0, 0, 255),
                    2
                )

                cv2.rectangle(
                    frame,
                    (left, top - 35),
                    (right, top),
                    (0, 0, 255),
                    cv2.FILLED
                )

                cv2.putText(
                    frame,
                    "Unknown",
                    (left + 6, top - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )

        try:
            cv2.imshow("Face Recognition Attendance", frame)
        except cv2.error:
            # No display available (e.g. running inside a headless
            # container even with ENABLE_WEBCAM set) — stop cleanly
            # instead of crashing the request.
            break

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


def mark_attendance(roll_no, date):
    admin_id = session['admin_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM attendance WHERE admin_id=%s AND roll_no=%s AND date=%s",
        (admin_id, roll_no, date)
    )

    # Already marked today
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return False

    current_time = datetime.now().strftime("%H:%M:%S")

    cursor.execute(
        "INSERT INTO attendance (admin_id, roll_no, date, time) VALUES (%s, %s, %s, %s)",
        (admin_id, roll_no, date, current_time)
    )

    conn.commit()

    try:
        threading.Thread(
            target=playsound,
            args=("static/sounds/success.mp3",),
            daemon=True
        ).start()
    except Exception:
        pass

    cursor.close()
    conn.close()

    return True


# ---------------- VIEW ATTENDANCE ----------------

@app.route('/view_attendance', methods=['GET', 'POST'])
@login_required
def view_attendance():

    admin_id = session['admin_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    today = datetime.now()
    month = today.month
    year = today.year

    if request.method == "POST":
        month = int(request.form['month'])
        year = int(request.form['year'])

    # -----------------------
    # CALCULATE WORKING DAYS (Sunday excluded)
    # -----------------------
    if month == today.month and year == today.year:
        last_day = today.day
    else:
        last_day = calendar.monthrange(year, month)[1]

    total_days_month = 0
    for day in range(1, last_day + 1):
        if datetime(year, month, day).weekday() != 6:
            total_days_month += 1

    # -----------------------
    # GET STUDENTS
    # -----------------------
    cursor.execute("SELECT name, roll_no FROM students WHERE admin_id=%s", (admin_id,))
    students = cursor.fetchall()

    attendance_list = []
    month_str = f"{month:02d}-{year}"

    for name, roll_no in students:

        cursor.execute("""
            SELECT DISTINCT date FROM attendance
            WHERE admin_id=%s AND roll_no=%s AND date LIKE %s
        """, (admin_id, roll_no, "%" + month_str))

        month_dates = cursor.fetchall()

        present_month = 0
        for d in month_dates:
            try:
                date_obj = datetime.strptime(d[0], "%d-%m-%Y")
                if date_obj.weekday() != 6:
                    present_month += 1
            except Exception:
                pass

        # Percentage (max 100%)
        if total_days_month > 0:
            percentage = round((present_month / total_days_month) * 100, 2)
            percentage = min(percentage, 100)
        else:
            percentage = 0

        attendance_list.append(
            (
                name,
                roll_no,
                present_month,
                total_days_month,
                percentage
            )
        )

    cursor.close()
    conn.close()

    return render_template(
        "view_attendance.html",
        attendance=attendance_list,
        month=month,
        year=year,
        months=range(1, 13),
        years=range(2024, 2031)
    )


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
