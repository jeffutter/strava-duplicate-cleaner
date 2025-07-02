from typing import List, Dict, Tuple
from strava_client import Activity


class DataQualityAnalyzer:
    def calculate_data_completeness_score(self, activity: Activity) -> int:
        score = 0
        
        if activity.has_heartrate and activity.average_heartrate:
            score += 10
        if activity.has_power and activity.average_power:
            score += 10
        if activity.has_cadence and activity.average_cadence:
            score += 5
        if activity.has_temperature:
            score += 3
        if activity.has_map:
            score += 8
        
        if activity.distance > 0:
            score += 5
        
        device_trust_scores = {
            'garmin': 5,
            'wahoo': 5,
            'polar': 5,
            'suunto': 5,
            'fitbit': 4,
            'coros': 4,
            'apple watch': 3,
            'iphone': 2,
            'android': 2,
            'strava': 1,
            'unknown': 0
        }
        
        device_name_lower = activity.device_name.lower()
        device_score = 0
        for device, trust_score in device_trust_scores.items():
            if device in device_name_lower:
                device_score = trust_score
                break
        score += device_score
        
        if activity.kudos_count > 0 or activity.comment_count > 0:
            score += 2
        
        if activity.manual:
            score -= 10
        
        return max(0, score)
    
    def compare_activity_quality(self, activity1: Activity, activity2: Activity) -> Dict:
        score1 = self.calculate_data_completeness_score(activity1)
        score2 = self.calculate_data_completeness_score(activity2)
        
        comparison = {
            'activity1_score': score1,
            'activity2_score': score2,
            'winner': None,
            'score_difference': abs(score1 - score2),
            'details': self._get_comparison_details(activity1, activity2)
        }
        
        if score1 > score2:
            comparison['winner'] = 'activity1'
        elif score2 > score1:
            comparison['winner'] = 'activity2'
        else:
            comparison['winner'] = 'tie'
        
        return comparison
    
    def _get_comparison_details(self, activity1: Activity, activity2: Activity) -> Dict:
        return {
            'heartrate': {
                'activity1': activity1.has_heartrate and activity1.average_heartrate is not None,
                'activity2': activity2.has_heartrate and activity2.average_heartrate is not None
            },
            'power': {
                'activity1': activity1.has_power and activity1.average_power is not None,
                'activity2': activity2.has_power and activity2.average_power is not None
            },
            'cadence': {
                'activity1': activity1.has_cadence and activity1.average_cadence is not None,
                'activity2': activity2.has_cadence and activity2.average_cadence is not None
            },
            'temperature': {
                'activity1': activity1.has_temperature,
                'activity2': activity2.has_temperature
            },
            'device_trust': {
                'activity1': self._get_device_trust_level(activity1.device_name),
                'activity2': self._get_device_trust_level(activity2.device_name)
            },
            'social_engagement': {
                'activity1': activity1.kudos_count + activity1.comment_count,
                'activity2': activity2.kudos_count + activity2.comment_count
            },
            'manual': {
                'activity1': activity1.manual,
                'activity2': activity2.manual
            }
        }
    
    def _get_device_trust_level(self, device_name: str) -> str:
        device_name_lower = device_name.lower()
        
        if any(device in device_name_lower for device in ['garmin', 'wahoo', 'polar', 'suunto']):
            return 'high'
        elif any(device in device_name_lower for device in ['fitbit', 'coros']):
            return 'medium-high'
        elif 'apple watch' in device_name_lower:
            return 'medium'
        elif any(device in device_name_lower for device in ['iphone', 'android']):
            return 'low'
        elif 'strava' in device_name_lower:
            return 'very-low'
        else:
            return 'unknown'
    
    def get_available_data_types(self, activity: Activity) -> List[str]:
        data_types = []
        
        if activity.has_heartrate and activity.average_heartrate:
            data_types.append('heartrate')
        if activity.has_power and activity.average_power:
            data_types.append('power')
        if activity.has_cadence and activity.average_cadence:
            data_types.append('cadence')
        if activity.has_temperature:
            data_types.append('temperature')
        if activity.distance > 0:
            data_types.append('gps')
        if activity.total_elevation_gain > 0:
            data_types.append('elevation')
        
        return data_types
    
    def get_data_completeness_summary(self, activity: Activity) -> Dict:
        data_types = self.get_available_data_types(activity)
        score = self.calculate_data_completeness_score(activity)
        
        return {
            'score': score,
            'available_data_types': data_types,
            'data_type_count': len(data_types),
            'device_trust_level': self._get_device_trust_level(activity.device_name),
            'has_social_engagement': activity.kudos_count > 0 or activity.comment_count > 0,
            'is_manual': activity.manual
        }