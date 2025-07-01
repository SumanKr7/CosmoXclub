from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pyrebase, os, firebase_admin
import requests
import json
from dotenv import load_dotenv
from werkzeug.security import check_password_hash
from firebase_admin import credentials, db as admin_db, auth as admin_auth
from datetime import datetime, timezone

from utils import (
    all_users_properties,
    get_current_user,
    is_email_registered,
    all_users_properties_admin,
    db_alive,
    is_valid_name,
    is_valid_email,
    is_valid_phone,
    is_valid_password,
    _process_post,
    validate_property_form,
    collect_property_form_data,
    homes_images
)

load_dotenv()

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': os.getenv("FIREBASE_DATABASE_URL")
})

firebaseConfig = {
    'apiKey': os.getenv("FIREBASE_API_KEY"),
    'authDomain': os.getenv("FIREBASE_AUTH_DOMAIN"),
    'databaseURL': os.getenv("FIREBASE_DATABASE_URL"),
    'projectId': os.getenv("FIREBASE_PROJECT_ID"),
    'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET"),
    'messagingSenderId': os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    'appId': os.getenv("FIREBASE_APP_ID"),
    'measurementId': os.getenv("FIREBASE_MEASUREMENT_ID")
}

firebase = pyrebase.initialize_app(firebaseConfig)
pyrebase_auth = firebase.auth()
db = firebase.database()

def is_email_verified():
    try:
        id_token = session.get('id_token')
        if id_token:
            decoded_token = admin_auth.verify_id_token(id_token)
            user = admin_auth.get_user(decoded_token['uid'])
            return user.email_verified
    except Exception:
        pass
    return False

UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

UPLOAD_FOLDER_PROFILE = 'static/profile/'
app.config['UPLOAD_FOLDER_PROFILE'] = UPLOAD_FOLDER_PROFILE

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.context_processor
def inject_user():
    try:
        return dict(user=get_current_user())
    except Exception as e:
        return dict(user={})

# Route for the home page

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        if not email:
            flash("Email is required.", "light")
            return redirect(url_for('home'))

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "light")
            return redirect(url_for('home'))

        try:
            admin_db.reference('subscriptions').push({
                "email": email,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            flash("Thank you for subscribing!", "success")
        except Exception as e:
            flash("Your email couldn't be subscribed at the moment. Please try again later.", "light")

        return redirect(url_for('home'))

    return render_template('home.html')

# Route for about pages

@app.route('/about-us')
def about_us():
    return render_template('about-us.html')

# Route for contact page

@app.route('/contact-us', methods=['GET', 'POST'])
def contact_us():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        phone   = request.form.get('phone', '').strip()
        message = request.form.get('message', '').strip()

        if not all([name, email, phone, message]):
            flash("All fields are required.", "light")
            return redirect(url_for('contact-us'))
        
        if not is_valid_name(name):
            flash("Please enter a valid name.", "light")
            return redirect(url_for('contact-us'))

        if not is_valid_email(email):
            flash("Please enter a valid email address.", "light")
            return redirect(url_for('contact-us'))

        if not is_valid_phone(phone):
            flash("Please enter a valid phone number.", "light")
            return redirect(url_for('contact-us'))

        try:
            admin_db.reference('contact_form').push({
                "name": name,
                "email": email,
                "phone": phone,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            flash("Thank you for contacting us!", "success")
        except Exception as e:
            flash("Your message couldn’t be sent right now. Please try again later.", "light")
        
        return redirect(url_for('contact-us'))

    return render_template('contact-us.html')

# Route for FAQ

@app.route('/faq')
def faq():
    return render_template('faq.html')

# Route for blog

@app.route('/blog')
def blog():
    return render_template('blog.html')

# Route for home exchange

@app.route('/home-exchange')
def home_exchange():
    house = all_users_properties()
    return render_template("home-exchange.html", house=house)

@app.route('/home-details/<uid>')
def home_details(uid):
    one_properties = all_users_properties()
    house_details = one_properties.get(uid)
    return render_template("home-details.html", house_details=house_details)

# User authentication routes

@app.route('/signup', methods=['POST', 'GET'])
def signup():
    try:
        if 'user' in session:
            return redirect(url_for('home'))
        
        if request.method == 'GET':
            return redirect(url_for('home', show='signup'))
        
        if 'admin-user' in session:
            session.clear()

        name     = request.form.get('fullname', '').strip()
        phone    = request.form.get('phone', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not all([name, phone, email, password]):
            return jsonify({"status": "error", "message": "Please enter all details."}), 400
        
        if not is_valid_name(name):
            return jsonify({"status": "error", "message": "Please enter a valid name."}), 400

        if not is_valid_phone(phone):
            return jsonify({"status": "error", "message": "Invalid phone number."}), 400

        if not is_valid_email(email):
            return jsonify({"status": "error", "message": "Invalid email address."}), 400

        if not is_valid_password(password):
            return jsonify({"status": "error", "message":  "Password must be 8+ characters with uppercase, lowercase, number, and special character."}), 400
        
        if not db_alive():
            return jsonify({"status": "error", "message":  "We're unable to process your request at the moment. Please try again later."}), 503

        user = pyrebase_auth.create_user_with_email_and_password(email, password)
        session['user'] = user['localId']
        session['id_token'] = user['idToken']
        session['refresh_token'] = user['refreshToken']
        session['email'] = email

        user_data = {
            "name": name,
            "phone": phone,
            "email": email,
            "email_verified": 'No',
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        admin_db.reference(f'users/{user["localId"]}').set(user_data)

        return redirect(url_for('home'))

    except Exception as e:
        error_message = str(e)
        if "EMAIL_EXISTS" in error_message:
            return jsonify({"status": "error", "message": "Email already registered."}), 400
        else:
            return jsonify({"status": "error", "message": "We're unable to process your request at the moment. Please try again later."}), 500

@app.route('/login', methods=['POST', 'GET'])
def login():
    try:
        if 'user' in session:
            return redirect(url_for('home'))
        
        if request.method == 'GET':
            return redirect(url_for('home', show='login'))

        if 'admin-user' in session:
            session.clear()

        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not all([email, password]):
            return jsonify({"status": "error", "message": "Email and Password are required."}), 400
        
        if not is_valid_email(email):
            return jsonify({"status": "error", "message": "Enter valid email address."}), 400

        if not is_valid_password(password):
            return jsonify({"status": "error", "message":  "Enter valid password."}), 400
        
        if not db_alive():
            return jsonify({"status": "error", "message":  "We're unable to process your request at the moment. Please try again later."}), 503

        user = pyrebase_auth.sign_in_with_email_and_password(email, password)

        session['user']     = user['localId']
        session['id_token'] = user['idToken']
        session['refresh_token'] = user['refreshToken']
        session['email']    = email

        return redirect(url_for('home'))

    except Exception as e:
        error_message = str(e)
        if "INVALID_LOGIN_CREDENTIALS" in error_message:
            return jsonify({"status": "error", "message": "Invalid email or password."}), 401
        else:
            return jsonify({"status": "error", "message": "We're unable to process your request at the moment. Please try again later."}), 500

@app.route('/forgot-password', methods=['POST', 'GET'])
def forgot_password():
    try:
        if 'user' in session:
            return redirect(url_for('home'))
        
        if request.method == 'GET':
            return redirect(url_for('home', show='forgot'))

        email = request.form.get('email', '').strip()

        if not email:
            return jsonify({"status": "error", "message": "Email is required."}), 400

        if not is_valid_email(email):
            return jsonify({"status": "error", "message": "Enter valid email address."}), 400
        
        if not db_alive():
            return jsonify({"status": "error", "message":  "We're unable to process your request at the moment. Please try again later."}), 503
        
        if not is_email_registered(email):
            return jsonify({"status": "error","message": "Email not registered. Please enter your registered email."}), 404

        pyrebase_auth.send_password_reset_email(email)
        return jsonify({"status": "success", "message": "Password reset email sent successfully!"}), 200

    except Exception as e:
        return jsonify({"status": "error","message": "Failed to send password reset email. Please try again later."}), 500
    
# User routes

@app.route('/resend-verification-email')
def resend_verification_email():
    if 'user' not in session or 'id_token' not in session or 'refresh_token' not in session:
        flash("Please log in to verify your email.", "warning")
        return redirect(url_for('login'))

    try:
        id_token = session['id_token']
        refresh_token = session['refresh_token']
        api_key = os.getenv("FIREBASE_API_KEY")

        refresh_url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
        refresh_payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        refresh_response = requests.post(refresh_url, data=refresh_payload)
        if refresh_response.status_code == 200:
            refreshed_data = refresh_response.json()
            id_token = refreshed_data['id_token']
            session['id_token'] = id_token
            session['refresh_token'] = refreshed_data['refresh_token']

        verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
        payload = {
            "requestType": "VERIFY_EMAIL",
            "idToken": id_token
        }

        response = requests.post(verify_url, json=payload)
        if response.status_code == 200:
            flash("Verification email sent successfully. Please check your inbox.", "success")
        else:
            error = response.json().get('error', {}).get('message', 'Unknown error')
            flash(f"Failed to send verification email: {error}", "danger")
    except Exception as e:
        flash(f"Error sending verification email: {str(e)}", "danger")

    return redirect(url_for('my_account'))

@app.route('/email-action')
def email_action():
    mode = request.args.get('mode')
    oob_code = request.args.get('oobCode')

    firebase_config = {
        'apiKey': os.getenv("FIREBASE_API_KEY"),
        'authDomain': os.getenv("FIREBASE_AUTH_DOMAIN"),
    }

    if mode == 'verifyEmail':
        return render_template("email-verify.html", firebase_config=firebase_config)
    elif mode == 'resetPassword':
        return render_template("reset-password.html", firebase_config=firebase_config, oob_code=oob_code)
    else:
        return render_template("invalid-action.html")
    
    
@app.route('/api/email-verified', methods=['POST'])
def email_verified():
    try:
        id_token = request.json.get('idToken')
        if not id_token:
            return jsonify({"error": "Missing ID token"}), 400

        # Decode token to get user ID
        decoded_token = admin_auth.verify_id_token(id_token)
        uid = decoded_token['uid']

        # Confirm email is verified in Auth
        user_record = admin_auth.get_user(uid)
        if not user_record.email_verified:
            return jsonify({"error": "Email not verified in Auth"}), 403

        # Prepare update data
        data = {
            "email_verified": "Yes",
            "email_verified_at": datetime.now(timezone.utc).isoformat()
        }

        # Update using admin_db
        admin_db.reference(f'users/{uid}').update(data)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
@app.route('/my-account', methods=['GET', 'POST'])
def my_account():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    if not db_alive():
        flash("An unexpected error occurred while loading your account details.", "light")
        return render_template("503.html"), 503

    try:
        uid = session['user']
        email_verified = is_email_verified()

        if request.method == "POST":
            return _process_post(uid)

        return render_template("my-account.html", email_verified=email_verified)

    except Exception:
        flash("An unexpected error occurred while loading your account details.", "light")
        return render_template("503.html"), 503


@app.route('/my-home', methods=['GET', 'POST'])
def my_home():
    if 'user' not in session:
        return redirect(url_for('home'))

    if not is_email_verified():
        flash("Please verify your email before adding home details.", "light")
        return redirect(url_for('my_account'))
    
    uid = session['user']

    if request.method == 'POST':
        try:
            admin_db.reference(f'users/{uid}/properties').delete()
            return jsonify({'success': True}), 200
        except Exception as e:
            return jsonify({'success': False, 'message': 'Error deleting home. Please try again later.'}), 500

    try:
        user = admin_db.reference(f'users/{uid}').get() or {}
        return render_template('my-home.html', user=user, uid=uid)
    
    except Exception as e:
        flash("An unexpected error occurred while loading your home.", "light")
        return render_template("503.html"), 503

@app.route('/edit-home-details', methods=['GET', 'POST'])
def edit_home_details():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    if not is_email_verified():
        flash("Please verify your email before editing home details.", "light")
        return redirect(url_for('my_account'))

    try:
        uid = session['user']

        if request.method == 'POST':
            data = collect_property_form_data(request.form)

            data["house_status"] = "Not Verified"
            data["submitted_at"] = datetime.now(timezone.utc).isoformat()

            required = [
                "title", "status", "property_type", "price", "area",
                "bedrooms", "bathrooms", "address", "city", "state",
                "pin_code", "description", "building_age", "garage",
                "rooms", "features", "name", "email", "phone"
            ]
            if any(data[k] == "" or data[k] == [] for k in required):
                flash("Please fill out every field.", "light")
                return redirect(request.url)

            ok, errors = validate_property_form(data)
            if not ok:
                for msg in errors.values():
                    flash(msg, "light")
                return redirect(request.url)

            try:
                admin_db.reference(f'users/{uid}/properties').update(data)

                images_ref = admin_db.reference(f'users/{uid}/properties/images').get()
                if not images_ref:
                    flash("Please upload home images.", "light")
                    return redirect(url_for('upload_home_img'))

                flash("Home details submitted successfully.", "success")
                return redirect(url_for('edit_home_details'))

            except Exception:
                flash("An error occurred while submitting your home details. Please try again later.", "light")
                return redirect(request.url)

        return render_template("edit-home-details.html")
    
    except Exception as e:
        flash("An unexpected error occurred while submitting your home details.", "light")
        return render_template("503.html"), 503

@app.route('/update-home-images', methods=['GET', 'POST'])
def update_home_images():
    if 'user' not in session:
        return redirect(url_for('home'))
    
    if not is_email_verified():
        flash("Please verify your email before adding home images.", "light")
        return redirect(url_for('my_account'))
    
    try:
        uid = session['user']
        if request.method == "POST":
            return homes_images(uid)
        
        return render_template("update-home-images.html")
    except Exception as e:
        flash("An unexpected error occurred while uploading home images.", "light")
        return render_template("503.html"), 503
    
@app.route('/my-home-details/<uid>')
def my_house_view(uid):
    if 'user' not in session:
        return redirect(url_for('home'))
    
    if not is_email_verified():
        flash("Please verify your email before viewing home details.", "light")
        return redirect(url_for('my_account'))
    
    try:
        one_properties = all_users_properties_admin()
        house_details = one_properties.get(uid)
        if not house_details:
                return render_template('404.html'), 404
        
        return render_template("home-details.html", house_details=house_details)
    
    except Exception as e:
        flash("An unexpected error occurred while loading your property details.", "light")
        return render_template("503.html"), 503

# Admin routes

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'admin-user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        if 'user' in session:
            session.clear()

        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email and not password:
            return jsonify({"status": "error", "message": "Email and Password are required."}), 400
        
        if not is_valid_email(email):
            return jsonify({"status": "error", "message": "Enter valid email address."}), 400

        if not is_valid_password(password):
            return jsonify({"status": "error", "message":  "Enter valid password."}), 400
        
        if not db_alive():
            return jsonify({"status": "error", "message":  "We're unable to process your request at the moment. Please try again later."}), 503

        if email == ADMIN_EMAIL and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin-user'] = 'admin'
            return jsonify({"redirect": url_for('dashboard')}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid email or password."}), 401

    return render_template("admin.html")

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'admin-user' not in session:
        return redirect(url_for('home'))

    house = all_users_properties_admin()

    try:
        all_users = admin_db.reference('users').get()
        total_users = len(all_users) if all_users else 0

        verified_homes_count     = 0
        not_verified_homes_count = 0
        total_members            = 0

        for uid, user_data in house.items():
            properties = user_data.get("properties", {})
            house_status = properties.get("house_status")

            if house_status == "Verified":
                verified_homes_count += 1
            elif house_status == "Not Verified":
                not_verified_homes_count += 1

            membership = user_data.get("membership_details", {})
            plan = membership.get("plan", "").strip().lower()
            if plan in ['Silver', 'Gold', 'Platinum']:
                total_members += 1

        total_homes = verified_homes_count + not_verified_homes_count

        return render_template("dashboard.html",
            total_users               = total_users,
            all_users                 = all_users,
            total_homes               = total_homes,
            verified_homes_count      = verified_homes_count,
            not_verified_homes_count  = not_verified_homes_count,
            total_members             = total_members
        )
    except Exception as e:
        flash("An error occurred while loading the dashboard. Please try again later.", "light")
        return render_template("503.html"), 503
    
@app.route('/edit-user-profile/<uid>', methods=['GET', 'POST'])
def edit_user_profile(uid: str):
    if 'admin-user' not in session:
        return redirect(url_for('home'))

    try:
        user_ref  = admin_db.reference(f'users/{uid}')
        user_data = user_ref.get()
        if not user_data:
            return render_template('404.html'), 404

        if request.method == "POST":
            return _process_post(uid)

        return render_template("edit-user-profile.html", user=user_data, uid=uid)

    except Exception as e:
        flash("An unexpected error occurred while editing the profile.", "light")
        return render_template("503.html"), 503
    
@app.route('/all-homes', methods=['GET', 'POST'])
def all_homes():
    if 'admin-user' not in session:
        return redirect(url_for('home'))

    users_ref = admin_db.reference('users')

    if request.method == 'POST':
        user_id     = request.form.get('user_id')
        new_status  = request.form.get('dropdown_option')

        if not user_id or not new_status:
            flash('Missing user id or status; nothing was updated.', 'light')
            return redirect(url_for('all_homes'))

        try:
            users_ref.child(user_id).child('properties') \
                     .update({'house_status': new_status})
            flash('Home status updated successfully.', 'success')
        except Exception as e:
            flash('Could not update the status. Please try again.', 'light')

        return redirect(url_for('all_homes'))

    try:
        all_users  = users_ref.get() or {}
        house_data = all_users_properties_admin() or {}

        verified_homes      = 0
        not_verified_homes  = 0
        member_count        = 0

        for user in house_data.values():
            status = (user.get("properties", {}).get("house_status") or "").strip()
            if status == "Verified":
                verified_homes += 1
            elif status == "Not Verified":
                not_verified_homes += 1

            plan = (user.get("membership_details", {}).get("plan") or "").strip().lower()
            if plan in {"silver", "gold", "platinum"}:
                member_count += 1

        context = {
            "total_users":              len(all_users),
            "all_users":                house_data,
            "total_homes":              verified_homes + not_verified_homes,
            "verified_homes_count":     verified_homes,
            "not_verified_homes_count": not_verified_homes,
            "total_members":            member_count,
        }
        return render_template("all-homes.html", **context)

    except Exception as e:
        flash("An error occurred while loading the home data.", "light")
        return render_template("503.html"), 503

@app.route('/admin-home-details/<uid>')
def admin_home_details(uid):
    if 'admin-user' not in session:
        return redirect(url_for('home'))
    
    try:
        one_properties = all_users_properties_admin()
        house_details = one_properties.get(uid)
        
        if not house_details:
            return render_template('404.html'), 404
            
        return render_template("admin-home-details.html", house_details=house_details)
        
    except Exception as e:
        flash("An unexpected error occurred while load property details.", "light")
        return render_template("503.html"), 503

    
@app.route('/admin-edit-home-details/<uid>', methods=['GET', 'POST'])
def admin_edit_home_details1(uid):
    if 'admin-user' not in session:
        return redirect(url_for('home'))
    try:
        user_ref = admin_db.reference(f'users/{uid}')
        user_data = user_ref.get()

        if not user_data:
            return render_template('404.html'), 404

        if request.method == 'POST':
            data = collect_property_form_data(request.form)

            data["submitted_at"] = datetime.now(timezone.utc).isoformat()

            required = [
                "title", "status", "property_type", "price", "area",
                "bedrooms", "bathrooms", "address", "city", "state",
                "pin_code", "description", "building_age", "garage",
                "rooms", "features", "name", "email", "phone"
            ]
            if any(data[k] == "" or data[k] == [] for k in required):
                flash("Please fill out every field.", "light")
                return redirect(request.url)

            ok, errors = validate_property_form(data)
            if not ok:
                for msg in errors.values():
                    flash(msg, "light")
                return redirect(request.url)

            
            admin_db.reference(f'users/{uid}/properties').update(data)

            user_ref.child('properties').update(data)
            flash("Home details updated successfully.", "success")
            return redirect(url_for('edit_home_details', user=user_data, uid=uid))

        return render_template("admin-edit-home-details.html", user=user_data, uid=uid)

    except Exception as e:
        flash("An unexpected error occurred while editing the homes details.", "light")
        return render_template("503.html"), 503
    
@app.route('/admin-update-home-images/<uid>', methods=['GET', 'POST'])
def admin_update_home_images(uid):
    if 'admin-user' not in session:
        return redirect(url_for('home'))
    try:
        if request.method == "POST":
            return homes_images(uid)
        
        user_data = admin_db.reference(f'users/{uid}').get()
        if not user_data:
            return render_template('404.html'), 404
        
        return render_template("admin-update-home-images.html", user=user_data, uid=uid)
    except Exception as e:
        flash("An unexpected error occurred while editing the home images.", "light")
        print(e)
        return render_template("503.html"), 503
    
@app.route('/update-membership', methods=['GET', 'POST'])
def update_membership():
    if 'admin-user' not in session:
        return redirect(url_for('home'))
    
    try:
        if request.method == 'POST':
            user_id = request.form.get('user_id')
            action  = request.form.get('action', 'update')

            try:
                ref = admin_db.reference(f'users/{user_id}/membership_details')
                
                if action == 'remove':
                    ref.delete()
                    flash("Membership details removed successfully!", "success")
                else:
                    membership_data = {
                        'plan'      : request.form.get('dropdown_option'),
                        'start_date': request.form.get('start_date'),
                        'end_date'  : request.form.get('end_date')
                    }
                    ref.update(membership_data)
                    flash("Membership details saved successfully!", "success")
            except Exception as e:
                flash("Error updating membership details. Please try again later.", "light")

            return redirect(url_for('update_membership'))

        house       = all_users_properties_admin()
        all_users   = admin_db.reference('users').get() or {}
        total_users = len(all_users)

        total_members = sum(
            1 for data in house.values()
            if data.get('membership_details', {}).get('plan', '').lower() in ['silver', 'gold', 'platinum']
        )

        return render_template(
            "update-membership.html",
            total_users=total_users,
            all_users=all_users,
            total_members=total_members
        )
    
    except Exception as e:
        flash("An unexpected error occurred while updating membership details.", "light")
        return render_template("503.html"), 503

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(port=5003, debug=True)