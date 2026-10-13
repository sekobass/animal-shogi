"""Run browser interaction checks (requires Playwright and Chromium)."""
import argparse
import time
import urllib.request
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('url')
parser.add_argument('--verified-proxy-fetch', action='store_true', help='Use Python TLS trust for CDN fetches in managed cloud browsers')
args = parser.parse_args()
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
    page = browser.new_page()
    if args.verified_proxy_fetch:
        def fetch(route):
            response = urllib.request.urlopen(route.request.url, timeout=60)
            route.fulfill(status=response.status, body=response.read(), headers={
                'Content-Type': response.headers.get('Content-Type', 'application/octet-stream'),
                'Access-Control-Allow-Origin': '*'})
        page.route('https://cdn.jsdelivr.net/**', fetch)
    page.goto(args.url)
    page.wait_for_function('!document.querySelector("#first").disabled', timeout=90000)
    start = time.monotonic()
    page.click('#first')
    page.locator('#board button').nth(7).click()
    page.locator('#board button').nth(4).click()
    page.wait_for_function('state.turn === 0 && !busy', timeout=30000)
    assert page.locator('#hand button').count() >= 1
    page.click('#second')
    page.wait_for_function('state.turn === 0 && !busy', timeout=30000)
    assert page.locator('#board button').count() == 12
    print(f'PASS browser: first/second, capture, stronger AI; interaction checks {time.monotonic()-start:.2f}s')
    browser.close()
