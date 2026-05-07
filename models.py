from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LevelDefinition:
    title: str
    required_xp: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LevelDefinition":
        return cls(
            title=str(data.get("title", "")).strip(),
            required_xp=int(data.get("required_xp", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Task:
    id: str
    title: str
    description: str
    task_type: str
    date: Optional[str]
    repeat_days: List[str]
    duration_minutes: int
    status: str
    category: str
    xp_reward: int
    created_at: str
    completed_at: Optional[str] = None
    timer_state: str = "idle"
    timer_started_at: Optional[str] = None
    timer_remaining_seconds: Optional[int] = None
    last_moved_at: Optional[str] = None
    state_date: Optional[str] = None
    completion_dates: List[str] = field(default_factory=list)
    scheduled_dates: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")).strip(),
            description=str(data.get("description", "")).strip(),
            task_type=str(data.get("task_type", "one_time")),
            date=data.get("date"),
            repeat_days=list(data.get("repeat_days", [])),
            duration_minutes=int(data.get("duration_minutes", 0)),
            status=str(data.get("status", "pending")),
            category=str(data.get("category", "not_urgent_important")),
            xp_reward=int(data.get("xp_reward", 0)),
            created_at=str(data.get("created_at", "")),
            completed_at=data.get("completed_at"),
            timer_state=str(data.get("timer_state", "idle")),
            timer_started_at=data.get("timer_started_at"),
            timer_remaining_seconds=data.get("timer_remaining_seconds"),
            last_moved_at=data.get("last_moved_at"),
            state_date=data.get("state_date"),
            completion_dates=list(data.get("completion_dates", [])),
            scheduled_dates=list(data.get("scheduled_dates", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProgressState:
    current_week_id: str
    current_week_start: str
    current_week_end: str
    current_month_id: str
    weekly_xp: int = 0
    monthly_xp: int = 0
    current_level_index: int = 1
    last_daily_rollover: Optional[str] = None
    last_weekly_rollover: Optional[str] = None
    last_monthly_rollover: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProgressState":
        return cls(
            current_week_id=str(data.get("current_week_id", "")),
            current_week_start=str(data.get("current_week_start", "")),
            current_week_end=str(data.get("current_week_end", "")),
            current_month_id=str(data.get("current_month_id", "")),
            weekly_xp=int(data.get("weekly_xp", 0)),
            monthly_xp=int(data.get("monthly_xp", 0)),
            current_level_index=int(data.get("current_level_index", 1)),
            last_daily_rollover=data.get("last_daily_rollover"),
            last_weekly_rollover=data.get("last_weekly_rollover"),
            last_monthly_rollover=data.get("last_monthly_rollover"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeeklyStatsEntry:
    week_id: str
    week_start: str
    week_end: str
    planned_tasks: int
    completed_tasks: int
    xp_earned: int
    completion_rate: float
    best_categories: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeeklyStatsEntry":
        return cls(
            week_id=str(data.get("week_id", "")),
            week_start=str(data.get("week_start", "")),
            week_end=str(data.get("week_end", "")),
            planned_tasks=int(data.get("planned_tasks", 0)),
            completed_tasks=int(data.get("completed_tasks", 0)),
            xp_earned=int(data.get("xp_earned", 0)),
            completion_rate=float(data.get("completion_rate", 0)),
            best_categories=list(data.get("best_categories", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MonthlyStatsEntry:
    month_id: str
    month_start: str
    month_end: str
    xp_earned: int
    level_index: int
    level_title: str
    planned_tasks: int
    completed_tasks: int
    medal_key: str
    medal_label: str
    medal_icon: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonthlyStatsEntry":
        return cls(
            month_id=str(data.get("month_id", "")),
            month_start=str(data.get("month_start", "")),
            month_end=str(data.get("month_end", "")),
            xp_earned=int(data.get("xp_earned", 0)),
            level_index=int(data.get("level_index", 1)),
            level_title=str(data.get("level_title", "")),
            planned_tasks=int(data.get("planned_tasks", 0)),
            completed_tasks=int(data.get("completed_tasks", 0)),
            medal_key=str(data.get("medal_key", "")),
            medal_label=str(data.get("medal_label", "")),
            medal_icon=str(data.get("medal_icon", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class YearlyMonthEntry:
    month_id: str
    label: str
    xp_earned: int
    level_index: int
    level_title: str
    medal_key: str
    medal_label: str
    medal_icon: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "YearlyMonthEntry":
        return cls(
            month_id=str(data.get("month_id", "")),
            label=str(data.get("label", "")),
            xp_earned=int(data.get("xp_earned", 0)),
            level_index=int(data.get("level_index", 1)),
            level_title=str(data.get("level_title", "")),
            medal_key=str(data.get("medal_key", "")),
            medal_label=str(data.get("medal_label", "")),
            medal_icon=str(data.get("medal_icon", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Settings:
    levels: List[LevelDefinition]
    base_xp_by_category: Dict[str, int]
    week_start: str = "monday"
    data_directory: str = "data"
    carry_over_one_time_tasks: bool = True
    theme: str = "light"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        return cls(
            levels=[LevelDefinition.from_dict(item) for item in data.get("levels", [])],
            base_xp_by_category={
                str(key): int(value)
                for key, value in data.get("base_xp_by_category", {}).items()
            },
            week_start=str(data.get("week_start", "monday")),
            data_directory=str(data.get("data_directory", "data")),
            carry_over_one_time_tasks=bool(data.get("carry_over_one_time_tasks", True)),
            theme=str(data.get("theme", "light")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "levels": [level.to_dict() for level in self.levels],
            "base_xp_by_category": dict(self.base_xp_by_category),
            "week_start": self.week_start,
            "data_directory": self.data_directory,
            "carry_over_one_time_tasks": self.carry_over_one_time_tasks,
            "theme": self.theme,
        }


def default_levels() -> List[LevelDefinition]:
    return [
        LevelDefinition("Шут, заметивший путь", 0),
        LevelDefinition("Любознательный странник", 100),
        LevelDefinition("Ученик монастыря", 250),
        LevelDefinition("Собранный послушник", 450),
        LevelDefinition("Хранитель распорядка", 700),
        LevelDefinition("Постигающий путь", 1000),
        LevelDefinition("Мастер внутреннего порядка", 1400),
        LevelDefinition("Наставник тишины", 1900),
        LevelDefinition("Монах ясного разума", 2500),
        LevelDefinition("Архимонах великой дисциплины", 3200),
    ]


def default_settings() -> Settings:
    return Settings(
        levels=default_levels(),
        base_xp_by_category={
            "urgent_important": 20,
            "urgent_not_important": 10,
            "not_urgent_important": 15,
            "not_urgent_not_important": 5,
        },
        week_start="monday",
        data_directory="data",
        carry_over_one_time_tasks=True,
        theme="light",
    )
