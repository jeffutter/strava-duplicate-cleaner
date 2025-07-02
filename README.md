# Strava Duplicate Cleaner

A Python tool to find duplicate activities in your Strava account and provide URLs for manual deletion. Duplicates often occur when multiple devices (GPS watch, phone app, etc.) record the same workout.

## Features

- **Smart Duplicate Detection**: Uses time overlap, distance, and duration similarity to identify duplicates
- **DST Time Shift Handling**: Automatically detects duplicates even with ±1 hour time differences
- **Data Quality Analysis**: Recommends which activity to keep based on data completeness (heart rate, power, cadence, etc.)
- **Auto-deletion for Clear Winners**: Automatically marks obvious duplicates; only prompts when activities are very similar
- **Batch URL Output**: Provides a consolidated list of deletion URLs at the end
- **Flexible Date Ranges**: Search all activities or specify custom date ranges
- **OAuth Authentication**: Secure authentication with Strava API (read-only)

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create Strava API Application**
   - Go to https://www.strava.com/settings/api
   - Create a new application
   - Set Authorization Callback Domain to `localhost`

3. **Configure the Tool**
   ```bash
   cp config.json.template config.json
   ```
   Edit `config.json` and add your Client ID and Client Secret from Strava.

4. **Initial Authentication**
   ```bash
   python main.py --setup
   ```

## Usage

### Basic Usage
```bash
# Check last 30 days for duplicates
python main.py --last-days 30

# Check specific date range
python main.py --start-date 2024-01-01 --end-date 2024-12-31

# Show all URLs without prompts
python main.py --dry-run --last-days 7
```

### Advanced Options
```bash
# Custom overlap threshold (default: 80%)
python main.py --overlap-threshold 90 --last-days 30

# Enable debug logging to see detection details
python main.py --debug --last-days 30
```

## How It Works

### Duplicate Detection Algorithm
1. **Time-based clustering**: Groups activities by date
2. **Time shift handling**: Checks original time plus ±1 hour shifts to handle DST issues
3. **Overlap detection**: Checks if activities have overlapping time periods
4. **Similarity scoring**: Compares activity type, distance, and duration
5. **Quality analysis**: Scores activities based on data completeness

### Data Quality Scoring
Activities are scored based on:
- Heart rate data: +10 points
- Power data: +10 points  
- Cadence data: +5 points
- Temperature data: +3 points
- GPS accuracy: +5 points
- Device trust level: +0-5 points
- Social engagement: +2 points
- Manual activities: -10 points

### Duplicate Criteria
Two activities are considered duplicates if:
- Same activity type
- Start times within 10 minutes (or within 10 minutes after applying ±1 hour DST shift)
- Distance similarity within 5%
- Duration similarity within 5%
- Time overlap > 80%

## Safety Features

- **Manual deletion only**: Tool never deletes activities automatically
- **URL-based approach**: Provides direct links for manual deletion in browser
- **Dry-run mode** to show all URLs without prompts
- **Detailed comparison** showing data quality differences
- **Manual selection** to choose which activity to delete

## Example Output

```
=== Potential Duplicate Found ===
Activity 1: Morning Run          | Activity 2: Morning Run
Device: Garmin Forerunner 945    | Device: Strava iPhone App
Date: 2024-01-15 08:30:00        | Date: 2024-01-15 08:32:00
Duration: 45:23                  | Duration: 45:18
Distance: 10.2 km                | Distance: 10.1 km
Avg HR: 145 bpm ✓                | Avg HR: -- ✗
Power: -- ✗                      | Power: -- ✗
Cadence: 178 spm ✓               | Cadence: -- ✗
Data Score: 85/100               | Data Score: 45/100

Recommendation: Keep Activity 1 (more complete data)
✓ Auto-marked Morning Run (ID: 123456789) for deletion (clear winner)

==================================================
SUMMARY
==================================================
Total activities scanned: 150
Duplicate pairs found: 3
Activities marked for deletion: 3

📋 Activities to delete manually:
==================================================
 1. Morning Run (ID: 123456789)
    https://www.strava.com/activities/123456789
 2. Evening Ride (ID: 987654321)
    https://www.strava.com/activities/987654321

💡 Copy and paste these URLs into your browser to delete the activities.
```

## Configuration

The `config.json` file contains:
- Strava API credentials
- Duplicate detection thresholds
- OAuth settings

## Troubleshooting

### Authentication Issues
- Ensure your Strava app has the correct callback domain (`localhost`)
- Check that your Client ID and Client Secret are correct
- Try running `python main.py --setup` again

### Rate Limiting
The tool automatically handles Strava's API rate limits with exponential backoff.

### No Duplicates Found
- Try lowering the overlap threshold: `--overlap-threshold 70`
- Check a longer time period: `--last-days 90`
- Verify activities were actually recorded by multiple devices

## Security

- API credentials are stored in `config.json` (keep this file secure)
- Access tokens are stored securely using the system keyring
- All API calls use HTTPS
- No activity data is stored permanently

## Limitations

- Manual deletion required (deletion URLs provided)
- Requires manual review of each duplicate pair
- Limited to activities accessible via Strava API
- Subject to Strava API rate limits (100 requests per 15 minutes, 1000 per day)