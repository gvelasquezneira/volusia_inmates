import asyncio
import json
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import sqlite3
import time
import os

async def main():
    # Initialize SQLite database
    conn = sqlite3.connect('volusia_inmates.db')
    cursor = conn.cursor()

    # Create a table with one row per record
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inmates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_num TEXT UNIQUE,
            inmate_id TEXT,
            last_name TEXT,
            first_name TEXT,
            middle_name TEXT,
            suffix TEXT,
            sex TEXT,
            race TEXT,
            booking_date TEXT,
            release_date TEXT,
            in_custody TEXT,
            photo_link TEXT,
            charges TEXT
        )
    ''')

    conn.commit()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # Navigate to the disclaimer page
        disclaimer_url = "https://volusiamug.vcgov.org/Disclaimer.aspx"
        print("Navigating to disclaimer page...")
        await page.goto(disclaimer_url, wait_until="networkidle")

        # Click the "Accept" button
        accept_button = page.locator('input[name="ButtonAccept"]')
        await accept_button.click()
        print("Clicked 'Accept' button")
        await page.wait_for_load_state("networkidle")

        # Save HTML for debugging
        disclaimer_html = await page.content()
        with open("disclaimer_page.html", "w", encoding="utf-8") as f:
            f.write(disclaimer_html)

        # Click the "Recent Bookings" button
        recent_button = page.locator('input[name="btnRecentBookings"]')
        await recent_button.click()
        print("Clicked 'Recent Bookings' button")
        await page.wait_for_load_state("networkidle")

        # Save the results page HTML for debugging
        results_html = await page.content()
        with open("results_page.html", "w", encoding="utf-8") as f:
            f.write(results_html)
        print("Saved results page HTML for debugging")

        # Base URL for relative links
        base_url = "https://volusiamug.vcgov.org/"

        # Process the results page
        results_soup = BeautifulSoup(results_html, 'html.parser')

        # Try different ways to find the table
        inmates_table = None
        all_tables = results_soup.find_all('table')
        print(f"Found {len(all_tables)} tables on the page")

        for i, table in enumerate(all_tables):
            if table.get('id') == 'Grid':
                inmates_table = table
                print(f"Found inmates table at index {i}")
                break

        if inmates_table is None:
            print("Trying more generic table search")
            for i, table in enumerate(all_tables):
                first_row = table.find('tr')
                if first_row:
                    cells = first_row.find_all('td')
                    if len(cells) >= 2:
                        headers_text = [cell.get_text().strip() for cell in cells]
                        if "Booking #" in headers_text or "Inmate ID" in headers_text:
                            inmates_table = table
                            print(f"Found inmates table by header content at index {i}")
                            break

        if inmates_table:
            # Extract rows (skip the header row)
            rows = inmates_table.find_all('tr')[1:]  # Skip header row
            print(f"Found {len(rows)} inmate rows in the table")

            # Process each inmate row
            for row_index, row in enumerate(rows):
                cells = row.find_all('td')
                if len(cells) <= 1:
                    print(f"Skipping row {row_index} (likely pagination)")
                    continue

                if len(cells) >= 12:  # Ensure we have all the expected columns
                    # Extract inmate data
                    booking_link = cells[0].find('a')
                    booking_num = booking_link.text.strip() if booking_link else ""
                    detail_url = booking_link['href'] if booking_link else ""

                    # Extract image URL if present
                    img_tag = cells[1].find('img')
                    photo_url = base_url + img_tag['src'] if img_tag else ""

                    inmate_id = cells[2].text.strip()
                    last_name = cells[3].text.strip()
                    first_name = cells[4].text.strip()
                    middle_name = cells[5].text.strip()
                    suffix = cells[6].text.strip()
                    sex = cells[7].text.strip()
                    race = cells[8].text.strip()
                    booking_date = cells[9].text.strip()
                    release_date = cells[10].text.strip()
                    in_custody = cells[11].text.strip()

                    print(f"Processing inmate {row_index}: {first_name} {last_name} (Booking #{booking_num})")

                    # Initialize list to store charges
                    charges_list = []

                    # Visit the detail page to get charges
                    if detail_url:
                        await asyncio.sleep(1.5)  # Delay to avoid overwhelming the server
                        await page.goto(base_url + detail_url, wait_until="networkidle")
                        detail_html = await page.content()
                        detail_soup = BeautifulSoup(detail_html, 'html.parser')

                        # Find the charges table
                        charges_table = None
                        all_detail_tables = detail_soup.find_all('table')

                        for table in all_detail_tables:
                            if table.get('id') == 'Grid':
                                charges_table = table
                                break

                        if charges_table is None and all_detail_tables:
                            first_table = all_detail_tables[0]
                            first_row = first_table.find('tr')
                            if first_row:
                                headers = [h.text.strip() for h in first_row.find_all('td')]
                                if 'Charge #' in headers or 'Statute' in headers:
                                    charges_table = first_table

                        if charges_table:
                            charge_rows = charges_table.find_all('tr')[1:]  # Skip header row
                            charge_count = 0

                            for charge_row in charge_rows:
                                charge_cells = charge_row.find_all('td')
                                if len(charge_cells) <= 1:
                                    continue

                                if len(charge_cells) >= 10:
                                    charge_count += 1
                                    charge = {
                                        'charge_num': charge_cells[0].text.strip() if len(charge_cells) > 0 else "",
                                        'statute': charge_cells[1].text.strip() if len(charge_cells) > 1 else "",
                                        'description': charge_cells[2].text.strip() if len(charge_cells) > 2 else "",
                                        'bond_type': charge_cells[3].text.strip() if len(charge_cells) > 3 else "",
                                        'bond_amount': charge_cells[4].text.strip() if len(charge_cells) > 4 else "",
                                        'bond_num': charge_cells[5].text.strip() if len(charge_cells) > 5 else "",
                                        'arrest_case': charge_cells[6].text.strip() if len(charge_cells) > 6 else "",
                                        'court_case': charge_cells[7].text.strip() if len(charge_cells) > 7 else "",
                                        'disposition': charge_cells[8].text.strip() if len(charge_cells) > 8 else "",
                                        'charge_status': charge_cells[9].text.strip() if len(charge_cells) > 9 else "",
                                        'other_statute': charge_cells[10].text.strip() if len(charge_cells) > 10 else "",
                                        'other_description': charge_cells[11].text.strip() if len(charge_cells) > 11 else ""
                                    }
                                    charges_list.append(charge)

                            print(f"Processed {charge_count} charges for inmate {booking_num}")
                        else:
                            print(f"No charges table found for inmate {booking_num}")

                    # Combine inmate data with charges (as JSON string)
                    row_data = (
                        booking_num, inmate_id, last_name, first_name, middle_name,
                        suffix, sex, race, booking_date, release_date, in_custody,
                        photo_url, json.dumps(charges_list)
                    )

                    # Insert data into database
                    try:
                        cursor.execute('''
                            INSERT OR REPLACE INTO inmates (
                                booking_num, inmate_id, last_name, first_name, middle_name,
                                suffix, sex, race, booking_date, release_date, in_custody,
                                photo_link, charges
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', row_data)
                        conn.commit()
                    except sqlite3.Error as e:
                        print(f"Error inserting inmate {booking_num}: {e}")

        else:
            print("No inmates table found on the results page. Check results_page.html for the HTML structure.")

        conn.close()
        print("Data scraped and saved to volusia_inmates.db")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())