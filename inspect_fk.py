from app import create_app, db
from sqlalchemy import inspect

# Create the Flask app
app = create_app()

# Push the app context to work with the database
with app.app_context():
    # Create an inspector
    inspector = inspect(db.engine)

    # Get foreign keys for the 'booking' table
    foreign_keys = inspector.get_foreign_keys('booking')

    # Print details about the foreign keys
    for fk in foreign_keys:
        print(f"Foreign Key: {fk['name']}, Column: {fk['constrained_columns']}, References: {fk['referred_table']}({fk['referred_columns']})")
