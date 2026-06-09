import os
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urlparse
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
import psycopg2

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-this")


def get_connection():
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "port": os.getenv("DB_PORT", "5432"),
    }
    missing = [key for key in ("database", "user", "password") if not config[key]]
    if missing:
        raise RuntimeError(
            "Database credentials missing. Copy .env.example to .env and set "
            f"DB_NAME, DB_USER, and DB_PASSWORD. Missing: {', '.join(missing)}"
        )
    return psycopg2.connect(**config)


def _flash_pg_error(exc):
    """Show Postgres errors (e.g. BEFORE DELETE trigger RAISE) in the UI."""
    diag = getattr(exc, "diag", None)
    msg = diag.message_primary if diag and diag.message_primary else str(exc)
    flash(msg.strip().split("\n")[0], "error")


def normalize_image_filename(raw_value):
    """Keep only filename so DB does not store full URLs."""
    if not raw_value:
        return None
    value = raw_value.strip()
    if not value:
        return None

    parsed = urlparse(value)
    path = parsed.path if parsed.scheme and parsed.netloc else value
    filename = os.path.basename(path.replace("\\", "/"))
    filename = unquote(filename).strip()
    return filename or None


# ── PUBLIC PAGES ──────────────────────────────────────────

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


# ── AUTH ──────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        if session.get("role_id") == 2:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("products_dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", submitted=True, email=email,
                                   message="Email and password are required.")

        conn = get_connection()
        cur  = conn.cursor()
        try:
            cur.execute(
                "SELECT user_id, full_name, role_id FROM users WHERE email = %s AND password = %s",
                (email, password),
            )
            user = cur.fetchone()
        except Exception:
            user = None
        finally:
            cur.close()
            conn.close()

        if not user:
            return render_template("login.html", submitted=True, email=email,
                                   message="Account not found.")

        session["user_id"]   = user[0]
        session["full_name"] = user[1]
        session["role_id"]   = user[2]

        if user[2] == 2:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("products_dashboard"))

    return render_template("login.html", submitted=False)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        form_data = {
            "full_name": request.form.get("full_name", "").strip(),
            "email":     request.form.get("email", "").strip(),
            "password":  request.form.get("password", ""),
            "phone":     request.form.get("phone", "").strip(),
            "address":   request.form.get("address", "").strip(),
        }

        if not form_data["full_name"] or not form_data["email"] or not form_data["password"]:
            return render_template("signup.html", submitted=True, form_data=form_data,
                                   message="Full name, email, and password are required.")

        if len(form_data["password"]) < 8:
            return render_template("signup.html", submitted=True, form_data=form_data,
                                   message="Password must be at least 8 characters long.")

        conn = get_connection()
        cur  = conn.cursor()
        try:
            cur.execute("SELECT user_id FROM users WHERE email = %s", (form_data["email"],))
            if cur.fetchone():
                return render_template("signup.html", submitted=True, form_data=form_data,
                                       message="Email already exists. Please use another email.")

            cur.execute(
                """
                INSERT INTO users (full_name, email, password, phone, role_id, address)
                VALUES (%s, %s, %s, %s, 1, %s)
                """,
                (
                    form_data["full_name"],
                    form_data["email"],
                    form_data["password"],
                    form_data["phone"] or None,
                    form_data["address"] or None,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            return render_template("signup.html", submitted=True, form_data=form_data,
                                   message="Could not create account.")
        finally:
            cur.close()
            conn.close()

        return render_template("signup.html", submitted=True, form_data={},
                               message="Sign up successful. Please login.")

    return render_template("signup.html", submitted=False, form_data={})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── ADMIN: DASHBOARD ──────────────────────────────────────

@app.route("/admin")
def admin_dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    if session.get("role_id") != 2:
        return redirect(url_for("products_dashboard"))
    return render_template("admin/admin_dashboard.html")


# ── ADMIN: CATEGORIES ─────────────────────────────────────

@app.route("/admin/categories")
def admin_categories():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT category_id, category_name FROM categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/categories.html", categories=categories)


@app.route("/admin/categories/add", methods=["POST"])
def admin_add_category():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    name = request.form.get("category_name", "").strip()
    if name:
        conn = get_connection()
        cur  = conn.cursor()
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
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM categories WHERE category_id = %s", (category_id,))
        conn.commit()
        flash("Category removed.", "success")
    except psycopg2.Error as e:
        conn.rollback()
        _flash_pg_error(e)
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_categories"))


# ── ADMIN: BRANDS ─────────────────────────────────────────

@app.route("/admin/brands")
def admin_brands():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT brand_id, brand_name FROM brands ORDER BY brand_name")
    brands = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/brands.html", brands=brands)


@app.route("/admin/brands/add", methods=["POST"])
def admin_add_brand():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    name = request.form.get("brand_name", "").strip()
    if name:
        conn = get_connection()
        cur  = conn.cursor()
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
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM brands WHERE brand_id = %s", (brand_id,))
        conn.commit()
        flash("Brand removed.", "success")
    except psycopg2.Error as e:
        conn.rollback()
        _flash_pg_error(e)
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_brands"))


# ── ADMIN: PRODUCTS ───────────────────────────────────────

@app.route("/admin/products")
def admin_products():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT p.product_id, p.product_name, c.category_name, b.brand_name,
               p.price_per_day, p.deposit
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        JOIN brands     b ON p.brand_id    = b.brand_id
        ORDER BY p.product_name
    """)
    products = cur.fetchall()
    cur.execute("SELECT category_id, category_name FROM categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.execute("SELECT brand_id, brand_name FROM brands ORDER BY brand_name")
    brands = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/products.html", products=products,
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
    image_name = normalize_image_filename(
        request.form.get("image", "") or request.form.get("image_url", "")
    )

    if not all([name, category_id, brand_id, price, image_name]):
        return redirect(url_for("admin_products"))

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO products (product_name, category_id, brand_id, price_per_day, deposit, image_url)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, category_id, brand_id, price, deposit, image_name))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_products"))


# ── ADMIN: INVENTORY ──────────────────────────────────────

@app.route("/admin/inventory")
def admin_inventory():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT i.inventory_id, p.product_name, i.availability_status, i.item_condition
        FROM inventory i
        JOIN products p ON i.product_id = p.product_id
        ORDER BY p.product_name
    """)
    inventory = cur.fetchall()
    cur.execute("SELECT product_id, product_name FROM products ORDER BY product_name")
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/inventory.html", inventory=inventory, products=products)


@app.route("/admin/inventory/add", methods=["POST"])
def admin_add_inventory():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    product_id = request.form.get("product_id")
    status     = request.form.get("availability_status", "available")
    condition  = request.form.get("item_condition", "good")

    if not product_id:
        return redirect(url_for("admin_inventory"))

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO inventory (product_id, availability_status, item_condition)
            VALUES (%s, %s, %s)
        """, (product_id, status, condition))
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
    if status in ("available", "reserved", "rented", "maintenance", "retired"):
        conn = get_connection()
        cur  = conn.cursor()
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


# ── ADMIN: BOOKINGS ───────────────────────────────────────

@app.route("/admin/bookings")
def admin_bookings():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT b.booking_id, u.full_name, p.product_name,
               b.start_date, b.end_date, b.status
        FROM bookings b
        JOIN users     u ON b.user_id      = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        WHERE LOWER(TRIM(COALESCE(b.status, ''))) <> 'cancelled'
        ORDER BY b.booking_id DESC
    """)
    bookings = cur.fetchall()
    pending_bookings = [b for b in bookings if b[5] == "pending"]
    confirmed_bookings = [b for b in bookings if b[5] == "confirmed"]
    cur.close()
    conn.close()
    return render_template(
        "admin/bookings.html",
        bookings=bookings,
        pending_bookings=pending_bookings,
        confirmed_bookings=confirmed_bookings,
    )


@app.route("/admin/bookings/update/<int:booking_id>", methods=["POST"])
def admin_update_booking(booking_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))

    new_status = request.form.get("status")
    if new_status not in ("confirmed", "cancelled"):
        return redirect(url_for("admin_bookings"))

    conn = get_connection()
    cur  = conn.cursor()
    try:
        if new_status == "confirmed":
            cur.execute("CALL confirm_booking(%s)", (booking_id,))
        else:
            cur.execute(
                "SELECT b.inventory_id, b.status FROM bookings b WHERE b.booking_id = %s",
                (booking_id,),
            )
            booking = cur.fetchone()
            if not booking:
                return redirect(url_for("admin_bookings"))
            inventory_id, current_status = booking
            if current_status not in ("pending", "confirmed"):
                return redirect(url_for("admin_bookings"))

            cur.execute("UPDATE bookings SET status = 'cancelled' WHERE booking_id = %s", (booking_id,))
            cur.execute(
                "UPDATE inventory SET availability_status = 'available' WHERE inventory_id = %s",
                (inventory_id,),
            )
            cur.execute(
                "UPDATE rentals SET status = 'cancelled' WHERE booking_id = %s AND status = 'ongoing'",
                (booking_id,),
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(str(e).split("\n")[0] if str(e) else "Booking update failed.", "error")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_bookings"))


# ── ADMIN: USERS ──────────────────────────────────────────

@app.route("/admin/users")
def admin_users():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT user_id, full_name, email, phone, address FROM users WHERE role_id = 1 ORDER BY full_name")
    regular_users = cur.fetchall()
    cur.execute("SELECT user_id, full_name, email, phone, address FROM users WHERE role_id = 2 ORDER BY full_name")
    admins = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/users.html", regular_users=regular_users, admins=admins)


# ── ADMIN: PAYMENTS ───────────────────────────────────────

@app.route("/admin/payments")
def admin_payments():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT pay.payment_id, u.full_name, p.product_name,
               pay.amount, pay.payment_date, pay.status, r.status AS rental_status
        FROM payments pay
        JOIN rentals   r ON pay.rental_id  = r.rental_id
        JOIN bookings  b ON r.booking_id   = b.booking_id
        JOIN users     u ON b.user_id      = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        ORDER BY pay.payment_date DESC NULLS LAST, pay.payment_id DESC
    """)
    payments = cur.fetchall()
    cur.close()
    conn.close()
    pending_payments = [x for x in payments if x[5] == "pending"]
    paid_payments = [x for x in payments if x[5] == "paid"]
    refunded_payments = [x for x in payments if x[5] == "refunded"]
    return render_template(
        "admin/payments.html",
        pending_payments=pending_payments,
        paid_payments=paid_payments,
        refunded_payments=refunded_payments,
    )


@app.route("/admin/payments/update/<int:payment_id>", methods=["POST"])
def admin_update_payment(payment_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    status = request.form.get("status")
    if status not in ("paid", "pending", "refunded"):
        return redirect(url_for("admin_payments"))
    conn = get_connection()
    cur  = conn.cursor()
    try:
        # Stamp payment_date only when marking paid; clear when not paid (matches trigger intent).
        if status == "paid":
            cur.execute(
                """
                UPDATE payments
                SET status = %s, payment_date = CURRENT_TIMESTAMP
                WHERE payment_id = %s
                """,
                (status, payment_id),
            )
        else:
            cur.execute(
                """
                UPDATE payments
                SET status = %s, payment_date = NULL
                WHERE payment_id = %s
                """,
                (status, payment_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_payments"))


# ── ADMIN: RENTALS ────────────────────────────────────────

@app.route("/admin/rentals")
def admin_rentals():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT r.rental_id, u.full_name, p.product_name,
               r.issue_date, r.due_date, r.status
        FROM rentals r
        JOIN bookings  b ON r.booking_id   = b.booking_id
        JOIN users     u ON b.user_id      = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        ORDER BY r.rental_id DESC
    """)
    rentals = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/rentals.html", rentals=rentals)


# ── ADMIN: RETURNS ────────────────────────────────────────

@app.route("/admin/returns")
def admin_returns():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT rt.return_id, u.full_name, p.product_name,
               rt.return_date, rt.item_condition
        FROM returns rt
        JOIN rentals   r ON rt.rental_id   = r.rental_id
        JOIN bookings  b ON r.booking_id   = b.booking_id
        JOIN users     u ON b.user_id      = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        ORDER BY rt.return_id DESC
    """)
    returns = cur.fetchall()
    cur.execute("""
        SELECT r.rental_id, u.full_name, p.product_name, r.due_date
        FROM rentals r
        JOIN bookings  b ON r.booking_id   = b.booking_id
        JOIN users     u ON b.user_id      = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        WHERE r.status = 'ongoing'
          AND r.rental_id NOT IN (SELECT rental_id FROM returns)
        ORDER BY r.due_date
    """)
    pending_returns = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/returns.html", returns=returns, pending_returns=pending_returns)


@app.route("/admin/returns/process/<int:rental_id>", methods=["POST"])
def admin_process_return(rental_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))

    return_date = request.form.get("return_date")
    condition   = request.form.get("item_condition")
    penalty_amount_raw = (request.form.get("penalty_amount") or "0").strip()
    penalty_reason = request.form.get("penalty_reason", "").strip()

    if not return_date or condition not in ("excellent", "good", "fair", "damaged", "lost"):
        flash("Please provide a valid return date and item condition.", "error")
        return redirect(url_for("admin_returns"))

    try:
        penalty_amount = Decimal(penalty_amount_raw or "0")
    except InvalidOperation:
        flash("Penalty amount must be a valid number.", "error")
        return redirect(url_for("admin_returns"))

    if penalty_amount < 0:
        flash("Penalty amount cannot be negative.", "error")
        return redirect(url_for("admin_returns"))

    if penalty_amount > 0 and not penalty_reason:
        flash("Penalty reason is required when penalty amount is greater than 0.", "error")
        return redirect(url_for("admin_returns"))

    try:
        return_date_obj = date.fromisoformat(return_date)
    except ValueError:
        flash("Invalid return date format.", "error")
        return redirect(url_for("admin_returns"))

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "CALL process_return(%s, %s::date, %s, %s::numeric, %s)",
            (
                rental_id,
                return_date_obj,
                condition,
                penalty_amount,
                penalty_reason if penalty_amount > 0 else "",
            ),
        )
        conn.commit()
        flash("Return processed successfully.", "success")
    except Exception as e:
        conn.rollback()
        msg = str(e).split("\n")[0] if str(e) else "Could not process return."
        flash(f"Could not process return: {msg}", "error")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_returns"))


# ── ADMIN: PENALTIES ──────────────────────────────────────

@app.route("/admin/penalties")
def admin_penalties():
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT pe.penalty_id, u.full_name, p.product_name,
               pe.amount, pe.reason, pe.status
        FROM penalties pe
        JOIN returns   rt ON pe.return_id   = rt.return_id
        JOIN rentals   r  ON rt.rental_id   = r.rental_id
        JOIN bookings  b  ON r.booking_id   = b.booking_id
        JOIN users     u  ON b.user_id      = u.user_id
        JOIN inventory i  ON b.inventory_id = i.inventory_id
        JOIN products  p  ON i.product_id   = p.product_id
        ORDER BY pe.penalty_id DESC
    """)
    penalties = cur.fetchall()
    cur.execute("""
        SELECT rt.return_id, u.full_name, p.product_name, rt.item_condition
        FROM returns rt
        JOIN rentals   r ON rt.rental_id   = r.rental_id
        JOIN bookings  b ON r.booking_id   = b.booking_id
        JOIN users     u ON b.user_id      = u.user_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        WHERE rt.return_id NOT IN (SELECT return_id FROM penalties)
        ORDER BY rt.return_id DESC
    """)
    returnable = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin/penalties.html", penalties=penalties, returnable=returnable)


@app.route("/admin/penalties/add/<int:return_id>", methods=["POST"])
def admin_add_penalty(return_id):
    if not session.get("user_id") or session.get("role_id") != 2:
        return redirect(url_for("login"))
    amount = request.form.get("amount")
    reason = request.form.get("reason", "").strip()
    if not amount or not reason:
        return redirect(url_for("admin_penalties"))
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("INSERT INTO penalties (return_id, amount, reason) VALUES (%s, %s, %s)",
                    (return_id, amount, reason))
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
    cur  = conn.cursor()
    try:
        cur.execute("UPDATE penalties SET status = %s WHERE penalty_id = %s", (status, penalty_id))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("admin_penalties"))


# ── USER: BROWSE PRODUCTS ─────────────────────────────────

@app.route("/products")
def products_dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT p.product_id, p.product_name, c.category_name, b.brand_name,
               p.price_per_day, p.deposit, p.image_url,
               EXISTS (
                   SELECT 1
                   FROM inventory i
                   WHERE i.product_id = p.product_id
                     AND LOWER(TRIM(COALESCE(i.availability_status, ''))) != 'retired'
               ) AS has_available_inventory
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        JOIN brands     b ON p.brand_id    = b.brand_id
        ORDER BY p.product_name
    """)
    products = cur.fetchall()
    cur.execute("SELECT category_id, category_name FROM categories ORDER BY category_name")
    categories = cur.fetchall()
    cur.execute("SELECT brand_id, brand_name FROM brands ORDER BY brand_name")
    brands = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("user_dashboard/products_dashboard.html",
                           products=products, categories=categories, brands=brands)


# ── USER: PRODUCT DETAIL ──────────────────────────────────

@app.route("/products/<int:product_id>")
def product_detail(product_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT p.product_id, p.product_name, c.category_name, b.brand_name,
               p.price_per_day, p.deposit, p.image_url
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        JOIN brands     b ON p.brand_id    = b.brand_id
        WHERE p.product_id = %s
    """, (product_id,))
    product = cur.fetchone()

    if not product:
        cur.close()
        conn.close()
        return redirect(url_for("products_dashboard"))

    cur.execute("""
        SELECT inventory_id, item_condition FROM inventory
        WHERE product_id = %s
          AND LOWER(TRIM(COALESCE(availability_status, ''))) != 'retired'
    """, (product_id,))
    inventory_items = cur.fetchall()

    cur.execute("""
        SELECT u.full_name, r.rating, r.comment
        FROM reviews r
        JOIN users u ON r.user_id = u.user_id
        WHERE r.product_id = %s
        ORDER BY r.review_id DESC
    """, (product_id,))
    reviews = cur.fetchall()

    cur.execute("SELECT get_avg_rating(%s)", (product_id,))
    avg_rating = cur.fetchone()[0]

    cur.execute("SELECT review_id FROM reviews WHERE user_id = %s AND product_id = %s",
                (session["user_id"], product_id))
    already_reviewed = cur.fetchone() is not None

    cur.execute("""
        SELECT 1 FROM rentals r
        JOIN bookings  b ON r.booking_id   = b.booking_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        WHERE b.user_id = %s AND i.product_id = %s
          AND r.status IN ('ongoing', 'returned', 'overdue')
        LIMIT 1
    """, (session["user_id"], product_id))
    has_rented = cur.fetchone() is not None

    view_mode = request.args.get("view", "details")
    if view_mode not in ("details", "book"):
        view_mode = "details"

    cur.close()
    conn.close()
    return render_template("user_dashboard/product_detail.html",
                           product=product, inventory_items=inventory_items,
                           reviews=reviews, avg_rating=avg_rating,
                           already_reviewed=already_reviewed,
                           can_review=has_rented, view_mode=view_mode)


# ── USER: BOOK A PRODUCT ──────────────────────────────────

@app.route("/book/<int:inventory_id>", methods=["POST"])
def book_product(inventory_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    product_id_hint = request.form.get("product_id", type=int)
    start_date = request.form.get("start_date")
    end_date   = request.form.get("end_date")

    def redirect_booking_page(category, message, pid=None):
        flash(message, category)
        target = pid if pid is not None else product_id_hint
        if target:
            return redirect(
                url_for("product_detail", product_id=target, view="book") + "#book-section"
            )
        return redirect(url_for("products_dashboard"))

    if not start_date or not end_date:
        return redirect_booking_page("error", "Please select both start and end dates.")

    try:
        start_date_obj = date.fromisoformat(start_date)
        end_date_obj = date.fromisoformat(end_date)
    except ValueError:
        return redirect_booking_page("error", "Invalid date format.")

    if end_date_obj < start_date_obj:
        return redirect_booking_page("error", "End date cannot be before start date.")

    conn = get_connection()
    cur  = conn.cursor()
    booking_ok = False
    booking_error = None
    product_id_for_error = product_id_hint
    try:
        # Lock this inventory row so two simultaneous submits cannot double-book.
        cur.execute(
            """
            SELECT product_id, LOWER(TRIM(COALESCE(availability_status, '')))
            FROM inventory
            WHERE inventory_id = %s
            FOR UPDATE
            """,
            (inventory_id,),
        )
        row = cur.fetchone()
        if not row:
            flash("This inventory item was not found.", "error")
            return redirect(url_for("products_dashboard"))

        product_id_for_error, inv_status = row
        if product_id_hint and product_id_hint != product_id_for_error:
            return redirect_booking_page(
                "error",
                "This booking form does not match the selected item. Please use the form on this page.",
                product_id_for_error,
            )

        if inv_status == "retired":
            return redirect_booking_page(
                "error",
                "This item is not available for booking.",
                product_id_for_error,
            )

        cur.execute(
            "SELECT check_date_overlap(%s, %s, %s, %s)",
            (inventory_id, start_date_obj, end_date_obj, 0),
        )
        if cur.fetchone()[0]:
            return redirect_booking_page(
                "error",
                "Those dates are already reserved for this item.",
                product_id_for_error,
            )

        cur.execute("""
            INSERT INTO bookings (user_id, inventory_id, start_date, end_date, status)
            VALUES (%s, %s, %s, %s, 'pending')
        """, (session["user_id"], inventory_id, start_date, end_date))
        conn.commit()
        flash("Booking request submitted. Waiting for admin confirmation.", "success")
        booking_ok = True
    except Exception:
        conn.rollback()
        booking_error = "Could not submit booking. Please try again."
    finally:
        cur.close()
        conn.close()

    if booking_ok:
        return redirect(url_for("my_bookings"))
    if booking_error:
        return redirect_booking_page("error", booking_error, product_id_for_error)
    return redirect(url_for("products_dashboard"))


# ── USER: MY BOOKINGS ─────────────────────────────────────

@app.route("/my/bookings")
def my_bookings():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT b.booking_id, p.product_name, b.start_date, b.end_date, b.status
        FROM bookings b
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        WHERE b.user_id = %s
          AND LOWER(TRIM(COALESCE(b.status, ''))) <> 'cancelled'
        ORDER BY b.booking_id DESC
    """, (session["user_id"],))
    bookings = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("user_dashboard/my_bookings.html", bookings=bookings)


@app.route("/my/bookings/cancel/<int:booking_id>", methods=["POST"])
def cancel_booking(booking_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT inventory_id, status FROM bookings
            WHERE booking_id = %s AND user_id = %s
        """, (booking_id, session["user_id"]))
        row = cur.fetchone()

        if not row or row[1] != "pending":
            flash("You can only cancel a booking before it has been confirmed.", "error")
            return redirect(url_for("my_bookings"))

        cur.execute("UPDATE bookings SET status = 'cancelled' WHERE booking_id = %s", (booking_id,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("my_bookings"))


# ── USER: MY RENTALS ──────────────────────────────────────

@app.route("/my/rentals")
def my_rentals():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT r.rental_id, p.product_name, r.issue_date, r.due_date,
               r.actual_return_date, r.status
        FROM rentals r
        JOIN bookings  b ON r.booking_id   = b.booking_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        WHERE b.user_id = %s
        ORDER BY r.rental_id DESC
    """, (session["user_id"],))
    rentals = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("user_dashboard/my_rentals.html", rentals=rentals)


# ── USER: MY PAYMENTS ─────────────────────────────────────

@app.route("/my/payments")
def my_payments():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT pay.payment_id, pay.rental_id, p.product_name, p.deposit,
               pay.amount, pay.payment_date, pay.status, r.status AS rental_status
        FROM payments pay
        JOIN rentals   r ON pay.rental_id  = r.rental_id
        JOIN bookings  b ON r.booking_id   = b.booking_id
        JOIN inventory i ON b.inventory_id = i.inventory_id
        JOIN products  p ON i.product_id   = p.product_id
        WHERE b.user_id = %s
        ORDER BY pay.payment_date DESC NULLS LAST, pay.payment_id DESC
    """, (session["user_id"],))
    payment_items = cur.fetchall()
    cur.close()
    conn.close()
    pending_payment_items = [x for x in payment_items if x[6] == "pending"]
    paid_payment_items = [x for x in payment_items if x[6] == "paid"]
    refunded_payment_items = [x for x in payment_items if x[6] == "refunded"]
    return render_template(
        "user_dashboard/my_payments.html",
        pending_payment_items=pending_payment_items,
        paid_payment_items=paid_payment_items,
        refunded_payment_items=refunded_payment_items,
    )


@app.route("/my/payments/pay/<int:payment_id>", methods=["POST"])
def pay_payment(payment_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT pay.payment_id FROM payments pay
            JOIN rentals  r ON pay.rental_id = r.rental_id
            JOIN bookings b ON r.booking_id  = b.booking_id
            WHERE pay.payment_id = %s AND b.user_id = %s AND pay.status = 'pending'
        """, (payment_id, session["user_id"]))
        if not cur.fetchone():
            return redirect(url_for("my_payments"))

        cur.execute(
            """
            UPDATE payments
            SET status = 'paid', payment_date = CURRENT_TIMESTAMP
            WHERE payment_id = %s
            """,
            (payment_id,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("my_payments"))


# ── USER: MY PROFILE ──────────────────────────────────────

@app.route("/my/profile", methods=["GET", "POST"])
def my_profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn    = get_connection()
    cur     = conn.cursor()
    message = None

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone     = request.form.get("phone", "").strip()
        address   = request.form.get("address", "").strip()
        password  = request.form.get("password", "")

        if not full_name:
            message = "Full name is required."
        else:
            try:
                if password:
                    if len(password) < 8:
                        message = "Password must be at least 8 characters."
                    else:
                        cur.execute("""
                            UPDATE users SET full_name=%s, phone=%s, address=%s, password=%s
                            WHERE user_id=%s
                        """, (full_name, phone or None, address or None, password, session["user_id"]))
                        conn.commit()
                        session["full_name"] = full_name
                        message = "Profile updated."
                else:
                    cur.execute("""
                        UPDATE users SET full_name=%s, phone=%s, address=%s
                        WHERE user_id=%s
                    """, (full_name, phone or None, address or None, session["user_id"]))
                    conn.commit()
                    session["full_name"] = full_name
                    message = "Profile updated."
            except Exception:
                conn.rollback()
                message = "Could not update profile."

    cur.execute("SELECT full_name, email, phone, address FROM users WHERE user_id = %s",
                (session["user_id"],))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("user_dashboard/my_profile.html", user=user, message=message)


# ── USER: MY REVIEWS ──────────────────────────────────────

@app.route("/my/reviews")
def my_reviews():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT r.review_id, p.product_name, r.rating, r.comment
        FROM reviews r
        JOIN products p ON r.product_id = p.product_id
        WHERE r.user_id = %s
        ORDER BY r.review_id DESC
    """, (session["user_id"],))
    reviews = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("user_dashboard/my_reviews.html", reviews=reviews)


@app.route("/reviews/add/<int:product_id>", methods=["POST"])
def add_review(product_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    rating  = request.form.get("rating")
    comment = request.form.get("comment", "").strip()

    if not rating or not rating.isdigit() or not (1 <= int(rating) <= 5):
        return redirect(url_for("product_detail", product_id=product_id))

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT 1 FROM rentals r
            JOIN bookings  b ON r.booking_id   = b.booking_id
            JOIN inventory i ON b.inventory_id = i.inventory_id
            WHERE b.user_id = %s AND i.product_id = %s
              AND r.status IN ('ongoing', 'returned', 'overdue')
            LIMIT 1
        """, (session["user_id"], product_id))
        if not cur.fetchone():
            return redirect(url_for("product_detail", product_id=product_id))

        cur.execute("SELECT 1 FROM reviews WHERE user_id = %s AND product_id = %s LIMIT 1",
                    (session["user_id"], product_id))
        if cur.fetchone():
            return redirect(url_for("product_detail", product_id=product_id))

        cur.execute("INSERT INTO reviews (user_id, product_id, rating, comment) VALUES (%s, %s, %s, %s)",
                    (session["user_id"], product_id, int(rating), comment or None))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("product_detail", product_id=product_id))


@app.route("/reviews/delete/<int:review_id>", methods=["POST"])
def delete_review(review_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM reviews WHERE review_id = %s AND user_id = %s",
                    (review_id, session["user_id"]))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for("my_reviews"))


if __name__ == "__main__":
    app.run(debug=True)