# RUTA: app/presentation/routes/auth_routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, current_user
from app.application.forms import LoginForm, TwoFactorForm
# Si estás usando Flask-Login con un UserLoader, el objeto 'user' cargado
# en verify_2fa ya contendrá el método is_system_admin().

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirección predeterminada si el usuario ya está logueado.
        # Asumimos que 'index' maneja la lógica de redirección post-login/2FA.
        return redirect(url_for('index')) 
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            usuario_service = current_app.config['USUARIO_SERVICE']
            user_id = usuario_service.attempt_login(form.username.data, form.password.data)

            if user_id:
                # Éxito en la contraseña, se procede a la verificación 2FA
                session['2fa_user_id'] = user_id
                session['2fa_username'] = form.username.data
                return redirect(url_for('auth.verify_2fa'))
            else:
                flash('Usuario o contraseña incorrectos.', 'danger')
        except Exception as e:
            current_app.logger.error(f"Error inesperado en login: {e}")
            flash("Ocurrió un error inesperado. Por favor, intente de nuevo.", 'danger')
            
    return render_template('auth/login.html', form=form)

@auth_bp.route('/login/verify', methods=['GET', 'POST'])
def verify_2fa():
    # Verifica que exista una sesión pendiente de 2FA
    if '2fa_user_id' not in session:
        return redirect(url_for('auth.login'))

    form = TwoFactorForm()
    if form.validate_on_submit():
        user_id = session['2fa_user_id']
        usuario_service = current_app.config['USUARIO_SERVICE']
        
        # user es el objeto Usuario si el código 2FA es válido
        user = usuario_service.verify_2fa_code(user_id, form.code.data)

        if user:
            # 1. Actualiza el último login
            usuario_service.update_last_login(user_id)

            # 2. Inicia la sesión del usuario
            login_user(user, remember=True)

            # 3. Limpia las variables de sesión 2FA
            session.pop('2fa_user_id', None)
            session.pop('2fa_username', None)
            
            flash(f'Bienvenido de nuevo, {user.nombre_completo or user.username}!', 'success')
            
            # ==========================================================
            # 🔑 LÓGICA DE REDIRECCIÓN CONDICIONAL (CORRECCIÓN CLAVE) 🔑
            # ==========================================================
            
            if user.is_system_admin():
                # Redirige a la nueva ruta visual del rol Sistemas
                return redirect(url_for('sistemas.dashboard'))
            
            # Si no es administrador de sistemas, se va a la ruta predeterminada (Legajos, RRHH)
            return redirect(url_for('index'))
            
            # ==========================================================
            
        else:
            flash('Código de verificación incorrecto o expirado.', 'danger')

    return render_template('auth/verify_2fa.html', form=form, username=session.get('2fa_username'))

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('Has cerrado la sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))