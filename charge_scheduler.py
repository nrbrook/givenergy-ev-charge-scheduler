import argparse
import datetime
import logging
from logging.handlers import RotatingFileHandler
import requests
import agile_prices
import re

log_file_max_size = 1 * 1024 * 1024  # 5 MB
log_file_backup_count = 0  # Number of backup files to keep

logger_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Setup logging for output and errors
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

logger = logging.getLogger('chargeLogger')
logger.setLevel(logging.INFO)

# API base URL and headers template
API_BASE_URL = 'https://api.givenergy.cloud/v1/ev-charger'
HEADERS_TEMPLATE = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

def parse_time(time_str):
    return datetime.datetime.strptime(time_str, "%H:%M").time()

def fetch_uuids(api_key, to_start):
    url = f'{API_BASE_URL}'
    params = {'page': '1'}
    headers = HEADERS_TEMPLATE.copy()
    headers['Authorization'] = f'Bearer {api_key}'
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json().get('data', [])

        # Filter UUIDs based on status
        uuids = []
        filter_statuses = ["Preparing", "SuspendedEVSE"] if to_start else ["Charging"]

        for charger in data:
            if charger['status'] in filter_statuses:
                uuids.append(charger['uuid'])
            else:
                # Log the skipped charging points
                logger.info(f"Skipping charger {charger['alias']} (UUID: {charger['uuid']}) - Status: {charger['status']}")

        return uuids
    except Exception as e:
        logger.error(f"Error fetching UUIDs: {e}")
        return []

def send_command(api_key, uuid, command):
    url = f'{API_BASE_URL}/{uuid}/commands/{command}'
    headers = HEADERS_TEMPLATE.copy()
    headers['Authorization'] = f'Bearer {api_key}'
    try:
        response = requests.post(url, headers=headers)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending command {command} to {uuid}: {e}")
        return None

def set_charging(api_key, status, uuid=None):
    command = 'start-charge' if status else 'stop-charge'
    uuids = [uuid] if uuid else fetch_uuids(api_key, status)
    if len(uuids) == 0:
        logger.info("No available chargers to control")
        return

    for uuid in uuids:
        response = send_command(api_key, uuid, command)
        if response and response.get('data', {}).get('success'):
            logger.info(f"Command {command} sent to {uuid}. Response: {response}")
        else:
            logger.error(f"Failed to send command {command} to {uuid}. Response: {response}")

def price_scheduler(api_key, charger_uuid, db, price):
    if db == None:
        raise ValueError(f"No database provided")
    prices = agile_prices.get_prices_from_db(db, 1)
    should_charge = prices[0]['price'] <= price
    logger.info(f"Current price {prices[0]['price']}p {'<=' if should_charge else '>'} {price}p, should{'' if should_charge else ' not'} charge")
    set_charging(api_key, should_charge, charger_uuid)

def process_schedule(api_key, charger_uuid, schedule_file, db):
    try:
        with open(schedule_file, 'r') as file:
            lines = file.readlines()
            if not lines or len(lines) == 0:
                logger.info("No schedule")
                return

            price_pattern = re.compile(r'(\d+)p')
            price_match = price_pattern.match(lines[0].strip())
            if price_match:
                price_scheduler(api_key, charger_uuid, db, int(price_match.group(1)))
            else:
                time_pattern = re.compile(r'(\d{1,2})([:.](\d{1,2}))?-(\d{1,2})([:.](\d{1,2}))?')
                time_match = time_pattern.match(lines[0].strip())
                if time_match:
                    groups = time_match.groups()
                    start_hour, start_minute, end_hour, end_minute = groups[0], groups[2], groups[3], groups[5]
                    start_minute = '00' if start_minute is None else start_minute
                    end_minute = '00' if end_minute is None else end_minute

                    start_time = parse_time(f"{start_hour}:{start_minute}")
                    end_time = parse_time(f"{end_hour}:{end_minute}")

                    now = datetime.datetime.now().time()

                    if start_time <= now <= end_time:
                        set_charging(api_key, True, charger_uuid)
                    elif end_time < now < (datetime.datetime.combine(datetime.date.today(), end_time) + datetime.timedelta(minutes=5)).time():
                        set_charging(api_key, False, charger_uuid)
                        with open(schedule_file, 'w') as file_write:
                            file_write.writelines(lines[1:])
    except Exception as e:
        logger.error(f"Error processing schedule: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", "--api_key", required=True, help="API key for authentication")
    parser.add_argument("-c", "--charger_uuid", help="UUID of the charging point. If not provided, all charging points are controlled", default=None)
    parser.add_argument("-f", "--file", help="The schedule file. Will try `schedule.txt` in the current directory if omitted", default="schedule.txt")
    parser.add_argument("-d", "--database", help="The price database", default=None)
    parser.add_argument("-l", "--log", help="The log file. If provided, will not log to stdout", default=None)
    parser.add_argument("-e", "--error", help="The error log file", default=None)
    args = parser.parse_args()

    if args.log:
        print(f"Logging to {args.log}")
        file_handler = RotatingFileHandler(args.log, maxBytes=log_file_max_size, backupCount=log_file_backup_count)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logger_formatter)
        logger.addHandler(file_handler)
    else:
        logger.addHandler(console_handler)

    if args.error:
        print(f"Logging errors to {args.error}")
        error_handler = RotatingFileHandler(args.error, maxBytes=log_file_max_size, backupCount=log_file_backup_count)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logger_formatter)
        logger.addHandler(error_handler)

    process_schedule(args.api_key, args.charger_uuid, args.file, args.database)