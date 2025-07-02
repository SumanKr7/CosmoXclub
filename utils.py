import re
from flask import session, request, redirect, url_for, flash, current_app as app, Request
import os
import base64
from datetime import datetime, timezone, timedelta
from PIL import Image
from io import BytesIO
from firebase_admin import initialize_app, credentials, auth
from firebase_admin import db as admin_db
from typing import Dict, Any, Tuple, Set
import uuid, json

def db_alive() -> bool:
    try:
        admin_db.reference('healthcheck').get(shallow=True)
        return True
    except Exception:
        return False

def all_users_properties() -> Dict[str, Any]:
    try:
        all_users = admin_db.reference('users').get()
        if not all_users:
            return {}

        current_uid = session.get('user')

        filtered_users = {
            uid: data for uid, data in all_users.items()
            if uid != current_uid and data.get('properties', {}).get('house_status') == "Verified"
        }

        return filtered_users

    except Exception as e:
        return {}

def get_current_user() -> Dict[str, Any]:
    uid = session.get('user')
    if not uid:
        return {}

    try:
        user_data = admin_db.reference(f'users/{uid}').get()
        return user_data or {}
    except Exception as e:
        return {}

def is_email_registered(email: str) -> bool:
    try:
        users = admin_db.reference('users').get()
        if not users:
            return False

        return any(user.get('email') == email for user in users.values())

    except Exception as e:
        return False
    
def all_users_properties_admin():
    try:
        all_users = admin_db.reference('users').get()
        if not all_users:
            return {}

        filtered_users = {
            uid: data for uid, data in all_users.items()
            if 'properties' in data and data['properties'].get('house_status', '').strip() != ""
        }

        return filtered_users

    except Exception as e:
        return {}

def is_valid_name(name: str) -> bool:
    """Letters & spaces only, at least 2 chars."""
    return bool(re.fullmatch(r"^[A-Za-z\s]+$", name))

def is_valid_email(email: str) -> bool:
    """Simple RFC-5322-ish check."""
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))

def is_valid_phone(phone: str) -> bool:
    """10-15 digits, optional leading '+'."""
    return bool(re.fullmatch(r"^\+?\d{10,15}$", phone))

def is_valid_password(password: str) -> bool:
    """
    ≥8 chars, ≥1 upper, ≥1 lower, ≥1 digit, ≥1 special.
    Adjust the set @$!%*?& if you need more/less symbols.
    """
    return bool(re.fullmatch(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password))

def is_valid_occupation(occupation: str) -> bool:
    """Letters, spaces, & basic punctuation (e.g., 'Sr. Dev')"""
    return bool(re.fullmatch(r"[A-Za-z\s.&/-]{2,100}", occupation))

def is_valid_address(address: str) -> bool:
    """Letters, digits & basic punctuation; 5-120 chars."""
    return bool(re.fullmatch(r"[\w\s,./#\-]{5,120}", address))

def is_valid_city(city: str) -> bool:
    """Letters & spaces, 2-50 chars."""
    return bool(re.fullmatch(r"[A-Za-z\s]{2,50}", city))

def is_valid_state(state: str) -> bool:
    """Letters & spaces, 2-50 chars."""
    return bool(re.fullmatch(r"[A-Za-z\s]{2,50}", state))

def is_valid_pin_code(pin_code: str) -> bool:
    """Indian 6-digit PIN, cannot start with 0."""
    return bool(re.fullmatch(r"[1-9]\d{5}", pin_code))

def is_valid_about(about: str) -> bool:
    """Free-form message, 1-1000 visible chars."""
    clean = about.strip()
    return 0 < len(clean) <= 1000

def is_valid_title(title: str) -> bool:
    """Property title: 5-100 chars, letters, numbers, spaces, punctuation."""
    return bool(re.fullmatch(r"[\w\s.,'\"()\-]{5,100}", title))

def is_valid_status(status: str) -> bool:
    """Status: Must be 'For Rent' or 'For Sale'."""
    return status in ['For Rent', 'For Sale']

def is_valid_property_type(property_type: str) -> bool:
    """Property type: Must be one of the predefined types."""
    return property_type in ['Houses', 'Apartment', 'Villas', 'Commercial', 'Offices', 'Garage']

def is_valid_price(price: str) -> bool:
    """Price: Digits only, optional commas and decimals."""
    return bool(re.fullmatch(r"\d{1,3}(,\d{3})*(\.\d{1,2})?$|^\d+(\.\d{1,2})?$", price))

def is_valid_area(area: str) -> bool:
    """Area in square feet: positive number."""
    return bool(re.fullmatch(r"^\d+(\.\d{1,2})?$", area))

def is_valid_bedrooms(bedrooms: str) -> bool:
    """Bedrooms: Must be 1 to 5."""
    return bedrooms in ['1', '2', '3', '4', '5']

def is_valid_bathrooms(bathrooms: str) -> bool:
    """Bathrooms: Must be 1 to 5."""
    return bathrooms in ['1', '2', '3', '4', '5']

def is_valid_description(description: str) -> bool:
    """Free-form description: 1-1000 chars."""
    desc = description.strip()
    return 1 <= len(desc) <= 1000

def is_valid_building_age(building_age: str) -> bool:
    """Building age: Must match allowed options."""
    return building_age in ['0-5', '0-10', '0-15', '0-20', '20+', '']

def is_valid_garage(garage: str) -> bool:
    """Garage: 1-5 or empty."""
    return garage in ['1', '2', '3', '4', '5', '']

def is_valid_rooms(rooms: str) -> bool:
    """Rooms: 1-5 or empty."""
    return rooms in ['1', '2', '3', '4', '5', '']

def is_valid_features(features: list[str]) -> bool:
    """Features: all items must be from allowed list."""
    allowed = {
        "Air Condition", "Bedding", "Heating", "Internet", "Microwave",
        "Smoking Allow", "Terrace", "Balcony", "Icon", "Wi-Fi", "Beach", "Parking"
    }
    return all(f in allowed for f in features)

# My Account Profile Details and Image Upload

def _process_post(uid: str):
    if "cropped_image" in request.form:
        return _update_profile_image(uid)
    return _update_profile_details(uid)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename: str, allowed_extensions: Set[str] = ALLOWED_EXTENSIONS) -> bool:
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions

PROFILE_FOLDER = os.path.join("static", "profile")

def _update_profile_image(uid: str):
    try:
        cropped_data = request.form["cropped_image"]
        header, encoded = cropped_data.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_bytes)).convert("RGB")

        abs_folder = os.path.join(app.root_path, PROFILE_FOLDER)
        os.makedirs(abs_folder, exist_ok=True)

        filename = f"{uid}.webp"
        abs_path = os.path.join(abs_folder, filename)
        img.save(abs_path, format="WEBP", quality=80, method=6)

        image_url = f"/{PROFILE_FOLDER.replace(os.sep, '/')}/{filename}"

        admin_db.reference(f"users/{uid}").update({"profile_image": image_url})
        flash("Profile image updated successfully!", "success")

    except Exception as exc:
        flash("Error updating profile images. Please try again later.", "light")

    return redirect(request.url)

def validate_profile_form(profile_data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}

    rules = {
        "name"       : (is_valid_name,       "Name must contain only letters and spaces (2-100 chars)."),
        "occupation" : (is_valid_occupation, "Occupation can include letters, spaces, &, /, or -."),
        "phone"      : (is_valid_phone,      "Phone must be 10-15 digits, optional leading '+'."),
        "address"    : (is_valid_address,    "Address must be 5-120 chars; letters, numbers & punctuation."),
        "city"       : (is_valid_city,       "City may contain only letters and spaces (2-50 chars)."),
        "state"      : (is_valid_state,      "State may contain only letters and spaces (2-50 chars)."),
        "pin_code"   : (is_valid_pin_code,   "PIN must be a 6-digit Indian postal code (cannot start with 0)."),
        "about"      : (is_valid_about,      "About section must be 1-1000 characters.")
    }

    for field, (validator, msg) in rules.items():
        if not validator(profile_data.get(field, "").strip()):
            errors[field] = msg

    return (not errors), errors

IST = timezone(timedelta(hours=5, minutes=30))

def _update_profile_details(uid):
    required_fields = [
        "name", "occupation", "phone",
        "address", "city", "state",
        "pin_code", "about"
    ]
    profile_data = {f: request.form.get(f, "").strip() for f in required_fields}

    if not all(profile_data.values()):
        flash("Please fill out every field.", "light")
        return redirect(request.url)

    ok, errors = validate_profile_form(profile_data)
    if not ok:
        for message in errors.values():
            flash(message, "light")
        return redirect(request.url)
    
    now_ist = datetime.now(IST)
    time    = now_ist.strftime("%d-%m-%Y, %H:%M")

    profile_data["submitted_at"] = time

    try:
        admin_db.reference(f"users/{uid}").update(profile_data)
        flash("Profile details updated successfully!", "success")
    except Exception as exc:
        flash("Error updating profile details. Please try again later.", "light")

    return redirect(request.url)

#  Upload Homes Details

def collect_property_form_data(form: "Request.form") -> Dict[str, Any]:
    field_map = {
        "title"          : "title",
        "status"         : "status",
        "property_type"  : "property_type",
        "price"          : "price",
        "area"           : "area",
        "bedrooms"       : "bedrooms",
        "bathrooms"      : "bathrooms",
        "address"        : "address",
        "city"           : "city",
        "state"          : "state",
        "pincode"        : "pin_code",
        "description"    : "description",
        "building_age"   : "building_age",
        "garage"         : "garage",
        "rooms"          : "rooms",
        "contact_name"   : "name",
        "contact_email"  : "email",
        "contact_phone"  : "phone",
    }

    data = {
        dst: form.get(src, "").strip()
        for src, dst in field_map.items()
    }
    data["features"] = form.getlist("features")
    return data


def validate_property_form(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    errors: Dict[str, str] = {}

    rules = {
        "title"          : (is_valid_title,        "Title must be 5-100 characters, valid punctuation allowed."),
        "status"         : (is_valid_status,       "Status must be 'For Sale' or 'For Rent'."),
        "property_type"  : (is_valid_property_type,"Choose a valid property type."),
        "price"          : (is_valid_price,        "Enter a valid price (e.g., 100000 or 1,00,000.00)."),
        "area"           : (is_valid_area,         "Area must be a positive number (e.g., 1200.50)."),
        "bedrooms"       : (is_valid_bedrooms,     "Bedrooms must be between 1 and 5."),
        "bathrooms"      : (is_valid_bathrooms,    "Bathrooms must be between 1 and 5."),
        "address"        : (is_valid_address,      "Address must be 5-120 characters, letters, numbers, punctuation allowed."),
        "city"           : (is_valid_city,         "City can contain only letters & spaces (2-50 chars)."),
        "state"          : (is_valid_state,        "State can contain only letters & spaces (2-50 chars)."),
        "pin_code"       : (is_valid_pin_code,     "PIN code must be a valid 6-digit Indian postal code."),
        "description"    : (is_valid_description,  "Description must be 1-1000 characters."),
        "building_age"   : (is_valid_building_age, "Select a valid building age."),
        "garage"         : (is_valid_garage,       "Garage must be between 1-5 or left empty."),
        "rooms"          : (is_valid_rooms,        "Rooms must be between 1-5 or left empty."),
        "features"       : (is_valid_features,     "One or more selected features are invalid."),
        "name"           : (is_valid_name,         "Name must contain only letters and spaces (min 2 chars)."),
        "email"          : (is_valid_email,        "Please enter a valid email address."),
        "phone"          : (is_valid_phone,        "Phone number must be 10-15 digits with optional '+' sign."),
    }

    for field, (validator, msg) in rules.items():
        value = data.get(field, "")
        if field == "features" and not validator(value):
            errors[field] = msg
        elif field != "features" and not validator(str(value).strip()):
            errors[field] = msg

    return (not errors), errors

# Upload Homes Image

def homes_images(uid: str):
    if "cropped_image1" in request.form:
        return add_homes_image(uid)
    return delete_homes_details(uid)

def add_homes_image(uid: str):
    try:
        cropped_data    = request.form.get('cropped_image1')
        header, encoded = cropped_data.split(',', 1)
        img_data        = base64.b64decode(encoded)
        img             = Image.open(BytesIO(img_data))

        filename = f"{uuid.uuid4().hex}.webp"
        rel_path = os.path.join('static', 'uploads', uid, filename)
        abs_path = os.path.join(app.root_path, rel_path)

        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        img.save(abs_path, format='WEBP')

        url_path = f"/static/uploads/{uid}/{filename}"

        existing_images = admin_db.reference(f'users/{uid}/properties/images').get()
        if not existing_images:
            existing_images = []
        elif isinstance(existing_images, dict):
            existing_images = list(existing_images.values())

        existing_images.append(url_path)

        admin_db.reference(f'users/{uid}/properties/images').set(existing_images)
        admin_db.reference(f'users/{uid}/properties/house_status').set('Not Verified')

        flash("Image uploaded successfully!", "success")
    except Exception as e:
        flash("Error uploading image. Please try again later.", "light")

    return redirect(request.url)

def delete_homes_details(uid: str):
    try:
        existing_data = admin_db.reference(f'users/{uid}/properties/images').get()
        old_image_paths = existing_data if isinstance(existing_data, list) else []

        images_to_keep_json = request.form.get('images_to_keep', '[]')
        try:
            images_to_keep = json.loads(images_to_keep_json)
            if not isinstance(images_to_keep, list):
                raise ValueError("Parsed images_to_keep is not a list.")
        except Exception as e:
            images_to_keep = []
            flash("Invalid image data submitted.", "light")

        for old_path in old_image_paths:
            if old_path not in images_to_keep:
                try:
                    old_file_path = os.path.join("static", *old_path.split("/")[2:])
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                except Exception as e:
                    flash("Error deleting file(s).", "light")

        admin_db.reference(f'users/{uid}/properties/images').set(images_to_keep)
        flash("Images updated successfully!", "success")
    except Exception as e:
        flash("Error updating homes images. Please try again later.", "light")

    return redirect(request.url)