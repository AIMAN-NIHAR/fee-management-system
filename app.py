from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import Config
from database import get_db, init_app

import sys
import os
import threading
import shutil
import glob
from datetime import datetime
from flask import send_file

def resource_path(relative_path):
    """Get correct path whether running normally or as a packaged .exe"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

app = Flask(__name__, template_folder=resource_path('templates'), static_folder=resource_path('static'))


def backup_database():
    """Silently copies the database into a backups folder every time the app starts."""
    try:
        db_path = app.config['DATABASE']
        if not os.path.exists(db_path):
            return

        backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_path = os.path.join(backup_dir, f'fee_management_{timestamp}.db')
        shutil.copy2(db_path, backup_path)

        backups = sorted(glob.glob(os.path.join(backup_dir, 'fee_management_*.db')))
        for old_backup in backups[:-15]:
            os.remove(old_backup)

    except Exception:
        pass  # Never let a backup failure crash the app


app.config.from_object(Config)
init_app(app)  # makes sure the SQLite connection closes after each request

backup_database()


@app.route('/')
def home():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cur.fetchone()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]

            if user[3] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) FROM students")
    total_students = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(total_amount), 0) FROM fees")
    total_fees = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM payments")
    total_payments = cur.fetchone()[0]

    cur.execute("""
        SELECT students.full_name, students.roll_number, fees.total_amount, fees.status
        FROM fees
        JOIN students ON fees.student_id = students.id
        WHERE fees.status IN ('unpaid', 'partial')
        ORDER BY fees.due_date ASC
    """)
    pending_fees = cur.fetchall()

    cur.execute("SELECT full_name, roll_number, department FROM students ORDER BY id DESC LIMIT 5")
    recent_students = cur.fetchall()

    cur.execute("""
        SELECT students.full_name, payments.amount_paid, payments.payment_date
        FROM payments
        JOIN fees ON payments.fee_id = fees.id
        JOIN students ON fees.student_id = students.id
        ORDER BY payments.payment_date DESC LIMIT 5
    """)
    recent_payments = cur.fetchall()

    return render_template('admin_dashboard.html',
                            total_students=total_students,
                            total_fees=total_fees,
                            total_payments=total_payments,
                            pending_fees=pending_fees,
                            recent_students=recent_students,
                            recent_payments=recent_payments)


@app.route('/admin/students')
def manage_students():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM students")
    students = cur.fetchall()

    return render_template('manage_students.html', students=students)


@app.route('/admin/students/add', methods=['GET', 'POST'])
def add_student():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        full_name = request.form['full_name']
        roll_number = request.form['roll_number']
        department = request.form['department']
        semester = request.form['semester']
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        cur = db.cursor()

        try:
            cur.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 'student')",
                        (username, password))
            user_id = cur.lastrowid

            cur.execute("""INSERT INTO students (user_id, full_name, roll_number, department, semester)
                            VALUES (?, ?, ?, ?, ?)""",
                        (user_id, full_name, roll_number, department, semester))

            db.commit()
            flash('Student added successfully!')
            return redirect(url_for('manage_students'))

        except Exception as e:
            db.rollback()
            error_msg = str(e)

            if 'roll_number' in error_msg:
                flash('This Roll Number is already used by another student. Please use a different one.')
            elif 'username' in error_msg:
                flash('This Username is already taken. Please choose a different username.')
            else:
                flash('Something went wrong. Please check your input and try again.')

            return redirect(url_for('add_student'))

    return render_template('add_student.html')


@app.route('/admin/students/edit/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()

    if request.method == 'POST':
        full_name = request.form['full_name']
        roll_number = request.form['roll_number']
        department = request.form['department']
        semester = request.form['semester']

        cur.execute("""UPDATE students SET full_name=?, roll_number=?, department=?, semester=?
                        WHERE id=?""",
                    (full_name, roll_number, department, semester, student_id))
        db.commit()

        flash('Student updated successfully!')
        return redirect(url_for('manage_students'))

    cur.execute("SELECT * FROM students WHERE id = ?", (student_id,))
    student = cur.fetchone()

    if not student:
        flash('Student not found.')
        return redirect(url_for('manage_students'))

    return render_template('edit_student.html', student=student)


@app.route('/admin/students/delete/<int:student_id>')
def delete_student(student_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT user_id FROM students WHERE id = ?", (student_id,))
    result = cur.fetchone()

    if result:
        user_id = result[0]
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        flash('Student deleted successfully!')
    else:
        flash('Student not found.')

    return redirect(url_for('manage_students'))


@app.route('/admin/fees', methods=['GET', 'POST'])
def assign_fees():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()

    if request.method == 'POST':
        student_id = request.form['student_id']
        total_amount = request.form['total_amount']
        due_date = request.form['due_date']

        cur.execute("""INSERT INTO fees (student_id, total_amount, due_date, status)
                        VALUES (?, ?, ?, 'unpaid')""",
                    (student_id, total_amount, due_date))
        db.commit()

        flash('Fee assigned successfully!')
        return redirect(url_for('assign_fees'))

    cur.execute("SELECT * FROM students")
    students = cur.fetchall()

    cur.execute("""
        SELECT fees.id, students.full_name, fees.total_amount, fees.due_date, fees.status
        FROM fees
        JOIN students ON fees.student_id = students.id
        ORDER BY fees.id DESC
    """)
    fees = cur.fetchall()

    return render_template('assign_fees.html', students=students, fees=fees)


@app.route('/admin/fees/slip/<int:fee_id>')
def fee_slip(fee_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT fees.id, fees.total_amount, fees.due_date, fees.status, students.id,
               students.full_name, students.roll_number, students.department, students.semester
        FROM fees
        JOIN students ON fees.student_id = students.id
        WHERE fees.id = ?
    """, (fee_id,))
    row = cur.fetchone()

    if not row:
        flash('Fee record not found.')
        return redirect(url_for('assign_fees'))

    fee = (row[0], row[1], row[2], row[3])
    student = (row[4], None, row[5], row[6], row[7], row[8])

    cur.execute("SELECT amount_paid, payment_date FROM payments WHERE fee_id = ? ORDER BY payment_date", (fee_id,))
    payments = cur.fetchall()

    total_paid = sum(float(p[0]) for p in payments)
    balance = float(fee[1]) - total_paid

    return render_template('fee_slip.html', fee=fee, student=student, payments=payments,
                            total_paid=total_paid, balance=balance)


@app.route('/admin/payments', methods=['GET', 'POST'])
def record_payments():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()

    if request.method == 'POST':
        fee_id = request.form['fee_id']
        amount_paid = float(request.form['amount_paid'])
        payment_date = request.form['payment_date']

        cur.execute("""INSERT INTO payments (fee_id, amount_paid, payment_date)
                        VALUES (?, ?, ?)""",
                    (fee_id, amount_paid, payment_date))

        cur.execute("SELECT total_amount FROM fees WHERE id = ?", (fee_id,))
        total_amount = float(cur.fetchone()[0])

        cur.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM payments WHERE fee_id = ?", (fee_id,))
        total_paid = float(cur.fetchone()[0])

        if total_paid >= total_amount:
            new_status = 'paid'
        elif total_paid > 0:
            new_status = 'partial'
        else:
            new_status = 'unpaid'

        cur.execute("UPDATE fees SET status = ? WHERE id = ?", (new_status, fee_id))

        db.commit()

        flash('Payment recorded successfully!')
        return redirect(url_for('record_payments', last_fee_id=fee_id))

    cur.execute("""
        SELECT fees.id, students.full_name, fees.total_amount, fees.status
        FROM fees
        JOIN students ON fees.student_id = students.id
        WHERE fees.status IN ('unpaid', 'partial')
        ORDER BY fees.id DESC
    """)
    unpaid_fees = cur.fetchall()

    cur.execute("""
        SELECT students.full_name, payments.amount_paid, payments.payment_date, fees.id
        FROM payments
        JOIN fees ON payments.fee_id = fees.id
        JOIN students ON fees.student_id = students.id
        ORDER BY payments.payment_date DESC
    """)
    payments = cur.fetchall()

    last_fee_id = request.args.get('last_fee_id')

    return render_template('record_payments.html', unpaid_fees=unpaid_fees, payments=payments, last_fee_id=last_fee_id)

@app.route('/admin/backup')
def download_backup():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    db_path = app.config['DATABASE']
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    download_name = f'fee_management_backup_{timestamp}.db'

    return send_file(db_path, as_attachment=True, download_name=download_name)

@app.route('/admin/change_password', methods=['GET', 'POST'])
def change_password():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT password FROM users WHERE id = ?", (session['user_id'],))
        row = cur.fetchone()

        if not row or row[0] != current_password:
            flash('Current password is incorrect.')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match.')
            return redirect(url_for('change_password'))

        if len(new_password) < 4:
            flash('New password is too short.')
            return redirect(url_for('change_password'))

        cur.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, session['user_id']))
        db.commit()

        flash('Password changed successfully!')
        return redirect(url_for('admin_dashboard'))

    return render_template('change_password.html')


@app.route('/student/dashboard')
def student_dashboard():
    if 'role' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT * FROM students WHERE user_id = ?", (session['user_id'],))
    student = cur.fetchone()

    fees = []
    payments = []

    if student:
        student_id = student[0]

        # Each fee row now also includes paid_amount (fee[4]), so the
        # template can calculate "remaining" automatically without a
        # separate query.
        cur.execute("""
            SELECT fees.id, fees.total_amount, fees.due_date, fees.status,
                   COALESCE(SUM(payments.amount_paid), 0) AS paid_amount
            FROM fees
            LEFT JOIN payments ON payments.fee_id = fees.id
            WHERE fees.student_id = ?
            GROUP BY fees.id
            ORDER BY fees.due_date ASC
        """, (student_id,))
        fees = cur.fetchall()

        cur.execute("""
            SELECT payments.amount_paid, payments.payment_date
            FROM payments
            JOIN fees ON payments.fee_id = fees.id
            WHERE fees.student_id = ?
            ORDER BY payments.payment_date DESC
        """, (student_id,))
        payments = cur.fetchall()

    return render_template('student_dashboard.html', student=student, fees=fees, payments=payments)

@app.route('/exit_app')
def exit_app():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    def shutdown():
        os._exit(0)

    threading.Timer(1.0, shutdown).start()
    return render_template('exit.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000')
    app.run(debug=False, use_reloader=False)