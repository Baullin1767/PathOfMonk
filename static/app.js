function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  if (!toast) {
    return;
  }
  toast.textContent = message;
  toast.hidden = false;
  toast.classList.toggle("error", isError);
  clearTimeout(showToast._timer);
  showToast._timer = window.setTimeout(() => {
    toast.hidden = true;
  }, 2600);
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || !payload.success) {
    throw new Error(payload.message || "Не удалось выполнить действие.");
  }
  return payload;
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(Number(totalSeconds) || 0, 0);
  const hours = String(Math.floor(seconds / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
  const remainingSeconds = String(seconds % 60).padStart(2, "0");
  return `${hours}:${minutes}:${remainingSeconds}`;
}

function initializeTimers() {
  const timerCards = document.querySelectorAll("[data-timer-card]");
  if (!timerCards.length) {
    return;
  }

  const tick = () => {
    timerCards.forEach((card) => {
      const valueNode = card.querySelector(".timer-value");
      const isRunning = card.dataset.running === "true";
      let remaining = Number(card.dataset.remainingSeconds || "0");
      valueNode.textContent = formatDuration(remaining);
      if (isRunning && remaining > 0) {
        remaining -= 1;
        card.dataset.remainingSeconds = String(remaining);
      }
    });
  };

  tick();
  window.setInterval(tick, 1000);
}

function initializeDashboard() {
  document.addEventListener("click", async (event) => {
    const button = event.target.closest(".task-action-button");
    if (!button) {
      return;
    }

    const action = button.dataset.action;
    const taskId = button.dataset.taskId;
    if (!action || !taskId) {
      return;
    }

    button.disabled = true;
    try {
      await apiRequest(`/api/tasks/${taskId}/${action}`, { method: "POST" });
      window.location.reload();
    } catch (error) {
      showToast(error.message, true);
      button.disabled = false;
    }
  });
}

function collectTaskPayload() {
  const taskType = document.getElementById("task-type").value;
  const payload = {
    title: document.getElementById("task-title").value.trim(),
    description: document.getElementById("task-description").value.trim(),
    task_type: taskType,
    duration_minutes: Number(document.getElementById("task-duration").value),
    category: document.getElementById("task-category").value,
  };

  if (taskType === "one_time") {
    payload.date = document.getElementById("task-date").value;
  } else {
    payload.repeat_days = Array.from(
      document.querySelectorAll("#routine-fields input[type='checkbox']:checked")
    ).map((checkbox) => checkbox.value);
  }
  return payload;
}

function toggleTaskTypeFields(taskType) {
  const oneTimeFields = document.getElementById("one-time-fields");
  const routineFields = document.getElementById("routine-fields");
  const dateField = document.getElementById("task-date");

  if (taskType === "routine") {
    routineFields.hidden = false;
    oneTimeFields.hidden = true;
    dateField.required = false;
  } else {
    routineFields.hidden = true;
    oneTimeFields.hidden = false;
    dateField.required = true;
  }
}

function resetTaskForm() {
  document.getElementById("task-form").reset();
  document.getElementById("task-id").value = "";
  document.getElementById("task-form-title").textContent = "Новая задача";
  document.querySelectorAll("#routine-fields input[type='checkbox']").forEach((checkbox) => {
    checkbox.checked = false;
  });
  toggleTaskTypeFields("one_time");
}

function populateTaskForm(task) {
  document.getElementById("task-id").value = task.id;
  document.getElementById("task-title").value = task.title;
  document.getElementById("task-description").value = task.description || "";
  document.getElementById("task-type").value = task.task_type;
  document.getElementById("task-duration").value = task.duration_minutes;
  document.getElementById("task-category").value = task.category;
  document.getElementById("task-date").value = task.date || "";
  document.querySelectorAll("#routine-fields input[type='checkbox']").forEach((checkbox) => {
    checkbox.checked = Array.isArray(task.repeat_days) && task.repeat_days.includes(checkbox.value);
  });
  toggleTaskTypeFields(task.task_type);
  document.getElementById("task-form-title").textContent = "Редактирование задачи";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function initializeTasksPage() {
  const form = document.getElementById("task-form");
  if (!form) {
    return;
  }

  document.getElementById("task-type").addEventListener("change", (event) => {
    toggleTaskTypeFields(event.target.value);
  });

  document.getElementById("task-form-reset").addEventListener("click", () => {
    resetTaskForm();
  });

  document.querySelectorAll(".task-edit-button").forEach((button) => {
    button.addEventListener("click", () => {
      const task = JSON.parse(button.dataset.task);
      populateTaskForm(task);
    });
  });

  document.querySelectorAll(".task-delete-button").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!window.confirm("Удалить эту задачу?")) {
        return;
      }
      try {
        await apiRequest(`/api/tasks/${button.dataset.taskId}`, { method: "DELETE" });
        window.location.reload();
      } catch (error) {
        showToast(error.message, true);
      }
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const taskId = document.getElementById("task-id").value;
    const method = taskId ? "PUT" : "POST";
    const endpoint = taskId ? `/api/tasks/${taskId}` : "/api/tasks";

    try {
      await apiRequest(endpoint, {
        method,
        body: JSON.stringify(collectTaskPayload()),
      });
      window.location.reload();
    } catch (error) {
      showToast(error.message, true);
    }
  });

  toggleTaskTypeFields(document.getElementById("task-type").value);
}

function createLevelRow(title = "", xp = 0) {
  const row = document.createElement("div");
  row.className = "level-edit-row";
  row.innerHTML = `
    <input type="text" class="level-title-input" value="${title}" placeholder="Название уровня">
    <input type="number" class="level-xp-input" value="${xp}" min="0" placeholder="XP">
    <button type="button" class="link-button danger remove-level-row">Удалить</button>
  `;
  row.querySelector(".remove-level-row").addEventListener("click", () => row.remove());
  return row;
}

function initializeSettingsPage() {
  const form = document.getElementById("settings-form");
  if (!form) {
    return;
  }

  document.querySelectorAll(".remove-level-row").forEach((button) => {
    button.addEventListener("click", () => button.closest(".level-edit-row").remove());
  });

  document.getElementById("add-level-row").addEventListener("click", () => {
    const container = document.getElementById("level-rows");
    container.appendChild(createLevelRow("", 0));
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const levels = Array.from(document.querySelectorAll(".level-edit-row")).map((row) => ({
      title: row.querySelector(".level-title-input").value.trim(),
      required_xp: Number(row.querySelector(".level-xp-input").value),
    })).filter((level) => level.title);

    const payload = {
      theme: document.getElementById("settings-theme").value,
      week_start: document.getElementById("settings-week-start").value,
      data_directory: document.getElementById("settings-data-directory").value.trim(),
      carry_over_one_time_tasks: document.getElementById("settings-carry-over").checked,
      base_xp_by_category: {
        urgent_important: Number(document.getElementById("xp-urgent-important").value),
        urgent_not_important: Number(document.getElementById("xp-urgent-not-important").value),
        not_urgent_important: Number(document.getElementById("xp-not-urgent-important").value),
        not_urgent_not_important: Number(document.getElementById("xp-not-urgent-not-important").value),
      },
      levels,
    };

    try {
      await apiRequest("/api/settings", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      showToast("Настройки сохранены.");
      window.setTimeout(() => window.location.reload(), 700);
    } catch (error) {
      showToast(error.message, true);
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const pageId = document.body.dataset.page;
  if (pageId === "dashboard") {
    initializeDashboard();
  }
  if (pageId === "tasks") {
    initializeTasksPage();
  }
  if (pageId === "settings") {
    initializeSettingsPage();
  }
  initializeTimers();
});
