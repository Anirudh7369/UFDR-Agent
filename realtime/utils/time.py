from datetime import datetime

def is_valid_timestamp(date_string):
    try:
        datetime.strptime(str(date_string), "%Y-%m-%dT%H:%M:%SZ")
        return True
    except ValueError:
        return False