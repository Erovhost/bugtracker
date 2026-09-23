from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField

# Роли в том порядке, в каком их удобнее выбирать
ROLE_CHOICES = [
    ("tester", "tester"),
    ("developer", "developer"),
    ("admin", "admin"),
]


class ApproveForm(FlaskForm):
    # SelectField сам проверяет, что пришла одна из ролей списка
    role = SelectField("Роль", choices=ROLE_CHOICES)
    submit = SubmitField("Одобрить")
