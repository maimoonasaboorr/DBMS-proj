import os
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
import psycopg2
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-this")

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
    if session.get("user_id"):
        if session.get("role_id") == 2:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("products_dashboard"))

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

        session["user_id"] = user[0]
        session["full_name"] = user[1]
        role_id = user[2]
        session["role_id"] = role_id
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
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("products_dashboard.html")


@app.route("/admin")
def admin_dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if session.get("role_id") != 2:
        return redirect(url_for("products_dashboard"))
    return render_template("admin_dashboard.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── CATEGORIES ────────────────────────────────────────────

@app.route("/admin/categories")
def admin_categories():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT category_id, category_name FROM categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("categories.html", categories=categories)


@app.route("/admin/categories/add", methods=["POST"])
def admin_add_category():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    name = request.form.get("category_name", "").strip()
    if name:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO categories (category_name) VALUES (%s)", (name,))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/delete/<int:category_id>", methods=["POST"])
def admin_delete_category(category_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM categories WHERE category_id = %s", (category_id,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_categories"))


# ── BRANDS ────────────────────────────────────────────────

@app.route("/admin/brands")
def admin_brands():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT brand_id, brand_name FROM brands ORDER BY brand_name")
    brands = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("brands.html", brands=brands)


@app.route("/admin/brands/add", methods=["POST"])
def admin_add_brand():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    name = request.form.get("brand_name", "").strip()
    if name:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO brands (brand_name) VALUES (%s)", (name,))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    return redirect(url_for("admin_brands"))


@app.route("/admin/brands/delete/<int:brand_id>", methods=["POST"])
def admin_delete_brand(brand_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM brands WHERE brand_id = %s", (brand_id,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_brands"))


# ── PRODUCTS ──────────────────────────────────────────────

@app.route("/admin/products")
def admin_products():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.product_id, p.product_name, c.category_name, b.brand_name,
               p.price_per_day, p.deposit, p.status
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        JOIN brands b ON p.brand_id = b.brand_id
        ORDER BY p.product_name
        """
    )
    products = cur.fetchall()
    cur.execute("SELECT category_id, category_name FROM categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.execute("SELECT brand_id, brand_name FROM brands ORDER BY brand_name")
    brands = cur.fetchall()
    cur.close()
    conn.close()
    return render_template(
        "products.html", products=products, categories=categories, brands=brands
    )


@app.route("/admin/products/add", methods=["POST"])
def admin_add_product():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    name = request.form.get("product_name", "").strip()
    category_id = request.form.get("category_id")
    brand_id = request.form.get("brand_id")
    price = request.form.get("price_per_day")
    deposit = request.form.get("deposit", 0)
    image_url = request.form.get("image_url", "").strip() or None

    if not all([name, category_id, brand_id, price]):
        return redirect(url_for("admin_products"))

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO products (product_name, category_id, brand_id, price_per_day, deposit, image_url)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (name, category_id, brand_id, price, deposit, image_url),
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_products"))


@app.route("/admin/products/update-status/<int:product_id>", methods=["POST"])
def admin_update_product_status(product_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    status = request.form.get("status")
    if status in ("active", "inactive", "archived"):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE products SET status = %s WHERE product_id = %s", (status, product_id)
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    return redirect(url_for("admin_products"))


# ── INVENTORY ─────────────────────────────────────────────

@app.route("/admin/inventory")
def admin_inventory():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    inventory = []
    products = []
    error_message = None
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT i.inventory_id, p.product_name, i.serial_num,
                   i.availability_status, i.item_condition
            FROM inventory i
            JOIN products p ON i.product_id = p.product_id
            ORDER BY p.product_name
            """
        )
        inventory = cur.fetchall()
        cur.execute(
            "SELECT product_id, product_name FROM products WHERE status = 'active' ORDER BY product_name"
        )
        products = cur.fetchall()
    except Exception:
        error_message = "Could not load inventory data. Check inventory table columns and try again."
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return render_template(
        "inventory.html", inventory=inventory, products=products, error_message=error_message
    )


@app.route("/admin/inventory/add", methods=["POST"])
def admin_add_inventory():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    product_id = request.form.get("product_id")
    serial_num = request.form.get("serial_num", "").strip()
    condition = request.form.get("item_condition", "good")

    if not product_id or not serial_num:
        return redirect(url_for("admin_inventory"))

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO inventory (product_id, serial_num, item_condition)
            VALUES (%s, %s, %s)
            """,
            (product_id, serial_num, condition),
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_inventory"))


@app.route("/admin/inventory/update-status/<int:inventory_id>", methods=["POST"])
def admin_update_inventory_status(inventory_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    status = request.form.get("availability_status")
    valid = ("available", "reserved", "rented", "maintenance", "retired")
    if status in valid:
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE inventory SET availability_status = %s WHERE inventory_id = %s",
                (status, inventory_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    return redirect(url_for("admin_inventory"))


if __name__ == "__main__":
    app.run(debug=True)