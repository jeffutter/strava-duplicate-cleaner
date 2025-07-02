import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
from dataclasses import dataclass
from strava_client import Activity


@dataclass
class DuplicatePair:
    activity1: Activity
    activity2: Activity
    overlap_percentage: float
    time_difference: timedelta
    recommended_keep: Activity
    recommended_delete: Activity
    reason: str
    is_very_similar: bool = False


class DuplicateDetector:
    def __init__(self, config: Dict):
        # Time window handles normal device sync delays; DST shifts are handled by ±1h time shift checking
        self.time_window_minutes = config.get('time_window_minutes', 10)
        self.distance_tolerance_percent = config.get('distance_tolerance_percent', 5)
        self.duration_tolerance_percent = config.get('duration_tolerance_percent', 5)
        self.minimum_overlap_percent = config.get('minimum_overlap_percent', 80)
        self.logger = logging.getLogger(__name__)

    def find_overlapping_activities(self, activities: List[Activity]) -> List[DuplicatePair]:
        duplicates = []

        activities_by_date = self._group_by_date(activities)

        for date, day_activities in activities_by_date.items():
            if len(day_activities) < 2:
                continue

            self.logger.debug(f"Date: {date} - Activities: {len(day_activities)}")

            day_activities.sort(key=lambda x: x.start_date)

            for i in range(len(day_activities)):
                for j in range(i + 1, len(day_activities)):
                    activity1 = day_activities[i]
                    activity2 = day_activities[j]

                    self.logger.debug("------------------------------")
                    self.logger.debug(f"A1: {activity1}")
                    self.logger.debug(f"A2: {activity2}")
                    self.logger.debug("------------------------------")

                    if self._are_potential_duplicates(activity1, activity2):
                        duplicate_pair = self._create_duplicate_pair(activity1, activity2)
                        if duplicate_pair:
                            duplicates.append(duplicate_pair)

        return duplicates

    def _group_by_date(self, activities: List[Activity]) -> Dict[str, List[Activity]]:
        groups = {}
        for activity in activities:
            date_key = activity.start_date.date().isoformat()
            if date_key not in groups:
                groups[date_key] = []
            groups[date_key].append(activity)
        return groups

    def _are_potential_duplicates(self, activity1: Activity, activity2: Activity) -> bool:
        if activity1.type != activity2.type:
            self.logger.debug(f"Different activity types: {activity1.type} vs {activity2.type}")
            return False

        # Check original time and ±1 hour shifts to handle DST issues
        time_shifts = [0, 3600, -3600]  # 0, +1 hour, -1 hour in seconds
        
        for shift in time_shifts:
            # Apply time shift to activity1's start time for comparison
            shifted_start1 = activity1.start_date + timedelta(seconds=shift)
            time_diff = abs((shifted_start1 - activity2.start_date).total_seconds() / 60)
            
            if time_diff <= self.time_window_minutes:
                self.logger.debug(f"Time check passed with {shift/3600:+.0f}h shift: {time_diff:.1f} minutes difference")
                
                if not self._similar_distance(activity1.distance, activity2.distance):
                    self.logger.debug(f"Distance difference too large: {activity1.distance} vs {activity2.distance}")
                    continue

                if not self._similar_duration(activity1.elapsed_time, activity2.elapsed_time):
                    self.logger.debug(f"Duration difference too large: {activity1.elapsed_time} vs {activity2.elapsed_time}")
                    continue

                overlap_percentage = self.calculate_overlap_percentage_with_shift(activity1, activity2, shift)
                if overlap_percentage >= self.minimum_overlap_percent:
                    self.logger.debug(f"Overlap check passed with {shift/3600:+.0f}h shift: {overlap_percentage:.1f}%")
                    return True
                else:
                    self.logger.debug(f"Overlap too low with {shift/3600:+.0f}h shift: {overlap_percentage:.1f}%")
        
        self.logger.debug("No time shift produced sufficient overlap")
        return False

    def _similar_distance(self, distance1: float, distance2: float) -> bool:
        if distance1 == 0 and distance2 == 0:
            return True
        if distance1 == 0 or distance2 == 0:
            return False

        diff_percent = abs(distance1 - distance2) / max(distance1, distance2) * 100
        return diff_percent <= self.distance_tolerance_percent

    def _similar_duration(self, duration1: int, duration2: int) -> bool:
        if duration1 == 0 and duration2 == 0:
            return True
        if duration1 == 0 or duration2 == 0:
            return False

        diff_percent = abs(duration1 - duration2) / max(duration1, duration2) * 100
        return diff_percent <= self.duration_tolerance_percent

    def calculate_overlap_percentage(self, activity1: Activity, activity2: Activity) -> float:
        return self.calculate_overlap_percentage_with_shift(activity1, activity2, 0)
    
    def calculate_overlap_percentage_with_shift(self, activity1: Activity, activity2: Activity, shift_seconds: int) -> float:
        start1 = activity1.start_date + timedelta(seconds=shift_seconds)
        end1 = start1 + timedelta(seconds=activity1.elapsed_time)
        start2 = activity2.start_date
        end2 = start2 + timedelta(seconds=activity2.elapsed_time)

        if not self.determine_time_overlap(start1, end1, start2, end2):
            return 0.0

        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap_duration = (overlap_end - overlap_start).total_seconds()

        min_duration = min(activity1.elapsed_time, activity2.elapsed_time)
        if min_duration == 0:
            return 0.0

        return (overlap_duration / min_duration) * 100

    def determine_time_overlap(self, start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
        return start1 <= end2 and start2 <= end1

    def _create_duplicate_pair(self, activity1: Activity, activity2: Activity) -> DuplicatePair:
        # Find the best time shift for overlap calculation
        best_overlap = 0
        best_shift = 0
        time_shifts = [0, 3600, -3600]  # 0, +1 hour, -1 hour in seconds
        
        for shift in time_shifts:
            overlap = self.calculate_overlap_percentage_with_shift(activity1, activity2, shift)
            if overlap > best_overlap:
                best_overlap = overlap
                best_shift = shift
        
        # Calculate time difference using the best shift
        shifted_start1 = activity1.start_date + timedelta(seconds=best_shift)
        time_difference = abs(shifted_start1 - activity2.start_date)

        quality1 = self._calculate_activity_quality_score(activity1)
        quality2 = self._calculate_activity_quality_score(activity2)

        # Determine if activities are very similar (small quality difference)
        quality_difference = abs(quality1 - quality2)
        is_very_similar = quality_difference <= 5  # Within 5 points
        
        if quality1 > quality2:
            recommended_keep = activity1
            recommended_delete = activity2
            reason = f"Activity 1 has better data quality (score: {quality1} vs {quality2})"
        elif quality2 > quality1:
            recommended_keep = activity2
            recommended_delete = activity1
            reason = f"Activity 2 has better data quality (score: {quality2} vs {quality1})"
        else:
            # For tie-breaking, use the shifted time if applicable
            if shifted_start1 <= activity2.start_date:
                recommended_keep = activity1
                recommended_delete = activity2
                reason = "Activity 1 was recorded earlier"
            else:
                recommended_keep = activity2
                recommended_delete = activity1
                reason = "Activity 2 was recorded earlier"

        if best_shift != 0:
            reason += f" (detected with {best_shift/3600:+.0f}h time shift)"

        return DuplicatePair(
            activity1=activity1,
            activity2=activity2,
            overlap_percentage=best_overlap,
            time_difference=time_difference,
            recommended_keep=recommended_keep,
            recommended_delete=recommended_delete,
            reason=reason,
            is_very_similar=is_very_similar
        )

    def _calculate_activity_quality_score(self, activity: Activity) -> int:
        score = 0

        if activity.has_heartrate and activity.average_heartrate:
            score += 10
        if activity.has_power and activity.average_power:
            score += 10
        if activity.has_cadence and activity.average_cadence:
            score += 5
        if activity.has_temperature:
            score += 3

        # Prefer activities with map/GPS data (important for Stryd vs other sources)
        if activity.has_map:
            score += 8

        if activity.distance > 0:
            score += 5

        device_scores = {
            'garmin': 5,
            'wahoo': 5,
            'polar': 5,
            'suunto': 5,
            'stryd': 4,  # Add Stryd device support
            'iphone': 2,
            'android': 2,
            'strava': 1
        }

        device_name_lower = activity.device_name.lower()
        for device, device_score in device_scores.items():
            if device in device_name_lower:
                score += device_score
                break

        if activity.kudos_count > 0 or activity.comment_count > 0:
            score += 2

        if activity.manual:
            score -= 10

        return max(0, score)
