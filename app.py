import os
from dotenv import load_dotenv
from flask import Flask, render_template, request
import psycopg2
load_dotenv()
app = Flask(__name__)

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        return render_template(
            "login.html",
            submitted=True,
            email=email,
            message="Login form submitted (UI only).",
        )

    return render_template("login.html", submitted=False)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        form_data = {
            "full_name": request.form.get("full_name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "role_id": request.form.get("role_id", "").strip(),
            "address": request.form.get("address", "").strip(),
        }
        return render_template(
            "signup.html",
            submitted=True,
            message="Sign up form submitted (UI only).",
            form_data=form_data,
        )

    return render_template("signup.html", submitted=False, form_data={})


if __name__ == "__main__":
    app.run(debug=True)