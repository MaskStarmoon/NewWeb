from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
bcrypt = Bcrypt(app)

# Kunci rahasia untuk sesi (gantilah dengan nilai yang lebih aman)
app.secret_key = 'SvngFox'

# Variabel global untuk menyimpan waktu terakhir exp ditingkatkan
last_exp_increase = datetime.now()

# Tentukan folder tempat menyimpan foto profil
UPLOAD_FOLDER = 'static/profile_pics/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def create_table():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            password TEXT,
            level INTEGER,
            exp INTEGER,
            coins INTEGER DEFAULT 0,
            rank INTEGER DEFAULT 1,
            title TEXT DEFAULT 'Newbie',  -- Default title untuk peringkat 1
            profile_pic TEXT DEFAULT NULL,
            redeemed_codes TEXT DEFAULT NULL,
            last_check_in DATETIME DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

create_table()

# Ubah sesuai kebutuhan: 24 jam dalam satuan detik
CHECK_IN_INTERVAL = 24 * 60 * 60

@app.route('/daily_check_in')
def daily_check_in():
    if 'user_id' in session:
        user_id = session['user_id']

        # Cek apakah pengguna sudah melakukan check-in hari ini
        last_check_in_time = get_last_check_in_time(user_id)
        current_time = datetime.now()

        if last_check_in_time and current_time - last_check_in_time < timedelta(seconds=CHECK_IN_INTERVAL):
            flash('Anda sudah melakukan check-in dalam 24 jam terakhir.', 'info')
        else:
            # Berikan pengguna 10 exp dan 10 koin karena check-in
            give_daily_rewards(user_id)

            flash('Anda telah berhasil melakukan check-in harian! Anda mendapatkan 10 exp dan 10 koin.', 'success')

        return redirect(url_for('profile'))
    else:
        flash('Anda perlu masuk terlebih dahulu.', 'error')
        return redirect(url_for('login'))

def get_last_check_in_time(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT last_check_in FROM registrations WHERE id = ?', (user_id,))
    last_check_in_time = cursor.fetchone()
    conn.close()
    return last_check_in_time[0] if last_check_in_time else None

def give_daily_rewards(user_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Berikan pengguna 10 exp dan 10 koin
    cursor.execute('UPDATE registrations SET exp = exp + 10, coins = coins + 10, last_check_in = ? WHERE id = ?', (datetime.now(), user_id))

    conn.commit()
    conn.close()

# Rute lainnya di sini

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register_user():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO registrations (name, email, password, level, exp, coins) VALUES (?, ?, ?, ?, ?, ?)',
                       (name, email, hashed_password, 1, 0, 0))
        conn.commit()
        conn.close()

        flash('Pendaftaran berhasil. Sekarang Anda dapat masuk.', 'success')
        return redirect(url_for('home'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_user():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = get_user_by_email(email)

        try:
            if user and bcrypt.check_password_hash(user[3], password):
                session['user_id'] = user[0]
                flash('Login successful!', 'success')
                return redirect(url_for('profile'))
            else:
                flash('Email atau password salah. Silakan coba lagi.', 'error')
                return redirect(url_for('login'))
        except ValueError:
            flash('Invalid password or salt. Please try again.', 'error')
            return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' in session:
        user_id = session['user_id']

        # Cek dan tingkatkan exp jika sudah waktunya
        check_and_increase_exp(user_id)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, level, exp, coins, rank, title, profile_pic FROM registrations WHERE id = ?', (user_id,))
        user = cursor.fetchone()

        if request.method == 'POST':
            # Ambil file foto dari formulir
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']

                # Periksa apakah file diizinkan
                if file and allowed_file(file.filename):
                    # Generate nama unik dan aman untuk file
                    filename = secure_filename(file.filename)

                    # Simpan file di folder upload
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    # Update nama file foto profil di database
                    cursor.execute('UPDATE registrations SET profile_pic = ? WHERE id = ?', (filename, user_id))
                    conn.commit()

                    flash('Foto profil berhasil diunggah atau diubah.', 'success')
                else:
                    flash('Format file tidak diizinkan. Gunakan format: png, jpg, jpeg, atau gif.', 'error')
            else:
                flash('Gagal mengunggah atau mengubah foto profil.', 'error')

        conn.close()

        if user:
            return render_template('profile.html', user=user, user_id=user_id)
        else:
            flash('Pengguna tidak ditemukan.', 'error')
            return redirect(url_for('login'))
    else:
        flash('Anda perlu masuk terlebih dahulu.', 'error')
        return redirect(url_for('login'))

@app.route('/static/profile_pics', methods=['GET', 'POST'])
def update_profile_picture():
    if 'user_id' in session:
        user_id = session['user_id']

        # Implementasikan logika untuk mengupdate foto profil
        if request.method == 'POST':
            # Ambil file foto dari formulir
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']

                # Periksa apakah file diizinkan
                if file and allowed_file(file.filename):
                    # Generate nama unik dan aman untuk file
                    filename = secure_filename(file.filename)

                    # Simpan file di folder upload
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

                    # Update nama file foto profil di database
                    cursor.execute('UPDATE registrations SET profile_pic = ? WHERE id = ?', (filename, user_id))
                    conn.commit()

                    flash('Foto profil berhasil diunggah atau diubah.', 'success')
                else:
                    flash('Format file tidak diizinkan. Gunakan format: png, jpg, jpeg, atau gif.', 'error')
            else:
                flash('Gagal mengunggah atau mengubah foto profil.', 'error')

        return redirect(url_for('profile'))  # Ganti dengan URL yang sesuai

    flash('Anda perlu masuk terlebih dahulu.', 'error')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Anda telah keluar.', 'info')
    return redirect(url_for('home'))

@app.route('/search_user/<int:user_id>')
def search_user(user_id):
    if user_id == 0:
        return render_template('search.html')
    else:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, level, exp, coins, rank, title, profile_pic FROM registrations WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()

        if user:
            return render_template('search_result.html', user=user)
        else:
            flash('Akun tidak ditemukan.', 'error')
            return redirect(url_for('home'))

@app.route('/search')
def search():
    return render_template('search.html')

@app.route('/search', methods=['POST'])
def search_user_post():
    if request.method == 'POST':
        user_id = request.form['user_id']
        return redirect(url_for('search_user', user_id=user_id))

@app.route('/redeem')
def redeem():
    return render_template('redeem.html')

@app.route('/redeem', methods=['POST'])
def redeemed_codes():
    if request.method == 'POST':
        # Pastikan pengguna masuk sebelum dapat menebus hadiah
        if 'user_id' in session:
            user_id = session['user_id']

            # Lakukan validasi penebusan (misalnya, kode penebusan dari formulir)
            redeem_code = request.form.get('redeem_code')

            # Contoh: validasi kode penebusan
            if redeem_code == 'SECRET_CODE':
                conn = sqlite3.connect('database.db')
                cursor = conn.cursor()
                cursor.execute('SELECT exp, coins FROM registrations WHERE id = ?', (user_id,))
                user = cursor.fetchone()

                if user:
                    # Tambahkan hadiah ke pengguna
                    new_exp = user[0] + 100000
                    new_coins = user[1] + 100

                    # Perbarui nilai exp dan koin di database
                    cursor.execute('UPDATE registrations SET exp = ?, coins = ? WHERE id = ?', (new_exp, new_coins, user_id))
                    conn.commit()
                    conn.close()

                    flash('Anda telah berhasil menebus hadiah!', 'success')
                else:
                    flash('Gagal mendapatkan informasi pengguna.', 'error')
            else:
                flash('Kode penebusan tidak valid.', 'error')

            return redirect(url_for('profile'))  # Ganti dengan URL yang sesuai
        else:
            flash('Anda perlu masuk terlebih dahulu.', 'error')
            return redirect(url_for('login'))

def get_user_by_email(email):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM registrations WHERE email = ?', (email,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_title_by_rank(rank):
  titles = {
      1: 'Newbie',
      2: 'Pemula',
      3: 'Pemula Senior',
      4: 'Senior',
      5: 'Kapten',
      6: 'Pemimpin Kapten',
      7: 'Jenderal',
      8: 'Jenderal Besar',
      9: 'King',
      10: 'Emperor',
      11: 'Leluhur',
      12: 'Pencerahan Surgawi',
      # Menambahkan title untuk setiap peringkat setelah peringkat 12
      13: 'Human Immortal',
      14: 'Earth Immortal',
      15: 'Golden Immortal',
      16: 'Immortal Surgawi',
      17: 'Demigod',
      18: 'God'
      # Dan seterusnya sesuai kebutuhan
  }

  return titles.get(rank, 'Unknown')

# Fungsi check_and_increase_exp yang telah diperbarui

def check_and_increase_exp(user_id):
    global last_exp_increase

    # Hitung selisih waktu sejak terakhir exp ditingkatkan
    time_difference = datetime.now() - last_exp_increase
    minutes_difference = time_difference.total_seconds() / 60

    # Jika sudah 1 menit atau lebih, tingkatkan exp dan update waktu terakhir
    if minutes_difference >= 1:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT level, exp, coins, rank FROM registrations WHERE id = ?', (user_id,))
        user = cursor.fetchone()

        # Periksa apakah exp sudah mencapai ambang batas naik level
        if user and user[1] >= 100:
            new_level = user[0] + 1
            new_exp = user[1] - 100  # Sisa exp setelah naik level
            new_coins = user[2] + 10  # Contoh: Beri 10 koin setiap kali naik level

            # Reset level menjadi 0 dan tingkatkan peringkat ketika mencapai level 9
            if new_level == 9:
                new_level = 0
                new_rank = user[3] + 1  # Tingkatkan peringkat

                # Set title berdasarkan peringkat baru
                title = get_title_by_rank(new_rank)

                cursor.execute('UPDATE registrations SET rank = ?, title = ? WHERE id = ?', (new_rank, title, user_id))
            else:
                new_rank = user[3]
                title = get_title_by_rank(new_rank)

        else:
            new_level = user[0]
            new_exp = user[1] + 1  # Tingkatkan exp sebesar 1
            new_coins = user[2]  # Tidak ada perubahan pada koin
            new_rank = user[3]
            title = get_title_by_rank(new_rank)

        cursor.execute('UPDATE registrations SET exp = ?, level = ?, coins = ? WHERE id = ?', (new_exp, new_level, new_coins, user_id))
        conn.commit()
        conn.close()

        # Update waktu terakhir exp ditingkatkan
        last_exp_increase = datetime.now()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
