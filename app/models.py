from flask_sqlalchemy import SQLAlchemy
from . import db
from datetime import datetime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey

class CarOwner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    profile_pic = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    notification_preference = db.Column(db.String(100), nullable=True)
    payment_preference = db.Column(db.String(100), nullable=True)
    car_model = db.Column(db.String(100), nullable=False)
    ratings = db.Column(db.Float, default=0.0)
    history = db.Column(db.JSON, nullable=True)

    # Relationships
    

class Renter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    profile_pic = db.Column(db.String(200), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    notification_preference = db.Column(db.String(100), nullable=True)
    payment_preference = db.Column(db.String(100), nullable=True)
    renting_place = db.Column(db.String(200), nullable=False)
    ratings = db.Column(db.Float, default=0.0)
    price = db.Column(db.Float, nullable=False)
    place_type = db.Column(db.String(50), nullable=False)  # residential, commercial
    amenities = db.Column(db.String(200), nullable=True)  # e.g., security, lighting
    timing = db.Column(db.String(100), nullable=False)  # e.g., 9am-5pm

    history = db.Column(db.JSON, nullable=True)  # Track rental history as a JSON list of bookings

    # Relationships
    
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    renter_id = db.Column(db.Integer, db.ForeignKey('renter.id'), nullable=False)
    place_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    amenities = db.Column(db.String(200), nullable=True)
    available = db.Column(db.Boolean, default=True)
    lat = db.Column(db.Float, nullable=False)  # New column
    lng = db.Column(db.Float, nullable=False)  # New column

    # Relationships
    renter = db.relationship('Renter', backref='locations', lazy=True)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, nullable=False)  # Either CarOwner or Renter
    receiver_id = db.Column(db.Integer, nullable=False)  # Either Renter or CarOwner
    message_content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    booking_id = db.Column(db.Integer, ForeignKey('booking.id'), nullable=False)
    read_status = db.Column(db.Boolean, default=False)  # Track if the message was read

    # Relationships
    booking = db.relationship('Booking', backref=db.backref('messages', lazy=True))

    def __repr__(self):
        return f'<Message {self.id}>'

    @property
    def sender(self):
        # Fetch the sender (either CarOwner or Renter)
        if self.sender_id in [car_owner.id for car_owner in CarOwner.query.all()]:
            return CarOwner.query.get(self.sender_id)
        else:
            return Renter.query.get(self.sender_id)

    @property
    def receiver(self):
        # Fetch the receiver (either Renter or CarOwner)
        if self.receiver_id in [car_owner.id for car_owner in CarOwner.query.all()]:
            return CarOwner.query.get(self.receiver_id)
        else:
            return Renter.query.get(self.receiver_id)


from sqlalchemy import ForeignKey

import enum
from datetime import datetime
from sqlalchemy import Enum

class BookingStatus(enum.Enum):
    Pending = "Pending"
    Approved = "Approved"
    Rejected = "Rejected"

class PaymentStatus(enum.Enum):
    Due = "Due"
    Paid = "Paid"

class Booking(db.Model):
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    car_owner_id = db.Column(db.Integer, db.ForeignKey('car_owner.id', name='fk_booking_car_owner_id'), index=True, nullable=False)
    renter_id = db.Column(db.Integer, db.ForeignKey('renter.id', name='fk_booking_renter_id'), index=True, nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id', name='fk_booking_location_id'), index=True, nullable=True)
    message = db.Column(db.Text, nullable=False)
    preferred_date = db.Column(db.Date, nullable=False)
    contact = db.Column(db.String(200), nullable=False)
    status = db.Column(Enum(BookingStatus), default=BookingStatus.Approved, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted = db.Column(db.Boolean, default=False, nullable=False)
    payment_status = db.Column(Enum(PaymentStatus), default=PaymentStatus.Due, nullable=False)
    rating = db.Column(db.Integer, nullable=True)
    # Relationships
    car_owner = db.relationship("CarOwner", backref="bookings", lazy=True)
    renter = db.relationship("Renter", backref="bookings", lazy=True)
    location = db.relationship("Location", backref="bookings", lazy=True)


    @property
    def can_message(self):
        return self.status == "Approved"

    # After booking approval, the location becomes unavailable
    def approve_booking(self):
        if self.status != BookingStatus.Pending:
            raise ValueError("Booking has already been processed.")

        self.status = BookingStatus.Approved
        if self.location:
            self.location.available = False
        self.add_to_histories()
        db.session.commit()

    # Add to car owner's and renter's booking history
    def add_to_histories(self):
        car_owner = self.car_owner
        renter = self.renter

        # Update CarOwner's history
        if car_owner.history is None:
            car_owner.history = []
        else:
            car_owner.history = list(car_owner.history)

        car_owner.history.append({
            'location': self.location.place_name,
            'preferred_date': self.preferred_date.isoformat(),
            'status': self.status.value,
        })

        # Update Renter's history
        if renter.history is None:
            renter.history = []
        else:
            renter.history = list(renter.history)

        renter.history.append({
            'location': self.location.place_name,
            'preferred_date': self.preferred_date.isoformat(),
            'status': self.status.value,
        })

        db.session.commit()


    # After booking time is over, the location becomes available again
    @classmethod
    def after_booking_ends(cls, booking_id):
        booking = cls.query.get(booking_id)
        if not booking:
            raise ValueError(f"No booking found with ID {booking_id}")

        if booking.location:
            booking.location.available = True
            db.session.commit()

import enum




