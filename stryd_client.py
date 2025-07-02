import requests
import time
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from dateutil import parser
from strava_client import Activity


class StrydClient:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.base_url = "https://www.stryd.com/b"
        self.api_base = "https://api.stryd.com/b/api/v1"
        self.session = requests.Session()
        self.token = None
        self.user_id = None
        self.logger = logging.getLogger(__name__)

    def authenticate(self) -> bool:
        """Authenticate with Stryd and get access token"""
        auth_url = f"{self.base_url}/email/signin"
        auth_data = {
            "email": self.email,
            "password": self.password
        }

        try:
            # Debug log the curl command
            self._debug_curl_command('POST', auth_url, data=auth_data)

            response = self.session.post(auth_url, json=auth_data)
            response.raise_for_status()

            auth_response = response.json()
            self.token = auth_response.get('token')
            self.user_id = auth_response.get('id')

            if self.token:
                # Set authorization header for subsequent requests - note the space after "Bearer:"
                self.session.headers.update({
                    'Authorization': f'Bearer: {self.token}',
                    'Content-Type': 'application/json'
                })
                self.logger.debug("Stryd authentication successful")
                return True
            else:
                self.logger.error("Authentication response missing token")
                return False

        except requests.exceptions.RequestException as e:
            self._handle_request_error(e, 'POST', auth_url, data=auth_data)
            return False

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """Make authenticated request to Stryd API"""
        if not self.token:
            if not self.authenticate():
                return None

        url = f"{self.api_base}{endpoint}"
        max_retries = 3
        backoff_factor = 1

        for attempt in range(max_retries):
            try:
                # Debug log the curl command
                self._debug_curl_command(method, url, **kwargs)

                response = self.session.request(method, url, **kwargs)

                if response.status_code == 401:
                    # Token might have expired, try to re-authenticate
                    if self.authenticate():
                        response = self.session.request(method, url, **kwargs)
                    else:
                        return None

                if response.status_code == 429:
                    # Rate limiting - wait and retry
                    time.sleep(backoff_factor * (2 ** attempt))
                    continue

                if response.status_code == 430:
                    # Specific handling for 430 errors (likely routing/endpoint issues)
                    error_msg = f"Stryd API endpoint error (430): {method} {url}"
                    try:
                        error_body = response.text
                        if error_body:
                            error_msg += f" - Response: {error_body}"
                    except:
                        pass
                    self.logger.debug(f"{error_msg} - This suggests the endpoint path may be incorrect")
                    return None

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                self._handle_request_error(e, method, url, **kwargs)
                if attempt == max_retries - 1:
                    return None
                # Don't retry on 430 errors as they're likely endpoint issues
                if hasattr(e, 'response') and e.response and e.response.status_code == 430:
                    return None
                time.sleep(backoff_factor * (2 ** attempt))

        return None

    def get_activities(self, start_date: datetime = None, end_date: datetime = None) -> List[Activity]:
        """Get activities from Stryd calendar API"""
        activities = []

        # Convert dates to Unix timestamps as required by the real Stryd API
        if start_date:
            start_timestamp = int(start_date.timestamp())
        else:
            # Default to last 30 days if no start date provided
            start_timestamp = int((datetime.now() - timedelta(days=30)).timestamp())

        if end_date:
            end_timestamp = int(end_date.timestamp())
        else:
            end_timestamp = int(datetime.now().timestamp())

        # Use the correct parameters from Firefox inspector
        params = {
            'from': start_timestamp,
            'to': end_timestamp,
            'include_deleted': 'false'
        }

        # Use the correct endpoint structure from Firefox inspector
        if not self.user_id:
            self.logger.error("User ID not available for calendar endpoint")
            return activities

        endpoint = f'/users/{self.user_id}/calendar'
        self.logger.debug(f"Requesting Stryd calendar from {start_timestamp} to {end_timestamp}")
        data = self._make_request('GET', endpoint, params=params)

        if data is None:
            self.logger.error("Failed to fetch Stryd activities from calendar endpoint")
            print("❌ Unable to fetch Stryd activities from calendar endpoint.")
            print("   This may indicate:")
            print("   1. Authentication issues")
            print("   2. Invalid date range")
            print("   3. API permissions")
            print("   4. No activities in date range")
            return activities

        if not data:
            self.logger.error("No data returned from successful endpoint")
            return activities

        # Debug log the structure of the returned data
        self.logger.debug(f"Stryd API returned data with keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

        # The calendar endpoint might return a different structure - let's inspect it
        activities_data = None
        if isinstance(data, dict):
            # Try different possible keys for activities data
            for possible_key in ['activities', 'runs', 'workouts', 'data', 'calendar', 'items']:
                if possible_key in data:
                    activities_data = data[possible_key]
                    self.logger.debug(f"Found activities in key: {possible_key}")
                    break

            # If no direct key, look for arrays in the response
            if activities_data is None:
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 0:
                        activities_data = value
                        self.logger.debug(f"Using list from key: {key}")
                        break

        elif isinstance(data, list):
            activities_data = data
            self.logger.debug("Response is a direct list")

        if activities_data is None:
            self.logger.warning(f"Could not find activities in response structure: {data}")
            return activities

        if not activities_data:
            self.logger.info(f"No activities found in date range {start_timestamp} to {end_timestamp}")
            return activities

        self.logger.debug(f"Found {len(activities_data)} activities in Stryd response")

        for activity_data in activities_data:
            try:
                activity = self._parse_activity(activity_data)
                activities.append(activity)
            except Exception as e:
                print(f"Failed to parse Stryd activity {activity_data.get('id', 'unknown')}: {e}")
                self.logger.debug(f"Activity data that failed to parse: {activity_data}")
                continue

        return activities

    def get_activity_details(self, activity_id: str) -> Optional[Activity]:
        """Get detailed activity information"""
        data = self._make_request('GET', f'/activities/{activity_id}')
        if data:
            try:
                return self._parse_detailed_activity(data)
            except Exception as e:
                print(f"Failed to parse detailed Stryd activity {activity_id}: {e}")
        return None

    def get_activity_url(self, activity_id: str) -> str:
        """Get URL for manual activity viewing/deletion in PowerCenter"""
        if not self.user_id:
            # Fallback if user_id is not available
            return f"https://www.stryd.com/powercenter/calendar/entries/activities/{activity_id}"

        return f"https://www.stryd.com/powercenter/athletes/{self.user_id}/calendar/entries/activities/{activity_id}"

    def _parse_activity(self, data: Dict) -> Activity:
        """Parse Stryd activity data into StrydActivity object"""
        # Convert timestamp to datetime
        if 'timestamp' in data:
            start_date = datetime.fromtimestamp(data['timestamp'], tz=timezone.utc)
        else:
            # Fallback to parsing date string if available
            start_date = datetime.now(tz=timezone.utc)

        # Extract activity name/title
        name = data.get('name', data.get('title', f"Run {data.get('id', 'Unknown')}"))

        # Convert distance from meters to meters (keep consistent with Strava)
        distance = data.get('distance', 0.0)

        # Duration in seconds - try multiple possible fields
        elapsed_time = (data.get('total_timer_time') or
                       data.get('duration') or
                       data.get('elapsed_time') or
                       data.get('moving_time') or
                       data.get('timer_time') or 0)

        # If elapsed_time is still 0, try to calculate from distance and speed
        if elapsed_time == 0 and distance > 0:
            avg_speed = data.get('average_speed', data.get('avg_speed', 0))
            if avg_speed > 0:
                elapsed_time = int(distance / avg_speed)  # Calculate time from distance/speed
                self.logger.debug(f"Calculated elapsed_time {elapsed_time}s from distance {distance}m and speed {avg_speed}m/s")

        # Determine if activity has map data
        map_data = data.get('map')
        has_valid_map = False
        if map_data and isinstance(map_data, dict):
            map_id = map_data.get('id', '')
            summary_polyline = map_data.get('summary_polyline', '')
            polyline = map_data.get('polyline', '')
            has_valid_map = bool((map_id and map_id.strip()) or
                               (summary_polyline and summary_polyline.strip()) or
                                (polyline and polyline.strip()))

        has_map = bool(data.get('has_gps', False) or has_valid_map or data.get('polyline'))

        # Convert ID to int, handling string IDs from Stryd
        activity_id = data.get('id', data.get('activity_id', 0))
        if isinstance(activity_id, str):
            try:
                activity_id = int(activity_id) if activity_id.isdigit() else hash(activity_id) % (10**9)
            except:
                activity_id = hash(activity_id) % (10**9)  # Fallback to hash for non-numeric IDs

        return Activity(
            id=activity_id,
            name=name,
            start_date=start_date,
            elapsed_time=elapsed_time,
            distance=distance,
            type=data.get('sport', data.get('activity_type', 'Run')),
            device_name=data.get('device_name', 'Stryd Pod'),
            has_heartrate=bool(data.get('average_heart_rate', data.get('has_heartrate', False))),
            has_power=bool(data.get('average_power', data.get('has_power', True))),  # Stryd always has power
            has_cadence=bool(data.get('average_cadence', data.get('has_cadence', True))),  # Stryd always has cadence
            has_temperature=bool(data.get('average_temp', data.get('has_temperature', False))),
            has_map=has_map,
            average_heartrate=data.get('average_heart_rate', data.get('average_heartrate')),
            average_power=data.get('average_power', data.get('ftp')),
            average_cadence=data.get('average_cadence'),
            average_speed=data.get('average_speed', 0.0),
            total_elevation_gain=data.get('total_elevation_gain', 0.0),
            kudos_count=0,  # Not available in Stryd
            comment_count=0,  # Not available in Stryd
            manual=False  # Stryd activities are typically not manual
        )

    def _parse_detailed_activity(self, data: Dict) -> Activity:
        """Parse detailed Stryd activity data"""
        # Similar to _parse_activity but with potentially more detailed fields
        return self._parse_activity(data)

    def _debug_curl_command(self, method: str, url: str, data=None, params=None, **kwargs):
        """Generate and log curl command equivalent for debugging"""
        if not self.logger.isEnabledFor(logging.DEBUG):
            return

        curl_parts = ['curl', '-X', method.upper()]

        # Add headers
        headers = self.session.headers.copy()
        if 'json' in kwargs and kwargs['json']:
            headers['Content-Type'] = 'application/json'

        for key, value in headers.items():
            curl_parts.extend(['-H', f"'{key}: {value}'"])

        # Add data/body
        if 'json' in kwargs and kwargs['json']:
            curl_parts.extend(['-d', f"'{json.dumps(kwargs['json'])}'"])
        elif data:
            curl_parts.extend(['-d', f"'{json.dumps(data) if isinstance(data, dict) else data}'"])

        # Add query parameters
        if params:
            url_with_params = url + '?' + '&'.join([f'{k}={v}' for k, v in params.items()])
        elif 'params' in kwargs and kwargs['params']:
            url_with_params = url + '?' + '&'.join([f'{k}={v}' for k, v in kwargs['params'].items()])
        else:
            url_with_params = url

        curl_parts.append(f"'{url_with_params}'")

        curl_command = ' '.join(curl_parts)
        self.logger.debug(f"Stryd API Request (curl format): {curl_command}")

    def _handle_request_error(self, error: Exception, method: str, url: str, **kwargs):
        """Handle and log request errors with detailed information"""
        error_msg = f"Stryd API request failed: {method} {url}"

        if hasattr(error, 'response') and error.response is not None:
            status_code = error.response.status_code
            error_msg += f" - Status: {status_code}"

            try:
                error_body = error.response.text
                if error_body:
                    error_msg += f" - Response: {error_body}"
            except:
                pass

        error_msg += f" - Error: {str(error)}"

        # Print error message for user visibility
        print(f"❌ {error_msg}")

        # Debug log the curl command for this failed request
        self._debug_curl_command(method, url, **kwargs)
