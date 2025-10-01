# Importa la librería pyodbc para la conexión con SQL Server y Flask's 'g' y 'current_app'.
import pyodbc
from flask import g, current_app

# Define una función auxiliar interna para crear una conexión a la base de datos.
def _get_db_connection(username, password):
    try:
        # Construye la cadena de conexión usando la configuración de la aplicación.
        conn_str = (
            f"DRIVER={current_app.config['DB_DRIVER']};"
            f"SERVER={current_app.config['DB_SERVER']};"
            f"DATABASE={current_app.config['DB_DATABASE']};"
            f"UID={username};"
            f"PWD={password};"
        )
        # Establece y devuelve la conexión.
        return pyodbc.connect(conn_str)
    except pyodbc.Error as ex:
        # Si hay un error, lo registra en el log de la aplicación y lo relanza.
        current_app.logger.error(f"Error de conexión a la BD con usuario {username}: {ex}")
        raise

# Define una función para obtener una conexión de SOLO LECTURA.
# Utiliza el objeto 'g' de Flask para almacenar la conexión durante el ciclo de una petición.
def get_db_read():
    if 'db_read' not in g:
        # Si no hay conexión de lectura en 'g', crea una nueva con las credenciales de lectura.
        g.db_read = _get_db_connection(
            current_app.config['DB_USERNAME_READ'],
            current_app.config['DB_PASSWORD_READ']
        )
    return g.db_read

# Define una función para obtener una conexión de LECTURA/ESCRITURA.
def get_db_write():
    if 'db_write' not in g:
        # Si no hay conexión de escritura en 'g', crea una nueva con las credenciales de escritura.
        g.db_write = _get_db_connection(
            current_app.config['DB_USERNAME_WRITE'],
            current_app.config['DB_PASSWORD_WRITE']
        )
    return g.db_write

# Define una función para cerrar las conexiones al final de la petición.
def close_db(e=None):
    # Busca y cierra la conexión de lectura si existe.
    db_read = g.pop('db_read', None)
    if db_read is not None:
        db_read.close()
    
    # Busca y cierra la conexión de escritura si existe.
    db_write = g.pop('db_write', None)
    if db_write is not None:
        db_write.close()

# Define una función para inicializar el manejo de la base de datos en la aplicación Flask.
def init_app_db(app):
    # Registra la función 'close_db' para que se ejecute al final de cada contexto de aplicación.
    app.teardown_appcontext(close_db) 
