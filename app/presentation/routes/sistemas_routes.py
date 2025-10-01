# RUTA: app/presentation/routes/sistemas_routes.py

from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from app.decorators import role_required # Asumimos que este decorador verifica el rol
from app.application.forms import UserManagementForm # Asumimos un formulario para la gestión de usuarios
import io
from datetime import datetime

# Blueprint para las funcionalidades exclusivas del rol de Sistemas.
sistemas_bp = Blueprint('sistemas', __name__, url_prefix='/sistemas') 

# ------------------------------------------------------------------------
# 1. VISTAS PRINCIPALES DEL DASHBOARD
# ------------------------------------------------------------------------

@sistemas_bp.route('/dashboard')
@login_required
@role_required('Sistemas')
def dashboard():
    """
    Controlador principal del Dashboard de Sistemas. 
    Muestra la vista VISUAL con tarjetas de acceso y monitoreo.
    (Redirección post-login desde auth_routes.py)
    """
    # 🔑 CORRECCIÓN: Carga la vista con íconos y tarjetas (sistemas_inicio.html)
    return render_template('sistemas/sistemas_inicio.html') 


@sistemas_bp.route('/auditoria')
@login_required
@role_required('Sistemas')
def auditoria():
    """
    Vista de Auditoría: Muestra la tabla de logs (el 'puro texto').
    """
    page = request.args.get('page', 1, type=int)
    audit_service = current_app.config['AUDIT_SERVICE']
    
    # Lógica de servicio para obtener los logs paginados
    pagination = audit_service.get_logs(page, 20)
    
    # Registro de auditoría
    audit_service.log(current_user.id, 'Auditoria', 'CONSULTA', f'El usuario consultó la página {page} de la bitácora.')
    
    return render_template('sistemas/auditoria.html', pagination=pagination)


# ------------------------------------------------------------------------
# 2. GESTIÓN DE USUARIOS (Desde la tarjeta 'Gestión de Roles y Usuarios')
# ------------------------------------------------------------------------

@sistemas_bp.route('/usuarios')
@login_required
@role_required('Sistemas')
def gestionar_usuarios():
    """
    Muestra el listado y el control de usuarios del sistema (CRUD).
    """
    usuario_service = current_app.config['USUARIO_SERVICE']
    usuarios = usuario_service.get_all_users_with_roles() 
    
    return render_template('sistemas/gestionar_usuarios.html', usuarios=usuarios)


@sistemas_bp.route('/usuarios/crear', methods=['GET', 'POST'])
@login_required
@role_required('Sistemas')
def crear_usuario():
    # Asumimos que el form está definido en app.application.forms
    form = UserManagementForm() 
    
    if form.validate_on_submit():
        try:
            usuario_service = current_app.config['USUARIO_SERVICE']
            usuario_service.create_user(form.data)
            flash('Usuario creado con éxito.', 'success')
            return redirect(url_for('sistemas.gestionar_usuarios'))
        except Exception as e:
            flash(f'Error al crear usuario: {e}', 'danger')

    return render_template('sistemas/crear_usuario.html', form=form)


@sistemas_bp.route('/usuarios/editar/<int:user_id>', methods=['GET', 'POST'])
@login_required
@role_required('Sistemas')
def editar_usuario(user_id):
    usuario_service = current_app.config['USUARIO_SERVICE']
    user = usuario_service.get_user_by_id(user_id)
    
    if not user:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('sistemas.gestionar_usuarios'))

    form = UserManagementForm(obj=user)
    
    if form.validate_on_submit():
        try:
            usuario_service.update_user(user_id, form.data)
            flash('Usuario actualizado con éxito.', 'success')
            return redirect(url_for('sistemas.gestionar_usuarios'))
        except Exception as e:
            flash(f'Error al actualizar usuario: {e}', 'danger')

    return render_template('sistemas/editar_usuario.html', form=form, user=user)


@sistemas_bp.route('/usuarios/reset_password/<int:user_id>', methods=['POST'])
@login_required
@role_required('Sistemas')
def reset_password(user_id):
    """Resetea la contraseña de un usuario a un valor predeterminado o aleatorio."""
    try:
        usuario_service = current_app.config['USUARIO_SERVICE']
        usuario_service.reset_user_password(user_id) 
        
        flash('Contraseña reseteada con éxito. El usuario deberá cambiarla al iniciar sesión.', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error al resetear contraseña del usuario {user_id}: {e}")
        flash('Ocurrió un error técnico al resetear la contraseña.', 'danger')
        
    return redirect(url_for('sistemas.gestionar_usuarios'))


# ------------------------------------------------------------------------
# 3. MANTENIMIENTO TÉCNICO Y BACKUPS (Desde la tarjeta 'Monitoreo')
# ------------------------------------------------------------------------

@sistemas_bp.route('/mantenimiento/backups')
@login_required
@role_required('Sistemas')
def gestion_backups():
    """
    Vista de gestión y listado de copias de seguridad (Backups).
    """
    # Lógica para obtener el historial de backups y el estado de la configuración
    return render_template('sistemas/gestion_backups.html') 

@sistemas_bp.route('/mantenimiento/run_backup', methods=['POST'])
@login_required
@role_required('Sistemas')
def run_backup():
    """
    Ejecuta una copia de seguridad manual.
    """
    try:
        # Asumimos que BACKUP_SERVICE está configurado en current_app.config
        current_app.config['BACKUP_SERVICE'].execute_full_backup()
        flash('Copia de seguridad iniciada con éxito.', 'success')
    except Exception as e:
        flash(f'Error al ejecutar la copia de seguridad: {e}', 'danger')
        
    return redirect(url_for('sistemas.gestion_backups'))


@sistemas_bp.route('/mantenimiento/estado_servidor')
@login_required
@role_required('Sistemas')
def estado_servidor():
    """
    Vista para el monitoreo de rendimiento de CPU/Memoria y conexiones a BD.
    """
    # Aquí se jalarían los datos técnicos en tiempo real o logs recientes.
    return render_template('sistemas/estado_servidor.html')

@sistemas_bp.route('/errores')
@login_required
@role_required('Sistemas')
def errores():
    """
    Vista para ver el registro de errores críticos de la aplicación.
    """
    # Lógica para obtener los últimos logs de errores de la aplicación
    return render_template('sistemas/registro_errores.html')

# ------------------------------------------------------------------------
# 4. REPORTES TÉCNICOS/AVANZADOS
# ------------------------------------------------------------------------

@sistemas_bp.route('/reportes')
@login_required
@role_required('Sistemas')
def reportes():
    """
    Listado de reportes técnicos avanzados (ej. Reporte de Usuarios Inactivos).
    """
    return render_template('sistemas/reportes.html')


# ------------------------------------------------------------------------
# 5. SOLICITUDES PENDIENTES (Para que funcione el enlace de la tarjeta)
# ------------------------------------------------------------------------

@sistemas_bp.route('/solicitudes')
@login_required
@role_required('Sistemas')
def solicitudes_pendientes():
    """
    Vista para que el Encargado de Sistemas gestione solicitudes 
    (ej. restablecimiento de acceso o peticiones de permisos).
    """
    # Lógica de servicio: Obtener solicitudes pendientes desde la BD
    # solicitudes_service = current_app.config.get('SOLICITUDES_SERVICE')
    # solicitudes = solicitudes_service.get_pending_requests()
    
    # Renderiza la plantilla HTML (que debes crear: solicitudes_pendientes.html)
    return render_template('sistemas/solicitudes_pendientes.html')