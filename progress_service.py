from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from models import LevelDefinition, ProgressState, Settings, Task


class ProgressService:
    CATEGORY_LABELS = {
        "urgent_important": "Срочные и важные",
        "urgent_not_important": "Срочные, но не важные",
        "not_urgent_important": "Не срочные, но важные",
        "not_urgent_not_important": "Не срочные и не важные",
    }

    CATEGORY_ORDER = [
        "urgent_important",
        "urgent_not_important",
        "not_urgent_important",
        "not_urgent_not_important",
    ]

    WEEKDAY_NAMES = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    MEDAL_INFO = {
        "bronze_path": {"label": "Бронзовая медаль пути", "icon": "🥉"},
        "silver_discipline": {"label": "Серебряная медаль дисциплины", "icon": "🥈"},
        "gold_clarity": {"label": "Золотая медаль ясности", "icon": "🥇"},
        "platinum_monk": {"label": "Платиновая медаль монаха", "icon": "✦"},
    }

    def __init__(self, storage: Any) -> None:
        self.storage = storage

    @staticmethod
    def today() -> date:
        return datetime.now().date()

    @staticmethod
    def parse_date(value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()

    @staticmethod
    def parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value)

    @classmethod
    def get_week_bounds(cls, reference_date: date, week_start: str) -> Tuple[date, date]:
        start_index = 0 if week_start == "monday" else 6
        current_index = reference_date.weekday()
        delta = (current_index - start_index) % 7
        week_start_date = reference_date - timedelta(days=delta)
        return week_start_date, week_start_date + timedelta(days=6)

    @classmethod
    def get_week_id(cls, reference_date: date, week_start: str) -> str:
        week_start_date, _ = cls.get_week_bounds(reference_date, week_start)
        year, week_number, _ = week_start_date.isocalendar()
        return f"{year}-W{week_number:02d}"

    @staticmethod
    def get_month_id(reference_date: date) -> str:
        return reference_date.strftime("%Y-%m")

    @classmethod
    def initial_progress_state(cls, settings: Settings, today_value: date | None = None) -> ProgressState:
        today_value = today_value or cls.today()
        week_start, week_end = cls.get_week_bounds(today_value, settings.week_start)
        return ProgressState(
            current_week_id=cls.get_week_id(today_value, settings.week_start),
            current_week_start=week_start.isoformat(),
            current_week_end=week_end.isoformat(),
            current_month_id=cls.get_month_id(today_value),
            weekly_xp=0,
            monthly_xp=0,
            current_level_index=1,
            last_daily_rollover=today_value.isoformat(),
            last_weekly_rollover=today_value.isoformat(),
            last_monthly_rollover=today_value.isoformat(),
        )

    @staticmethod
    def is_task_completed_on(task: Task, target_date: date) -> bool:
        return target_date.isoformat() in task.completion_dates

    @classmethod
    def calculate_task_xp(cls, task: Task, settings: Settings) -> int:
        base_xp = settings.base_xp_by_category.get(task.category, 10)
        return base_xp + max(task.duration_minutes, 0) // 10

    @classmethod
    def is_task_scheduled_for_date(cls, task: Task, target_date: date) -> bool:
        if task.task_type == "routine":
            weekday_name = cls.WEEKDAY_NAMES[target_date.weekday()]
            return weekday_name in task.repeat_days
        if not task.date:
            return False
        return task.date == target_date.isoformat()

    @classmethod
    def count_task_occurrences_in_range(cls, task: Task, range_start: date, range_end: date) -> int:
        if task.task_type == "routine":
            count = 0
            cursor = range_start
            while cursor <= range_end:
                if cls.is_task_scheduled_for_date(task, cursor):
                    count += 1
                cursor += timedelta(days=1)
            return count

        scheduled_dates = {
            item for item in task.scheduled_dates if range_start <= cls.parse_date(item) <= range_end
        }
        if not scheduled_dates and task.date:
            task_date = cls.parse_date(task.date)
            if range_start <= task_date <= range_end:
                scheduled_dates.add(task.date)
        return len(scheduled_dates)

    @classmethod
    def count_completed_occurrences_in_range(cls, task: Task, range_start: date, range_end: date) -> int:
        return len(
            [
                item
                for item in task.completion_dates
                if range_start <= cls.parse_date(item) <= range_end
            ]
        )

    @classmethod
    def calculate_level_index(cls, monthly_xp: int, levels: List[LevelDefinition]) -> int:
        current = 1
        for index, level in enumerate(levels, start=1):
            if monthly_xp >= level.required_xp:
                current = index
        return current

    @classmethod
    def get_medal_for_level(cls, level_index: int) -> Dict[str, str]:
        if level_index <= 2:
            medal_key = "bronze_path"
        elif level_index <= 5:
            medal_key = "silver_discipline"
        elif level_index <= 8:
            medal_key = "gold_clarity"
        else:
            medal_key = "platinum_monk"
        return {"key": medal_key, **cls.MEDAL_INFO[medal_key]}

    def record_completion(self, task: Task) -> ProgressState:
        settings = self.storage.load_settings()
        progress = self.storage.load_progress()
        xp_earned = self.calculate_task_xp(task, settings)
        progress.weekly_xp += xp_earned
        progress.monthly_xp += xp_earned
        progress.current_level_index = self.calculate_level_index(progress.monthly_xp, settings.levels)
        self.storage.save_progress(progress)
        return progress

    def get_weekly_progress(self, tasks: List[Task], today_value: date | None = None) -> Dict[str, Any]:
        settings = self.storage.load_settings()
        progress = self.storage.load_progress()
        today_value = today_value or self.today()
        week_start, week_end = self.get_week_bounds(today_value, settings.week_start)
        max_weekly_xp = 0
        planned_tasks = 0
        completed_tasks = 0

        for task in tasks:
            occurrences = self.count_task_occurrences_in_range(task, week_start, week_end)
            if occurrences == 0:
                continue
            planned_tasks += occurrences
            completed_tasks += self.count_completed_occurrences_in_range(task, week_start, week_end)
            max_weekly_xp += occurrences * self.calculate_task_xp(task, settings)

        fill_percent = 0 if max_weekly_xp == 0 else min(progress.weekly_xp / max_weekly_xp, 1) * 100
        return {
            "week_id": self.get_week_id(today_value, settings.week_start),
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "week_label": f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}",
            "current_xp": progress.weekly_xp,
            "max_xp": max_weekly_xp,
            "fill_percent": round(fill_percent, 2),
            "planned_tasks": planned_tasks,
            "completed_tasks": completed_tasks,
        }

    def get_monthly_progress(self, today_value: date | None = None) -> Dict[str, Any]:
        settings = self.storage.load_settings()
        progress = self.storage.load_progress()
        today_value = today_value or self.today()

        current_level_index = self.calculate_level_index(progress.monthly_xp, settings.levels)
        progress.current_level_index = current_level_index
        self.storage.save_progress(progress)

        current_level = settings.levels[current_level_index - 1]
        next_level = settings.levels[min(current_level_index, len(settings.levels) - 1)]
        current_threshold = current_level.required_xp
        next_threshold = next_level.required_xp if current_level_index < len(settings.levels) else current_threshold
        span = max(next_threshold - current_threshold, 1)
        current_within_level = progress.monthly_xp - current_threshold
        fill_percent = 100 if current_level_index == len(settings.levels) else max(
            0,
            min(current_within_level / span, 1) * 100,
        )

        return {
            "month_id": self.get_month_id(today_value),
            "month_label": today_value.strftime("%m.%Y"),
            "monthly_xp": progress.monthly_xp,
            "current_level_index": current_level_index,
            "current_level_title": current_level.title,
            "next_level_title": None if current_level_index == len(settings.levels) else next_level.title,
            "next_level_threshold": None if current_level_index == len(settings.levels) else next_threshold,
            "fill_percent": round(fill_percent, 2),
            "levels": [level.to_dict() for level in settings.levels],
            "medal_preview": self.get_medal_for_level(current_level_index),
        }

    def get_daily_summary(self, today_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_tasks = len(today_tasks)
        completed = [task for task in today_tasks if task["status"] == "completed"]
        completed_count = len(completed)
        completed_minutes = sum(task["duration_minutes"] for task in completed)
        completed_xp = sum(task["xp_reward"] for task in completed)
        total_minutes = sum(task["duration_minutes"] for task in today_tasks)
        completion_percent = 0 if total_tasks == 0 else round((completed_count / total_tasks) * 100, 2)
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_count,
            "completed_minutes": completed_minutes,
            "total_minutes": total_minutes,
            "earned_xp": completed_xp,
            "completion_percent": completion_percent,
        }

    def get_best_categories(self, tasks: List[Task], range_start: date, range_end: date) -> List[Dict[str, Any]]:
        buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"planned": 0, "completed": 0})

        for task in tasks:
            planned = self.count_task_occurrences_in_range(task, range_start, range_end)
            completed = self.count_completed_occurrences_in_range(task, range_start, range_end)
            if planned == 0:
                continue
            buckets[task.category]["planned"] += planned
            buckets[task.category]["completed"] += completed

        if not buckets:
            return []

        results: List[Dict[str, Any]] = []
        best_rate = 0.0
        for category, values in buckets.items():
            rate = 0.0 if values["planned"] == 0 else values["completed"] / values["planned"]
            best_rate = max(best_rate, rate)
            results.append(
                {
                    "category": category,
                    "label": self.CATEGORY_LABELS.get(category, category),
                    "planned": values["planned"],
                    "completed": values["completed"],
                    "completion_rate": round(rate * 100, 2),
                }
            )

        return [
            item
            for item in sorted(results, key=lambda item: (-item["completion_rate"], -item["completed"]))
            if item["completion_rate"] == round(best_rate * 100, 2)
        ] or sorted(results, key=lambda item: (-item["completion_rate"], -item["completed"]))[:1]
