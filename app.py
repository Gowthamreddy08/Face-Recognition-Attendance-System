from playsound import playsound
import threading
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import cv2
import face_recognition
import numpy as np
from datetime import datetime, timedelta
import calendar
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "face_attendance_secret_key"

# ---------------- EMAIL CONFIG ----------------

EMAIL_ADDRESS = "yourgmail@gmail.com"
EMAIL_PASSWORD = "your_16_character_app_password"

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # ---------------- ADMIN TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # ---------------- STUDENTS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        name TEXT,
        roll_no TEXT,
        email TEXT,
        branch TEXT,
        year TEXT,
        UNIQUE(admin_id, roll_no)
    )
    """)

    # Add email column automatically for old databases
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        # Column already exists
        pass

    # ---------------- ATTENDANCE TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        roll_no TEXT,
        date TEXT,
        time TEXT
    )
    """)

    conn.commit()
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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM admin")
    count = cursor.fetchone()[0]

    conn.close()

    if count == 0:
        return redirect(url_for("signup"))

    return redirect(url_for("login"))


# ---------------- SIGNUP ----------------

@app.route("/signup", methods=["GET", "POST"])
def signup():

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        cursor.execute(
            "SELECT id FROM admin WHERE username=?",
            (username,)
        )

        if cursor.fetchone():

            conn.close()

            return render_template(
                "signup.html",
                error="Username already exists."
            )

        password = generate_password_hash(password)

        cursor.execute(
            "INSERT INTO admin(username,password) VALUES(?,?)",
            (username, password)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    conn.close()

    return render_template("signup.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    error = None

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id,password FROM admin WHERE username=?",
            (username,)
        )

        row = cursor.fetchone()

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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM students WHERE admin_id=?",
        (admin_id,)
    )

    total_students = cursor.fetchone()[0]

    today = datetime.now().strftime("%d-%m-%Y")

    cursor.execute(
        """
        SELECT COUNT(DISTINCT roll_no)
        FROM attendance
        WHERE admin_id=? AND date=?
        """,
        (admin_id, today)
    )

    today_attendance = cursor.fetchone()[0]

    absent_students = total_students - today_attendance

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

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        try:

            cursor.execute(
                """
                INSERT INTO students
                (admin_id,name,roll_no,email,branch,year)
                VALUES(?,?,?,?,?,?)
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

        except sqlite3.IntegrityError:

            conn.close()

            return "Roll Number already exists."

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

    conn = sqlite3.connect("database.db")
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
        WHERE admin_id=?
        ORDER BY name
    """, (admin_id,))

    students = cursor.fetchall()

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

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # ---------------- DELETE ----------------
    if request.method == "POST" and request.form.get("action") == "delete":

        cursor.execute(
            "SELECT roll_no FROM students WHERE id=? AND admin_id=?",
            (student_id, admin_id)
        )

        student = cursor.fetchone()

        if student:

            roll_no = student[0]

            cursor.execute(
                "DELETE FROM attendance WHERE admin_id=? AND roll_no=?",
                (admin_id, roll_no)
            )

            cursor.execute(
                "DELETE FROM students WHERE id=? AND admin_id=?",
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
            "SELECT roll_no FROM students WHERE id=? AND admin_id=?",
            (student_id, admin_id)
        )

        old_roll = cursor.fetchone()[0]

        cursor.execute("""
            UPDATE students
            SET
                name=?,
                roll_no=?,
                email=?,
                branch=?,
                year=?
            WHERE id=? AND admin_id=?
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
        WHERE id=? AND admin_id=?
    """, (student_id, admin_id))

    student = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_student.html",
        student=student
    )
# ---------------- ATTENDANCE ----------------
@app.route('/attendance')
@login_required
def attendance():
    start_attendance()
    return redirect(url_for('view_attendance'))

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
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT name
                    FROM students
                    WHERE admin_id=? AND roll_no=?
                    """,
                    (session["admin_id"], roll_no)
                )

                result = cursor.fetchone()
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

        cv2.imshow("Face Recognition Attendance", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

def mark_attendance(roll_no, date):
    admin_id = session['admin_id']

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM attendance WHERE admin_id=? AND roll_no=? AND date=?",
        (admin_id, roll_no, date)
    )

    if not cursor.fetchone():

        time = datetime.now().strftime("%H:%M:%S")

        cursor.execute(
            "INSERT INTO attendance (admin_id, roll_no, date, time) VALUES (?, ?, ?, ?)",
            (admin_id, roll_no, date, time)
        )

        conn.commit()

        # Play success sound
        threading.Thread(
            target=playsound,
            args=("static/sounds/success.mp3",),
            daemon=True
        ).start()

    conn.close()

# ---------------- VIEW ATTENDANCE ----------------
@app.route('/view_attendance', methods=['GET', 'POST'])
@login_required
def view_attendance():

    admin_id = session['admin_id']

    conn = sqlite3.connect("database.db")
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
    cursor.execute("SELECT name, roll_no FROM students WHERE admin_id=?",(admin_id,))
    students = cursor.fetchall()

    attendance_list = []
    month_str = f"{month:02d}-{year}"

    for name, roll_no in students:

        cursor.execute("""
            SELECT DISTINCT date FROM attendance
            WHERE admin_id=? AND roll_no=? AND date LIKE ?
        """, (admin_id, roll_no, "%" + month_str))

        month_dates = cursor.fetchall()

        present_month = 0
        for d in month_dates:
            try:
                date_obj = datetime.strptime(d[0], "%d-%m-%Y")
                if date_obj.weekday() != 6:
                    present_month += 1
            except:
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
    app.run(debug=True)