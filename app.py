from functools import wraps
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

def db():
    return mysql.connector.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DATABASE"],
        port=app.config.get("MYSQL_PORT", 3306)
    )

def execute(sql, params=(), one=False, all=False, commit=False):
    con = db()
    cur = con.cursor(dictionary=True)
    cur.execute(sql, params)
    data = None
    if one:
        data = cur.fetchone()
    if all:
        data = cur.fetchall()
    if commit:
        con.commit()
        data = cur.lastrowid
    cur.close()
    con.close()
    return data

def login_required(role=None):
    def outer(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("Permission denied.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return inner
    return outer

@app.context_processor
def inject_user():
    return {"user": session}

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        
        if not name or not email or not password or not role:
            flash("All fields are required.", "danger")
            return render_template("register.html")
            
        if role not in ["donor", "receiver"]:
            flash("Choose donor or receiver only.", "danger")
            return render_template("register.html")
            
        old = execute("SELECT id FROM users WHERE email=%s", (email,), one=True)
        if old:
            flash("Email already registered.", "danger")
            return render_template("register.html")
            
        hashed_password = generate_password_hash(password)
        execute("INSERT INTO users(name,email,password,role,phone,address) VALUES(%s,%s,%s,%s,%s,%s)",
                (name, email, hashed_password, role, phone, address), commit=True)
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        selected_role = request.form.get("role", "").strip()
        
        if not email or not password or not selected_role:
            flash("Please fill in all fields.", "warning")
            return render_template("login.html")
            
        u = execute("SELECT * FROM users WHERE email=%s", (email,), one=True)
        if u:
            if check_password_hash(u["password"], password):
                if u["role"] == selected_role:
                    session["user_id"] = u["id"]
                    session["name"] = u["name"]
                    session["role"] = u["role"]
                    session["email"] = u["email"]
                    flash("Login successful.", "success")
                    return redirect(url_for("dashboard"))
                else:
                    flash("This account is not registered as selected role.", "danger")
                    return render_template("login.html")
            else:
                flash("Invalid email or password.", "danger")
                return render_template("login.html")
        else:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required()
def dashboard():
    if session["role"] == "donor":
        return redirect(url_for("donor_dashboard"))
    if session["role"] == "receiver":
        return redirect(url_for("receiver_dashboard"))
    return redirect(url_for("admin_dashboard"))

@app.route("/donor")
@login_required("donor")
def donor_dashboard():
    donations = execute("""SELECT *, DATE_FORMAT(expiry_datetime,'%d-%m-%Y %h:%i %p') exp
                           FROM food_donations WHERE donor_id=%s ORDER BY id DESC""",
                        (session["user_id"],), all=True)
    return render_template("donor_dashboard.html", donations=donations)

@app.route("/add_food", methods=["GET","POST"])
@login_required("donor")
def add_food():
    if request.method == "POST":
        execute("""INSERT INTO food_donations
                (donor_id,food_name,food_type,quantity,location,pickup_address,expiry_datetime,description)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (session["user_id"], request.form["food_name"], request.form["food_type"],
                 request.form["quantity"], request.form["location"], request.form["pickup_address"],
                 request.form["expiry_datetime"], request.form.get("description")), commit=True)
        flash("Food added successfully.", "success")
        return redirect(url_for("donor_dashboard"))
    return render_template("add_food.html")

@app.route("/receiver")
@login_required("receiver")
def receiver_dashboard():
    foods = execute("SELECT COUNT(*) c FROM food_donations WHERE status='Available' AND expiry_datetime >= NOW()", one=True)
    reqs = execute("SELECT COUNT(*) c FROM food_requests WHERE receiver_id=%s", (session["user_id"],), one=True)
    return render_template("receiver_dashboard.html", foods=foods, reqs=reqs)

@app.route("/available_food")
@login_required("receiver")
def available_food():
    q = request.args.get("q","")
    sql = """SELECT f.*, u.name donor_name, DATE_FORMAT(f.expiry_datetime,'%d-%m-%Y %h:%i %p') exp
             FROM food_donations f JOIN users u ON f.donor_id=u.id
             WHERE f.status='Available' AND f.expiry_datetime >= NOW()"""
    params = ()
    if q:
        sql += " AND (f.food_name LIKE %s OR f.location LIKE %s)"
        params = (f"%{q}%", f"%{q}%")
    sql += " ORDER BY f.id DESC"
    foods = execute(sql, params, all=True)
    return render_template("available_food.html", foods=foods, q=q)

@app.route("/request_food/<int:food_id>", methods=["POST"])
@login_required("receiver")
def request_food(food_id):
    existing = execute("SELECT id FROM food_requests WHERE food_id=%s AND receiver_id=%s", (food_id, session["user_id"]), one=True)
    if existing:
        flash("You have already requested this food item.", "warning")
        return redirect(url_for("my_requests"))
        
    food = execute("SELECT * FROM food_donations WHERE id=%s AND status='Available' AND expiry_datetime >= NOW()", (food_id,), one=True)
    if not food:
        flash("Food not available or already expired.", "danger")
        return redirect(url_for("available_food"))
        
    message = request.form.get("message", "").strip()
    if not message:
        flash("Claim message notes are required.", "warning")
        return redirect(url_for("available_food"))
        
    execute("INSERT INTO food_requests(food_id,receiver_id,message) VALUES(%s,%s,%s)",
            (food_id, session["user_id"], message), commit=True)
    execute("UPDATE food_donations SET status='Requested' WHERE id=%s", (food_id,), commit=True)
    flash("Request sent.", "success")
    return redirect(url_for("my_requests"))

@app.route("/my_requests")
@login_required("receiver")
def my_requests():
    reqs = execute("""SELECT r.*, f.food_name, f.quantity, f.location, f.pickup_address, u.name donor_name
                      FROM food_requests r
                      JOIN food_donations f ON r.food_id=f.id
                      JOIN users u ON f.donor_id=u.id
                      WHERE r.receiver_id=%s ORDER BY r.id DESC""", (session["user_id"],), all=True)
    return render_template("my_requests.html", reqs=reqs)

@app.route("/manage_requests")
@login_required("donor")
def manage_requests():
    reqs = execute("""SELECT r.*, f.food_name, f.quantity, f.location, f.pickup_address,
                             u.name receiver_name, u.phone receiver_phone
                      FROM food_requests r
                      JOIN food_donations f ON r.food_id=f.id
                      JOIN users u ON r.receiver_id=u.id
                      WHERE f.donor_id=%s ORDER BY r.id DESC""", (session["user_id"],), all=True)
    return render_template("manage_requests.html", reqs=reqs)

@app.route("/update_request/<int:rid>/<action>", methods=["POST"])
@login_required("donor")
def update_request(rid, action):
    r = execute("""SELECT r.*, f.donor_id FROM food_requests r
                   JOIN food_donations f ON r.food_id=f.id WHERE r.id=%s""", (rid,), one=True)
    if not r or r["donor_id"] != session["user_id"]:
        flash("Request not found.", "danger")
        return redirect(url_for("manage_requests"))
    if action == "accept":
        execute("UPDATE food_requests SET request_status='Accepted' WHERE id=%s", (rid,), commit=True)
        execute("UPDATE food_donations SET status='Accepted' WHERE id=%s", (r["food_id"],), commit=True)
    elif action == "reject":
        execute("UPDATE food_requests SET request_status='Rejected' WHERE id=%s", (rid,), commit=True)
        execute("UPDATE food_donations SET status='Available' WHERE id=%s", (r["food_id"],), commit=True)
    elif action == "complete":
        execute("UPDATE food_requests SET request_status='Completed' WHERE id=%s", (rid,), commit=True)
        execute("UPDATE food_donations SET status='Completed' WHERE id=%s", (r["food_id"],), commit=True)
    flash("Request updated.", "success")
    return redirect(url_for("manage_requests"))

@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    data = {
        "users": execute("SELECT COUNT(*) c FROM users", one=True),
        "donations": execute("SELECT COUNT(*) c FROM food_donations", one=True),
        "requests": execute("SELECT COUNT(*) c FROM food_requests", one=True)
    }
    recent_users = execute("SELECT id, name, email, role, phone, DATE_FORMAT(created_at,'%d-%m-%Y') dt FROM users ORDER BY id DESC LIMIT 5", all=True)
    recent_donations = execute("""
        SELECT f.id, f.food_name, f.status, u.name donor_name, DATE_FORMAT(f.created_at,'%d-%m-%Y') dt
        FROM food_donations f
        JOIN users u ON f.donor_id = u.id
        ORDER BY f.id DESC LIMIT 5
    """, all=True)
    return render_template("admin_dashboard.html", data=data, recent_users=recent_users, recent_donations=recent_donations)

@app.route("/admin/users")
@login_required("admin")
def admin_users():
    users = execute("""
        SELECT u.id, u.name, u.email, u.role, u.phone, u.address,
               (SELECT COUNT(*) FROM food_donations WHERE donor_id = u.id) AS donation_count,
               (SELECT COUNT(*) FROM food_requests WHERE receiver_id = u.id) AS request_count
        FROM users u
        ORDER BY u.id DESC
    """, all=True)
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/edit/<int:user_id>", methods=["POST"])
@login_required("admin")
def admin_edit_user(user_id):
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    
    if not name or not email or role not in ["donor", "receiver", "admin"]:
        flash("Invalid input data. Name, Email, and valid Role are required.", "danger")
        return redirect(url_for("admin_users"))
        
    # Check email duplicate excluding current user
    existing = execute("SELECT id FROM users WHERE email=%s AND id!=%s", (email, user_id), one=True)
    if existing:
        flash("Email is already in use by another account.", "danger")
        return redirect(url_for("admin_users"))
        
    execute("""
        UPDATE users 
        SET name=%s, email=%s, role=%s, phone=%s, address=%s 
        WHERE id=%s
    """, (name, email, role, phone, address, user_id), commit=True)
    flash("User details updated successfully.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required("admin")
def admin_delete_user(user_id):
    if user_id == session["user_id"]:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for("admin_users"))
        
    execute("DELETE FROM users WHERE id=%s", (user_id,), commit=True)
    flash("User deleted successfully.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/donations")
@login_required("admin")
def admin_donations():
    donations = execute("""SELECT f.*, u.name donor_name FROM food_donations f
                           JOIN users u ON f.donor_id=u.id ORDER BY f.id DESC""", all=True)
    return render_template("admin_donations.html", donations=donations)

if __name__ == "__main__":
    app.run(debug=True)
