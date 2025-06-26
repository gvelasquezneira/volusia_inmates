import os
import json
import logging
from sqlalchemy import Column, String, Integer, text
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template
from sqlalchemy.exc import OperationalError

# Set up logging
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__)
application = app
app.logger.setLevel(logging.DEBUG)

# Configure database
db_path = os.path.abspath('volusia_inmates.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True  # Log SQL queries for debugging

db = SQLAlchemy()
db.init_app(app)

# Test database connection
try:
    with app.app_context():
        db.session.execute(text("SELECT 1")).scalar()
        app.logger.info("Database connection successful")
except Exception as e:
    app.logger.error(f"Failed to connect to database: {e}")

class Inmate(db.Model):
    __tablename__ = 'inmates'
    
    id = Column(Integer, primary_key=True)
    booking_num = Column(String, unique=True)
    inmate_id = Column(String)
    last_name = Column(String)
    first_name = Column(String)
    middle_name = Column(String)
    suffix = Column(String)
    sex = Column(String)
    race = Column(String)
    booking_date = Column(String)
    release_date = Column(String)
    in_custody = Column(String)
    photo_link = Column(String)
    charges = Column(String)

@app.route('/')
def index():
    try:
        # Verify database file exists
        if not os.path.exists('volusia_inmates.db'):
            app.logger.error("Database file volusia_inmates.db not found")
            return render_template('error.html', 
                                  heading='Database Not Found',
                                  error_message='The database file is missing. Please run the scraper (volusia.py).')
        
        # Query all inmates
        inmates = db.session.execute(text("SELECT * FROM inmates ORDER BY booking_date DESC")).all()
        inmate_data = []
        
        for row in inmates:
            try:
                charges = json.loads(row.charges) if row.charges else []
            except json.JSONDecodeError as e:
                app.logger.error(f"Invalid JSON in charges for booking_num {row.booking_num}: {e}")
                charges = []
            
            inmate = {
                'id': row.id,
                'booking_num': row.booking_num,
                'inmate_id': row.inmate_id,
                'last_name': row.last_name,
                'first_name': row.first_name,
                'middle_name': row.middle_name,
                'suffix': row.suffix,
                'sex': row.sex,
                'race': row.race,
                'booking_date': row.booking_date,
                'release_date': row.release_date,
                'in_custody': row.in_custody,
                'photo_link': row.photo_link,
                'charges': charges,
                'charge_count': len(charges)
            }
            inmate_data.append(inmate)
        
        if not inmate_data:
            app.logger.warning("No inmates found in database")
            return render_template('error.html', 
                                  heading='No Inmate Data',
                                  error_message='The database is empty. Please run the scraper (volusia.py) to populate it.')
        
        return render_template('index.html', inmates=inmate_data)
    
    except OperationalError as e:
        app.logger.error(f"Database error: {e}")
        return render_template('error.html', 
                              heading='Database Connection Failed',
                              error_message='Unable to access inmate data. Please ensure the database is populated.')
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return render_template('error.html', 
                              heading='Internal Server Error',
                              error_message='An unexpected error occurred. Please try again later.')


if __name__ == '__main__':
    app.run(debug=False)
