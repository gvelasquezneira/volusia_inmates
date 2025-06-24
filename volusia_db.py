import sqlite3
import json

conn = sqlite3.connect('volusia_inmates.db')
cursor = conn.cursor()
cursor.execute('SELECT booking_num, first_name, last_name, charges FROM inmates')
rows = cursor.fetchall()

for row in rows:
    booking_num, first_name, last_name, charges_json = row
    charges = json.loads(charges_json)  # Parse JSON string to list
    print(f"{first_name} {last_name} ({booking_num}): {len(charges)} charges")
    for charge in charges:
        print(f"  Charge {charge['charge_num']}: {charge['description']}")

conn.close()