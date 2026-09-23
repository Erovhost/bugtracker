import sqlalchemy as sa
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from app import db
from app.models import User

REQUIRED = "Заполните это поле."


class LoginForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired(REQUIRED)])
    password = PasswordField("Пароль", validators=[DataRequired(REQUIRED)])
    remember_me = BooleanField("Запомнить меня")
    submit = SubmitField("Войти")


class RegistrationForm(FlaskForm):
    username = StringField(
        "Логин",
        validators=[
            DataRequired(REQUIRED),
            Length(max=64, message="Не длиннее 64 символов."),
        ],
    )
    email = StringField(
        "Почта",
        validators=[
            DataRequired(REQUIRED),
            Email("Введите корректный адрес почты."),
            Length(max=120, message="Не длиннее 120 символов."),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(REQUIRED),
            Length(min=8, message="Пароль должен быть не короче 8 символов."),
        ],
    )
    password2 = PasswordField(
        "Повторите пароль",
        validators=[
            DataRequired(REQUIRED),
            EqualTo("password", "Пароли не совпадают."),
        ],
    )
    submit = SubmitField("Зарегистрироваться")

    # Flask-WTF сам вызывает методы validate_<имя поля>
    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(User.username == username.data))
        if user is not None:
            raise ValidationError("Этот логин уже занят.")

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(User.email == email.data))
        if user is not None:
            raise ValidationError("Эта почта уже зарегистрирована.")
