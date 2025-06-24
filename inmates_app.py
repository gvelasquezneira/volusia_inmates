import os
import json
from sqlalchemy import Column, String, Integer, text
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template
import sqlite3

app = Flask(__name__)
application = app
db = SQLAlchemy()

# Configure database
db_path = os.path.abspath('volusia_inmates.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False

db.init_app(app)

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
        # Query all inmates
        inmates = db.session.execute(text("SELECT * FROM inmates ORDER BY booking_date DESC")).all()
        inmate_data = []
        
        for row in inmates:
            # Parse charges JSON
            charges = json.loads(row.charges) if row.charges else []
            
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
        
        return render_template('index.html', inmates=inmate_data)
    
    except Exception as e:
        return render_template('error.html', 
                              heading='Database Connection Failed',
                              error_message=str(e))

if __name__ == '__main__':
    app.run(debug=True)