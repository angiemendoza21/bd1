
import pyodbc

try:
    conn = pyodbc.connect(
        'DRIVER={SQL Server};'
        'SERVER=LAPTOP-DAYANNA\\SQLEXPRESS;'
        'DATABASE=BD1;'
        'Trusted_Connection=yes;'
    )
    print("Conexión exitosa 🎉 SQL Server conectado.")
except Exception as e:
    print("❌ Error al conectar:")
    print(e)
