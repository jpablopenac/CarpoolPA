from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, BooleanField
from wtforms.validators import DataRequired, Email, Length
from .models import DAYS, IDA_SLOTS, VUELTA_SLOTS


class PreferenceForm(FlaskForm):
    # One form reused per day
    ida_slot = SelectField("Módulo de entrada", choices=[("", "--")]+[(s, s) for s in IDA_SLOTS])
    vuelta_slot = SelectField("Módulo de salida", choices=[("", "--")]+[(s, s) for s in VUELTA_SLOTS])
    flex_ida = BooleanField("Flexibilizar ida")
    flex_vuelta = BooleanField("Flexibilizar vuelta")
    volunteer_second_day = BooleanField("Voluntario segundo día")
    submit = SubmitField("Guardar")
