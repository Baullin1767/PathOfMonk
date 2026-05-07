from __future__ import annotations

import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

from models import LevelDefinition, Settings
from progress_service import ProgressService
from stats_service import StatsService
from storage import JsonStorage
from task_service import TaskService


RUSSIAN_WEEKDAYS = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]
RUSSIAN_MONTHS = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]
SIDEBAR_QUOTES = [
    "Небольшие верные действия каждый день превращаются в устойчивый путь.",
    "Тихий порядок в дне рождает большую ясность в мыслях.",
    "Лучший ритм не давит, а помогает двигаться спокойно и точно.",
    "Одна завершённая задача укрепляет путь сильнее, чем десять смутных намерений.",
    "Дисциплина становится мягче, когда день устроен с уважением к себе.",
    "Собранность начинается не с рывка, а с одного честного шага.",
    "Когда главное выбрано ясно, остальное перестаёт шуметь.",
    "Устойчивый прогресс складывается из маленьких обещаний, которые ты сдержал.",
    "Спокойный темп часто приводит дальше, чем беспокойная спешка.",
    "Хороший день не обязан быть идеальным, ему достаточно быть осознанным.",
]


def create_app() -> Flask:
    app = Flask(__name__)
    project_root = Path(__file__).resolve().parent
    storage = JsonStorage(project_root)
    task_service = TaskService(storage)
    progress_service = ProgressService(storage)
    stats_service = StatsService(storage)

    app.config["storage"] = storage
    app.config["task_service"] = task_service
    app.config["progress_service"] = progress_service
    app.config["stats_service"] = stats_service

    @app.before_request
    def apply_rollovers() -> None:
        if request.path.startswith("/static/"):
            return
        stats_service.run_rollovers_if_needed()

    @app.context_processor
    def inject_shared_context() -> Dict[str, Any]:
        settings = storage.load_settings()
        today = datetime.now().date()
        quote_index = today.toordinal() % len(SIDEBAR_QUOTES)
        return {
            "theme": settings.theme,
            "sidebar_quote": SIDEBAR_QUOTES[quote_index],
            "category_labels": ProgressService.CATEGORY_LABELS,
            "weekday_labels": {
                "monday": "Понедельник",
                "tuesday": "Вторник",
                "wednesday": "Среда",
                "thursday": "Четверг",
                "friday": "Пятница",
                "saturday": "Суббота",
                "sunday": "Воскресенье",
            },
        }

    @app.get("/")
    def index() -> str:
        today = datetime.now().date()
        today_tasks = task_service.get_today_tasks()
        dashboard = build_dashboard_context(progress_service, today_tasks, today)
        return render_template("index.html", **dashboard)

    @app.get("/tasks")
    def tasks_page() -> str:
        return render_template(
            "tasks.html",
            tasks=task_service.get_all_tasks(),
            today=datetime.now().date().isoformat(),
        )

    @app.get("/stats/weekly")
    def weekly_stats_page() -> str:
        weekly_entries = storage.load_weekly_stats()
        weekly_progress = progress_service.get_weekly_progress(storage.load_tasks())
        return render_template(
            "weekly_stats.html",
            weekly_entries=weekly_entries,
            weekly_progress=weekly_progress,
        )

    @app.get("/progress/monthly")
    def monthly_progress_page() -> str:
        monthly_progress = progress_service.get_monthly_progress()
        monthly_entries = storage.load_monthly_stats()
        return render_template(
            "monthly_progress.html",
            monthly_progress=monthly_progress,
            monthly_entries=monthly_entries,
        )

    @app.get("/stats/yearly")
    def yearly_stats_page() -> str:
        yearly_entries = storage.load_yearly_stats()
        return render_template("yearly_stats.html", yearly_entries=yearly_entries)

    @app.get("/settings")
    def settings_page() -> str:
        settings = storage.load_settings()
        return render_template("settings.html", settings=settings)

    @app.get("/api/tasks/today")
    def api_today_tasks():
        return success_response(task_service.get_today_tasks())

    @app.post("/api/tasks")
    def api_create_task():
        try:
            task = task_service.create_task(request.get_json(force=True))
        except ValueError as error:
            return error_response(str(error), 400)
        return success_response(task, "Задача создана.")

    @app.put("/api/tasks/<task_id>")
    def api_update_task(task_id: str):
        try:
            task = task_service.update_task(task_id, request.get_json(force=True))
        except ValueError as error:
            return error_response(str(error), 400)
        return success_response(task, "Задача обновлена.")

    @app.delete("/api/tasks/<task_id>")
    def api_delete_task(task_id: str):
        try:
            task_service.delete_task(task_id)
        except ValueError as error:
            return error_response(str(error), 404)
        return success_response({"task_id": task_id}, "Задача удалена.")

    @app.post("/api/tasks/<task_id>/start")
    def api_start_task(task_id: str):
        try:
            task = task_service.start_task(task_id)
        except ValueError as error:
            return error_response(str(error), 400)
        return success_response(task, "Таймер запущен.")

    @app.post("/api/tasks/<task_id>/pause")
    def api_pause_task(task_id: str):
        try:
            task = task_service.pause_task(task_id)
        except ValueError as error:
            return error_response(str(error), 400)
        return success_response(task, "Таймер поставлен на паузу.")

    @app.post("/api/tasks/<task_id>/finish")
    def api_finish_task(task_id: str):
        try:
            task = task_service.finish_task(task_id)
            finished_task = next(item for item in storage.load_tasks() if item.id == task_id)
            progress = progress_service.record_completion(finished_task)
        except ValueError as error:
            return error_response(str(error), 400)
        return success_response(
            {
                "task": task,
                "progress": {
                    "weekly_xp": progress.weekly_xp,
                    "monthly_xp": progress.monthly_xp,
                    "current_level_index": progress.current_level_index,
                },
            },
            "Задача завершена, опыт начислен.",
        )

    @app.post("/api/tasks/<task_id>/carry-over")
    def api_carry_over_task(task_id: str):
        try:
            task = task_service.carry_over_task(task_id)
        except ValueError as error:
            return error_response(str(error), 400)
        return success_response(task, "Задача перенесена.")

    @app.get("/api/progress/weekly")
    def api_weekly_progress():
        return success_response(progress_service.get_weekly_progress(storage.load_tasks()))

    @app.get("/api/progress/monthly")
    def api_monthly_progress():
        return success_response(progress_service.get_monthly_progress())

    @app.get("/api/stats/weekly")
    def api_weekly_stats():
        return success_response([entry.to_dict() for entry in storage.load_weekly_stats()])

    @app.get("/api/stats/yearly")
    def api_yearly_stats():
        return success_response([entry.to_dict() for entry in storage.load_yearly_stats()])

    @app.get("/api/settings")
    def api_get_settings():
        return success_response(storage.load_settings().to_dict())

    @app.put("/api/settings")
    def api_save_settings():
        try:
            settings = parse_settings_payload(request.get_json(force=True))
            storage.save_settings(settings)
            task_service.recalculate_all_task_rewards()
            stats_service.run_rollovers_if_needed()
        except ValueError as error:
            return error_response(str(error), 400)
        return success_response(settings.to_dict(), "Настройки сохранены.")

    return app


def build_dashboard_context(progress_service: ProgressService, today_tasks: list[dict[str, Any]], today) -> Dict[str, Any]:
    grouped_tasks: Dict[str, list[dict[str, Any]]] = {
        category: [] for category in ProgressService.CATEGORY_ORDER
    }
    for task in today_tasks:
        grouped_tasks[task["category"]].append(task)

    monthly_progress = progress_service.get_monthly_progress(today)
    current_level_index = monthly_progress["current_level_index"]
    all_levels = monthly_progress["levels"]
    start_index = max(current_level_index - 3, 0)
    end_index = min(start_index + 4, len(all_levels))
    dashboard_levels = []
    for offset, level in enumerate(all_levels[start_index:end_index], start=start_index + 1):
        dashboard_levels.append({**level, "index": offset})

    map_points = [
        {"index": 1, "x": 18, "y": 76},
        {"index": 2, "x": 24, "y": 69},
        {"index": 3, "x": 32, "y": 64},
        {"index": 4, "x": 41, "y": 70},
        {"index": 5, "x": 50, "y": 75},
        {"index": 6, "x": 59, "y": 66},
        {"index": 7, "x": 68, "y": 58},
        {"index": 8, "x": 77, "y": 61},
        {"index": 9, "x": 86, "y": 45},
        {"index": 10, "x": 92, "y": 34},
    ]
    map_path_points = " ".join(f'{point["x"]},{point["y"]}' for point in map_points)

    current_date_label = (
        f"{RUSSIAN_WEEKDAYS[today.weekday()].capitalize()}, {today.day} "
        f"{RUSSIAN_MONTHS[today.month - 1]} {today.year}"
    )
    return {
        "current_date_label": current_date_label,
        "today_tasks": today_tasks,
        "grouped_tasks": grouped_tasks,
        "daily_summary": progress_service.get_daily_summary(today_tasks),
        "weekly_progress": progress_service.get_weekly_progress(progress_service.storage.load_tasks(), today),
        "monthly_progress": monthly_progress,
        "dashboard_levels": dashboard_levels,
        "map_points": map_points,
        "map_path_points": map_path_points,
    }


def parse_settings_payload(payload: Dict[str, Any]) -> Settings:
    levels = [LevelDefinition.from_dict(item) for item in payload.get("levels", [])]
    if not levels:
        raise ValueError("Нужен хотя бы один уровень.")
    if any(level.required_xp < 0 for level in levels):
        raise ValueError("Пороги опыта не могут быть отрицательными.")
    sorted_thresholds = [level.required_xp for level in levels]
    if sorted_thresholds != sorted(sorted_thresholds):
        raise ValueError("Пороги уровней должны идти по возрастанию.")

    return Settings(
        levels=levels,
        base_xp_by_category={
            "urgent_important": int(payload.get("base_xp_by_category", {}).get("urgent_important", 20)),
            "urgent_not_important": int(payload.get("base_xp_by_category", {}).get("urgent_not_important", 10)),
            "not_urgent_important": int(payload.get("base_xp_by_category", {}).get("not_urgent_important", 15)),
            "not_urgent_not_important": int(payload.get("base_xp_by_category", {}).get("not_urgent_not_important", 5)),
        },
        week_start=str(payload.get("week_start", "monday")),
        data_directory=str(payload.get("data_directory", "data")),
        carry_over_one_time_tasks=bool(payload.get("carry_over_one_time_tasks", True)),
        theme=str(payload.get("theme", "light")),
    )


def success_response(data: Any, message: str | None = None):
    payload = {"success": True, "data": data}
    if message:
        payload["message"] = message
    return jsonify(payload)


def error_response(message: str, status_code: int):
    return jsonify({"success": False, "message": message}), status_code


app = create_app()


if __name__ == "__main__":
    url = "http://127.0.0.1:5000"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
