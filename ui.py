from datetime import datetime, timedelta
from typing import Optional, Tuple
from strava_client import Activity
from duplicate_detector import DuplicatePair
from data_analyzer import DataQualityAnalyzer


class UserInterface:
    def __init__(self):
        self.analyzer = DataQualityAnalyzer()
    
    def display_duplicate_pair(self, duplicate_pair: DuplicatePair, pair_number: int, total_pairs: int):
        print(f"\n{'='*60}")
        print(f"Potential Duplicate {pair_number}/{total_pairs}")
        print(f"{'='*60}")
        
        activity1 = duplicate_pair.activity1
        activity2 = duplicate_pair.activity2
        
        summary1 = self.analyzer.get_data_completeness_summary(activity1)
        summary2 = self.analyzer.get_data_completeness_summary(activity2)
        
        print(f"Activity 1: {activity1.name:<25} | Activity 2: {activity2.name}")
        print(f"ID: {activity1.id:<33} | ID: {activity2.id}")
        print(f"Device: {activity1.device_name:<25} | Device: {activity2.device_name}")
        print(f"Date: {activity1.start_date.strftime('%Y-%m-%d %H:%M:%S'):<25} | Date: {activity2.start_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {self._format_duration(activity1.elapsed_time):<25} | Duration: {self._format_duration(activity2.elapsed_time)}")
        print(f"Distance: {activity1.distance/1000:.2f} km{'':<15} | Distance: {activity2.distance/1000:.2f} km")
        
        hr1_text = f"{activity1.average_heartrate:.0f} bpm ✓" if activity1.average_heartrate else "-- ✗"
        hr2_text = f"{activity2.average_heartrate:.0f} bpm ✓" if activity2.average_heartrate else "-- ✗"
        print(f"Avg HR: {hr1_text:<25} | Avg HR: {hr2_text}")
        
        power1_text = f"{activity1.average_power:.0f}W ✓" if activity1.average_power else "-- ✗"
        power2_text = f"{activity2.average_power:.0f}W ✓" if activity2.average_power else "-- ✗"
        print(f"Power: {power1_text:<25} | Power: {power2_text}")
        
        cadence1_text = f"{activity1.average_cadence:.0f} spm ✓" if activity1.average_cadence else "-- ✗"
        cadence2_text = f"{activity2.average_cadence:.0f} spm ✓" if activity2.average_cadence else "-- ✗"
        print(f"Cadence: {cadence1_text:<25} | Cadence: {cadence2_text}")
        
        gps1_text = "GPS ✓" if activity1.has_map else "GPS ✗"
        gps2_text = "GPS ✓" if activity2.has_map else "GPS ✗"
        print(f"Map/GPS: {gps1_text:<25} | Map/GPS: {gps2_text}")
        
        print(f"Data Score: {summary1['score']}/100{'':<15} | Data Score: {summary2['score']}/100")
        print(f"Social: {activity1.kudos_count + activity1.comment_count} interactions{'':<12} | Social: {activity2.kudos_count + activity2.comment_count} interactions")
        
        print(f"\nOverlap: {duplicate_pair.overlap_percentage:.1f}%")
        print(f"Time Difference: {self._format_time_difference(duplicate_pair.time_difference)}")
        print(f"Recommendation: Keep Activity {'1' if duplicate_pair.recommended_keep.id == activity1.id else '2'}")
        print(f"Reason: {duplicate_pair.reason}")
    
    def prompt_for_action(self, duplicate_pair: DuplicatePair) -> str:
        while True:
            print(f"\nWhat would you like to do?")
            print(f"[1] Mark Activity {duplicate_pair.recommended_delete.id} for deletion (recommended)")
            print(f"[2] Mark Activity {duplicate_pair.recommended_keep.id} for deletion")
            print(f"[s] Skip this pair")
            print(f"[q] Quit")
            
            choice = input("Choice [1/2/s/q]: ").strip().lower()
            
            if choice in ['1', '2', 's', 'q']:
                return choice
            else:
                print("Invalid choice. Please enter 1, 2, s, or q.")
    
    def display_progress(self, current: int, total: int, action: str = "Processing"):
        percentage = (current / total) * 100 if total > 0 else 0
        print(f"\r{action}: {current}/{total} ({percentage:.1f}%)", end='', flush=True)
        if current == total:
            print()
    
    def get_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        print("Enter date range for duplicate detection:")
        print("Leave blank to search all activities")
        
        start_date = None
        end_date = None
        
        start_input = input("Start date (YYYY-MM-DD) [Enter for no limit]: ").strip()
        if start_input:
            try:
                start_date = datetime.strptime(start_input, '%Y-%m-%d')
            except ValueError:
                print("Invalid date format. Using no start date limit.")
        
        end_input = input("End date (YYYY-MM-DD) [Enter for no limit]: ").strip()
        if end_input:
            try:
                end_date = datetime.strptime(end_input, '%Y-%m-%d')
                end_date = end_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                print("Invalid date format. Using no end date limit.")
        
        return start_date, end_date
    
    def get_last_days(self) -> Optional[int]:
        while True:
            days_input = input("Enter number of days to search (or 'all' for all activities): ").strip().lower()
            
            if days_input == 'all':
                return None
            
            try:
                days = int(days_input)
                if days > 0:
                    return days
                else:
                    print("Please enter a positive number.")
            except ValueError:
                print("Please enter a valid number or 'all'.")
    
    def display_summary(self, total_activities: int, total_duplicates: int, marked_for_deletion: int, deletion_urls: list = None):
        print(f"\n{'='*50}")
        print(f"SUMMARY")
        print(f"{'='*50}")
        print(f"Total activities scanned: {total_activities}")
        print(f"Duplicate pairs found: {total_duplicates}")
        print(f"Activities marked for deletion: {marked_for_deletion}")
        
        if deletion_urls and len(deletion_urls) > 0:
            print(f"\n📋 Activities to delete manually:")
            print(f"{'='*50}")
            for i, (activity, url) in enumerate(deletion_urls, 1):
                print(f"{i:2d}. {activity.name} (ID: {activity.id})")
                print(f"    {url}")
            print(f"\n💡 Copy and paste these URLs into your browser to delete the activities.")
        elif marked_for_deletion > 0:
            print(f"\n📋 Activities marked for deletion shown above.")
    
    def display_deletion_url(self, activity: Activity):
        url = f"https://www.strava.com/activities/{activity.id}"
        print(f"\n🔗 Delete: {url}")
        print(f"   Activity: {activity.name} (ID: {activity.id})")
    
    def display_welcome(self):
        print("🚴 Strava Duplicate Cleaner")
        print("=" * 40)
        print("This tool will help you find duplicate activities in your Strava account.")
        print("It will provide URLs for manual deletion of duplicate activities.")
        print("Duplicates often occur when multiple devices record the same workout.")
        print()
    
    def display_authentication_needed(self):
        print("🔐 Authentication required")
        print("You need to authenticate with Strava to access your activities.")
        print("A browser window will open for authorization.")
        print()
    
    def display_error(self, message: str):
        print(f"❌ Error: {message}")
    
    def display_success(self, message: str):
        print(f"✅ {message}")
    
    def display_warning(self, message: str):
        print(f"⚠️  {message}")
    
    def _format_duration(self, seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def _format_time_difference(self, td: timedelta) -> str:
        total_seconds = int(td.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"