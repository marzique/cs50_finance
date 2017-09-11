from cs50 import SQL
from flask import session
from helpers import usd

db = SQL("sqlite:///finance.db")

def get_cash():
    return float(db.execute("SELECT cash FROM users WHERE id = :id",
                            id=session["user_id"])[0]["cash"])


def get_username():
    return db.execute("SELECT username FROM users WHERE id = :id", id=session["user_id"] )[0]["username"]
