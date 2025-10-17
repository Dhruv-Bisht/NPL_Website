from flask import Flask, render_template, request,redirect,url_for
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
# UPLOAD_FOLDER = 'static/uploads'
UPLOAD_FOLDER = os.path.join('static','uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
# os.makedirs(UPLOAD_FOLDER,exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'],exist_ok=True)

# Initialize database
def init_db():
    conn = sqlite3.connect('npl.db')
    cursor = conn.cursor()

    # Create players table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            base_price TEXT,
            role TEXT,
            image_filename TEXT,
            sold integer default 0
        )
    ''')

    # Create teams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT,
            captain TEXT,
            phone TEXT,
            logo_filename TEXT
        )
    ''')

    # Create bids table
    cursor.execute('''CREATE TABLE IF NOT EXISTS auctions(
        id integer primary key autoincrement,
        player_id integer,
        team_id integer,
        bid_amount real,
        timestamp datetime default current_timestamp,
        foreign key(player_id) references players(id),
        foreign key(team_id) references teams(id)
        )
    ''')
    # Ensure new column exists (for backward compatibility)
    cursor.execute("PRAGMA table_info(players)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'sold' not in columns:
        cursor.execute("ALTER TABLE players ADD COLUMN sold INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

# Home route
@app.route("/")
def home():
    return render_template('index.html')

# player Registration route
@app.route('/player',methods=['GET','POST'])
def player():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        base_price = request.form['base_price']
        role = request.form['role']
        # photo = request.form['photo']

        # Handle image upload
        image = request.files['photo']
        image_filename = None

        if image:
            image_filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'],image_filename))

        # save to database
        conn = sqlite3.connect('npl.db')
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO players(name,phone,base_price,role,image_filename) VALUES(?,?,?,?,?)
        ''',(name,phone,base_price,role,image_filename))

        conn.commit()
        conn.close()

        return redirect(url_for('home'))
    return render_template('player.html')

# Team Registration route
@app.route('/captain',methods=['GET','POST'])
def captain():
    if request.method == 'POST':
        team_name = request.form['team_name']
        phone = request.form['phone']
        captain = request.form['captain']

        # Handle the logo
        logo = request.files.get('logo')
        logo_filename = None
        if logo and logo.filename!='':
            logo_filename = secure_filename(logo.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'],logo_filename)
            print("Saving to:",save_path)
            logo.save(save_path)
            print("Saved Successfully")
        else:
            print("No logo file uploaded")
        # Save to database
        conn = sqlite3.connect('npl.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO teams(team_name,captain,phone,logo_filename) VALUES (?,?,?,?)
        ''',(team_name,phone,captain,logo_filename))
        conn.commit()
        conn.close()
        print(f"✅ Team Registered: {team_name}, {captain}, {logo_filename}")
        return redirect(url_for('home'))
    return render_template('captain.html')

# View Registered Teams
@app.route('/teams')
def teams():
    conn = sqlite3.connect('npl.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id,team_name, captain, phone, logo_filename FROM teams")
    all_teams = cursor.fetchall()
    conn.close()
    return render_template('team.html',teams=all_teams)


# delete the team
@app.route('/delete_team/<int:team_id>', methods=['POST'])
def delete_team(team_id):
    conn = sqlite3.connect('npl.db')
    cursor = conn.cursor()

    # Optional: get the logo filename to delete the file as well
    cursor.execute("SELECT logo_filename FROM teams WHERE id=?", (team_id,))
    row = cursor.fetchone()
    if row and row[0]:
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], row[0])
        if os.path.exists(logo_path):
            os.remove(logo_path)

    # Delete the team from the database
    cursor.execute("DELETE FROM teams WHERE id=?", (team_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('teams'))


@app.route('/auction')
def auction():
    # Get all players
    conn = sqlite3.connect('npl.db')
    cursor = conn.cursor()
    # cursor.execute("SELECT * FROM players")
    # players = cursor.fetchall()

    # Fetch first unsold players
    cursor.execute('''
        select id,name,base_price,role,image_filename from players where sold=0 order by id limit 1
    ''') 
    player = cursor.fetchone()

    # Fetch all teams
    cursor.execute("SELECT id, team_name FROM teams")
    teams = cursor.fetchall()
    conn.close()

    if not player:
        return render_template('auction_done.html')

    return render_template('auction_live.html', player=player, teams=teams)



# For bidding
@app.route('/bid',methods=['POST'])
def bid():
    data = request.json
    player_id = data['player_id']
    team_id = data['team_id']
    bid_amount = data['bid_amount']

    conn = sqlite3.connect('npl.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO bids(player_id,team_id,bid_amount) VALUES (?,?,?)
    ''',(player_id,team_id,bid_amount))
    conn.commit()
    conn.close()
    # return redirect(url_for('auction'))
    return {'status':'success'}

# Finalize the bid sale after 10sec
@app.route('/finalize/<int:player_id>', methods=['POST'])
def finalize(player_id):
    # Get team_id and bid_amount safely and ensure they’re integers
    team_id = request.form.get('team_id')
    bid_amount = request.form.get('bid_amount')

    if not team_id or not bid_amount:
        return "Missing data", 400

    try:
        team_id = int(team_id)
        bid_amount = int(bid_amount)
    except ValueError:
        return "Invalid data type", 400

    conn = sqlite3.connect('npl.db')
    cursor = conn.cursor()

    # Insert auction record
    cursor.execute('''
        INSERT INTO auctions(player_id, team_id, bid_amount)
        VALUES (?, ?, ?)
    ''', (player_id, team_id, bid_amount))

    # Update player as sold
    cursor.execute('''
        UPDATE players SET sold = 1, team_id = ? WHERE id = ?
    ''', (team_id, player_id))

    conn.commit()
    conn.close()

    return redirect(url_for('auction'))


# To view all registered players.
@app.route('/register_player')
def register_player():
    conn = sqlite3.connect('npl.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id,name, phone, base_price, role, image_filename FROM players")
    all_players = cursor.fetchall()
    conn.close()
    return render_template('view.html',players=all_players)

# delete the team
@app.route('/delete_player/<int:player_id>', methods=['POST'])
def delete_player(player_id):
    conn = sqlite3.connect('npl.db')
    cursor = conn.cursor()

    # Optional: get the logo filename to delete the file as well
    cursor.execute("SELECT image_filename FROM players WHERE id=?", (player_id,))
    row = cursor.fetchone()
    if row and row[0]:
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], row[0])
        if os.path.exists(logo_path):
            os.remove(logo_path)

    # Delete the team from the database
    cursor.execute("DELETE FROM players WHERE id=?", (player_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('register_player'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)