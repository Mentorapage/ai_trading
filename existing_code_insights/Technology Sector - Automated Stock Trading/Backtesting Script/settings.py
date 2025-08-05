# Settings for backtesting configuration

# Base date for backtesting (format: YYYY-MM-DD)
base_date = "2024-12-01"  # Change this to desired backtesting date

# Timestamps for trading window (13:29:00 EST for buying, 20:00:00 EST for end of day)
timestamp_13 = "2024-12-01T13:29:00-05:00"  # Buying time
timestamp_20 = "2024-12-01T20:00:00-05:00"  # End of day selling time

# Note: Update these timestamps when changing base_date
# Format must match: YYYY-MM-DDTHH:MM:SS-05:00 (EST timezone) 