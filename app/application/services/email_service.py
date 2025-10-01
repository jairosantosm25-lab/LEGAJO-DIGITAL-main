# Importa la clase Message para crear correos y Flask's 'current_app' y 'render_template'.
from flask_mail import Message
from flask import current_app, render_template

# Define el servicio para el envío de correos.
class EmailService:
    # El constructor recibe la instancia de Flask-Mail para poder enviar correos.
    def __init__(self, mail_instance):
        self.mail = mail_instance

    # Método para enviar el correo con el código de verificación 2FA.
    def send_2fa_code(self, recipient_email, user_name, code):
        try:
            # Crea un nuevo objeto Message con el asunto, remitente y destinatarios.
            msg = Message(
                subject='Tu Código de Verificación - Legajo Digital DIRESA',
                sender=current_app.config['MAIL_DEFAULT_SENDER'],
                recipients=[recipient_email]
            )
            # Renderiza el cuerpo del correo usando una plantilla HTML para darle formato.
            msg.html = render_template(
                'email/2fa_code_email.html',
                user_name=user_name,
                verification_code=code
            )
            # Envía el correo.
            self.mail.send(msg)
        except Exception as e:
            # Si ocurre un error, lo registra en el log y lanza una excepción más genérica.
            current_app.logger.error(f"Error al enviar email de 2FA a {recipient_email}: {e}")
            raise ConnectionError("No se pudo enviar el correo de verificación.")