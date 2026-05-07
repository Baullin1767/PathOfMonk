from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, List

from models import MonthlyStatsEntry, ProgressState, WeeklyStatsEntry, YearlyMonthEntry
from progress_service import ProgressService


class StatsService:
    def __init__(self, storage: Any) -> None:
        self.storage = storage
        self.progress_service = ProgressService(storage)

    def run_rollovers_if_needed(self, today_value: date | None = None) -> None:
        today_value = today_value or ProgressService.today()
        today_iso = today_value.isoformat()
        settings = self.storage.load_settings()
        tasks = self.storage.load_tasks()
        progress = self.storage.load_progress()
        weekly_stats = self.storage.load_weekly_stats()
        monthly_stats = self.storage.load_monthly_stats()
        yearly_stats = self.storage.load_yearly_stats()

        tasks_changed = False
        progress_changed = False
        weekly_changed = False
        monthly_changed = False
        yearly_changed = False

        target_week_id = ProgressService.get_week_id(today_value, settings.week_start)
        target_month_id = ProgressService.get_month_id(today_value)

        if progress.current_week_id and progress.current_week_id != target_week_id:
            # Weekly reset is snapshot-first: we archive the finished week before
            # mutating any dates or zeroing XP, so historical reporting stays stable.
            weekly_stats.append(self._build_weekly_snapshot(progress, tasks))
            current_week_start, current_week_end = ProgressService.get_week_bounds(today_value, settings.week_start)
            progress.current_week_id = target_week_id
            progress.current_week_start = current_week_start.isoformat()
            progress.current_week_end = current_week_end.isoformat()
            progress.weekly_xp = 0
            progress.last_weekly_rollover = today_iso
            progress_changed = True
            weekly_changed = True

        if progress.current_month_id and progress.current_month_id != target_month_id:
            # Monthly archive also happens before the reset so medals and levels are
            # calculated from the actual finished month instead of the new empty one.
            month_entry = self._build_monthly_snapshot(progress, tasks)
            monthly_stats.append(month_entry)
            yearly_stats.append(self._build_yearly_entry(month_entry))
            progress.current_month_id = target_month_id
            progress.monthly_xp = 0
            progress.current_level_index = 1
            progress.last_monthly_rollover = today_iso
            progress_changed = True
            monthly_changed = True
            yearly_changed = True

        if progress.last_daily_rollover != today_iso:
            tasks_changed = self._carry_over_overdue_one_time_tasks(tasks, today_value) or tasks_changed
            progress.last_daily_rollover = today_iso
            progress_changed = True

        if tasks_changed:
            self.storage.save_tasks(tasks)
        if progress_changed:
            progress.current_level_index = ProgressService.calculate_level_index(
                progress.monthly_xp,
                settings.levels,
            )
            self.storage.save_progress(progress)
        if weekly_changed:
            self.storage.save_weekly_stats(weekly_stats)
        if monthly_changed:
            self.storage.save_monthly_stats(monthly_stats)
        if yearly_changed:
            self.storage.save_yearly_stats(yearly_stats)

    def _carry_over_overdue_one_time_tasks(self, tasks: List[Any], today_value: date) -> bool:
        settings = self.storage.load_settings()
        if not settings.carry_over_one_time_tasks:
            return False

        changed = False
        today_iso = today_value.isoformat()
        now_iso = datetime.now().isoformat()
        for task in tasks:
            if task.task_type != "one_time" or task.status == "completed" or not task.date:
                continue
            if task.date >= today_iso:
                continue

            # The app may be reopened after several missed days. We move the task straight
            # to the current day so the user sees it immediately, but we also preserve the
            # path it travelled through scheduled_dates for weekly reporting.
            cursor = ProgressService.parse_date(task.date) + timedelta(days=1)
            while cursor <= today_value:
                next_date = cursor.isoformat()
                if next_date not in task.scheduled_dates:
                    task.scheduled_dates.append(next_date)
                cursor += timedelta(days=1)

            task.date = today_iso
            task.last_moved_at = now_iso
            task.state_date = today_iso
            task.status = "pending"
            task.timer_state = "idle"
            task.timer_started_at = None
            task.timer_remaining_seconds = task.duration_minutes * 60
            changed = True
        return changed

    def _build_weekly_snapshot(self, progress: ProgressState, tasks: List[Any]) -> WeeklyStatsEntry:
        range_start = ProgressService.parse_date(progress.current_week_start)
        range_end = ProgressService.parse_date(progress.current_week_end)

        planned_tasks = 0
        completed_tasks = 0
        for task in tasks:
            planned_tasks += ProgressService.count_task_occurrences_in_range(task, range_start, range_end)
            completed_tasks += ProgressService.count_completed_occurrences_in_range(task, range_start, range_end)

        completion_rate = 0.0 if planned_tasks == 0 else round((completed_tasks / planned_tasks) * 100, 2)
        best_categories = self.progress_service.get_best_categories(tasks, range_start, range_end)
        return WeeklyStatsEntry(
            week_id=progress.current_week_id,
            week_start=progress.current_week_start,
            week_end=progress.current_week_end,
            planned_tasks=planned_tasks,
            completed_tasks=completed_tasks,
            xp_earned=progress.weekly_xp,
            completion_rate=completion_rate,
            best_categories=best_categories,
        )

    def _build_monthly_snapshot(self, progress: ProgressState, tasks: List[Any]) -> MonthlyStatsEntry:
        year, month = [int(part) for part in progress.current_month_id.split("-")]
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        planned_tasks = 0
        completed_tasks = 0
        for task in tasks:
            planned_tasks += ProgressService.count_task_occurrences_in_range(task, month_start, month_end)
            completed_tasks += ProgressService.count_completed_occurrences_in_range(task, month_start, month_end)

        settings = self.storage.load_settings()
        level_index = ProgressService.calculate_level_index(progress.monthly_xp, settings.levels)
        level_title = settings.levels[level_index - 1].title
        medal = ProgressService.get_medal_for_level(level_index)
        return MonthlyStatsEntry(
            month_id=progress.current_month_id,
            month_start=month_start.isoformat(),
            month_end=month_end.isoformat(),
            xp_earned=progress.monthly_xp,
            level_index=level_index,
            level_title=level_title,
            planned_tasks=planned_tasks,
            completed_tasks=completed_tasks,
            medal_key=medal["key"],
            medal_label=medal["label"],
            medal_icon=medal["icon"],
        )

    def _build_yearly_entry(self, month_entry: MonthlyStatsEntry) -> YearlyMonthEntry:
        return YearlyMonthEntry(
            month_id=month_entry.month_id,
            label=month_entry.month_id,
            xp_earned=month_entry.xp_earned,
            level_index=month_entry.level_index,
            level_title=month_entry.level_title,
            medal_key=month_entry.medal_key,
            medal_label=month_entry.medal_label,
            medal_icon=month_entry.medal_icon,
        )
