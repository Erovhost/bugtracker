import sqlalchemy as sa
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
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
    submit = SubmitField("Создать")

    def validate_name(self, name):
        project = db.session.scalar(sa.select(Project).where(Project.name == name.data))
        if project is not None:
            raise ValidationError("Проект с таким названием уже есть.")
