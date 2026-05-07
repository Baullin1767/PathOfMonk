from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from models import (
    MonthlyStatsEntry,
    ProgressState,
    Settings,
    Task,
    WeeklyStatsEntry,
    YearlyMonthEntry,
    default_settings,
)
from progress_service import ProgressService


class JsonStorage:
    FILE_NAMES = {
        "tasks": "tasks.json",
        "progress": "progress.json",
        "weekly_stats": "weekly_stats.json",
        "monthly_stats": "monthly_stats.json",
        "yearly_stats": "yearly_stats.json",
        "settings": "settings.json",
    }

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.bootstrap_dir = self.project_root / "data"
        self.bootstrap_dir.mkdir(parents=True, exist_ok=True)
        self.bootstrap_settings_path = self.bootstrap_dir / self.FILE_NAMES["settings"]

        bootstrap_settings = self._load_bootstrap_settings()
        self.data_dir = self._resolve_data_directory(bootstrap_settings.data_directory)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_data_files()

    def _resolve_data_directory(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        return (self.project_root / raw_path).resolve()

    def _file_path(self, key: str) -> Path:
        return self.data_dir / self.FILE_NAMES[key]

    def _bootstrap_settings_payload(self) -> Dict[str, Any]:
        if not self.bootstrap_settings_path.exists():
            settings = default_settings()
            self._write_json(self.bootstrap_settings_path, settings.to_dict())
            return settings.to_dict()
        with self.bootstrap_settings_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_bootstrap_settings(self) -> Settings:
        return Settings.from_dict(self._bootstrap_settings_payload())

    def _sync_settings_files(self, settings: Settings) -> None:
        payload = settings.to_dict()
        self._write_json_if_changed(self.bootstrap_settings_path, payload)
        self._write_json_if_changed(self._file_path("settings"), payload)

    def ensure_data_files(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        first_start = not any(self._file_path(key).exists() for key in self.FILE_NAMES if key != "settings")
        settings = self._load_bootstrap_settings()

        if first_start:
            demo_data = self._build_demo_payload(settings)
            self._write_json(self._file_path("tasks"), demo_data["tasks"])
            self._write_json(self._file_path("progress"), demo_data["progress"])
            self._write_json(self._file_path("weekly_stats"), demo_data["weekly_stats"])
            self._write_json(self._file_path("monthly_stats"), demo_data["monthly_stats"])
            self._write_json(self._file_path("yearly_stats"), demo_data["yearly_stats"])
            self._sync_settings_files(settings)
            return

        self._ensure_file("tasks", [])
        progress_state = ProgressService.initial_progress_state(settings)
        self._ensure_file("progress", progress_state.to_dict())
        self._ensure_file("weekly_stats", [])
        self._ensure_file("monthly_stats", [])
        self._ensure_file("yearly_stats", [])
        self._sync_settings_files(settings)

    def _ensure_file(self, key: str, default_payload: Any) -> None:
        file_path = self._file_path(key)
        if not file_path.exists():
            self._write_json(file_path, default_payload)

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        temp_path.replace(path)

    def _write_json_if_changed(self, path: Path, payload: Any) -> None:
        current_payload = self._read_json(path, None)
        if current_payload == payload:
            return
        self._write_json(path, payload)

    def _read_json(self, path: Path, default_payload: Any) -> Any:
        if not path.exists():
            return default_payload
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def load_tasks(self) -> List[Task]:
        payload = self._read_json(self._file_path("tasks"), [])
        return [Task.from_dict(item) for item in payload]

    def save_tasks(self, tasks: List[Task]) -> None:
        self._write_json(self._file_path("tasks"), [task.to_dict() for task in tasks])

    def load_progress(self) -> ProgressState:
        settings = self.load_settings()
        default_progress = ProgressService.initial_progress_state(settings).to_dict()
        payload = self._read_json(self._file_path("progress"), default_progress)
        return ProgressState.from_dict(payload)

    def save_progress(self, progress: ProgressState) -> None:
        self._write_json(self._file_path("progress"), progress.to_dict())

    def load_weekly_stats(self) -> List[WeeklyStatsEntry]:
        payload = self._read_json(self._file_path("weekly_stats"), [])
        return [WeeklyStatsEntry.from_dict(item) for item in payload]

    def save_weekly_stats(self, entries: List[WeeklyStatsEntry]) -> None:
        self._write_json(self._file_path("weekly_stats"), [entry.to_dict() for entry in entries])

    def load_monthly_stats(self) -> List[MonthlyStatsEntry]:
        payload = self._read_json(self._file_path("monthly_stats"), [])
        return [MonthlyStatsEntry.from_dict(item) for item in payload]

    def save_monthly_stats(self, entries: List[MonthlyStatsEntry]) -> None:
        self._write_json(self._file_path("monthly_stats"), [entry.to_dict() for entry in entries])

    def load_yearly_stats(self) -> List[YearlyMonthEntry]:
        payload = self._read_json(self._file_path("yearly_stats"), [])
        return [YearlyMonthEntry.from_dict(item) for item in payload]

    def save_yearly_stats(self, entries: List[YearlyMonthEntry]) -> None:
        self._write_json(self._file_path("yearly_stats"), [entry.to_dict() for entry in entries])

    def load_settings(self) -> Settings:
        payload = self._read_json(self._file_path("settings"), self._bootstrap_settings_payload())
        settings = Settings.from_dict(payload)
        resolved_dir = self._resolve_data_directory(settings.data_directory)
        if resolved_dir != self.data_dir:
            self.data_dir = resolved_dir
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.ensure_data_files()
            payload = self._read_json(self._file_path("settings"), payload)
            settings = Settings.from_dict(payload)
        return settings

    def save_settings(self, settings: Settings) -> None:
        target_dir = self._resolve_data_directory(settings.data_directory)
        if target_dir != self.data_dir:
            self.change_data_directory(target_dir, settings)
            return
        self._sync_settings_files(settings)

    def change_data_directory(self, target_dir: str | Path, settings: Settings) -> None:
        resolved_target = self._resolve_data_directory(str(target_dir))
        resolved_target.mkdir(parents=True, exist_ok=True)
        current_files = {
            key: self._file_path(key)
            for key in self.FILE_NAMES
            if self._file_path(key).exists()
        }
        for key, source_path in current_files.items():
            target_path = resolved_target / self.FILE_NAMES[key]
            shutil.copy2(source_path, target_path)

        self.data_dir = resolved_target
        settings.data_directory = self._normalize_data_directory_for_settings(resolved_target)
        self._sync_settings_files(settings)
        self.ensure_data_files()

    def _normalize_data_directory_for_settings(self, resolved_target: Path) -> str:
        try:
            return str(resolved_target.relative_to(self.project_root))
        except ValueError:
            return str(resolved_target)

    def _build_demo_payload(self, settings: Settings) -> Dict[str, Any]:
        now = datetime.now()
        today = now.date()
        yesterday = today - timedelta(days=1)
        previous_week_start, previous_week_end = ProgressService.get_week_bounds(
            today - timedelta(days=7), settings.week_start
        )
        previous_month_anchor = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        previous_month_end = today.replace(day=1) - timedelta(days=1)
        progress = ProgressService.initial_progress_state(settings, today)
        progress.weekly_xp = 35
        progress.monthly_xp = 135
        progress.current_level_index = ProgressService.calculate_level_index(progress.monthly_xp, settings.levels)

        demo_tasks = [
            Task(
                id=str(uuid.uuid4()),
                title="Утреннее планирование",
                description="Разобрать день и выделить три главных шага.",
                task_type="routine",
                date=None,
                repeat_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
                duration_minutes=20,
                status="pending",
                category="not_urgent_important",
                xp_reward=17,
                created_at=(now - timedelta(days=10)).isoformat(),
                timer_remaining_seconds=20 * 60,
            ),
            Task(
                id=str(uuid.uuid4()),
                title="Фокус-блок по ключевой задаче",
                description="Один глубокий блок без отвлечений.",
                task_type="routine",
                date=None,
                repeat_days=["monday", "wednesday", "friday"],
                duration_minutes=50,
                status="pending",
                category="urgent_important",
                xp_reward=25,
                created_at=(now - timedelta(days=8)).isoformat(),
                timer_remaining_seconds=50 * 60,
            ),
            Task(
                id=str(uuid.uuid4()),
                title="Проверить счета и дедлайны",
                description="Закрыть срочные организационные мелочи.",
                task_type="one_time",
                date=today.isoformat(),
                repeat_days=[],
                duration_minutes=25,
                status="pending",
                category="urgent_not_important",
                xp_reward=12,
                created_at=(now - timedelta(days=2)).isoformat(),
                timer_remaining_seconds=25 * 60,
                scheduled_dates=[today.isoformat()],
            ),
            Task(
                id=str(uuid.uuid4()),
                title="Прочитать 15 страниц книги по профессии",
                description="Невыполненная задача со вчера, чтобы показать перенос.",
                task_type="one_time",
                date=yesterday.isoformat(),
                repeat_days=[],
                duration_minutes=30,
                status="pending",
                category="not_urgent_important",
                xp_reward=18,
                created_at=(now - timedelta(days=3)).isoformat(),
                timer_remaining_seconds=30 * 60,
                scheduled_dates=[yesterday.isoformat()],
            ),
            Task(
                id=str(uuid.uuid4()),
                title="Подвести итоги дня",
                description="Короткий обзор выполненного и план на завтра.",
                task_type="routine",
                date=None,
                repeat_days=["monday", "tuesday", "wednesday", "thursday", "friday"],
                duration_minutes=15,
                status="completed",
                category="not_urgent_not_important",
                xp_reward=6,
                created_at=(now - timedelta(days=12)).isoformat(),
                completed_at=(now - timedelta(hours=1)).isoformat(),
                timer_state="completed",
                timer_remaining_seconds=0,
                state_date=today.isoformat(),
                completion_dates=[today.isoformat()],
            ),
        ]

        demo_weekly_stats = [
            {
                "week_id": ProgressService.get_week_id(previous_week_start, settings.week_start),
                "week_start": previous_week_start.isoformat(),
                "week_end": previous_week_end.isoformat(),
                "planned_tasks": 18,
                "completed_tasks": 14,
                "xp_earned": 168,
                "completion_rate": 77.78,
                "best_categories": [
                    {
                        "category": "not_urgent_important",
                        "label": "Не срочные, но важные",
                        "planned": 7,
                        "completed": 6,
                        "completion_rate": 85.71,
                    }
                ],
            }
        ]

        previous_month_id = ProgressService.get_month_id(previous_month_anchor)
        medal = ProgressService.get_medal_for_level(4)
        demo_month_entry = {
            "month_id": previous_month_id,
            "month_start": previous_month_anchor.isoformat(),
            "month_end": previous_month_end.isoformat(),
            "xp_earned": 520,
            "level_index": 4,
            "level_title": settings.levels[3].title,
            "planned_tasks": 64,
            "completed_tasks": 49,
            "medal_key": medal["key"],
            "medal_label": medal["label"],
            "medal_icon": medal["icon"],
        }

        return {
            "tasks": [task.to_dict() for task in demo_tasks],
            "progress": progress.to_dict(),
            "weekly_stats": demo_weekly_stats,
            "monthly_stats": [demo_month_entry],
            "yearly_stats": [
                {
                    "month_id": previous_month_id,
                    "label": previous_month_anchor.strftime("%m.%Y"),
                    "xp_earned": 520,
                    "level_index": 4,
                    "level_title": settings.levels[3].title,
                    "medal_key": medal["key"],
                    "medal_label": medal["label"],
                    "medal_icon": medal["icon"],
                }
            ],
        }
