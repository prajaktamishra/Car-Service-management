from flask import Flask, render_template, request, redirect, url_for, session, flash 
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__,static_url_path='/static/')
app.secret_key = 'your_secret_key'

def create_tables():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            available INTEGER DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY,
            model TEXT,
            plate_number TEXT UNIQUE,
            seats INTEGER,
            available INTEGER DEFAULT 1       
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY,
            origin TEXT,
            destination TEXT,
            distance REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            driver_id INTEGER,
            car_id INTEGER,
            pickup_location TEXT,
            destination TEXT,
            pickup_time TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (driver_id) REFERENCES drivers(id),
            FOREIGN KEY (car_id) REFERENCES cars(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cars_renting (
            id INTEGER PRIMARY KEY,
            model TEXT,
            plate_number TEXT UNIQUE,
            seats INTEGER,
            available INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS car_bookings (
            id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            car_model TEXT,
            plate_number TEXT,
            pickup_location TEXT,
            pickup_time TEXT,
            days INTEGER
        )
    ''')

    conn.commit()
    conn.close()
create_tables()

def is_logged_in():
    return 'username' in session

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if login_user(username, password):
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if len(username) < 2:
            flash('Username must be at least 2 characters long', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
        elif signup_user(username, password):
            flash('You have successfully signed up', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already exists', 'error')
    return render_template('signup.html')

def login_user(username, password):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cursor.fetchone()
    conn.close()
    if user and check_password_hash(user[2], password):
        return True
    return False

def signup_user(username, password):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

@app.route('/dashboard')
def dashboard():
    if is_logged_in():
        return render_template('dashboard.html', username=session['username'])
    else:
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

def get_driver_details():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, phone FROM drivers WHERE available = 1 LIMIT 1")
    driver_data = cursor.fetchall()[0]
    if driver_data:
        driver_name= driver_data[0]
        phone = driver_data[1]
        conn.close()
        return driver_name, phone
    else:
        conn.close()
        return None, None

def get_car_details(seats):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT plate_number FROM cars WHERE available = 1 AND seats = ? ORDER BY RANDOM() LIMIT 1", (seats,))
    car_number_plate = cursor.fetchone()[0]
    conn.close()
    return car_number_plate

@app.route('/book_taxi', methods=['GET', 'POST'])
def book_taxi():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        pickup = request.form['pickup_location']
        destination = request.form['destination']
        time = request.form['time']
        seats = request.form['seats']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute("INSERT INTO customers (name, phone) VALUES (?, ?)", (name, phone))
        conn.commit()

        cursor.execute("SELECT last_insert_rowid()")
        customer_id = cursor.fetchone()[0]

        cursor.execute("SELECT id, name, phone FROM drivers WHERE available = 1 LIMIT 1")
        driver_data = cursor.fetchone()
        if driver_data:
            driver_id, driver_name, driver_phone = driver_data

            cursor.execute("SELECT id, plate_number FROM cars WHERE seats = ? AND available = 1 LIMIT 1", (seats,))
            car_data = cursor.fetchone()
            if car_data:
                car_id, car_plate_number = car_data
            
                cursor.execute("SELECT distance, rate FROM routes WHERE origin = ? AND destination = ?", (pickup, destination))
                route_data = cursor.fetchone()
                if route_data:
                    distance, rate = route_data

                    cursor.execute("INSERT INTO bookings (customer_id, driver_id, car_id, pickup_location, destination, pickup_time) VALUES (?, ?, ?, ?, ?, ?)",
                                    (customer_id, driver_id, car_id, pickup, destination, time))
                    conn.commit()

                    cursor.execute("UPDATE drivers SET available = 0 WHERE id = ?", (driver_id,))
                    conn.commit()

                    cursor.execute("UPDATE cars SET available = 0 WHERE id = ?", (car_id,))
                    conn.commit()
                    conn.close()

                    bill_amount = distance * rate

                    booking_details = {
                        'driver_name': driver_name,
                        'driver_phone': driver_phone,
                        'car_plate_number': car_plate_number,
                        'distance': distance,
                        'bill_amount': bill_amount
                    }

                    return render_template('book_taxi.html', result=booking_details)

    return render_template('book_taxi.html', result=None)

@app.route('/rent_car', methods=['GET', 'POST'])
def rent_car():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        seats = request.form['seats']
        pickup_location = request.form['pickup_location']
        pickup_time = request.form['pickup_time']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute("SELECT id, model, plate_number FROM cars_renting WHERE seats = ? AND available = 1", (seats,))
        car_data = cursor.fetchone()

        if car_data:
            car_id, model, plate_number = car_data
            cursor.execute("INSERT INTO car_bookings (name, phone, car_model, plate_number, pickup_location, pickup_time) VALUES (?, ?, ?, ?, ?, ?)",
                            (name, phone, model, plate_number, pickup_location, pickup_time))
            conn.commit()
            conn.close()

            session['car_id'] = car_id
            session['car_model'] = model
            session['car_plate_number'] = plate_number
            session['name'] = name
            session['phone'] = phone
            session['pickup_location'] = pickup_location
            session['pickup_time'] = pickup_time

            return redirect(url_for('rental_confirmation'))

    return render_template('rent_car.html')

@app.route('/rental_confirmation')
def rental_confirmation():
    car_id = session.get('car_id')
    car_model = session.get('car_model')
    car_plate_number = session.get('car_plate_number')
    name = session.get('name')
    phone = session.get('phone')
    pickup_location = session.get('pickup_location')
    pickup_time = session.get('pickup_time')

    return render_template('rental_confirmation.html', car_id=car_id, car_model=car_model, car_plate_number=car_plate_number, name=name, phone=phone, pickup_location=pickup_location, pickup_time=pickup_time)
if __name__ == '__main__':
    app.run(debug=True)
