import os
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
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


@app.route("/faqs")
def faqs():
    return render_template("faqs.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/services")
def services():
    return render_template("services.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not email or not password:
            return render_template(
                "login.html",
                submitted=True,
                email=email,
                message="Email and password are required.",
            )

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT user_id, full_name, role_id
                FROM users
                WHERE email = %s AND password = %s
                """,
                (email, password),
            )
            user = cur.fetchone()
        except Exception:
            user = None
        finally:
            cur.close()
            conn.close()

        if not user:
            return render_template(
                "login.html",
                submitted=True,
                email=email,
                message="Account not found.",
            )

        role_id = user[2]
        if role_id == 2:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("products_dashboard"))

    return render_template("login.html", submitted=False)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        form_data = {
            "full_name": request.form.get("full_name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "password": request.form.get("password", ""),
            "phone": request.form.get("phone", "").strip(),
            "address": request.form.get("address", "").strip(),
        }

        if not form_data["full_name"] or not form_data["email"] or not form_data["password"]:
            return render_template(
                "signup.html",
                submitted=True,
                message="Full name, email, and password are required.",
                form_data=form_data,
            )
        if len(form_data["password"]) < 8:
            return render_template(
                "signup.html",
                submitted=True,
                message="Password must be at least 8 characters long.",
                form_data=form_data,
            )

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT user_id FROM users WHERE email = %s", (form_data["email"],))
            if cur.fetchone():
                return render_template(
                    "signup.html",
                    submitted=True,
                    message="Email already exists. Please use another email.",
                    form_data=form_data,
                )

            cur.execute(
                """
                INSERT INTO users (full_name, email, password, phone, role_id, address)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    form_data["full_name"],
                    form_data["email"],
                    form_data["password"],
                    form_data["phone"] or None,
                    1,
                    form_data["address"] or None,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            return render_template(
                "signup.html",
                submitted=True,
                message="Could not create account.",
                form_data=form_data,
            )
        finally:
            cur.close()
            conn.close()

        return render_template(
            "signup.html",
            submitted=True,
            message="Sign up successful. Please login.",
            form_data={},
        )

    return render_template("signup.html", submitted=False, form_data={})


@app.route("/products")
def products_dashboard():
    return render_template("products_dashboard.html")


@app.route("/admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")


if __name__ == "__main__":
    app.run(debug=True)