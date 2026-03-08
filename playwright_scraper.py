import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import unquote

# Direct URL for a specific conference, which is more reliable
url = "https://highschoolsports.nj.com/boyssoccer/standings/season/2023-2024?conference=Big%20North"


def fetch_with_playwright(url):
    """
    Fetches the content of a URL using Playwright, handling dynamic content.
    This version navigates directly to a conference-specific URL.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Block the fides.js script to prevent the privacy overlay
        page.route("**/fides.js*", lambda route: route.abort())

        try:
            # Navigate to the URL
            print(f"Navigating to direct conference URL: {url}")
            page.goto(url, timeout=120000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")  # Wait for all network requests to finish

            # List to store intercepted API responses
            api_responses = []

            def handle_response(response):
                # Filter for potential API calls returning JSON
                if "/api/v3/" in response.url and "application/json" in response.headers.get("content-type", ""):
                    try:
                        api_responses.append(
                            {
                                "url": response.url,
                                "status": response.status,
                                "json_data": response.json(),
                            }
                        )
                    except Exception as e:
                        print(f"Could not parse JSON from {response.url}: {e}")

            page.on("response", handle_response)

            # Give some time for asynchronous requests to complete after initial load
            page.wait_for_timeout(10000)  # Wait for 10 seconds

            # Save the final HTML content (for debugging purposes if API not found)
            content = page.content()
            with open("playwright_output.html", "w") as f:
                f.write(content)
            print("Saved final HTML to playwright_output.html")

            # Process captured API responses
            if api_responses:
                print("\n--- Captured API Responses ---")
                with open("network_api_responses.json", "w") as f:
                    json.dump(api_responses, f, indent=4)
                print("API responses saved to network_api_responses.json")
                # For now, we will return the content, but later we will use the API data
            else:
                print("No relevant API responses captured.")

            return content
        except Exception as e:
            print(f"An error occurred during Playwright execution: {e}")
            page.screenshot(path="playwright_error_screenshot.png")

            # Save content on error as well for debugging
            error_content = page.content()
            with open("playwright_output.html", "w") as f:
                f.write(error_content)
            print("Saved HTML on error to playwright_output.html")

            print("Screenshot taken on error.")
            return None
        finally:
            browser.close()


def analyze_page(url):
    """
    Analyzes the page to extract standings data. It now uses Playwright by default
    as we know the content is dynamic.
    """
    print("Fetching content with Playwright...")
    html_content = fetch_with_playwright(url)

    if not html_content:
        print("Failed to fetch page content with Playwright.")
        return

    soup = BeautifulSoup(html_content, "html.parser")
    is_js_rendered = True

    # Updated selector to be more specific to the standings page
    stats_table = soup.find("table", class_="standings-table")

    if not stats_table:
        print("Could not find the standings table with class 'standings-table' in the fetched HTML.")
        return

    print("\n--- Raw HTML of the stats table ---\n")
    print(stats_table.prettify())

    headers = [th.get_text(strip=True) for th in stats_table.find_all("th")]
    print("\n--- Column Headers ---\n")
    print(headers)

    # The standings table has a different structure, rows are directly in tbody
    player_rows = stats_table.find("tbody").find_all("tr") if stats_table.find("tbody") else []
    print("\n--- 3 Sample Rows ---\n")
    for i, row in enumerate(player_rows[:3]):
        # For standings, we can get team name from the 'a' tag and then other stats
        team_name = row.find("a").get_text(strip=True) if row.find("a") else "N/A"

        # Get all other data cells
        row_data = [td.get_text(strip=True) for td in row.find_all("td")]

        # Prepend team name to the rest of the data
        full_row = [team_name] + row_data[1:]  # Assuming first column is the team name, which we already got

        print(f"Row {i+1}: {full_row}")

    print("\n--- Report ---\n")
    if is_js_rendered:
        print("The page content is JavaScript-rendered and was fetched using Playwright.")
    else:
        # This path is no longer taken, but kept for logical completeness
        print("The page content is static HTML.")


if __name__ == "__main__":
    analyze_page(url)

