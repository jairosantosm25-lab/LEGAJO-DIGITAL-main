# RUTA: app/infrastructure/persistence/sqlserver_repository.py

# RUTA: app/infrastructure/persistence/sqlserver_repository.py

from app.database.connector import get_db_read, get_db_write
from app.domain.models.usuario import Usuario
from app.domain.models.personal import Personal
from app.domain.repositories.i_usuario_repository import IUsuarioRepository
from app.domain.repositories.i_personal_repository import IPersonalRepository
from app.domain.repositories.i_auditoria_repository import IAuditoriaRepository
from app.utils.pagination import SimplePagination

def _row_to_dict(cursor, row):
    if not row: return None
    # Función de utilidad para convertir una fila del cursor a un diccionario
    return dict(zip([column[0] for column in cursor.description], row))

class SqlServerUsuarioRepository(IUsuarioRepository):
    
    # -------------------------------------------------------------
    # 🔑 CORRECCIÓN CLAVE: MÉTODO AÑADIDO PARA LISTAR USUARIOS 🔑
    # -------------------------------------------------------------
    def find_all_users_with_roles(self):
        """
        Obtiene la lista completa de usuarios con sus roles y estados para 
        la tabla de Gestión de Usuarios.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        
        # Asumimos que este SP existe y retorna los campos necesarios:
        # id, username, nombre_completo, rol_nombre, last_login, is_active/activo.
        query = "{CALL p_obtener_usuarios_para_gestion}"
        cursor.execute(query)
        
        # 1. Obtener la lista de diccionarios desde la BD
        results = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        
        # 2. Mapear cada diccionario al objeto Usuario.
        # Esto asume que Usuario.from_dict sabe cómo manejar los campos de rol.
        return [Usuario.from_dict(d) for d in results]

    # -------------------------------------------------------------
    # FIN DEL MÉTODO AÑADIDO
    # -------------------------------------------------------------

    def find_by_id(self, user_id):
        conn = get_db_read()
        cursor = conn.cursor()
        query = "{CALL sp_obtener_usuario_por_id(?)}"
        cursor.execute(query, user_id)
        row_dict = _row_to_dict(cursor, cursor.fetchone())
        return Usuario.from_dict(row_dict)

    def find_by_username_with_email(self, username):
        conn = get_db_read()
        cursor = conn.cursor()
        query = "{CALL sp_obtener_usuario_por_username(?)}"
        cursor.execute(query, username)
        row_dict = _row_to_dict(cursor, cursor.fetchone())
        return Usuario.from_dict(row_dict)

    def set_2fa_code(self, user_id, hashed_code, expiry_date):
        conn = get_db_write()
        cursor = conn.cursor()
        query = "UPDATE usuarios SET two_factor_code = ?, two_factor_expiry = ? WHERE id_usuario = ?"
        cursor.execute(query, hashed_code, expiry_date, user_id)
        conn.commit()

    def clear_2fa_code(self, user_id):
        conn = get_db_write()
        cursor = conn.cursor()
        query = "UPDATE usuarios SET two_factor_code = NULL, two_factor_expiry = NULL WHERE id_usuario = ?"
        cursor.execute(query, user_id)
        conn.commit()

    def update_password_hash(self, username, new_hash):
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_actualizar_password_usuario(?, ?)}", username, new_hash)
        conn.commit()     

    def update_last_login(self, user_id):
        """Llama a un SP para actualizar la fecha del último login."""
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_actualizar_ultimo_login(?)}", user_id)
        conn.commit()

# --- REPOSITORIO DE PERSONAL ---
# Implementación completa del repositorio de personal.
class SqlServerPersonalRepository(IPersonalRepository):

    def check_dni_exists(self, dni):
        """Verifica si un DNI ya existe en la tabla de personal."""
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM personal WHERE dni = ?", dni)
        return cursor.fetchone() is not None

    def get_all_documents_with_expiration(self):
        """Llama al SP para obtener todos los documentos activos con fecha de vencimiento."""
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_listar_documentos_con_vencimiento}")
        return [_row_to_dict(cursor, row) for row in cursor.fetchall()]


    def find_document_by_id(self, document_id):
        """
        Llama al SP para obtener los datos de un único documento por su ID.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_obtener_documento_por_id(?)}", document_id)
        return cursor.fetchone()

    def delete_document_by_id(self, document_id):
        """
        Llama al SP para la eliminación lógica de un documento.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_eliminar_documento_logico(?)}", document_id)
        conn.commit()


    def find_tipos_documento_by_seccion(self, id_seccion):
        """
        Llama a un procedimiento almacenado para obtener los tipos de documento 
        asociados a una sección.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        
        cursor.execute("{CALL sp_listar_tipos_documento_por_seccion(?)}", id_seccion)
        
        # Devuelve una lista de diccionarios, ideal para ser convertida a JSON
        return [{"id": row.id_tipo, "nombre": row.nombre_tipo} for row in cursor.fetchall()]


    # Llama a un SP para obtener la lista de documentos de un empleado.
    def find_documents_by_personal_id(self, personal_id):
        conn = get_db_read()
        cursor = conn.cursor()
        # Este SP debe devolver la lista de documentos para un id_personal.
        cursor.execute("{CALL sp_listar_documentos_por_personal(?)}", personal_id)
        # Se asume que el SP devuelve filas que se pueden mapear al modelo Documento.
        return [_row_to_dict(cursor, row) for row in cursor.fetchall()]

    def get_full_legajo_by_id(self, personal_id):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_obtener_legajo_completo_por_personal(?)}", personal_id)
        
        # El primer resultado es la información del personal.
        personal_info = _row_to_dict(cursor, cursor.fetchone())
        if not personal_info:
            return None # Si no hay datos personales, el legajo no existe.

        legajo = {"personal": personal_info}
        
        # Se procesan los siguientes conjuntos de resultados.
        if cursor.nextset(): legajo["estudios"] = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        if cursor.nextset(): legajo["capacitaciones"] = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        if cursor.nextset(): legajo["contratos"] = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        if cursor.nextset(): legajo["historial_laboral"] = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        if cursor.nextset(): legajo["licencias"] = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        if cursor.nextset(): legajo["documentos"] = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            
        return legajo
    
    # Llama a un SP para listar, filtrar y paginar al personal.
    def get_all_paginated(self, page, per_page, filters):
        conn = get_db_read()
        cursor = conn.cursor()
        dni_filter = filters.get('dni') if filters else None
        nombres_filter = filters.get('nombres') if filters else None
        
        cursor.execute("{CALL sp_listar_personal_paginado(?, ?, ?, ?)}", page, per_page, dni_filter, nombres_filter)
        results = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        
        cursor.nextset()
        total = cursor.fetchone()[0]
        return SimplePagination(results, page, per_page, total)

    # Llama a un SP para crear un nuevo registro de personal.
    def create(self, form_data):
        conn = get_db_write()
        cursor = conn.cursor()
        params = (form_data.get('dni'), form_data.get('nombres'), form_data.get('apellidos'), form_data.get('sexo'),
                  form_data.get('fecha_nacimiento'), form_data.get('direccion'), form_data.get('telefono'),
                  form_data.get('email'), form_data.get('estado_civil'), form_data.get('nacionalidad'),
                  form_data.get('id_unidad'), form_data.get('fecha_ingreso'))
        cursor.execute("{CALL sp_registrar_personal(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", params)
        new_id = cursor.fetchone()[0]
        conn.commit()
        return new_id
    
    # Llama a un SP para añadir un documento.
    def add_document(self, doc_data, file_bytes):
        conn = get_db_write()
        cursor = conn.cursor()
        params = (
            doc_data.get('id_personal'), 
            doc_data.get('id_tipo'), 
            doc_data.get('id_seccion'),
            doc_data.get('nombre_archivo'), 
            doc_data.get('fecha_emision'), 
            doc_data.get('fecha_vencimiento'),
            doc_data.get('descripcion'), 
            file_bytes, 
            doc_data.get('hash_archivo')
        )
        cursor.execute("{CALL sp_subir_documento(?, ?, ?, ?, ?, ?, ?, ?, ?)}", params)
        conn.commit()
    
    # Métodos para obtener listas para los formularios SelectField.
    def get_unidades_for_select(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT id_unidad, nombre FROM unidad_administrativa ORDER BY nombre")
        return [(row.id_unidad, row.nombre) for row in cursor.fetchall()]

    def get_secciones_for_select(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT id_seccion, nombre_seccion FROM legajo_secciones ORDER BY id_seccion")
        return [(row.id_seccion, row.nombre_seccion) for row in cursor.fetchall()]

    def get_tipos_documento_by_seccion(self, seccion_id):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_listar_tipos_documento_por_seccion(?)}", seccion_id)
        return [(row.id_tipo, row.nombre_tipo) for row in cursor.fetchall()]


    def get_tipos_documento_for_select(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("SELECT id_tipo, nombre_tipo FROM tipo_documento ORDER BY nombre_tipo")
        return [(row.id_tipo, row.nombre_tipo) for row in cursor.fetchall()]

    # Implementación del método de actualización.
    def update(self, personal_id, form_data):
        conn = get_db_write()
        cursor = conn.cursor()
        # Llama a un SP para actualizar los datos del personal.
        # El SP debe estar preparado para recibir todos los campos del formulario.
        params = (
            personal_id,
            form_data.get('dni'),
            form_data.get('nombres'),
            form_data.get('apellidos'),
            form_data.get('sexo'),
            form_data.get('fecha_nacimiento'),
            form_data.get('direccion'),
            form_data.get('telefono'),
            form_data.get('email'),
            form_data.get('estado_civil'),
            form_data.get('nacionalidad'),
            form_data.get('id_unidad'),
            form_data.get('fecha_ingreso')
        )
        cursor.execute("{CALL sp_actualizar_personal(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)}", params)
        conn.commit()


    # Llama a un SP para obtener todos los datos necesarios para el reporte general.
    def get_all_for_report(self):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_generar_reporte_general_personal}")
        return [_row_to_dict(cursor, row) for row in cursor.fetchall()]     
    
    # Llama al SP para el borrado suave (desactivación) de un empleado.
    def delete_by_id(self, personal_id):
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_eliminar_personal(?)}", personal_id)
        conn.commit()
        
    def find_by_id(self, personal_id):
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_obtener_personal_por_id(?)}", personal_id)
        row = cursor.fetchone()
        return Personal.from_dict(_row_to_dict(cursor, row)) if row else None

    def get_tipos_documento_by_seccion(self, id_seccion):
        """
        Llama a un SP para obtener los tipos de documento asociados a una sección
        y los devuelve en un formato ideal para JSON.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_listar_tipos_documento_por_seccion(?)}", id_seccion)
        # Devuelve directamente una lista de diccionarios
        return [{"id": row.id_tipo, "nombre": row.nombre_tipo} for row in cursor.fetchall()]     

# --- REPOSITORIO DE AUDITORÍA ---
# Implementación completa y corregida del repositorio de auditoría.
class SqlServerAuditoriaRepository(IAuditoriaRepository):
    # Llama a un SP para registrar un evento en la bitácora.
    def log_event(self, id_usuario, modulo, accion, descripcion, detalle_json=None):
        conn = get_db_write()
        cursor = conn.cursor()
        cursor.execute("{CALL sp_registrar_bitacora(?, ?, ?, ?, ?)}", id_usuario, modulo, accion, descripcion, detalle_json)
        conn.commit()

    # Obtiene los logs de forma paginada.
    def get_all_logs_paginated(self, page, per_page):
        conn = get_db_read()
        cursor = conn.cursor()
        # Llama a un SP que maneja la paginación de la tabla bitacora.
        cursor.execute("{CALL sp_listar_bitacora_paginada(?, ?)}", page, per_page)
        # Procesa los resultados.
        results = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        # Obtiene el total de registros para los controles de paginación.
        cursor.nextset()
        total = cursor.fetchone()[0]
        return SimplePagination(results, page, per_page, total)
    

# --- REPOSITORIO DE SOLICITUDES DE MODIFICACIÓN ---
# Asume que tienes una interfaz I_solicitud_repository definida en tu capa domain.
# Si no la tienes, puedes simplemente hacer que esta clase no extienda nada por ahora.

class SqlServerSolicitudRepository: # Si no tienes la interfaz, usa esto
# class SqlServerSolicitudRepository(ISolicitudRepository): # Si tienes la interfaz
    
    def get_pending_requests(self):
        """
        Llama al SP para obtener la lista de solicitudes PENDIENTES.
        """
        conn = get_db_read()
        cursor = conn.cursor()
        
        # 🔑 CORRECCIÓN: Llamada al SP de gestión con el parámetro 'LISTAR' 🔑
        # Asumimos que el SP requiere un parámetro de acción ('LISTAR') y un ID (None)
        query = "{CALL sp_gestionar_solicitud_modificacion(?, ?)}"
        
        # El SP debe estar programado para devolver el listado cuando 'LISTAR' es el primer parámetro
        cursor.execute(query, 'LISTAR', None) 
        
        results = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        
        # Nota: Aquí deberías mapear los resultados a un objeto Solicitud,
        # pero devolveremos el diccionario para simplificar y pasar a la plantilla.
        return results

    def process_request(self, request_id, action):
        """
        Procesa (APRUEBA/RECHAZA) una solicitud por su ID.
        """
        conn = get_db_write()
        cursor = conn.cursor()
        
        # 🔑 CORRECCIÓN: Llamada al SP de gestión para APROBAR/RECHAZAR 🔑
        # 'action' será 'APROBAR' o 'RECHAZAR' desde la ruta de Flask
        query = "{CALL sp_gestionar_solicitud_modificacion(?, ?)}"
        
        # El SP debe recibir la acción (APROBAR/RECHAZAR) y el ID de la solicitud
        cursor.execute(query, action.upper(), request_id) 
        conn.commit()
        
        # El SP debe actualizar el campo de Legajo si es aprobación.
        # Asumimos que el SP maneja la lógica de actualización/rechazo.
        return True