from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
import uuid
from contextlib import contextmanager
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Secret key for sessions (admin login). Set FLASK_SECRET_KEY in your
# environment for production; this fallback is fine for local testing only.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-only-change-me')

# Simple admin password gate for destructive/admin actions (delete team,
# delete player, finalize sale). Set ADMIN_PASSWORD in your environment.
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB per upload
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

DB_PATH = 'npl.db'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    """Yields a connection and guarantees it's closed even on error."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                base_price REAL,
                role TEXT,
                image_filename TEXT,
                sold INTEGER DEFAULT 0,
                team_id INTEGER,
                sold_price REAL,
                FOREIGN KEY(team_id) REFERENCES teams(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL,
                captain TEXT,
                phone TEXT,
                logo_filename TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auctions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                team_id INTEGER,
                bid_amount REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(player_id) REFERENCES players(id),
                FOREIGN KEY(team_id) REFERENCES teams(id)
            )
        ''')

        # --- Backward-compatible migrations for DBs created by older code ---
        cursor.execute("PRAGMA table_info(players)")
        player_columns = [info[1] for info in cursor.fetchall()]
        if 'sold' not in player_columns:
            cursor.execute("ALTER TABLE players ADD COLUMN sold INTEGER DEFAULT 0")
        if 'team_id' not in player_columns:
            cursor.execute("ALTER TABLE players ADD COLUMN team_id INTEGER")
        if 'sold_price' not in player_columns:
            cursor.execute("ALTER TABLE players ADD COLUMN sold_price REAL")

        conn.commit()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage):
    """Validates and saves an uploaded image with a collision-proof name.

    Returns the stored filename, or None if no valid file was provided.
    Raises ValueError if a file was provided but has a disallowed extension.
    """
    if not file_storage or file_storage.filename == '':
        return None

    original_name = secure_filename(file_storage.filename)
    if not allowed_file(original_name):
        raise ValueError('Only image files (png, jpg, jpeg, gif, webp) are allowed.')

    ext = original_name.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
    return unique_name


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Please log in as admin to do that.')
            return redirect(url_for('admin_login', next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template('index.html')


@app.route('/player', methods=['GET', 'POST'])
def player():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        base_price = request.form.get('base_price', '').strip()
        role = request.form.get('role', '').strip()

        if not name or not phone or not base_price or not role:
            flash('Please fill in all required fields.')
            return render_template('player.html')

        try:
            image_filename = save_upload(request.files.get('photo'))
        except ValueError as e:
            flash(str(e))
            return render_template('player.html')

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO players(name, phone, base_price, role, image_filename)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, phone, base_price, role, image_filename))
            conn.commit()

        return redirect(url_for('home'))
    return render_template('player.html')


@app.route('/captain', methods=['GET', 'POST'])
def captain():
    if request.method == 'POST':
        team_name = request.form.get('team_name', '').strip()
        phone = request.form.get('phone', '').strip()
        captain_name = request.form.get('captain', '').strip()

        if not team_name or not phone or not captain_name:
            flash('Please fill in all required fields.')
            return render_template('captain.html')

        try:
            logo_filename = save_upload(request.files.get('logo'))
        except ValueError as e:
            flash(str(e))
            return render_template('captain.html')

        with get_db() as conn:
            cursor = conn.cursor()
            # Column order is (team_name, captain, phone, logo_filename) -
            # the values below must line up with that exact order.
            cursor.execute('''
                INSERT INTO teams(team_name, captain, phone, logo_filename)
                VALUES (?, ?, ?, ?)
            ''', (team_name, captain_name, phone, logo_filename))
            conn.commit()

        return redirect(url_for('home'))
    return render_template('captain.html')


@app.route('/teams')
def teams():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, team_name, captain, phone, logo_filename FROM teams")
        all_teams = cursor.fetchall()
    return render_template('team.html', teams=all_teams)


@app.route('/register_player')
def register_player():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, phone, base_price, role, image_filename, sold
            FROM players
        ''')
        all_players = cursor.fetchall()
    return render_template('view.html', players=all_players)


# ---------------------------------------------------------------------------
# Admin login (guards delete + finalize actions)
# ---------------------------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            next_url = request.args.get('next') or url_for('home')
            return redirect(next_url)
        flash('Incorrect password.')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('home'))


# ---------------------------------------------------------------------------
# Admin-only actions
# ---------------------------------------------------------------------------

@app.route('/delete_team/<int:team_id>', methods=['POST'])
@admin_required
def delete_team(team_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT logo_filename FROM teams WHERE id=?", (team_id,))
        row = cursor.fetchone()
        if row and row[0]:
            logo_path = os.path.join(app.config['UPLOAD_FOLDER'], row[0])
            if os.path.exists(logo_path):
                os.remove(logo_path)
        cursor.execute("DELETE FROM teams WHERE id=?", (team_id,))
        conn.commit()
    return redirect(url_for('teams'))


@app.route('/delete_player/<int:player_id>', methods=['POST'])
@admin_required
def delete_player(player_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT image_filename FROM players WHERE id=?", (player_id,))
        row = cursor.fetchone()
        if row and row[0]:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], row[0])
            if os.path.exists(image_path):
                os.remove(image_path)
        cursor.execute("DELETE FROM players WHERE id=?", (player_id,))
        conn.commit()
    return redirect(url_for('register_player'))


# ---------------------------------------------------------------------------
# Auction
# ---------------------------------------------------------------------------

@app.route('/auction')
def auction():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, base_price, role, image_filename
            FROM players WHERE sold = 0 ORDER BY id LIMIT 1
        ''')
        current_player = cursor.fetchone()

        cursor.execute("SELECT id, team_name FROM teams")
        all_teams = cursor.fetchall()

    if not current_player:
        return render_template('auction_done.html')

    return render_template('auction_live.html', player=current_player, teams=all_teams)


@app.route('/current_bid/<int:player_id>')
def current_bid(player_id):
    """Polled by the auction page so every bidder sees the same live state."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT auctions.bid_amount, teams.team_name
            FROM auctions
            JOIN teams ON teams.id = auctions.team_id
            WHERE auctions.player_id = ?
            ORDER BY auctions.bid_amount DESC, auctions.timestamp DESC
            LIMIT 1
        ''', (player_id,))
        row = cursor.fetchone()

    if row:
        return {'bid_amount': row[0], 'team_name': row[1]}
    return {'bid_amount': None, 'team_name': None}


@app.route('/bid', methods=['POST'])
def bid():
    data = request.get_json(silent=True) or {}
    player_id = data.get('player_id')
    team_id = data.get('team_id')
    bid_amount = data.get('bid_amount')

    if not player_id or not team_id or bid_amount is None:
        return {'status': 'error', 'message': 'Missing data'}, 400

    try:
        player_id = int(player_id)
        team_id = int(team_id)
        bid_amount = float(bid_amount)
    except (TypeError, ValueError):
        return {'status': 'error', 'message': 'Invalid data'}, 400

    with get_db() as conn:
        cursor = conn.cursor()

        # Reject a bid that doesn't beat the current highest bid for this player.
        cursor.execute('''
            SELECT MAX(bid_amount) FROM auctions WHERE player_id = ?
        ''', (player_id,))
        highest = cursor.fetchone()[0]
        if highest is not None and bid_amount <= highest:
            return {'status': 'error', 'message': 'Bid must be higher than the current bid'}, 400

        cursor.execute('''
            INSERT INTO auctions(player_id, team_id, bid_amount) VALUES (?, ?, ?)
        ''', (player_id, team_id, bid_amount))
        conn.commit()

    return {'status': 'success'}


@app.route('/finalize/<int:player_id>', methods=['POST'])
@admin_required
def finalize(player_id):
    """Sells the player to whoever actually placed the highest bid.

    The winning team/amount is derived from the auctions table on the
    server, never trusted from the client - this closes the exploit where
    a client could POST an arbitrary team_id/bid_amount and "win" a player
    without ever bidding.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT team_id, bid_amount FROM auctions
            WHERE player_id = ?
            ORDER BY bid_amount DESC, timestamp DESC
            LIMIT 1
        ''', (player_id,))
        winning_bid = cursor.fetchone()

        if winning_bid:
            team_id, bid_amount = winning_bid
            cursor.execute('''
                UPDATE players SET sold = 1, team_id = ?, sold_price = ? WHERE id = ?
            ''', (team_id, bid_amount, player_id))
        else:
            # Nobody bid on this player - mark as unsold (2) so it's skipped
            # instead of being retried forever.
            cursor.execute('''
                UPDATE players SET sold = 2 WHERE id = ?
            ''', (player_id,))

        conn.commit()

    return redirect(url_for('auction'))


if __name__ == '__main__':
    init_db()
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode)
