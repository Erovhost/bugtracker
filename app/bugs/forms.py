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
