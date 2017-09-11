from cs50 import SQL
# from sql import SQL --> if not in cs50_ide
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from sqlquery import *
from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    """Main page that shows your stocks and cash."""

    username = get_username()
    cash = get_cash()   # float, not usd() yet
    cash_usd = usd(cash)

    # all purchases of :username
    list_of_dicts = db.execute("SELECT * FROM purchases WHERE username = :username", username=username)

    # current price of all your stocks
    totals_sum = 0.0

    # if you haven't any stocks (just registered, or sold all -> cash == sum)
    if not list_of_dicts:
         return render_template("index.html", cash_usd=cash_usd, money_sum_usd=cash_usd)

    symbol_list = []
    name_list = []
    shares_list = []
    price_list = []
    total_list = []

    zipper = zip(symbol_list, name_list, shares_list, price_list, total_list)

    for dic in list_of_dicts:
        symbol = dic["symbol"]
        symbol_list.append(symbol)

        name = lookup(symbol)["name"]
        name_list.append(name)

        shares = dic["shares"]
        shares_list.append(shares)

        price = lookup(symbol)["price"]     # not passed
        total = price * shares              # not passed

        price_usd = usd(price)
        price_list.append(price_usd)

        total_usd = usd(total)
        total_list.append(total_usd)

        totals_sum += total

    money_sum = totals_sum + cash

    return render_template("index.html", zipper=zipper, cash_usd=cash_usd, money_sum_usd=usd(money_sum))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of amount."""
    if request.method == "POST":

        # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide amount symbol")

        # ensure shares was submitted
        elif not request.form.get("shares"):
            return apology("must provide amount of shares")

        # returns dictionary with keys: "name", "symbol", "price"
        item_to_buy = lookup(request.form.get("symbol"))

        # ensure proper symbol
        if not item_to_buy:
            return apology("invalid symbol")

        # ensures that amount - only positive integer
        try:
            # amount of shares to buy
            amount = int(request.form.get("shares"))
            if amount <= 0:
                return apology("invalid amount")
        except ValueError:
            return apology("invalid amount")

        money = get_cash()
        username = get_username()

        # price for one stock
        price = item_to_buy["price"]

        # symbol of the stock (e.g. 'NFLX')
        symbol = request.form.get("symbol").upper()

        # ensure user has enough money
        if amount * price > money:
            return apology("not enough money")

        # if enough money
        elif amount * price < money:
            '''IMPLEMENT DATABASE QUERYING HERE'''

            # check if you already bough some of these stocks
            dict = db.execute("SELECT * FROM purchases WHERE username = :username AND symbol=:symbol",
                            username=username, symbol=request.form.get("symbol").upper())

            if not dict:
                # insert new stock with it's shares bounding to username
                db.execute("INSERT INTO purchases (username, symbol, time, shares) VALUES(:username, :symbol, CURRENT_TIMESTAMP, :shares)",
                                                    username=username, symbol=symbol, shares=amount)

            else:
                # updating shares amount and timestamp
                db.execute("UPDATE purchases SET shares = shares + :new_shares, time = CURRENT_TIMESTAMP WHERE username = :username AND symbol=:symbol",
                            new_shares=amount, username=username, symbol=symbol)


            # withdrawing money
            db.execute("UPDATE users SET cash = :new_cash WHERE id = :id",
                        new_cash=money - (amount * price), id=session["user_id"] )

            # updating history
            db.execute("INSERT INTO history (username, symbol, price, shares, time) VALUES(:username, :symbol, :price, :shares, CURRENT_TIMESTAMP)",
                        username=username, symbol=symbol, price=usd(price), shares=amount)

            return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions."""

    username = get_username()
    list_of_dicts = db.execute("SELECT * from history WHERE username=:username", username=username)

    # new deals at the top
    list_of_dicts.reverse()

    symbol_list = []
    shares_list = []
    price_list = []
    time_list = []

    zipper = zip(symbol_list, shares_list, price_list, time_list)

    for dic in list_of_dicts:

        symbol = dic["symbol"]
        symbol_list.append(symbol)

        shares = dic["shares"]
        shares_list.append(shares)

        price = dic["price"]
        price_list.append(price)

        time = dic["time"]
        time_list.append(time)

    return render_template("history.html", zipper=zipper)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                            username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"),
                                                    rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":

        # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must symbol")


        # {'name': 'Netflix, Inc.', 'price': 179.0, 'symbol': 'NFLX'}
        list_of_dicts = lookup(request.form.get("symbol"))

        # ensure correct symbols
        if not list_of_dicts:
            return apology("invalid symbol")

        return render_template("quoted.html", symbol=list_of_dicts["symbol"], name=list_of_dicts["name"], price=usd(list_of_dicts["price"]))

        # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    """Register user."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # ensure that both passwords same
        elif request.form.get("password") != request.form.get("password2"):
            return apology("different passwords")


        # INSERT new registered user to database (username and hashed password)
        result = db.execute( "INSERT INTO users (username, hash) VALUES(:username, :hash)",
                username=request.form.get("username"), hash=pwd_context.hash(request.form.get("password")) )
        if not result:
            return apology("this username is already taken")

        # query database for username again
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        """Register user."""
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of amount."""
    if request.method == "POST":

        # ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide amount symbol")

        # ensure shares was submitted
        elif not request.form.get("shares"):
            return apology("must provide amount of shares")

        # returns dictionary with keys: "name", "symbol", "price"
        item_to_sell = lookup(request.form.get("symbol"))

        # ensure proper symbol
        if not item_to_sell:
            return apology("invalid symbol")

        username = get_username()
        symbol = request.form.get("symbol").upper()

        # current amount of shares of symbol
        shares = db.execute("SELECT shares FROM purchases WHERE username = :username AND symbol = :symbol",
                            username=username, symbol=symbol)[0]["shares"]

        if not shares:
            return apology("you don't have this stock")

        try:
            # amount of shares to buy
            amount = int(request.form.get("shares"))
            if amount <= 0:
                return apology("invalid amount")
        except ValueError:
            return apology("invalid amount")

        # ensure user has enough shares to sell
        if shares < amount:
            return apology("not enough shares")

        # for history
        sell_amount = - amount

        # current price for one stock
        price = item_to_sell["price"]

        # current account cash
        money = get_cash()

        # updating shares amount and timestamp
        db.execute("UPDATE purchases SET shares = shares - :amount, time = CURRENT_TIMESTAMP WHERE username = :username AND symbol=:symbol",
                    amount=amount, username=username, symbol=request.form.get("symbol").upper())

        # replenish money
        db.execute("UPDATE users SET cash = :new_cash WHERE id = :id",
                    new_cash=money + (amount * price), id=session["user_id"] )


        # updating history
        db.execute("INSERT INTO history (username, symbol, price, shares, time) VALUES(:username, :symbol, :price, :shares, CURRENT_TIMESTAMP)",
                    username=username, symbol=symbol, price=usd(price), shares=sell_amount)


        # deleting row from index when all stocks sold
        new_shares = db.execute("SELECT shares FROM purchases WHERE username = :username AND symbol = :symbol",
                            username=username, symbol=request.form.get("symbol").upper())[0]["shares"]
        if new_shares == 0:
            db.execute("DELETE FROM purchases WHERE username = :username AND symbol = :symbol",
                            username=username, symbol=request.form.get("symbol").upper())
            print("SHARES = 0")

        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")


@app.route("/fullfill", methods=["GET", "POST"])
@login_required
def fullfill():
    """Adds money to your account."""
    if request.method == "POST":

        try:
            money = float(request.form.get("money"))
            if money <= 0:
                return apology("wrong amount")
        except:
            return apology("wrong amount")

        # adds money
        db.execute("UPDATE users SET cash = cash + :add_cash WHERE id = :id",
                    add_cash=money, id=session["user_id"] )


        return redirect(url_for("index"))

        # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("fullfill.html")

