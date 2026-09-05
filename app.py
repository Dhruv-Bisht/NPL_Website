import os
import base64
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, or_

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-in-production")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Vercel's filesystem is read-only except /tmp.
# Set DATABASE_URL to PostgreSQL for persistent production data.
if os.getenv("DATABASE_URL"):
    database_url = os.getenv("DATABASE_URL")
elif os.getenv("VERCEL"):
    database_url = "sqlite:////tmp/npl.db"
else:
    # Anchored to this file's own folder (not the process's current working
    # directory) so `python app.py` always reads/writes the same npl.db
    # regardless of which directory you happen to launch it from.
    database_url = "sqlite:///" + os.path.join(BASE_DIR, "npl.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    role = db.Column(db.String(40), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    batting = db.Column(db.String(30), default="Right")
    bowling = db.Column(db.String(60), default="None")
    base_price = db.Column(db.Integer, nullable=False, default=100)
    photo_data = db.Column(db.Text, nullable=True)
    registered = db.Column(db.Boolean, default=True, nullable=False)
    auction_status = db.Column(db.String(30), default="AVAILABLE", nullable=False)
    sold_price = db.Column(db.Integer, nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship("Team", back_populates="players")

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    short_name = db.Column(db.String(10), unique=True, nullable=False)
    city = db.Column(db.String(80), nullable=False)
    logo_data = db.Column(db.Text, nullable=True)
    purse = db.Column(db.Integer, default=10000, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    players = db.relationship("Player", back_populates="team")

class Auction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"), nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="SOLD", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    player = db.relationship("Player")
    team = db.relationship("Team")

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            flash("Admin login required.", "error")
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_globals():
    return {
        "current_year": datetime.now().year,
        "admin_logged_in": bool(session.get("admin"))
    }

@app.route("/")
def index():
    players = Player.query.filter_by(registered=True).order_by(Player.created_at.desc()).limit(8).all()
    teams = Team.query.order_by(Team.name).all()
    sold = Player.query.filter_by(auction_status="SOLD").count()
    available = Player.query.filter_by(auction_status="AVAILABLE").count()
    return render_template("index.html", players=players, teams=teams, sold=sold, available=available)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        role = request.form["role"]
        age = int(request.form["age"])
        batting = request.form.get("batting", "Right")
        bowling = request.form.get("bowling", "None")
        base_price = int(request.form.get("base_price", 100))

        if Player.query.filter(func.lower(Player.email) == email).first():
            flash("A player with this email is already registered.", "error")
            return redirect(url_for("register"))

        photo = request.files.get("photo")
        photo_data = None
        if photo and photo.filename:
            raw = photo.read()
            if len(raw) > 2 * 1024 * 1024:
                flash("Photo must be smaller than 2 MB.", "error")
                return redirect(url_for("register"))
            mime = photo.mimetype or "image/jpeg"
            photo_data = f"data:{mime};base64," + base64.b64encode(raw).decode()

        player = Player(
            name=name, email=email, phone=phone, role=role, age=age,
            batting=batting, bowling=bowling, base_price=base_price,
            photo_data=photo_data
        )
        db.session.add(player)
        db.session.commit()
        flash("Player registered successfully and added to the auction pool.", "success")
        return redirect(url_for("register"))

    all_players = Player.query.filter_by(registered=True).order_by(Player.created_at.desc()).all()
    return render_template("register.html", players=all_players)

@app.route("/players")
def players():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()

    query = Player.query.filter_by(registered=True)
    if q:
        query = query.filter(
            or_(Player.name.ilike(f"%{q}%"), Player.email.ilike(f"%{q}%"))
        )
    if role:
        query = query.filter_by(role=role)
    if status:
        query = query.filter_by(auction_status=status)

    all_players = query.order_by(Player.name).all()
    return render_template("players.html", players=all_players, q=q, role=role, status=status)

@app.route("/player/<int:player_id>")
def player(player_id):
    p = db.get_or_404(Player, player_id)
    return render_template("player.html", player=p)

@app.route("/teams")
def teams():
    all_teams = Team.query.order_by(Team.name).all()
    return render_template("teams.html", teams=all_teams)

@app.route("/team/<int:team_id>")
def team(team_id):
    t = db.get_or_404(Team, team_id)
    players = Player.query.filter_by(team_id=t.id, auction_status="SOLD").order_by(Player.name).all()
    return render_template("team.html", team=t, players=players)

@app.route("/auction")
def auction():
    players = Player.query.filter_by(registered=True).order_by(Player.auction_status, Player.name).all()
    teams = Team.query.order_by(Team.name).all()
    return render_template("auction.html", players=players, teams=teams)

@app.route("/auction/sell", methods=["POST"])
@admin_required
def sell_player():
    player_id = int(request.form["player_id"])
    team_id = int(request.form["team_id"])
    amount = int(request.form["amount"])

    p = db.get_or_404(Player, player_id)
    t = db.get_or_404(Team, team_id)

    if p.auction_status == "SOLD":
        flash("This player has already been sold.", "error")
        return redirect(url_for("auction"))

    if amount < p.base_price:
        flash("Bid cannot be below the player's base price.", "error")
        return redirect(url_for("auction"))

    if amount > t.purse:
        flash(f"{t.name} does not have enough purse remaining.", "error")
        return redirect(url_for("auction"))

    t.purse -= amount
    p.auction_status = "SOLD"
    p.sold_price = amount
    p.team_id = t.id
    db.session.add(Auction(player_id=p.id, team_id=t.id, amount=amount, status="SOLD"))
    db.session.commit()

    flash(f"{p.name} sold to {t.name} for ₹{amount:,}.", "success")
    return redirect(url_for("auction"))

@app.route("/auction/unsold/<int:player_id>", methods=["POST"])
@admin_required
def mark_unsold(player_id):
    p = db.get_or_404(Player, player_id)
    if p.auction_status != "SOLD":
        p.auction_status = "UNSOLD"
        db.session.commit()
        flash(f"{p.name} marked unsold.", "success")
    return redirect(url_for("auction"))

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form["password"]
        if password == os.getenv("ADMIN_PASSWORD", "npladmin"):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Invalid admin password.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    return render_template(
        "admin.html",
        players=Player.query.order_by(Player.created_at.desc()).all(),
        teams=Team.query.order_by(Team.name).all(),
        auctions=Auction.query.order_by(Auction.created_at.desc()).limit(20).all()
    )

@app.route("/admin/team", methods=["POST"])
@admin_required
def create_team():
    name = request.form["name"].strip()
    short_name = request.form["short_name"].strip().upper()
    city = request.form["city"].strip()
    purse = int(request.form.get("purse", 10000))

    if Team.query.filter(or_(func.lower(Team.name) == name.lower(), func.lower(Team.short_name) == short_name.lower())).first():
        flash("Team name or short name already exists.", "error")
        return redirect(url_for("admin"))

    logo = request.files.get("logo")
    logo_data = None
    if logo and logo.filename:
        raw = logo.read()
        if len(raw) <= 2 * 1024 * 1024:
            mime = logo.mimetype or "image/png"
            logo_data = f"data:{mime};base64," + base64.b64encode(raw).decode()

    db.session.add(Team(name=name, short_name=short_name, city=city, purse=purse, logo_data=logo_data))
    db.session.commit()
    flash("Team created.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/team/<int:team_id>/delete", methods=["POST"])
@admin_required
def delete_team(team_id):
    team = db.get_or_404(Team, team_id)

    # Never silently remove a squad. A team with players must be emptied first.
    squad_size = Player.query.filter_by(team_id=team.id).count()
    if squad_size > 0:
        flash(f"Cannot delete {team.name}: remove its {squad_size} squad player(s) first.", "error")
        return redirect(url_for("admin"))

    # Remove auction records belonging to the team before deleting it.
    Auction.query.filter_by(team_id=team.id).delete(synchronize_session=False)
    team_name = team.name
    db.session.delete(team)
    db.session.commit()
    flash(f"{team_name} deleted successfully.", "success")
    return redirect(url_for("admin"))

@app.route("/api/stats")
def stats():
    return jsonify({
        "players": Player.query.filter_by(registered=True).count(),
        "teams": Team.query.count(),
        "sold": Player.query.filter_by(auction_status="SOLD").count(),
        "available": Player.query.filter_by(auction_status="AVAILABLE").count(),
        "unsold": Player.query.filter_by(auction_status="UNSOLD").count(),
    })

def seed():
    if Team.query.count() > 0:
        return
    teams = [
        ("Bangalore Blasters", "BB", "Bangalore"),
        ("Delhi Dynamos", "DD", "Delhi"),
        ("Mumbai Mavericks", "MM", "Mumbai"),
        ("Chennai Chargers", "CC", "Chennai"),
        ("Dehradun Daredevils", "DDD", "Dehradun"),
        ("Kolkata Kings", "KK", "Kolkata"),
    ]
    for name, short, city in teams:
        db.session.add(Team(name=name, short_name=short, city=city, purse=10000))
    db.session.commit()

with app.app_context():
    db.create_all()
    seed()

if __name__ == "__main__":
    app.run(debug=True)
