from flask import Blueprint, render_template, request, redirect, url_for, session, flash,jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from .models import db, CarOwner, Renter, Booking, Location, Message, BookingStatus, PaymentStatus
import os
from flask import send_from_directory,current_app, Flask
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_socketio import SocketIO
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
socketio = SocketIO(app)  # Now it should work

# from flask_login import current_user

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



bp = Blueprint('routes', __name__)
@bp.route("/", methods=["GET"])
def about():
    return render_template("about.html")

@bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_type = request.form.get("user_type")
        if user_type == "car_owner":
            return redirect(url_for("routes.car_owner_register"))
        elif user_type == "renter":
            return redirect(url_for("routes.renter_register"))
    return render_template("index.html")

@bp.route("/car_owner/register", methods=["GET", "POST"])
def car_owner_register():
    if request.method == "POST":
        name = request.form["name"]
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        car_model = request.form["car_model"]

        # Check if the email or username already exists
        existing_user = CarOwner.query.filter((CarOwner.email == email) | (CarOwner.username == username)).first()
        if existing_user:
            flash("Email or Username already exists. Please use a different one.", "danger")
            return redirect(url_for("routes.car_owner_register"))

        # Hash the password and create a new user
        hashed_password = generate_password_hash(password)
        new_owner = CarOwner(
            name=name,
            username=username,
            email=email,
            password=hashed_password,
            car_model=car_model
        )

        try:
            db.session.add(new_owner)
            db.session.commit()
            flash("Registration successful!", "success")
            return redirect(url_for("routes.login"))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred during registration. Please try again.", "danger")
            return redirect(url_for("routes.car_owner_register"))

    return render_template("car_owner_register.html")


@bp.route("/renter/register", methods=["GET", "POST"])
def renter_register():
    if request.method == "POST":
        name = request.form["name"]
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        renting_place = request.form["renting_place"]
        price = request.form["price"]
        place_type = request.form["place_type"]
        amenities = request.form.getlist("amenities")
        timing = request.form["timing"]

        new_renter = Renter(
            name=name, username=username, email=email, password=password, renting_place=renting_place,
            price=price, place_type=place_type, amenities=", ".join(amenities), timing=timing
        )
        db.session.add(new_renter)
        db.session.commit()
        flash("Registration successful!", "success")
        return redirect(url_for("routes.login"))
    return render_template("renter_register.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user_type = request.form.get("user_type")  # 'car_owner' or 'renter'

        # Fetch the user based on type
        if user_type == "car_owner":
            user = CarOwner.query.filter_by(username=username).first()
        elif user_type == "renter":
            user = Renter.query.filter_by(username=username).first()
        else:
            flash("Invalid user type selected.", "danger")
            return redirect(url_for("routes.login"))

        # Check if user exists and the password matches
        if user and check_password_hash(user.password, password):
            # Save user data in session
            session["user_id"] = user.id
            session["user_type"] = user_type
            session["user_name"] = user.name

            # Redirect based on user type
            if user_type == "car_owner":
                return redirect(url_for("routes.dashboard"))  # Assuming car owner's dashboard
            elif user_type == "renter":
                return redirect(url_for("routes.renter_dashboard"))  # Redirect to renter's dashboard
        else:
            flash("Invalid username or password.", "danger")
            return redirect(url_for("routes.login"))

    return render_template("login.html")



@bp.route("/dashboard")
def dashboard():
    if "user_id" not in session or session.get("user_type") != "car_owner":
        flash("Access denied. Please log in as a car owner.", "danger")
        return redirect(url_for("routes.login"))

    car_owner_id = session.get("user_id")
    car_owner = CarOwner.query.get(car_owner_id)
    
    # Handle search functionality
    search_query = request.args.get("search", "").strip()
    if search_query:
        # Perform a case-insensitive search on place_name or address
        locations = Location.query.filter(
            (Location.place_name.ilike(f"%{search_query}%")) |
            (Location.address.ilike(f"%{search_query}%"))
        ).filter(Location.available == True).all()
    else:
        # Default behavior: Fetch all available locations
        locations = Location.query.filter(Location.available == True).all()
    
    
    bookings = Booking.query.filter_by(car_owner_id=car_owner_id, deleted=False).all()
    
    # Prepare locations data with lat/lng fields
    locations_data = [
        {
            "id": location.id,
            "place_name": location.place_name,
            "address": location.address,
            "price": location.price,
            "amenities": location.amenities,
            "available": location.available,
            "lat": location.lat,  # Use the correct latitude field
            "lng": location.lng   # Use the correct longitude field
        }
        for location in locations
    ]

    return render_template("dashboard.html", car_owner=car_owner, locations=locations_data, bookings=bookings)

@socketio.on('send_message')
def handle_send_message(data):
    sender_id = data['sender_id']
    receiver_id = data['receiver_id']
    message_content = data['message_content']
    booking_id = data['booking_id']

    # Create a new message
    new_message = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message_content=message_content,
        booking_id=booking_id
    )
    db.session.add(new_message)
    db.session.commit()

    # Emit the message to the receiver
    emit('receive_message', {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'message_content': message_content,
        'timestamp': new_message.timestamp.isoformat(),
        'booking_id': booking_id
    }, room=f'booking_{booking_id}')

@socketio.on('join_room')
def handle_join_room(data):
    booking_id = data['booking_id']
    join_room(f'booking_{booking_id}')

@socketio.on('leave_room')
def handle_leave_room(data):
    booking_id = data['booking_id']
    leave_room(f'booking_{booking_id}')

@bp.route('/request_booking', methods=['POST'])
def request_booking():
    location_id = request.form.get('location_id')  # Get the location id passed in the form
    renter_id = request.form.get('renter_id')  # The renter who is booking the location

    user_name = request.form.get('user_name')  # Name of the user booking the slot
    message = request.form.get('message')  # Optional message from the user
    preferred_date = request.form.get('preferred_date')  # The date the user prefers for booking
    contact_details = request.form.get('contact_details')  # Contact details of the user
    car_owner_id = session.get("user_id")

    # Validate inputs
    if not location_id or not renter_id or not car_owner_id or not user_name or not contact_details:
        flash("All fields are required.", "danger")
        return redirect(url_for('routes.dashboard'))

    # Fetch the location, car owner, and renter details from the database
    location = Location.query.get(location_id)
    renter = Renter.query.get(renter_id)
    car_owner = CarOwner.query.get(car_owner_id)

    # Check if the location, car owner, and renter exist
    if not location or not renter or not car_owner:
        flash("Invalid location, renter, or car owner.", "danger")
        return redirect(url_for('routes.dashboard'))

    # Ensure that the location is available for booking
    if not location.available:
        flash("This location is not available for booking.", "danger")
        return redirect(url_for('routes.dashboard'))

    # Create a new booking request
    new_booking = Booking(
        car_owner_id=car_owner.id,
        renter_id=renter.id,
        location_id=location.id,
        message=message,
        preferred_date=datetime.strptime(preferred_date, "%Y-%m-%d"),
        contact=contact_details,
        status=BookingStatus.Pending.value
    )

    try:
        # Add the new booking request to the session and commit
        db.session.add(new_booking)
        db.session.commit()
        
        # Send a success message and redirect to the dashboard
        flash("Booking request submitted successfully!", "success")
        return redirect(url_for('routes.dashboard'))
    except Exception as e:
        # In case of an error, rollback the transaction and display an error message
        db.session.rollback()
        flash(f"Error submitting booking request: {e}", "danger")
        return redirect(url_for('routes.dashboard'))

@bp.route('/update_booking_status/<int:booking_id>', methods=['POST'])
def update_booking_status(booking_id):
    booking = Booking.query.get(booking_id)
    
    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('routes.dashboard'))  # Redirect to the booking list view

    # Get the new status from the form
    new_status = request.form.get('status')

    if new_status not in [BookingStatus.Pending.value, BookingStatus.Approved.value, BookingStatus.Rejected.value]:
        flash('Invalid status selected.', 'error')
        return redirect(url_for('routes.dashboard'))  # Redirect back to booking list

    # Update the booking status
    booking.status = new_status
    db.session.commit()

    flash('Booking status updated successfully.', 'success')
    return redirect(url_for('routes.dashboard'))  # Redirect back to the booking list


# Route to render the booking form
@bp.route('/booking_form/<location_id>', methods=['GET'])
def booking_form(location_id):
    # Fetch the location based on the ID
    location = Location.query.get(location_id)
    if not location:
        flash("Location not found.", "danger")
        return redirect(url_for('routes.dashboard'))

    # Fetch the renter details (This might depend on your logged-in user, so adjust accordingly)
    renter = Renter.query.get(location.renter_id)
    if not renter:
        flash("Renter not found for this location.", "danger")
        return redirect(url_for('routes.dashboard'))

    # Render the booking form page with location and renter details
    return render_template('booking_form.html', location=location, renter=renter)

@bp.route('/process_payment/<int:booking_id>', methods=['POST'])
def process_payment(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.payment_status == PaymentStatus.Paid:
        return jsonify({"message": "Booking is already paid."}), 400

    # Example: Validate payment details (you can integrate with payment APIs here)
    data = request.get_json()
    payment_method = data.get("paymentMethod")
    amount = data.get("amount")

    if not payment_method or not amount:
        return jsonify({"message": "Invalid payment details."}), 400

    # Simulate payment success
    booking.payment_status = PaymentStatus.Paid
    db.session.commit()

    return jsonify({"message": "Payment successful!"}), 200
@bp.route('/remove_booking/<int:booking_id>', methods=['POST'])
def remove_booking(booking_id):
    if "user_id" not in session or session.get("user_type") != "car_owner":
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    # Find the booking
    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({"success": False, "message": "Booking not found"}), 404

    # Mark the booking as removed (soft delete)
    booking.deleted = True
    db.session.commit()
    return jsonify({"success": True})
@bp.route("/delete_booking/<int:booking_id>", methods=["POST"])
def delete_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    try:
        db.session.delete(booking)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 400

@bp.route("/requested_booking", methods=["GET"])
def requested_booking():
    if "user_id" not in session or session.get("user_type") != "car_owner":
        flash("Access denied. Please log in as a car owner.", "danger")
        return redirect(url_for("routes.login"))

    car_owner_id = session.get("user_id")
    bookings = Booking.query.filter_by(car_owner_id=car_owner_id).all()

    return render_template("requested_booking.html", bookings=bookings)



@bp.route('/booking_history', methods=['GET'])
def booking_history():
    car_owner_id = session.get("user_id")
    bookings = Booking.query.filter_by(car_owner_id=car_owner_id).all()
    booking_data = [
        {
            "id": booking.id,
            "location": booking.location.address if booking.location else "N/A",
            "date": booking.preferred_date.strftime("%d %b %Y") if booking.preferred_date else "N/A",
            "total": booking.location.price if booking.location else "0.00",
            "rating": booking.rating  # Assuming the rating field exists in the Booking model
        }
        for booking in bookings
    ]
    return render_template('booking_history.html', bookings=booking_data)

@bp.route("/cancellation_policy", methods=["GET", "POST"])
def cancellation_policy():
    booking_id = request.args.get("booking_id")
    if not booking_id:
        flash("Booking ID is missing.", "danger")
        return redirect(url_for("routes.dashboard"))

    booking = Booking.query.get(booking_id)
    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("routes.dashboard"))

    if request.method == "POST":
        # Handle the actual cancellation logic
        booking.deleted = True
        try:
            db.session.commit()
            flash("Booking canceled successfully.", "success")
            return redirect(url_for("routes.dashboard"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error canceling booking: {e}", "danger")

    return render_template("cancellation_policy.html", booking=booking)

@bp.route("/confirm_booking", methods=["GET", "POST"])
def confirm_booking():
    # Handle booking confirmation logic here
    return redirect(url_for("routes.dashboard"))  # Redirect to dashboard or another page

@bp.route("/confirm_removal/<int:booking_id>", methods=["POST"])
def confirm_removal(booking_id):
    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({"success": False, "error": "Booking not found."}), 404

    try:
        db.session.delete(booking)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route("/renter/dashboard", methods=["GET"])
def renter_dashboard():
    if "user_id" not in session or session.get("user_type") != "renter":
        flash("Access denied. Please log in as a renter.", "danger")
        return redirect(url_for("routes.login"))

    renter_id = session.get("user_id")
    renter = Renter.query.get(renter_id)
    
    # Fetch locations and bookings for the renter
    locations = Location.query.filter_by(renter_id=renter_id).all()
    bookings = Booking.query.filter_by(renter_id=renter_id).all()

    # Check if any locations are unavailable due to an existing booking
    unavailable_locations = [location for location in locations if not location.available]
    
    # Fetch messages only for approved bookings
    approved_bookings = [booking for booking in bookings if booking.status.name == "Approved"]
    approved_booking_ids = [booking.id for booking in approved_bookings]

    # Fetch messages related to the approved bookings
    messages = Message.query.filter(
        (Message.receiver_id == renter_id) & (Message.booking_id.in_(approved_booking_ids))
    ).order_by(Message.timestamp).all()

    return render_template(
        "renter_dashboard.html", 
        renter=renter, 
        locations=locations, 
        bookings=bookings, 
        unavailable_locations=unavailable_locations, 
        messages=messages
    )


@bp.route("/renter/add_location", methods=["GET", "POST"])
def add_location():
    if request.method == 'POST':
        # Retrieve form data
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        address = request.form.get('address')
        place_name = request.form.get('place_name')
        price = request.form.get('price')
        amenities = request.form.get('amenities', '')

        # Debugging: Print form data
        print("Form Data:", lat, lng, address, place_name, price, amenities)

        # Check if all required fields are provided
        if not (lat and lng and address and place_name and price):
            flash("All fields are required.", "danger")
            return render_template('add_location.html')  # Render the form with errors

        try:
            # Get the renter ID from the session
            renter_id = session.get('user_id')
            if not renter_id:
                flash("You must be logged in to add a location.", "danger")
                return redirect(url_for('routes.login'))

            # Create a new Location object
            location = Location(
                renter_id=renter_id,
                place_name=place_name,
                address=address,
                price=price,
                amenities=amenities,
                lat=float(lat),
                lng=float(lng),
                available=True
            )

            # Add the location to the database
            db.session.add(location)
            db.session.commit()
            flash("Location added successfully!", "success")
            return redirect(url_for('routes.renter_dashboard'))  # Redirect to renter dashboard
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "danger")
            return render_template('add_location.html')  # Render the form with errors

    # For GET requests, render the form
    return render_template('add_location.html')




@bp.route('/edit_location/<int:location_id>', methods=['GET', 'POST'])
def edit_location(location_id):
    location = Location.query.get_or_404(location_id)
    
    if request.method == 'POST':
        # Update the location details from the form data
        location.place_name = request.form['place_name']
        location.address = request.form['address']
        location.price = request.form['price']
        location.amenities = request.form['amenities']
        location.available = 'available' in request.form  # Checkbox handling
        
        try:
            db.session.commit()
            flash("Location updated successfully!", "success")
            return redirect(url_for('routes.renter_dashboard'))  # Redirect to dashboard
        except Exception as e:
            db.session.rollback()
            flash("An error occurred while updating the location.", "danger")
    
    # Render the edit location form with current location data
    return render_template('edit_location.html', location=location)
@bp.route('/delete_location/<int:location_id>', methods=['POST'])
def delete_location(location_id):
    location = Location.query.get_or_404(location_id)
    
    try:
        db.session.delete(location)
        db.session.commit()
        flash("Location deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("An error occurred while deleting the location.", "danger")
    
    return redirect(url_for('routes.renter_dashboard'))

@bp.route('/toggle_availability_ajax/<int:location_id>', methods=['POST'])
def toggle_availability_ajax(location_id):
    location = Location.query.get_or_404(location_id)
    
    # Toggle the availability status
    location.available = not location.available
    
    try:
        # Save the updated status to the database
        db.session.commit()
        return jsonify({
            "success": True,
            "available": location.available
        })
    except Exception as e:
        # Rollback in case of an error
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


from flask import request, jsonify

@bp.route('/save_location', methods=['POST'])
def save_location():
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')

    if not lat or not lng:
        return jsonify({"success": False, "error": "Invalid coordinates"}), 400

    # Save the location in the database
    # For example, associate it with the current user/renter
    try:
        renter_id = session.get('user_id')  # Assuming the renter is logged in
        location = Location(renter_id=renter_id, place_name="Pinned Location",
                            address=f"Lat: {lat}, Lng: {lng}", price=0, amenities="", available=True)
        db.session.add(location)
        db.session.commit()
        return jsonify({"success": True, "message": "Location saved successfully!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("routes.login"))

    user_id = session.get("user_id")
    user_type = session.get("user_type")

    # Fetch the user based on their type
    if user_type == "car_owner":
        user = CarOwner.query.get(user_id)
    elif user_type == "renter":
        user = Renter.query.get(user_id)
    else:
        flash("Invalid user type.", "danger")
        return redirect(url_for("routes.dashboard"))

    if request.method == "POST":
        # Handle bio update
        user.bio = request.form.get("bio", user.bio)

        # Handle notification preference update
        notification_preference = request.form.get("notification_preference")
        if notification_preference:
            user.notification_preference = notification_preference

        # Handle payment preference update
        payment_preference = request.form.get("payment_preference")
        if payment_preference:
            user.payment_preference = payment_preference

        # Handle profile picture upload
        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)
                user.profile_pic = filename

        try:
            db.session.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating profile: {e}", "danger")

        return redirect(url_for("routes.profile"))

    return render_template("profile.html", user=user)




@bp.route("/renter_profile", methods=["GET", "POST"])
def renter_profile():
    if "user_id" not in session:
        return redirect(url_for("routes.login"))

    user_id = session.get("user_id")
    user_type = session.get("user_type")

    # Fetch the user based on their type
    if user_type == "car_owner":
        return redirect(url_for("routes.car_owner_profile"))
    elif user_type == "renter":
        user = Renter.query.get(user_id)
    else:
        flash("Invalid user type.", "danger")
        return redirect(url_for("routes.renter_dashboard"))

    if request.method == "POST":
        # Handle bio update
        user.bio = request.form.get("bio", user.bio)

        # Handle profile picture upload
        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)
                user.profile_pic = filename

        try:
            db.session.commit()
            flash("Profile updated successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating profile: {e}", "danger")

        return redirect(url_for("routes.renter_profile"))

    return render_template("renter_profile.html", user=user)

@bp.route("/renter/bookings", methods=["GET"])
def renter_bookings():
    if "user_id" not in session or session.get("user_type") != "renter":
        flash("Access denied. Please log in as a renter.", "danger")
        return redirect(url_for("routes.login"))

    renter_id = session.get("user_id")
    renter = Renter.query.get(renter_id)  # Fetch renter details
    bookings = Booking.query.filter_by(renter_id=renter_id).all()

    return render_template("renter_bookings.html", renter=renter, bookings=bookings)




@bp.route("/api/locations", methods=["GET"])
def get_locations():
    locations = Location.query.filter_by(available=True).all()
    locations_data = [
        {
            "id": location.id,
            "place_name": location.place_name,
            "address": location.address,
            "price": location.price,
            "amenities": location.amenities,
            "available": location.available,
            "lat": location.lat,
            "lng": location.lng
        }
        for location in locations
    ]
    return jsonify(locations_data)

@bp.route("/api/all_locations", methods=["GET"])
def all_locations():
    locations = Location.query.filter_by(available=True).all()

    locations_data = [
        {
            "id": location.id,
            "place_name": location.place_name,
            "address": location.address,
            "price": location.price,
            "amenities": location.amenities,
            "available": location.available,
            "lat": location.lat,
            "lng": location.lng
        }
        for location in locations
    ]

    return jsonify(locations_data)


@bp.route('/send_message', methods=['POST'])
def send_message():
    sender_id = session.get("user_id")
    receiver_id = request.form.get("receiver_id")
    message_content = request.form.get("message_content")
    booking_id = request.form.get("booking_id")

    print(f"Debug - Sender ID: {sender_id}, Receiver ID: {receiver_id}, Booking ID: {booking_id}")  # Debugging

    # Validate sender and receiver IDs
    if not sender_id or not receiver_id or not message_content or not booking_id:
        flash("All fields are required!", "danger")
        return redirect(url_for('routes.dashboard'))

    # Validate booking and ensure the sender is a participant in the booking
    booking = Booking.query.get(booking_id)
    if not booking:
        flash("Booking does not exist.", "danger")
        return redirect(url_for('routes.dashboard'))

    # Ensure sender is either car owner or renter
    if sender_id not in [booking.car_owner_id, booking.renter_id]:
        flash("You are not authorized to send messages for this booking.", "danger")
        return redirect(url_for('routes.dashboard'))

    # Ensure receiver_id matches the other participant
    if receiver_id == sender_id:
        flash("You cannot send a message to yourself.", "danger")
        return redirect(url_for('routes.view_messages', booking_id=booking_id))

    if int(receiver_id) not in [booking.car_owner_id, booking.renter_id]:
        flash("Invalid receiver. You cannot send a message to this user.", "danger")
        return redirect(url_for('routes.view_messages', booking_id=booking_id))

    # Create and save the message
    new_message = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message_content=message_content,
        booking_id=booking_id
    )

    try:
        db.session.add(new_message)
        db.session.commit()
        flash("Message sent successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error sending message: {e}", "danger")
        print(f"Error: {e}")  # Debugging output

    return redirect(url_for('routes.view_messages', booking_id=booking_id))

    
@bp.route('/reply_message/<int:message_id>', methods=['POST'])
def reply_message(message_id):
    sender_id = session.get("user_id")  # Current user (renter)
    reply_message_content = request.form.get("reply_message")

    if not sender_id or not reply_message_content:
        flash("All fields are required!", "danger")
        return redirect(url_for('routes.renter_dashboard'))  # Redirect to dashboard if fields are missing

    # Fetch the original message
    original_message = Message.query.get(message_id)
    if not original_message:
        flash("Message does not exist.", "danger")
        return redirect(url_for('routes.renter_dashboard'))  # Redirect to dashboard if message not found

    # Ensure the user is replying to a message they received
    if original_message.receiver_id != sender_id:
        flash("You can only reply to messages sent to you.", "danger")
        return redirect(url_for('routes.renter_dashboard'))  # Redirect to dashboard if unauthorized

    # Determine the receiver of the reply (the original sender)
    receiver_id = original_message.sender_id
    booking_id = original_message.booking_id  # Get the booking_id from the original message

    # Create and save the reply message
    new_reply = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message_content=reply_message_content,
        booking_id=booking_id
    )

    try:
        db.session.add(new_reply)
        db.session.commit()
        flash("Reply sent successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error sending reply: {e}", "danger")

    # Redirect to the view_messages route with the correct booking_id
    return redirect(url_for('routes.view_messages', booking_id=booking_id))
    
@bp.route('/view_messages/<int:booking_id>', methods=['GET'])
def view_messages(booking_id):
    # Get the current user's ID (sender or receiver)
    sender_id = session.get("user_id")
    
    # Validate the booking ID
    booking = Booking.query.get(booking_id)
    if not booking:
        flash("Booking does not exist.", "danger")
        return redirect(url_for('routes.renter_dashboard'))
    
    # Ensure that the user is a participant in this booking
    if sender_id not in [booking.car_owner_id, booking.renter_id]:
        flash("You are not authorized to view messages for this booking.", "danger")
        return redirect(url_for('routes.renter_dashboard'))
    
    # Fetch all messages related to this booking, ordered by the creation date
    messages = Message.query.filter_by(booking_id=booking_id).order_by(Message.timestamp).all()

    # Render the view messages page with the messages
    return render_template(
        'messages.html', 
        messages=messages, 
        booking=booking,
        user_id=sender_id,
        car_owner=booking.car_owner,
        renter=booking.renter
    )
@bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("routes.login"))
