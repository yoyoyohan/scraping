from playwright.sync_api import sync_playwright
import time

def test_wait_for_response():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.google.com")
        print("Page loaded.")

        try:
            # This is just a dummy URL to test if wait_for_response works
            # Google might make various requests, so we'll just wait for any image or script
            response = page.wait_for_response(lambda response: "/images/branding/googlelogo" in response.url or ".js" in response.url, timeout=10000)
            print(f"wait_for_response succeeded for URL: {response.url}")
        except Exception as e:
            print(f"wait_for_response failed: {e}")

        browser.close()

if __name__ == "__main__":
    test_wait_for_response()
