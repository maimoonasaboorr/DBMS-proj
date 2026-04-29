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
    cur.execute("""
        SELECT p.product_id, p.product_name, c.category_name, b.brand_name,
               p.price_per_day, p.deposit, p.status
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        JOIN brands b ON p.brand_id = b.brand_id
        ORDER BY p.product_name
    """)
    products = cur.fetchall()
    cur.execute("SELECT category_id, category_name FROM categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.execute("SELECT brand_id, brand_name FROM brands ORDER BY brand_name")
    brands = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("products.html", products=products,
                           categories=categories, brands=brands)


@app.route("/admin/products/add", methods=["POST"])
def admin_add_product():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    name        = request.form.get("product_name", "").strip()
    category_id = request.form.get("category_id")
    brand_id    = request.form.get("brand_id")
    price       = request.form.get("price_per_day")
    deposit     = request.form.get("deposit", 0)
    image_url   = request.form.get("image_url", "").strip() or None

    if not all([name, category_id, brand_id, price]):
        return redirect(url_for("admin_products"))

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO products (product_name, category_id, brand_id, price_per_day, deposit, image_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, category_id, brand_id, price, deposit, image_url))
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
            cur.execute("UPDATE products SET status = %s WHERE product_id = %s", (status, product_id))
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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT i.inventory_id, p.product_name, i.availability_status, i.item_condition
        FROM inventory i
        JOIN products p ON i.product_id = p.product_id
        ORDER BY p.product_name
        """
    )
    inventory = cur.fetchall()
    cur.execute("SELECT product_id, product_name FROM products WHERE status = 'active' ORDER BY product_name")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("inventory.html", inventory=inventory, products=products)


@app.route("/admin/inventory/add", methods=["POST"])
def admin_add_inventory():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    product_id = request.form.get("product_id")
    status = request.form.get("availability_status", "available")
    condition  = request.form.get("item_condition", "good")

    if not product_id:
        return redirect(url_for("admin_inventory"))

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO inventory (product_id, availability_status, item_condition)
            VALUES (%s, %s, %s)
            """,
            (product_id, status, condition),
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
            cur.execute("UPDATE inventory SET availability_status = %s WHERE inventory_id = %s",
                        (status, inventory_id))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    return redirect(url_for("admin_inventory"))

@app.route("/admin/bookings")
def admin_bookings():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT b.booking_id, u.full_name, p.product_name,
               b.start_date, b.end_date, b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products p ON i.product_id = p.product_id
        ORDER BY b.booking_id DESC
    """)
    bookings = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("bookings.html", bookings=bookings)


@app.route("/admin/bookings/update/<int:booking_id>", methods=["POST"])
def admin_update_booking(booking_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))

    new_status = request.form.get("status")
    if new_status not in ("confirmed", "cancelled"):
        return redirect(url_for("admin_bookings"))

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT inventory_id, start_date, end_date, status FROM bookings WHERE booking_id = %s", (booking_id,))
        booking = cur.fetchone()

        if not booking:
            return redirect(url_for("admin_bookings"))

        inventory_id = booking[0]
        start_date   = booking[1]
        end_date     = booking[2]
        current_status = booking[3]

        if new_status == "confirmed":
            if current_status != "pending":
                return redirect(url_for("admin_bookings"))

            # conflict check
            cur.execute("""
                SELECT 1 FROM bookings
                WHERE inventory_id = %s
                AND booking_id != %s
                AND status = 'confirmed'
                AND start_date <= %s AND end_date >= %s
            """, (inventory_id, booking_id, end_date, start_date))

            if cur.fetchone():
                return redirect(url_for("admin_bookings"))

            cur.execute("UPDATE bookings SET status = 'confirmed' WHERE booking_id = %s", (booking_id,))
            cur.execute("UPDATE inventory SET availability_status = 'rented' WHERE inventory_id = %s", (inventory_id,))
            cur.execute("INSERT INTO rentals (booking_id, issue_date, due_date) VALUES (%s, %s, %s)", (booking_id, start_date, end_date))

        elif new_status == "cancelled":
            if current_status not in ("pending", "confirmed"):
                return redirect(url_for("admin_bookings"))

            cur.execute("UPDATE bookings SET status = 'cancelled' WHERE booking_id = %s", (booking_id,))
            cur.execute("UPDATE inventory SET availability_status = 'available' WHERE inventory_id = %s", (inventory_id,))
            cur.execute("UPDATE rentals SET status = 'cancelled' WHERE booking_id = %s AND status = 'ongoing'", (booking_id,))

        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_bookings"))

@app.route("/admin/users")
def admin_users():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, full_name, email, phone, address
        FROM users WHERE role_id = 1 ORDER BY full_name
    """)
    regular_users = cur.fetchall()
    cur.execute("""
        SELECT user_id, full_name, email, phone, address
        FROM users WHERE role_id = 2 ORDER BY full_name
    """)
    admins = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("users.html", regular_users=regular_users, admins=admins)


@app.route("/admin/payments")
def admin_payments():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT pay.payment_id, u.full_name, p.product_name,
               pay.amount, pay.payment_date, pay.status
        FROM payments pay
        JOIN rentals r ON pay.rental_id = r.rental_id
        JOIN bookings b ON r.booking_id = b.booking_id
        JOIN users u ON b.user_id = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products p ON i.product_id = p.product_id
        ORDER BY pay.payment_date DESC
    """)
    payments = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("payments.html", payments=payments)


# ── RENTALS ───────────────────────────────────────────────

@app.route("/admin/rentals")
def admin_rentals():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.rental_id, u.full_name, p.product_name,
               r.issue_date, r.due_date, r.status
        FROM rentals r
        JOIN bookings b ON r.booking_id = b.booking_id
        JOIN users u ON b.user_id = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products p ON i.product_id = p.product_id
        ORDER BY r.rental_id DESC
    """)
    rentals = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("rentals.html", rentals=rentals)


# ── RETURNS ───────────────────────────────────────────────

@app.route("/admin/returns")
def admin_returns():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT rt.return_id, u.full_name, p.product_name,
               rt.return_date, rt.item_condition
        FROM returns rt
        JOIN rentals r ON rt.rental_id = r.rental_id
        JOIN bookings b ON r.booking_id = b.booking_id
        JOIN users u ON b.user_id = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products p ON i.product_id = p.product_id
        ORDER BY rt.return_id DESC
    """)
    returns = cur.fetchall()

    cur.execute("""
        SELECT r.rental_id, u.full_name, p.product_name, r.due_date
        FROM rentals r
        JOIN bookings b ON r.booking_id = b.booking_id
        JOIN users u ON b.user_id = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products p ON i.product_id = p.product_id
        WHERE r.status = 'ongoing'
        AND r.rental_id NOT IN (SELECT rental_id FROM returns)
        ORDER BY r.due_date
    """)
    pending_returns = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("returns.html", returns=returns, pending_returns=pending_returns)


@app.route("/admin/returns/process/<int:rental_id>", methods=["POST"])
def admin_process_return(rental_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))

    return_date = request.form.get("return_date")
    condition   = request.form.get("item_condition")

    if not return_date or condition not in ("excellent", "good", "fair", "damaged", "lost"):
        return redirect(url_for("admin_returns"))

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT b.inventory_id, r.due_date FROM rentals r
            JOIN bookings b ON r.booking_id = b.booking_id
            WHERE r.rental_id = %s
        """, (rental_id,))
        row = cur.fetchone()

        if not row:
            return redirect(url_for("admin_returns"))

        inventory_id = row[0]
        due_date     = row[1]

        from datetime import date
        return_date_obj = date.fromisoformat(return_date)
        rental_status = "returned" if return_date_obj <= due_date else "overdue"

        cur.execute("INSERT INTO returns (rental_id, return_date, item_condition) VALUES (%s, %s, %s)", (rental_id, return_date, condition))
        cur.execute("UPDATE rentals SET status = %s, actual_return_date = %s WHERE rental_id = %s", (rental_status, return_date, rental_id))
        cur.execute("UPDATE bookings SET status = 'completed' WHERE booking_id = (SELECT booking_id FROM rentals WHERE rental_id = %s)", (rental_id,))

        new_inv_status = "retired" if condition == "lost" else "available"
        cur.execute("UPDATE inventory SET availability_status = %s, item_condition = %s WHERE inventory_id = %s",
                    (new_inv_status, "damaged" if condition == "lost" else condition, inventory_id))

        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_returns"))


# ── PENALTIES ─────────────────────────────────────────────

@app.route("/admin/penalties")
def admin_penalties():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT pe.penalty_id, u.full_name, p.product_name,
               pe.amount, pe.reason, pe.status
        FROM penalties pe
        JOIN returns rt ON pe.return_id = rt.return_id
        JOIN rentals r ON rt.rental_id = r.rental_id
        JOIN bookings b ON r.booking_id = b.booking_id
        JOIN users u ON b.user_id = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products p ON i.product_id = p.product_id
        ORDER BY pe.penalty_id DESC
    """)
    penalties = cur.fetchall()

    cur.execute("""
        SELECT rt.return_id, u.full_name, p.product_name, rt.item_condition
        FROM returns rt
        JOIN rentals r ON rt.rental_id = r.rental_id
        JOIN bookings b ON r.booking_id = b.booking_id
        JOIN users u ON b.user_id = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products p ON i.product_id = p.product_id
        WHERE rt.return_id NOT IN (SELECT return_id FROM penalties)
        ORDER BY rt.return_id DESC
    """)
    returnable = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("penalties.html", penalties=penalties, returnable=returnable)


@app.route("/admin/penalties/add/<int:return_id>", methods=["POST"])
def admin_add_penalty(return_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    amount = request.form.get("amount")
    reason = request.form.get("reason", "").strip()
    if not amount or not reason:
        return redirect(url_for("admin_penalties"))
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO penalties (return_id, amount, reason) VALUES (%s, %s, %s)", (return_id, amount, reason))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_penalties"))


@app.route("/admin/penalties/update/<int:penalty_id>", methods=["POST"])
def admin_update_penalty(penalty_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    status = request.form.get("status")
    if status not in ("paid", "waived", "unpaid"):
        return redirect(url_for("admin_penalties"))
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE penalties SET status = %s WHERE penalty_id = %s", (status, penalty_id))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_penalties"))


if __name__ == "__main__":
    app.run(debug=True)



