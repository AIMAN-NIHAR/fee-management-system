from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

mysql = MySQL(app)

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()

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

    cur = mysql.connection.cursor()

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

    cur.close()

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

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM students")
    students = cur.fetchall()
    cur.close()

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

        cur = mysql.connection.cursor()

        try:
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'student')",
                        (username, password))
            user_id = cur.lastrowid

            cur.execute("""INSERT INTO students (user_id, full_name, roll_number, department, semester)
                            VALUES (%s, %s, %s, %s, %s)""",
                        (user_id, full_name, roll_number, department, semester))

            mysql.connection.commit()
            flash('Student added successfully!')
            return redirect(url_for('manage_students'))

        except Exception as e:
            mysql.connection.rollback()
            error_msg = str(e)

            if 'roll_number' in error_msg:
                flash('This Roll Number is already used by another student. Please use a different one.')
            elif 'username' in error_msg:
                flash('This Username is already taken. Please choose a different username.')
            else:
                flash('Something went wrong. Please check your input and try again.')

            return redirect(url_for('add_student'))

        finally:
            cur.close()

    return render_template('add_student.html')

@app.route('/admin/students/edit/<int:student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        full_name = request.form['full_name']
        roll_number = request.form['roll_number']
        department = request.form['department']
        semester = request.form['semester']

        cur.execute("""UPDATE students SET full_name=%s, roll_number=%s, department=%s, semester=%s
                        WHERE id=%s""",
                    (full_name, roll_number, department, semester, student_id))
        mysql.connection.commit()
        cur.close()

        flash('Student updated successfully!')
        return redirect(url_for('manage_students'))

    cur.execute("SELECT * FROM students WHERE id = %s", (student_id,))
    student = cur.fetchone()
    cur.close()

    if not student:
        flash('Student not found.')
        return redirect(url_for('manage_students'))

    return render_template('edit_student.html', student=student)

@app.route('/admin/students/delete/<int:student_id>')
def delete_student(student_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT user_id FROM students WHERE id = %s", (student_id,))
    result = cur.fetchone()

    if result:
        user_id = result[0]
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        mysql.connection.commit()
        flash('Student deleted successfully!')
    else:
        flash('Student not found.')

    cur.close()
    return redirect(url_for('manage_students'))

@app.route('/admin/fees', methods=['GET', 'POST'])
def assign_fees():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        student_id = request.form['student_id']
        total_amount = request.form['total_amount']
        due_date = request.form['due_date']

        cur.execute("""INSERT INTO fees (student_id, total_amount, due_date, status)
                        VALUES (%s, %s, %s, 'unpaid')""",
                    (student_id, total_amount, due_date))
        mysql.connection.commit()
        cur.close()

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

    cur.close()

    return render_template('assign_fees.html', students=students, fees=fees)

@app.route('/admin/fees/slip/<int:fee_id>')
def fee_slip(fee_id):
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT fees.id, fees.total_amount, fees.due_date, fees.status, students.id,
               students.full_name, students.roll_number, students.department, students.semester
        FROM fees
        JOIN students ON fees.student_id = students.id
        WHERE fees.id = %s
    """, (fee_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        flash('Fee record not found.')
        return redirect(url_for('assign_fees'))

    fee = (row[0], row[1], row[2], row[3])
    student = (row[4], None, row[5], row[6], row[7], row[8])

    cur.execute("SELECT amount_paid, payment_date FROM payments WHERE fee_id = %s ORDER BY payment_date", (fee_id,))
    payments = cur.fetchall()

    total_paid = sum(float(p[0]) for p in payments)
    balance = float(fee[1]) - total_paid

    cur.close()

    return render_template('fee_slip.html', fee=fee, student=student, payments=payments,
                            total_paid=total_paid, balance=balance)

@app.route('/admin/payments', methods=['GET', 'POST'])
def record_payments():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        fee_id = request.form['fee_id']
        amount_paid = float(request.form['amount_paid'])
        payment_date = request.form['payment_date']

        cur.execute("""INSERT INTO payments (fee_id, amount_paid, payment_date)
                        VALUES (%s, %s, %s)""",
                    (fee_id, amount_paid, payment_date))

        cur.execute("SELECT total_amount FROM fees WHERE id = %s", (fee_id,))
        total_amount = float(cur.fetchone()[0])

        cur.execute("SELECT COALESCE(SUM(amount_paid), 0) FROM payments WHERE fee_id = %s", (fee_id,))
        total_paid = float(cur.fetchone()[0])

        if total_paid >= total_amount:
            new_status = 'paid'
        elif total_paid > 0:
            new_status = 'partial'
        else:
            new_status = 'unpaid'

        cur.execute("UPDATE fees SET status = %s WHERE id = %s", (new_status, fee_id))

        mysql.connection.commit()
        cur.close()

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

    cur.close()

    last_fee_id = request.args.get('last_fee_id')

    return render_template('record_payments.html', unpaid_fees=unpaid_fees, payments=payments, last_fee_id=last_fee_id)

@app.route('/student/dashboard')
def student_dashboard():
    if 'role' not in session or session['role'] != 'student':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM students WHERE user_id = %s", (session['user_id'],))
    student = cur.fetchone()

    fees = []
    payments = []

    if student:
        student_id = student[0]

        cur.execute("SELECT id, total_amount, due_date, status FROM fees WHERE student_id = %s ORDER BY due_date ASC", (student_id,))
        fees = cur.fetchall()

        cur.execute("""
            SELECT payments.amount_paid, payments.payment_date
            FROM payments
            JOIN fees ON payments.fee_id = fees.id
            WHERE fees.student_id = %s
            ORDER BY payments.payment_date DESC
        """, (student_id,))
        payments = cur.fetchall()

    cur.close()

    return render_template('student_dashboard.html', student=student, fees=fees, payments=payments)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    import webbrowser
    webbrowser.open('http://127.0.0.1:5000')
    app.run(debug=True)