from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from models import Settings, Task
from progress_service import ProgressService


class TaskService:
    VALID_TYPES = {"routine", "one_time"}
    VALID_STATUSES = {"pending", "in_progress", "paused", "completed"}
    VALID_CATEGORIES = {
        "urgent_important",
        "urgent_not_important",
        "not_urgent_important",
        "not_urgent_not_important",
    }

    def __init__(self, storage: Any) -> None:
        self.storage = storage

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    def _settings(self) -> Settings:
        return self.storage.load_settings()

    def _calculate_xp(self, task: Task) -> int:
        return ProgressService.calculate_task_xp(task, self._settings())

    def _find_task(self, task_id: str, tasks: List[Task]) -> Tuple[int, Task]:
        for index, task in enumerate(tasks):
            if task.id == task_id:
                return index, task
        raise ValueError("Задача не найдена.")

    def _normalize_routine_state(self, task: Task, target_date: str) -> bool:
        changed = False
        if task.task_type != "routine":
            return changed

        if target_date in task.completion_dates:
            if task.state_date != target_date or task.status != "completed":
                task.state_date = target_date
                task.status = "completed"
                task.timer_state = "completed"
                task.timer_started_at = None
                task.timer_remaining_seconds = 0
                changed = True
            return changed

        if task.state_date != target_date:
            task.state_date = target_date
            task.status = "pending"
            task.timer_state = "idle"
            task.timer_started_at = None
            task.timer_remaining_seconds = task.duration_minutes * 60
            task.completed_at = None
            changed = True
        return changed

    def _effective_remaining_seconds(self, task: Task) -> int:
        if task.timer_remaining_seconds is None:
            return max(task.duration_minutes * 60, 0)
        if task.timer_state != "running" or not task.timer_started_at:
            return max(task.timer_remaining_seconds, 0)
        elapsed = int((self._now() - ProgressService.parse_datetime(task.timer_started_at)).total_seconds())
        return max(task.timer_remaining_seconds - elapsed, 0)

    def _pause_running_task(self, task: Task) -> bool:
        if task.timer_state != "running" or not task.timer_started_at:
            return False
        task.timer_remaining_seconds = self._effective_remaining_seconds(task)
        task.timer_state = "paused"
        task.timer_started_at = None
        task.status = "paused"
        return True

    def get_today_tasks(self) -> List[Dict[str, Any]]:
        return self.get_tasks_for_date(self._now().date().isoformat())

    def get_tasks_for_date(self, target_date: str) -> List[Dict[str, Any]]:
        tasks = self.storage.load_tasks()
        target = ProgressService.parse_date(target_date)
        changed = False
        scheduled_tasks: List[Dict[str, Any]] = []

        for task in tasks:
            if not ProgressService.is_task_scheduled_for_date(task, target):
                continue
            changed = self._normalize_routine_state(task, target_date) or changed
            task.xp_reward = self._calculate_xp(task)
            scheduled_tasks.append(self.serialize_task(task, target))

        if changed:
            self.storage.save_tasks(tasks)

        return sorted(
            scheduled_tasks,
            key=lambda item: (
                ProgressService.CATEGORY_ORDER.index(item["category"]),
                item["status"] == "completed",
                item["duration_minutes"],
                item["title"].lower(),
            ),
        )

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        tasks = self.storage.load_tasks()
        today = self._now().date()
        serialized = []
        changed = False
        for task in tasks:
            if task.task_type == "routine" and ProgressService.is_task_scheduled_for_date(task, today):
                changed = self._normalize_routine_state(task, today.isoformat()) or changed
            task.xp_reward = self._calculate_xp(task)
            serialized.append(self.serialize_task(task, today, include_schedule=True))
        if changed:
            self.storage.save_tasks(tasks)
        return sorted(serialized, key=lambda item: (item["task_type"], item["title"].lower()))

    def serialize_task(
        self,
        task: Task,
        target_date: datetime.date | Any,
        include_schedule: bool = False,
    ) -> Dict[str, Any]:
        if hasattr(target_date, "isoformat"):
            target_iso = target_date.isoformat()
        else:
            target_iso = str(target_date)
        remaining_seconds = self._effective_remaining_seconds(task)
        if task.status == "completed":
            remaining_seconds = 0

        payload = task.to_dict()
        payload.update(
            {
                "category_label": ProgressService.CATEGORY_LABELS.get(task.category, task.category),
                "status_label": {
                    "pending": "Ожидает",
                    "in_progress": "В работе",
                    "paused": "На паузе",
                    "completed": "Завершена",
                }.get(task.status, task.status),
                "is_completed_today": target_iso in task.completion_dates,
                "is_overdue": task.task_type == "one_time"
                and task.status != "completed"
                and task.date is not None
                and task.date < self._now().date().isoformat(),
                "timer_remaining_seconds": remaining_seconds,
                "can_carry_over": task.task_type == "one_time" and task.status != "completed",
            }
        )
        if include_schedule:
            payload["schedule_label"] = self._build_schedule_label(task)
        return payload

    def _build_schedule_label(self, task: Task) -> str:
        weekday_labels = {
            "monday": "Пн",
            "tuesday": "Вт",
            "wednesday": "Ср",
            "thursday": "Чт",
            "friday": "Пт",
            "saturday": "Сб",
            "sunday": "Вс",
        }
        if task.task_type == "routine":
            return ", ".join(weekday_labels.get(day, day) for day in task.repeat_days) or "Не задано"
        return task.date or "Без даты"

    def _validate_payload(self, payload: Dict[str, Any], existing_task: Task | None = None) -> Task:
        title = str(payload.get("title", "")).strip()
        if not title:
            raise ValueError("Укажите название задачи.")

        task_type = str(payload.get("task_type", existing_task.task_type if existing_task else "one_time"))
        if task_type not in self.VALID_TYPES:
            raise ValueError("Неизвестный тип задачи.")

        category = str(payload.get("category", existing_task.category if existing_task else "not_urgent_important"))
        if category not in self.VALID_CATEGORIES:
            raise ValueError("Неизвестная категория задачи.")

        try:
            duration_minutes = int(payload.get("duration_minutes", existing_task.duration_minutes if existing_task else 0))
        except (TypeError, ValueError) as error:
            raise ValueError("Длительность должна быть числом.") from error
        if duration_minutes <= 0:
            raise ValueError("Длительность должна быть больше нуля.")

        description = str(payload.get("description", existing_task.description if existing_task else "")).strip()
        repeat_days = list(payload.get("repeat_days", existing_task.repeat_days if existing_task else []))
        date_value = payload.get("date", existing_task.date if existing_task else None)

        if task_type == "routine":
            repeat_days = [str(day) for day in repeat_days if str(day) in ProgressService.WEEKDAY_NAMES]
            if not repeat_days:
                raise ValueError("Для рутинной задачи выберите дни повторения.")
            date_value = None
        else:
            if not date_value:
                raise ValueError("Для единичной задачи нужна дата.")
            ProgressService.parse_date(str(date_value))
            repeat_days = []

        if existing_task:
            task = existing_task
            task.title = title
            task.description = description
            task.task_type = task_type
            task.category = category
            task.duration_minutes = duration_minutes
            task.repeat_days = repeat_days
            task.date = str(date_value) if date_value else None
            if task.task_type == "one_time" and task.date and task.date not in task.scheduled_dates:
                task.scheduled_dates.append(task.date)
        else:
            now = self._now().isoformat()
            task = Task(
                id=str(uuid.uuid4()),
                title=title,
                description=description,
                task_type=task_type,
                date=str(date_value) if date_value else None,
                repeat_days=repeat_days,
                duration_minutes=duration_minutes,
                status="pending",
                category=category,
                xp_reward=0,
                created_at=now,
                timer_remaining_seconds=duration_minutes * 60,
                state_date=str(date_value) if task_type == "one_time" else None,
                scheduled_dates=[str(date_value)] if task_type == "one_time" and date_value else [],
            )

        task.xp_reward = self._calculate_xp(task)
        if task.status != "completed":
            max_seconds = task.duration_minutes * 60
            if task.timer_state == "running":
                task.timer_remaining_seconds = min(self._effective_remaining_seconds(task), max_seconds)
                task.timer_started_at = self._now().isoformat()
            elif task.timer_state == "paused":
                task.timer_remaining_seconds = min(task.timer_remaining_seconds or max_seconds, max_seconds)
            else:
                task.timer_remaining_seconds = max_seconds
                task.timer_state = "idle"
                task.status = "pending"
        return task

    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        tasks = self.storage.load_tasks()
        task = self._validate_payload(payload)
        tasks.append(task)
        self.storage.save_tasks(tasks)
        return self.serialize_task(task, self._now().date(), include_schedule=True)

    def update_task(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        tasks = self.storage.load_tasks()
        index, task = self._find_task(task_id, tasks)
        updated_task = self._validate_payload(payload, task)
        tasks[index] = updated_task
        self.storage.save_tasks(tasks)
        return self.serialize_task(updated_task, self._now().date(), include_schedule=True)

    def delete_task(self, task_id: str) -> None:
        tasks = self.storage.load_tasks()
        index, _ = self._find_task(task_id, tasks)
        tasks.pop(index)
        self.storage.save_tasks(tasks)

    def start_task(self, task_id: str) -> Dict[str, Any]:
        tasks = self.storage.load_tasks()
        today = self._now().date().isoformat()
        changed = False
        running_task_id = None

        for task in tasks:
            if task.id != task_id:
                changed = self._pause_running_task(task) or changed
                continue

            if task.task_type == "routine":
                self._normalize_routine_state(task, today)
            if task.status == "completed":
                raise ValueError("Задача уже завершена.")
            if task.task_type == "one_time" and task.date != today:
                raise ValueError("Эту единичную задачу нельзя запустить вне её текущей даты.")

            task.state_date = today
            task.status = "in_progress"
            task.timer_state = "running"
            task.timer_started_at = self._now().isoformat()
            task.timer_remaining_seconds = self._effective_remaining_seconds(task)
            task.xp_reward = self._calculate_xp(task)
            running_task_id = task.id
            changed = True

        if not running_task_id:
            raise ValueError("Задача не найдена.")
        if changed:
            self.storage.save_tasks(tasks)

        target_task = next(task for task in tasks if task.id == task_id)
        return self.serialize_task(target_task, self._now().date(), include_schedule=True)

    def pause_task(self, task_id: str) -> Dict[str, Any]:
        tasks = self.storage.load_tasks()
        _, task = self._find_task(task_id, tasks)
        if task.task_type == "routine":
            self._normalize_routine_state(task, self._now().date().isoformat())
        if not self._pause_running_task(task):
            if task.status == "completed":
                raise ValueError("Нельзя поставить на паузу завершённую задачу.")
            task.status = "paused"
            task.timer_state = "paused"
            task.timer_remaining_seconds = self._effective_remaining_seconds(task)
        self.storage.save_tasks(tasks)
        return self.serialize_task(task, self._now().date(), include_schedule=True)

    def finish_task(self, task_id: str) -> Dict[str, Any]:
        tasks = self.storage.load_tasks()
        _, task = self._find_task(task_id, tasks)
        today = self._now().date().isoformat()

        if task.task_type == "routine":
            self._normalize_routine_state(task, today)
        if task.status == "completed":
            raise ValueError("Задача уже завершена.")

        task.state_date = today
        task.status = "completed"
        task.timer_state = "completed"
        task.timer_started_at = None
        task.timer_remaining_seconds = 0
        task.completed_at = self._now().isoformat()
        if today not in task.completion_dates:
            task.completion_dates.append(today)
        task.xp_reward = self._calculate_xp(task)
        self.storage.save_tasks(tasks)
        return self.serialize_task(task, self._now().date(), include_schedule=True)

    def carry_over_task(self, task_id: str) -> Dict[str, Any]:
        tasks = self.storage.load_tasks()
        _, task = self._find_task(task_id, tasks)
        if task.task_type != "one_time":
            raise ValueError("Перенос доступен только для единичных задач.")
        if task.status == "completed":
            raise ValueError("Завершённую задачу переносить не нужно.")

        source_date = ProgressService.parse_date(task.date) if task.date else self._now().date()
        next_date = max(source_date, self._now().date()) + timedelta(days=1)
        task.date = next_date.isoformat()
        if task.date not in task.scheduled_dates:
            task.scheduled_dates.append(task.date)
        task.last_moved_at = self._now().isoformat()
        task.state_date = task.date
        task.status = "pending"
        task.timer_state = "idle"
        task.timer_started_at = None
        task.timer_remaining_seconds = task.duration_minutes * 60
        self.storage.save_tasks(tasks)
        return self.serialize_task(task, self._now().date(), include_schedule=True)

    def recalculate_all_task_rewards(self) -> None:
        tasks = self.storage.load_tasks()
        for task in tasks:
            task.xp_reward = self._calculate_xp(task)
        self.storage.save_tasks(tasks)
