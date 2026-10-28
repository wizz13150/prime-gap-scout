"""One canonical display-row setting, independent of report/export limits."""
import argparse
DEFAULT_DISPLAY_ROWS=10
MIN_DISPLAY_ROWS=10
MAX_DISPLAY_ROWS=30
def display_rows(value):
    text=str(value).strip()
    if isinstance(value,bool) or not text.isdecimal():
        raise ValueError('--display-rows requires an integer from10 through30')
    rows=int(text)
    if not MIN_DISPLAY_ROWS<=rows<=MAX_DISPLAY_ROWS:
        raise ValueError('--display-rows must be from10 through30')
    return rows
