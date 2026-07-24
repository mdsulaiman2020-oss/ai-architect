from datetime import datetime

def get_current_time_and_zone() -> dict:
    """
    Get the current local time and timezone information.

    Returns:
        dict: A dictionary containing:
            - 'iso': The ISO-8601 formatted datetime string.
            - 'formatted': A human-readable string in 'YYYY-MM-DD HH:MM:SS' format.
            - 'timezone': The timezone name/abbreviation (e.g., 'UTC', 'IST').
            - 'utc_offset': The UTC offset (e.g., '+0000', '+0530').
    """
    now = datetime.now().astimezone()
    return {
        "iso": now.isoformat(),
        "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": now.tzname(),
        "utc_offset": now.strftime("%z")
    }
