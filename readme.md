# GivEnergy EV Charging Scheduler Script

## Description
This script automates the management of electric vehicle (EV) charging schedules based on time or pricing indicators. It reads a schedule from a file, determines whether to start or stop charging, and can handle multiple charging points.

You can write a schedule such as:
```
22-23
0:30-1
4-5
```
And it will charge between those times. Or, if you use Octopus Agile, you can also schedule when a price goes below a set point:
```
10p
```

It is intended to be run on an always-on server/appliance. I run it on a Raspberry Pi zero which also [displays the upcoming Octopus Agile prices](https://github.com/nrbrook/octopus-agile-pi-prices/tree/inkyphat-improvements).

## Requirements
- Python 3.x
- Requests library
- pytz

## Installation
1. Ensure Python 3.x is installed on your system.
2. Ensure this repository has been cloned with submodules: `git clone --recurse-submodules https://github.com/nrbrook/givenergy-ev-charge-scheduler`
3. Install the requirements:

```
pip install -r requirements.txt
```

## Usage
```
usage: charge_scheduler.py [-h] -k API_KEY [-c CHARGER_UUID] [-f FILE] [-d DATABASE] [-l LOG] [-e ERROR]

options:
  -h, --help            show this help message and exit
  -k API_KEY, --api_key API_KEY
                        API key for authentication
  -c CHARGER_UUID, --charger_uuid CHARGER_UUID
                        UUID of the charging point. If not provided, all available charging points are controlled
  -f FILE, --file FILE  The schedule file. Will try `schedule.txt` in the current directory if omitted.
  -d DATABASE, --database DATABASE
                        The price database
  -l LOG, --log LOG     The log file. If provided, will not log to stdout
  -e ERROR, --error ERROR
                        The error log file. If provided, will not log to stderr
```

- `-k YOUR_API_KEY`: Replace `YOUR_API_KEY` with your actual API key which you can obtain [from GivEnergy](https://api.givenergy.cloud/account-settings/api-tokens)
- `-c CHARGER_UUID`: Optional. Specify a charger UUID to control a specific charger. If omitted, the script will operate on all available chargers.
- `-f FILE`: The file which contains the schedule. Will try `schedule.txt` in the current directory if omitted.
- `-d DATABASE`: The database containing the latest agile prices
- `-l LOG`: A file to store logs in
- `-e ERROR`: A file to store error logs in

### Schedule File
The `schedule.txt` file should contain entries in either of these formats:
- Time ranges: `HH:MM-HH:MM` or `HH.MM-HH.MM` – the script processes the first timeslot then removes it after it is complete, and continues to the next slot.
- Pricing signal: `XXp` (e.g., `15p`) – will charge when the price is at or below this rate

### Database

The prices are fetched into a local sqlite database with the included agile-prices submodule.

### Crontab

The script(s) can be scheduled to run with crontab (`crontab -e`):

If you just want to schedule by timeslot:

```
0,30 * * * * cd /path/to/this/dir; /usr/bin/python3 charge_scheduler.py -k <your_api_key> -f <schedule_file>
```

If you use Octopus agile and want to schedule by price:

```
0,30 * * * * cd /path/to/this/dir; /usr/bin/python3 charge_scheduler.py -k <your_api_key> -f <schedule_file> -d agile_prices/agileprices.sqlite
05 * * * * cd /path/to/this/dir/agile_prices; /usr/bin/python3 store_prices.py -r <region> -t <agile_tariff> > /path/to/your/log.log
```

You should replace `/path/to/this/dir` and `/path/to/your/log.log` with your local paths, and `<region>` and `<agile_tariff>` as follows:

- Go to the octopus developer page and scroll to "Unit rates"
- There you will see a URL, for example "https://api.octopus.energy/v1/products/AGILE-FLEX-22-11-25/electricity-tariffs/E-1R-AGILE-FLEX-22-11-25-M/standard-unit-rates/"
- Look at this part: `E-1R-AGILE-FLEX-22-11-25-M`. This is in the format `E-1R-AGILE-<tariff>-<region>`. The tariff is the part following "AGILE-", e.g. "FLEX-22-11-25". The region is the letter at the end, e.g. "M".