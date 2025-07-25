import asyncio
import json
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import sqlite3
import time
import os

async def main():
    conn = sqlite3.connect('volusia_mugshots.db')
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
        try:
            await page.goto(disclaimer_url, wait_until="networkidle")
        except Exception as e:
            await browser.close()
            return

        # Click the "Accept" button
        accept_button = page.locator('input[name="ButtonAccept"]')
        try:
            if await accept_button.count() == 0:
                raise Exception("Accept button not found")
            await accept_button.click()
            await page.wait_for_load_state("networkidle")
        except Exception as e:
            await browser.close()
            return

        # Save HTML for debugging
        disclaimer_html = await page.content()
        with open("disclaimer_page.html", "w", encoding="utf-8") as f:
            f.write(disclaimer_html)

        # Click the "Recent Bookings" button
        recent_button = page.locator('input[name="btnRecentBookings"]')
        try:
            if await recent_button.count() == 0:
                raise Exception("Recent Bookings button not found")
            await recent_button.click()
            await page.wait_for_load_state("networkidle")
        except Exception as e:
            await browser.close()
            return

        base_url = "https://volusiamug.vcgov.org/"
        page_num = 1

        while True:
            # Save the results page HTML for debugging
            results_html = await page.content()
            with open(f"results_page_{page_num}.html", "w", encoding="utf-8") as f:
                f.write(results_html)

            # Process the results page
            results_soup = BeautifulSoup(results_html, 'html.parser')

            # Try different ways to find the table
            inmates_table = None
            all_tables = results_soup.find_all('table')

            for i, table in enumerate(all_tables):
                if table.get('id') == 'Grid':
                    inmates_table = table
                    break

            if inmates_table is None:
                for i, table in enumerate(all_tables):
                    first_row = table.find('tr')
                    if first_row:
                        cells = first_row.find_all('td')
                        if len(cells) >= 2:
                            headers_text = [cell.get_text().strip() for cell in cells]
                            if "Booking #" in headers_text or "Inmate ID" in headers_text:
                                inmates_table = table
                            

            if inmates_table:
                # Extract rows (skip the header row)
                rows = inmates_table.find_all('tr')[1:]
             

                # Process each inmate row
                for row_index, row in enumerate(rows):
                    cells = row.find_all('td')
                    
                    if len(cells) <= 1:
                        continue

                    if len(cells) >= 12:  
                        booking_link = cells[0].find('a')
                        booking_num = booking_link.text.strip() if booking_link else ""
                        detail_url = booking_link['href'] if booking_link else ""
                       

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
                        

                        charges_list = []

                        if detail_url:
                            await asyncio.sleep(2)  # Increased delay to avoid rate limiting
                            try:
                                await page.goto(base_url + detail_url, wait_until="networkidle")
                            except Exception as e:
                                continue

                            detail_html = await page.content()
                            with open(f"detail_page_{booking_num}.html", "w", encoding="utf-8") as f:
                                f.write(detail_html)

                            detail_soup = BeautifulSoup(detail_html, 'html.parser')
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

                                    charge_count += 1
                                    charge = {
                                        'charge_num': charge_cells[0].text.strip() if len(charge_cells) > 0 else "N/A",
                                        'statute': charge_cells[1].text.strip() if len(charge_cells) > 1 else "N/A",
                                        'description': charge_cells[2].text.strip() if len(charge_cells) > 2 else "N/A",
                                        'bond_type': charge_cells[3].text.strip() if len(charge_cells) > 3 else "N/A",
                                        'bond_amount': charge_cells[4].text.strip() if len(charge_cells) > 4 else "N/A",
                                        'bond_num': charge_cells[5].text.strip() if len(charge_cells) > 5 else "N/A",
                                        'arrest_case': charge_cells[6].text.strip() if len(charge_cells) > 6 else "N/A",
                                        'court_case': charge_cells[7].text.strip() if len(charge_cells) > 7 else "N/A",
                                        'disposition': charge_cells[8].text.strip() if len(charge_cells) > 8 else "N/A",
                                        'charge_status': charge_cells[9].text.strip() if len(charge_cells) > 9 else "N/A",
                                        'other_statute': charge_cells[10].text.strip() if len(charge_cells) > 10 else "N/A",
                                        'other_description': charge_cells[11].text.strip() if len(charge_cells) > 11 else "N/A"
                                    }
                                    charges_list.append(charge)

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

            # Check for pagination "Next" button
            next_button = page.locator('input[value="Next"]')
            if await next_button.count() > 0 and await next_button.is_enabled():
                await next_button.click()
                await page.wait_for_load_state("networkidle")
                page_num += 1
            else:
                print(f"No 'Next' button found or disabled on page {page_num}. Stopping pagination.")
                break

        conn.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
