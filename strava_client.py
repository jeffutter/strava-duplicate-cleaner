import requests
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass
from dateutil import parser


@dataclass
class Activity:
    id: int
    name: str
    start_date: datetime
    elapsed_time: int
    distance: float
    type: str
    device_name: str
    has_heartrate: bool
    has_power: bool
    has_cadence: bool
    has_temperature: bool
    has_map: bool  # GPS/map data availability
    average_heartrate: Optional[float]
    average_power: Optional[float]
    average_cadence: Optional[float]
    average_speed: float
    total_elevation_gain: float
    kudos_count: int
    comment_count: int
    manual: bool = False


class StravaClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://www.strava.com/api/v3"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        })
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        backoff_factor = 1
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                
                if response.status_code == 429:
                    rate_limit_reset = response.headers.get('X-RateLimit-Reset')
                    if rate_limit_reset:
                        reset_time = int(rate_limit_reset)
                        current_time = int(time.time())
                        sleep_time = max(reset_time - current_time, 1)
                        print(f"Rate limit exceeded. Waiting {sleep_time} seconds...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"Request failed after {max_retries} attempts: {e}")
                    return None
                time.sleep(backoff_factor * (2 ** attempt))
        
        return None
    
    def get_activities(self, start_date: datetime = None, end_date: datetime = None, per_page: int = 30) -> List[Activity]:
        activities = []
        page = 1
        
        params = {
            'per_page': per_page,
            'page': page
        }
        
        if start_date:
            params['after'] = int(start_date.timestamp())
        if end_date:
            params['before'] = int(end_date.timestamp())
        
        while True:
            params['page'] = page
            data = self._make_request('GET', '/athlete/activities', params=params)
            
            if not data or len(data) == 0:
                break
            
            for activity_data in data:
                try:
                    activity = self._parse_activity(activity_data)
                    activities.append(activity)
                except Exception as e:
                    print(f"Failed to parse activity {activity_data.get('id', 'unknown')}: {e}")
                    continue
            
            if len(data) < per_page:
                break
                
            page += 1
            time.sleep(0.1)
        
        return activities
    
    def get_activity_details(self, activity_id: int) -> Optional[Activity]:
        data = self._make_request('GET', f'/activities/{activity_id}')
        if data:
            try:
                return self._parse_detailed_activity(data)
            except Exception as e:
                print(f"Failed to parse detailed activity {activity_id}: {e}")
        return None
    
    def get_activity_url(self, activity_id: int) -> str:
        return f"https://www.strava.com/activities/{activity_id}"
    
    def _parse_activity(self, data: Dict) -> Activity:
        start_date = parser.isoparse(data['start_date_local'])
        
        # Determine if activity has map data - Strava activities typically have GPS unless manual
        has_map = not data.get('manual', False) and data.get('start_latlng') is not None
        
        return Activity(
            id=data['id'],
            name=data['name'],
            start_date=start_date,
            elapsed_time=data.get('elapsed_time', 0),
            distance=data.get('distance', 0.0),
            type=data.get('type', 'Unknown'),
            device_name=data.get('device_name', 'Unknown'),
            has_heartrate=data.get('has_heartrate', False),
            has_power=data.get('device_watts', False),
            has_cadence=data.get('has_cadence', False),
            has_temperature=False,
            has_map=has_map,
            average_heartrate=data.get('average_heartrate'),
            average_power=data.get('average_watts'),
            average_cadence=data.get('average_cadence'),
            average_speed=data.get('average_speed', 0.0),
            total_elevation_gain=data.get('total_elevation_gain', 0.0),
            kudos_count=data.get('kudos_count', 0),
            comment_count=data.get('comment_count', 0),
            manual=data.get('manual', False)
        )
    
    def _parse_detailed_activity(self, data: Dict) -> Activity:
        start_date = parser.isoparse(data['start_date_local'])
        
        # Determine if activity has map data - check for GPS coordinates or polyline
        has_map = (not data.get('manual', False) and 
                   (data.get('start_latlng') is not None or 
                    data.get('map', {}).get('polyline') is not None))
        
        return Activity(
            id=data['id'],
            name=data['name'],
            start_date=start_date,
            elapsed_time=data.get('elapsed_time', 0),
            distance=data.get('distance', 0.0),
            type=data.get('type', 'Unknown'),
            device_name=data.get('device_name', 'Unknown'),
            has_heartrate=data.get('has_heartrate', False),
            has_power=data.get('device_watts', False),
            has_cadence=data.get('has_cadence', False),
            has_temperature=bool(data.get('average_temp')),
            has_map=has_map,
            average_heartrate=data.get('average_heartrate'),
            average_power=data.get('average_watts'),
            average_cadence=data.get('average_cadence'),
            average_speed=data.get('average_speed', 0.0),
            total_elevation_gain=data.get('total_elevation_gain', 0.0),
            kudos_count=data.get('kudos_count', 0),
            comment_count=data.get('comment_count', 0),
            manual=data.get('manual', False)
        )