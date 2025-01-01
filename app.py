# Import required libraries
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from pymongo import MongoClient
from datetime import datetime
import uuid
import time
from flask import Flask, render_template, jsonify, make_response
from bson.json_util import dumps
import os
import random
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitter_scraper.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

logger.info("Loading environment variables")
load_dotenv()

logger.info("Initializing MongoDB connection")
client = MongoClient(os.getenv('MONGODB_URI'))
db = client[os.getenv('MONGODB_DB_NAME')]
collection = db[os.getenv('MONGODB_COLLECTION')]

PROXY_USERNAME = os.getenv('PROXY_USERNAME')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD')
PROXY_PORT = os.getenv('PROXY_PORT')

TWITTER_USERNAME = os.getenv('TWITTER_USERNAME')
TWITTER_PASSWORD = os.getenv('TWITTER_PASSWORD')

CHROME_BINARY_PATH = os.getenv('CHROME_BINARY_PATH')
CHROME_DRIVER_PATH = os.getenv('CHROME_DRIVER_PATH')

proxy_servers = os.getenv('PROXY_SERVERS').split(',')
logger.info(f"Loaded {len(proxy_servers)} proxy servers")

def scrape_twitter():
    max_retries = 3
    current_proxy_index = 0
    driver = None
    
    while current_proxy_index < len(proxy_servers):
        try:
            if driver:
                logger.warning("Existing browser session found - closing it")
                try:
                    driver.quit()
                except Exception as e:
                    logger.error(f"Error closing existing driver: {str(e)}")

            logger.info("Setting up Chrome options")
            chrome_options = Options()
            chrome_options.binary_location = os.path.abspath(CHROME_BINARY_PATH)
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')

            service = Service(os.path.abspath(CHROME_DRIVER_PATH))
            
            logger.info(f"Starting new browser session with proxy {proxy_servers[current_proxy_index]}")
            
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            window_handles = driver.window_handles
            logger.info(f"Number of open windows: {len(window_handles)}")

            try:
                logger.info("Clearing browser data")
                driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
                driver.execute_cdp_cmd('Network.clearBrowserCache', {})
                
                logger.info("Navigating to Twitter login page")
                driver.get("https://twitter.com/login")
                
                new_handles = driver.window_handles
                if len(new_handles) > len(window_handles):
                    logger.warning(f"New windows detected! Current window count: {len(new_handles)}")
                    driver.switch_to.window(driver.window_handles[0])

                def random_delay():
                    delay = random.uniform(2, 4)
                    logger.debug(f"Random delay: {delay:.2f} seconds")
                    time.sleep(delay)
                
                logger.info("Starting login process")
                wait = WebDriverWait(driver, 20)
                username = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]')))
                
                logger.info("Entering username")
                for char in TWITTER_USERNAME:
                    username.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.3))
                random_delay()
                
                logger.info("Clicking next button")
                next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']")))
                next_button.click()
                random_delay()

                logger.info("Entering password")
                password = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="password"]')))
                for char in TWITTER_PASSWORD:
                    password.send_keys(char)
                    time.sleep(random.uniform(0.1, 0.3))
                random_delay()
                
                logger.info("Clicking login button")
                login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Log in']")))
                login_button.click()
                random_delay()
                
                try:
                    logger.info("Waiting for home page to load")
                    wait.until(lambda driver: (
                        len(driver.find_elements(By.CSS_SELECTOR, '[aria-label="Timeline: Trending now"]')) > 0 or
                        len(driver.find_elements(By.XPATH, "//span[text()='For You']")) > 0
                    ))
                    logger.info("Successfully logged in and reached home page")
                    
                    try:
                        logger.info("Attempting to click Explore link")
                        explore_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Search and explore']")))
                        explore_link.click()
                    except Exception as e:
                        logger.warning(f"Could not click Explore link: {str(e)}")
                        logger.info("Navigating directly to explore page")
                        driver.get("https://twitter.com/explore")
                    
                    logger.info("Navigated to explore page")
                    time.sleep(3)
                    
                    logger.info("Waiting for trending section to load")
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="trend"]')))
                    time.sleep(2)
                    
                    logger.info("Scrolling to load all trends")
                    driver.execute_script("window.scrollBy(0, 500)")
                    time.sleep(1)
                    
                    trends = []
                    
                    logger.info("Attempting Method 1 for trend extraction")
                    trend_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="trend"]')
                    for element in trend_elements:
                        try:
                            spans = element.find_elements(By.CSS_SELECTOR, 'span')
                            for span in spans:
                                text = span.text.strip()
                                if (text and 
                                    not text.endswith('posts') and 
                                    not text.startswith('Trending') and 
                                    not text.startswith('Entertainment') and
                                    not text.startswith('Politics') and
                                    not text.startswith('Sports') and
                                    not ' · ' in text and
                                    not text.startswith('Show more')):
                                    trends.append(text)
                        except Exception as e:
                            logger.debug(f"Failed to extract trend in Method 1: {str(e)}")
                            continue
                    
                    if not trends:
                        logger.info("Method 1 failed, attempting Method 2")
                        try:
                            trend_containers = driver.find_elements(By.CSS_SELECTOR, '[data-testid="cellInnerDiv"]')
                            for container in trend_containers:
                                try:
                                    trend_name = container.find_element(By.CSS_SELECTOR, 'div[dir="ltr"] span').text.strip()
                                    posts_text = container.find_element(By.CSS_SELECTOR, 'span[style*="color: rgb(83, 100, 113)"]').text.strip()
                                    
                                    if (trend_name and 
                                        'posts' in posts_text.lower() and 
                                        not trend_name.endswith('posts') and 
                                        not ' · ' in trend_name and
                                        not trend_name.startswith('Trending') and
                                        not trend_name.startswith('Entertainment') and
                                        not trend_name.startswith('Politics') and
                                        not trend_name.startswith('Sports')):
                                        trends.append(trend_name)
                                except:
                                    continue
                        except Exception as e:
                            logger.warning(f"Method 2 failed entirely: {str(e)}")
                    
                    if not trends:
                        logger.info("Method 2 failed, attempting Method 3 (JavaScript)")
                        try:
                            trends = driver.execute_script("""
                                return Array.from(document.querySelectorAll('[data-testid="trend"]'))
                                    .map(el => {
                                        const spans = el.querySelectorAll('span');
                                        for (const span of spans) {
                                            const text = span.textContent.trim();
                                            if (text && 
                                                !text.endsWith('posts') && 
                                                !text.startsWith('Trending') &&
                                                !text.startsWith('Entertainment') &&
                                                !text.startsWith('Politics') &&
                                                !text.startsWith('Sports') &&
                                                !text.includes(' · ')) {
                                                return text;
                                            }
                                        }
                                        return null;
                                    })
                                    .filter(text => text !== null);
                            """)
                        except Exception as e:
                            logger.warning(f"Method 3 failed: {str(e)}")
                    
                    logger.info("Processing extracted trends")
                    trends = [t for t in trends if t and not t.isspace() and 
                              not t.startswith('Entertainment') and 
                              not t.startswith('Politics') and 
                              not t.startswith('Sports') and 
                              not ' · ' in t]
                    trends = list(dict.fromkeys(trends))
                    
                    final_trends = []
                    for trend in trends:
                        if len(final_trends) >= 5:
                            break
                        if trend and trend.strip():
                            final_trends.append(trend)
                    
                    while len(final_trends) < 5:
                        final_trends.append("N/A")
                    
                    logger.info(f"Final extracted trends: {final_trends}")
                    
                    unique_id = str(uuid.uuid4())
                    logger.info(f"Generated UUID: {unique_id}")
                    
                    ip_address = None
                    
                    logger.info("Attempting to get IP address via ProxyMesh API")
                    try:
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                        }
                        response = requests.get(
                            'https://proxymesh.com/api/proxies/current_ip',
                            auth=(PROXY_USERNAME, PROXY_PASSWORD),
                            headers=headers,
                            timeout=10,
                            verify=False
                        )
                        
                        if response.status_code == 200:
                            ip_address = response.text.strip()
                            logger.info(f"Successfully got IP from ProxyMesh: {ip_address}")
                    except Exception as e:
                        logger.warning(f"ProxyMesh IP lookup failed: {str(e)}")
                    
                    if not ip_address:
                        logger.info("Attempting to get IP address via ipify.org")
                        try:
                            ip_address = driver.execute_script("""
                                return fetch('https://api.ipify.org')
                                    .then(response => response.text())
                                    .catch(error => null);
                            """)
                            if ip_address:
                                logger.info(f"Successfully got IP from ipify: {ip_address}")
                        except Exception as e:
                            logger.warning(f"ipify IP lookup failed: {str(e)}")

                    if not ip_address:
                        logger.info("Attempting to get IP address via ip-api.com")
                        try:
                            proxies = {
                                'http': f'http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{proxy_servers[current_proxy_index]}:31280',
                                'https': f'http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{proxy_servers[current_proxy_index]}:31280'
                            }
                            
                            session = requests.Session()
                            session.trust_env = False
                            response = session.get(
                                'http://ip-api.com/json/',
                                proxies=proxies,
                                headers=headers,
                                timeout=10,
                                verify=False
                            )
                            
                            if response.status_code == 200:
                                data = response.json()
                                ip_address = data.get('query')
                                logger.info(f"Successfully got IP from ip-api: {ip_address}")
                        except Exception as e:
                            logger.warning(f"ip-api IP lookup failed: {str(e)}")

                    if not ip_address or not any(c.isdigit() for c in ip_address):
                        logger.info("Attempting to get IP address via DNS lookup")
                        try:
                            import socket
                            ip_address = socket.gethostbyname(proxy_servers[current_proxy_index])
                            logger.info(f"Successfully got IP via DNS: {ip_address}")
                        except Exception as e:
                            logger.error(f"DNS lookup failed: {str(e)}")
                            ip_address = "Error getting IP"

                    logger.info("Preparing result for database")
                    result = {
                        "_id": unique_id,
                        "trend1": final_trends[0],
                        "trend2": final_trends[1],
                        "trend3": final_trends[2],
                        "trend4": final_trends[3],
                        "trend5": final_trends[4],
                        "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "ip_address": ip_address
                    }
                    
                    logger.info("Inserting result into database")
                    collection.insert_one(result)
                    logger.info("Successfully saved result to database")
                    return result

                except Exception as e:
                    logger.error(f"Error extracting trends: {str(e)}", exc_info=True)
                    raise e

            except Exception as e:
                logger.error(f"Error during scraping: {str(e)}", exc_info=True)
                raise e
            finally:
                if driver:
                    logger.info("Closing browser session")
                    try:
                        driver.quit()
                    except Exception as e:
                        logger.error(f"Error closing driver: {str(e)}")

        except Exception as e:
            logger.error(f"Error with proxy {proxy_servers[current_proxy_index]}: {str(e)}", exc_info=True)
            current_proxy_index += 1
            if current_proxy_index >= len(proxy_servers):
                logger.error("All proxy servers failed")
                raise Exception("All proxy servers failed")
            
def scrape_with_driver(driver):
    try:
        logger.info("Starting scrape with existing driver")
        driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
        driver.execute_cdp_cmd('Network.clearBrowserCache', {})
        
        logger.info("Navigating to Twitter login")
        driver.get("https://twitter.com/login")
        
        def random_delay():
            delay = random.uniform(2, 4)
            logger.debug(f"Random delay: {delay:.2f} seconds")
            time.sleep(delay)
        
        wait = WebDriverWait(driver, 20)
        logger.info("Waiting for username field")
        username = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]')))
        
        logger.info("Entering username")
        for char in TWITTER_USERNAME:
            username.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
        random_delay()
        
        logger.info("Clicking next button")
        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']")))
        next_button.click()
        random_delay()

        logger.info("Entering password")
        password = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="password"]')))
        for char in TWITTER_PASSWORD:
            password.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))
        random_delay()
        
        logger.info("Clicking login button")
        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Log in']")))
        login_button.click()
        random_delay()
        
        logger.info("Waiting for trending section")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="trend"]')))
        
        trending_topics = driver.find_elements(By.CSS_SELECTOR, '[data-testid="trend"]')
        trends = []
        
        logger.info("Extracting trends")
        for topic in trending_topics[:5]:
            try:
                trend_text = topic.find_element(By.CSS_SELECTOR, 'span').text
                trends.append(trend_text)
            except Exception as e:
                logger.warning(f"Failed to extract trend: {str(e)}")
                continue

        if not trends:
            logger.info("Primary trend extraction failed, trying fallback method")
            trending_topics = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"] span')
            trends = [topic.text for topic in trending_topics[:5] if topic.text.strip()]

        unique_id = str(uuid.uuid4())
        logger.info(f"Generated UUID: {unique_id}")
        
        try:
            logger.info("Attempting to get IP address")
            ip_address = driver.execute_script("""
                return fetch('http://proxymesh.com/api/whoami')
                    .then(response => response.text())
                    .catch(error => 'Unknown');
            """)
        except Exception as e:
            logger.warning(f"Primary IP lookup failed: {str(e)}")
            try:
                ip_address = driver.execute_script("""
                    return fetch('http://api.ipify.org')
                        .then(response => response.text())
                        .catch(error => 'Unknown');
                """)
            except Exception as e:
                logger.error(f"Backup IP lookup failed: {str(e)}")
                ip_address = "us-ca.proxymesh.com"

        logger.info("Preparing result for database")
        result = {
            "_id": unique_id,
            "trend1": trends[0] if len(trends) > 0 else "N/A",
            "trend2": trends[1] if len(trends) > 1 else "N/A",
            "trend3": trends[2] if len(trends) > 2 else "N/A",
            "trend4": trends[3] if len(trends) > 3 else "N/A",
            "trend5": trends[4] if len(trends) > 4 else "N/A",
            "date_time": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "ip_address": ip_address
        }
        
        logger.info("Inserting result into database")
        collection.insert_one(result)
        logger.info("Successfully saved result to database")
        return result

    except Exception as e:
        logger.error(f"Error in scrape_with_driver: {str(e)}", exc_info=True)
        raise e
    finally:
        logger.info("Closing browser session")
        driver.quit()

app = Flask(__name__)
logger.info("Flask app initialized")

@app.route("/")
def index():
    logger.info("Home page requested")
    return render_template("index.html")

@app.route("/run_script", methods=["GET"])
def run_script():
    logger.info("Scraping script requested")
    try:
        result = scrape_twitter()
        logger.info("Scraping completed successfully")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error running scraping script: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/get_results", methods=["GET"])
def get_results():
    logger.info("Results requested")
    try:
        records = list(collection.find())
        logger.info(f"Retrieved {len(records)} records")
        return dumps(records)
    except Exception as e:
        logger.error(f"Error retrieving results: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/download_data", methods=["GET"])
def download_data():
    try:
        logger.info("Data download requested")
        
        records = list(collection.find())
        
        if not records:
            logger.warning("No records found to download")
            return jsonify({"error": "No data available"}), 404
        
        formatted_records = []
        for record in records:
            formatted_records.append({
                "_id": str(record.get("_id", "")),
                "trend1": record.get("trend1", ""),
                "trend2": record.get("trend2", ""),
                "trend3": record.get("trend3", ""),
                "trend4": record.get("trend4", ""),
                "trend5": record.get("trend5", ""),
                "date_time": record.get("date_time", ""),
                "ip_address": record.get("ip_address", "")
            })
        
        output = make_response(dumps(formatted_records, indent=2))
        output.headers["Content-Disposition"] = "attachment; filename=twitter_trends.json"
        output.headers["Content-type"] = "application/json"
        
        logger.info(f"Successfully prepared JSON with {len(records)} records")
        return output
        
    except Exception as e:
        logger.error(f"Error downloading data: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    logger.info("Starting Flask application")
    app.run(debug=True)
