from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField

from app.auth.forms import RegistrationForm

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


class RoleForm(FlaskForm):
    role = SelectField("Роль", choices=ROLE_CHOICES)
    submit = SubmitField("Сменить роль")


# Наследуем форму регистрации: поля и проверки (уникальность логина
# и почты, длина и совпадение паролей) переходят сюда без копирования.
class CreateUserForm(RegistrationForm):
    role = SelectField("Роль", choices=ROLE_CHOICES)
    submit = SubmitField("Создать")
