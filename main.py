#!/usr/bin/env python3

import json
import argparse
import logging
import sys
from datetime import datetime, timedelta
from typing import List, Optional

from auth import StravaAuth
from strava_client import StravaClient
from stryd_client import StrydClient
from duplicate_detector import DuplicateDetector
from ui import UserInterface


def setup_logging(debug=False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def initialize_strava_client(config: dict, setup_mode: bool, ui) -> Optional[StravaClient]:
    """Initialize Strava client with OAuth authentication"""
    auth = StravaAuth(
        client_id=config['client_id'],
        client_secret=config['client_secret'],
        redirect_uri=config['redirect_uri']
    )
    
    if setup_mode:
        ui.display_authentication_needed()
        tokens = auth.authenticate(config['scope'])
        if tokens:
            ui.display_success("Authentication successful! You can now run the duplicate cleaner.")
        else:
            ui.display_error("Authentication failed.")
        return None
    
    access_token = auth.get_valid_access_token()
    if not access_token:
        ui.display_authentication_needed()
        tokens = auth.authenticate(config['scope'])
        if tokens:
            access_token = tokens['access_token']
        else:
            ui.display_error("Authentication failed.")
            return None
    
    return StravaClient(access_token)


def initialize_stryd_client(config: dict, setup_mode: bool, ui) -> Optional[StrydClient]:
    """Initialize Stryd client with email/password authentication"""
    if 'stryd' not in config:
        ui.display_error("Stryd configuration not found in config file. Please add stryd section with email and password.")
        return None
    
    stryd_config = config['stryd']
    email = stryd_config.get('email')
    password = stryd_config.get('password')
    
    if not email or not password:
        ui.display_error("Stryd email and password required in config file.")
        return None
    
    client = StrydClient(email, password)
    
    if setup_mode:
        ui.display_authentication_needed()
        if client.authenticate():
            ui.display_success("Stryd authentication successful! You can now run the duplicate cleaner.")
        else:
            ui.display_error("Stryd authentication failed.")
        return None
    
    if not client.authenticate():
        ui.display_error("Stryd authentication failed.")
        return None
    
    return client


def load_config(config_path: str = "config.json") -> dict:
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Config file '{config_path}' not found.")
        print("Please copy config.json.template to config.json and fill in your Strava API credentials.")
        print("\nTo get API credentials:")
        print("1. Go to https://www.strava.com/settings/api")
        print("2. Create a new application")
        print("3. Copy Client ID and Client Secret to config.json")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in config file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Find and remove duplicate activities from Strava or Stryd",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --setup                          # First-time authentication setup
  %(prog)s --last-days 30                   # Check last 30 days (Strava)
  %(prog)s --api stryd --last-days 30       # Check last 30 days (Stryd)
  %(prog)s --start-date 2024-01-01 --end-date 2024-12-31  # Date range
  %(prog)s --dry-run --last-days 7          # Show URLs only (no prompts)
  %(prog)s --overlap-threshold 90           # Custom overlap threshold
  %(prog)s --debug --last-days 7            # Enable debug logging
        """
    )
    
    parser.add_argument('--setup', action='store_true', 
                       help='Run initial authentication setup')
    parser.add_argument('--start-date', type=str,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--last-days', type=int,
                       help='Check activities from the last N days')
    parser.add_argument('--dry-run', action='store_true',
                       help='Find duplicates but do not prompt for action (show URLs only)')
    parser.add_argument('--overlap-threshold', type=float, default=80,
                       help='Minimum overlap percentage to consider duplicates (default: 80)')
    parser.add_argument('--config', type=str, default='config.json',
                       help='Path to config file (default: config.json)')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    parser.add_argument('--api', type=str, choices=['strava', 'stryd'], default='strava',
                       help='API to use: strava or stryd (default: strava)')
    
    args = parser.parse_args()
    
    setup_logging(args.debug)
    
    ui = UserInterface()
    ui.display_welcome()
    
    config = load_config(args.config)
    
    config['duplicate_threshold']['minimum_overlap_percent'] = args.overlap_threshold
    
    # Initialize client based on selected API
    if args.api == 'strava':
        client = initialize_strava_client(config, args.setup, ui)
    elif args.api == 'stryd':
        client = initialize_stryd_client(config, args.setup, ui)
    else:
        ui.display_error(f"Unsupported API: {args.api}")
        return
    
    if not client:
        ui.display_error("Failed to initialize API client")
        return
    detector = DuplicateDetector(config['duplicate_threshold'])
    
    start_date = None
    end_date = None
    
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            ui.display_error("Invalid start date format. Use YYYY-MM-DD")
            return
    
    if args.end_date:
        try:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
            end_date = end_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            ui.display_error("Invalid end date format. Use YYYY-MM-DD")
            return
    
    if args.last_days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.last_days)
    
    if not (args.start_date or args.end_date or args.last_days):
        if args.dry_run:
            last_days = ui.get_last_days()
            if last_days:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=last_days)
        else:
            start_date, end_date = ui.get_date_range()
    
    print(f"\n🔍 Fetching activities...")
    if start_date:
        print(f"   From: {start_date.strftime('%Y-%m-%d')}")
    if end_date:
        print(f"   To: {end_date.strftime('%Y-%m-%d')}")
    
    try:
        activities = client.get_activities(start_date, end_date)
    except Exception as e:
        ui.display_error(f"Failed to fetch activities: {e}")
        return
    
    if not activities:
        print("No activities found in the specified date range.")
        return
    
    print(f"✅ Found {len(activities)} activities")
    
    print("🔍 Detecting duplicates...")
    duplicate_pairs = detector.find_overlapping_activities(activities)
    
    if not duplicate_pairs:
        print("🎉 No duplicate activities found!")
        return
    
    print(f"⚠️  Found {len(duplicate_pairs)} potential duplicate pairs")
    
    deletion_list = []
    
    if args.dry_run:
        print("\n📋 DRY RUN - Showing all duplicate URLs")
        for i, pair in enumerate(duplicate_pairs, 1):
            ui.display_duplicate_pair(pair, i, len(duplicate_pairs))
            deletion_list.append((pair.recommended_delete, client.get_activity_url(pair.recommended_delete.id)))
        
        ui.display_summary(len(activities), len(duplicate_pairs), len(duplicate_pairs), deletion_list)
        return

    for i, pair in enumerate(duplicate_pairs, 1):
        ui.display_duplicate_pair(pair, i, len(duplicate_pairs))
        
        if pair.is_very_similar:
            choice = ui.prompt_for_action(pair)
            
            if choice == 'q':
                print("\nQuitting...")
                break
            elif choice == 's':
                print("Skipping this pair...")
                continue
            elif choice in ['1', '2']:
                if choice == '1':
                    activity_to_mark = pair.recommended_delete
                else:
                    activity_to_mark = pair.recommended_keep
                
                deletion_list.append((activity_to_mark, client.get_activity_url(activity_to_mark.id)))
                print(f"✓ Marked {activity_to_mark.name} (ID: {activity_to_mark.id}) for deletion")
        else:
            # Auto-mark the recommended activity for deletion
            deletion_list.append((pair.recommended_delete, client.get_activity_url(pair.recommended_delete.id)))
            print(f"✓ Auto-marked {pair.recommended_delete.name} (ID: {pair.recommended_delete.id}) for deletion (clear winner)")
    
    ui.display_summary(len(activities), len(duplicate_pairs), len(deletion_list), deletion_list)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)