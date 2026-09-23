import sqlalchemy as sa
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from app import db
from app.models import Project


class ProjectForm(FlaskForm):
    name = StringField(
        "Название",
        validators=[
            DataRequired("Заполните это поле."),
            Length(max=120, message="Не длиннее 120 символов."),
        ],
    )
    description = TextAreaField("Описание", validators=[Optional()])
    submit = SubmitField("Сохранить")

    # original_name — текущее название при редактировании (None при создании).
    # Без него форма ругалась бы на сам редактируемый проект.
    def __init__(self, original_name=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_name = original_name

    def validate_name(self, name):
        if name.data == self.original_name:
            return
        project = db.session.scalar(sa.select(Project).where(Project.name == name.data))
        if project is not None:
            raise ValidationError("Проект с таким названием уже есть.")


class AddMemberForm(FlaskForm):
    # Варианты (choices) задаёт маршрут. SelectField сам проверяет,
    # что пришло одно из разрешённых значений — подменить id не получится.
    user_id = SelectField("Пользователь", coerce=int)
    submit = SubmitField("Добавить")
