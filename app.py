from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import requests
import os
from datetime import datetime, timezone

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = "cedricbet-demo-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cedricbet.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

FOOTBALL_API_TOKEN = os.getenv("FOOTBALL_API_TOKEN")


# =========================
# USER
# =========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=1000.0)


# =========================
# BET
# =========================

class Bet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    team = db.Column(db.String(100), nullable=False)
    odds = db.Column(db.Float, nullable=False)
    stake = db.Column(db.Float, nullable=False)
    possible_win = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="PENDING")


with app.app_context():
    db.create_all()


# =========================
# CURRENT PREMIER LEAGUE MATCHES
# =========================

def get_matches():

    if not FOOTBALL_API_TOKEN:
        return []

    url = "https://api.football-data.org/v4/competitions/PL/matches"

    headers = {
        "X-Auth-Token": FOOTBALL_API_TOKEN
    }

    params = {
        "status": "SCHEDULED"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )

        if response.status_code != 200:
            print("Football API error:", response.status_code)
            return []

        data = response.json()

        matches = []

        now = datetime.now(timezone.utc)

        for match in data.get("matches", []):

            match_date = datetime.fromisoformat(
                match["utcDate"].replace("Z", "+00:00")
            )

            # Only show upcoming matches
            if match_date >= now:

                matches.append({
                    "id": match["id"],
                    "home": match["homeTeam"]["name"],
                    "away": match["awayTeam"]["name"],
                    "date": match_date
                })

        return matches[:20]

    except Exception as e:

        print("API connection error:", e)

        return []


# =========================
# HOME
# =========================

@app.route("/")
def home():

    user = None

    if "user_id" in session:
        user = db.session.get(
            User,
            session["user_id"]
        )

    matches = get_matches()

    return render_template(
        "index.html",
        user=user,
        matches=matches
    )


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:
            return "Username already exists."

        user = User(
            username=username,
            password=generate_password_hash(password),
            balance=1000.0
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(
            username=username
        ).first()

        if user and check_password_hash(
            user.password,
            password
        ):

            session["user_id"] = user.id

            return redirect(url_for("home"))

        return "Invalid username or password."

    return render_template("login.html")


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# =========================
# BET HISTORY
# =========================

@app.route("/history")
def history():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(
        User,
        session["user_id"]
    )

    bets = Bet.query.filter_by(
        user_id=user.id
    ).order_by(
        Bet.id.desc()
    ).all()

    return render_template(
        "history.html",
        bets=bets
    )


# =========================
# BET SLIP
# =========================

@app.route("/betslip", methods=["POST"])
def betslip():

    if "user_id" not in session:
        return redirect(url_for("login"))

    team = request.form["team"]
    odds = float(request.form["odds"])

    return render_template(
        "betslip.html",
        team=team,
        odds=odds
    )


# =========================
# PLACE DEMO BET
# =========================

@app.route("/bet", methods=["POST"])
def place_bet():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(
        User,
        session["user_id"]
    )

    team = request.form["team"]
    odds = float(request.form["odds"])
    stake = float(request.form["stake"])

    if stake <= 0:
        return "Invalid stake."

    if stake > user.balance:
        return "Insufficient demo balance."

    possible_win = stake * odds

    user.balance -= stake

    new_bet = Bet(
        user_id=user.id,
        team=team,
        odds=odds,
        stake=stake,
        possible_win=possible_win,
        status="PENDING"
    )

    db.session.add(new_bet)
    db.session.commit()

    return render_template(
        "bet_result.html",
        team=team,
        odds=odds,
        stake=stake,
        possible_win=possible_win,
        balance=user.balance
    )


# =========================
# START
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
