# Twitter Trending Topics Scraper

A Flask-based web application that scrapes trending topics from Twitter using Selenium and stores them in MongoDB.

## Prerequisites

- Python 3.10 or higher
- MongoDB database
- Chrome browser
- ProxyMesh account

## Installation

1. Clone the repository:
```bash
git clone https://github.com/manascb1344/twitter-proxymesh.git
cd twitter-proxymesh
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  
# On Windows, use: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Download Chrome browser and ChromeDriver:
```bash
# Download and extract Chrome (Linux)
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f

# Download ChromeDriver (make sure version matches your Chrome version)
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
```

5. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your configuration details:
     - MongoDB connection string
     - ProxyMesh credentials
     - Twitter login credentials
     - Chrome and ChromeDriver paths

```bash
cp .env.example .env
```

## Configuration

Edit the `.env` file with your credentials:

```env
# MongoDB Configuration
MONGODB_URI=your_mongodb_connection_string
MONGODB_DB_NAME=your_database_name
MONGODB_COLLECTION=your_collection_name

# Proxy Configuration
PROXY_USERNAME=your_proxymesh_username
PROXY_PASSWORD=your_proxymesh_password
PROXY_PORT=your_proxy_port

# Twitter Credentials
TWITTER_USERNAME=your_twitter_username
TWITTER_PASSWORD=your_twitter_password

# Chrome Configuration
CHROME_BINARY_PATH=path_to_chrome_binary
CHROME_DRIVER_PATH=path_to_chromedriver

# Proxy Servers
PROXY_SERVERS=proxy1.example.com,proxy2.example.com
```

## Running the Application

1. Start the Flask application:
```bash
python app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Use the web interface to:
   - Start scraping trending topics
   - View results
   - Download scraped data

## Logging

The application logs are stored in `twitter_scraper.log`. Monitor this file for debugging and tracking the scraping process.