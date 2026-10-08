import logging
import re
#from _pydatetime import timedelta
from datetime import datetime, timedelta

from utilities.helper import *


logger = logging.getLogger(__name__)


def validate_url_date_format(url, num) -> tuple[int, list, list] :

    urls = []
    date = []
    if url.endswith("Today.xml"):
        Validation_Output.append(helper_fuc(num, 'URL', 'Verify the date format in the URL', 'The URL should end with a date in YYYY-MM-DD format.', 'Failed', "The URL does not end with the expected date in YYYY-MM-DD format; it ends with 'Today' instead."))
        current_date = datetime.today()
        #current_date = datetime(2026,8,10)
        logger.info(f'Current Date: {current_date}')

        for i in range(7):
            new_date = (current_date + timedelta(days=i)).strftime("%Y-%m-%d")
            new_url = re.sub(
                r"(Today|YYYY-MM-DD|\d{4}-\d{2}-\d{2})(?=\.xml$)",
                new_date,
                url
            )
            urls.append(new_url)
            date.append(new_date)
        return num+1, urls, date

    elif url.endswith("YYYY-MM-DD.xml"):
        Validation_Output.append(helper_fuc(num, 'URL', 'Verify the date format in the URL', 'The URL should end with a date in YYYY-MM-DD format.', 'Passed', 'The URL ends with a date in the expected format.'))
        current_date = datetime.today()
        #current_date = datetime(2026, 8, 10)
        logger.info(f'Current Date: {current_date}')

        for i in range(7):
            new_date = (current_date + timedelta(days=i)).strftime("%Y-%m-%d")
            new_url = re.sub(
                r"(Today|YYYY-MM-DD|\d{4}-\d{2}-\d{2})(?=\.xml$)",
                new_date,
                url
            )
            urls.append(new_url)
            date.append(new_date)
        return num + 1, urls, date


    elif re.search(r"\d{4}-\d{2}-\d{2}\.xml$", url):
        Validation_Output.append(helper_fuc(num, 'URL', 'Verify the date format in the URL', 'The URL should end with a date in YYYY-MM-DD format.', 'Passed','The URL ends with a date in the expected format.'))
        current_date = datetime.today()
        #current_date = datetime(2026, 8, 10)
        logger.info(f'Current Date: {current_date}')

        for i in range(7):
            new_date = (current_date + timedelta(days=i)).strftime("%Y-%m-%d")
            new_url = re.sub(
                r"(Today|YYYY-MM-DD|\d{4}-\d{2}-\d{2})(?=\.xml$)",
                new_date,
                url
            )
            urls.append(new_url)
            date.append(new_date)
        return num + 1, urls, date


    else:
        Validation_Output.append(helper_fuc(num, 'URL', 'Verify the date format in the URL', 'The URL should end with a date in YYYY-MM-DD format.', 'Failed', "URL does not follow the expected date format (YYYY-MM-DD)"))
        return num + 1, urls, date
