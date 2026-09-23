"""Жизненный цикл бага: какие переходы статусов разрешены и кому.

Правила — из раздела «Жизненный цикл бага» ТЗ.
Здесь нет маршрутов и HTML, только логика: её легко проверять тестами.
"""

from app import db
from app.models import STATUS_LABELS, Comment

# (из статуса, в статус) -> роль, которая выполняет переход
TRANSITIONS = {
    ("new", "in_progress"): "developer",
    ("in_progress", "fixed"): "developer",
    ("new", "rejected"): "developer",
    ("in_progress", "rejected"): "developer",
    ("fixed", "closed"): "tester",
    ("fixed", "in_progress"): "tester",
    ("rejected", "new"): "tester",
}

# Подписи кнопок в карточке бага
BUTTON_LABELS = {
    ("new", "in_progress"): "Взять в работу",
    ("in_progress", "fixed"): "Исправлено",
    ("new", "rejected"): "Отклонить",
    ("in_progress", "rejected"): "Отклонить",
    ("fixed", "closed"): "Закрыть",
    ("fixed", "in_progress"): "Вернуть в работу",
    ("rejected", "new"): "Вернуть в новые",
}

ROLE_LABELS = {"developer": "разработчик", "tester": "тестировщик"}


def check_transition(user, bug, new_status, comment=None):
    """Можно ли user перевести bug в new_status.

    Возвращает None, если можно, иначе — текст ошибки для пользователя.
    """
    old_status = bug.status
    if user.has_role("admin"):
        return "Администратор не меняет статусы багов."
    if user not in bug.project.members:
        return "Менять статус могут только участники проекта."

    role = TRANSITIONS.get((old_status, new_status))
    if role is None:
        return (
            f"Переход из «{STATUS_LABELS.get(old_status, old_status)}» "
            f"в «{STATUS_LABELS.get(new_status, new_status)}» невозможен."
        )
    if not user.has_role(role):
        return f"Этот переход выполняет {ROLE_LABELS[role]}."

    # Дополнительные условия для отдельных переходов
    if (old_status, new_status) == ("new", "in_progress"):
        if bug.assignee is not None and bug.assignee_id != user.id:
            return "Баг назначен на другого разработчика."
    if old_status == "in_progress" and new_status in ("fixed", "rejected"):
        if bug.assignee_id != user.id:
            return "Это может сделать только исполнитель бага."
    if new_status == "rejected":
        if comment is None or comment.strip() == "":
            return "Укажите причину отклонения в комментарии."

    return None


def apply_transition(user, bug, new_status, comment=None):
    """Выполнить переход (после успешной check_transition). Коммит — за вызывающим."""
    old_status = bug.status

    if (old_status, new_status) == ("new", "in_progress"):
        # Свободный баг: взявший в работу становится исполнителем
        if bug.assignee is None:
            bug.assignee = user
    elif (old_status, new_status) == ("rejected", "new"):
        # Баг снова в общей очереди
        bug.assignee = None
    elif (old_status, new_status) == ("fixed", "in_progress"):
        # Исполнитель прежний; если его сняли — сразу в new, чтобы любой мог взять
        if bug.assignee is None:
            new_status = "new"

    bug.status = new_status
    # От имени updated_by триггер запишет строку в status_history
    bug.updater = user

    if comment is not None and comment.strip() != "":
        db.session.add(Comment(bug=bug, author=user, text=comment.strip()))

    return new_status


def available_transitions(user, bug):
    """Список (новый статус, подпись кнопки), доступных user для bug.

    Комментарий для отклонения здесь не проверяем: его вводят вместе с кнопкой.
    """
    result = []
    for (old_status, new_status), label in BUTTON_LABELS.items():
        if old_status != bug.status:
            continue
        check_comment = "ok" if new_status == "rejected" else None
        if check_transition(user, bug, new_status, check_comment) is None:
            result.append((new_status, label))
    return result
