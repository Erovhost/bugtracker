from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.models import PRIORITY_LABELS, SEVERITY_LABELS

REQUIRED = "Заполните это поле."


class BugForm(FlaskForm):
    title = StringField(
        "Заголовок",
        validators=[DataRequired(REQUIRED), Length(max=200, message="Не длиннее 200 символов.")],
    )
    steps = TextAreaField("Шаги воспроизведения", validators=[Optional()])
    expected = TextAreaField("Ожидаемый результат", validators=[Optional()])
    actual = TextAreaField("Фактический результат", validators=[Optional()])
    environment = StringField(
        "Окружение",
        validators=[Optional(), Length(max=200, message="Не длиннее 200 символов.")],
    )
    # Первый пункт с пустым значением: серьёзность тестировщик выбирает сам
    severity = SelectField(
        "Серьёзность",
        choices=[("", "— выберите —")] + list(SEVERITY_LABELS.items()),
        validators=[DataRequired("Выберите серьёзность.")],
    )
    priority = SelectField(
        "Приоритет",
        choices=list(PRIORITY_LABELS.items()),
        default="medium",
    )
    submit = SubmitField("Сохранить")


class CommentForm(FlaskForm):
    # DataRequired не пропускает и текст из одних пробелов
    text = TextAreaField(
        "Комментарий",
        validators=[
            DataRequired("Напишите текст комментария."),
            Length(max=5000, message="Не длиннее 5000 символов."),
        ],
    )
    submit = SubmitField("Отправить")


class AssignForm(FlaskForm):
    # Значения — строки: "" означает «не назначен», иначе id разработчика.
    # Варианты задаёт маршрут, подменить id на чужой не получится.
    assignee_id = SelectField("Исполнитель")
    submit = SubmitField("Сохранить")
