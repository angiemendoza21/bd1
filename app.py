import pyodbc
from flask import Flask, render_template, request, redirect, url_for, flash
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from io import BytesIO
from flask import send_file

app = Flask(__name__)
app.secret_key = "cambia_esta_clave"

# -------------------------------------------------------------------
#  CONEXIÓN A SQL SERVER (BD1)
# -------------------------------------------------------------------
def get_connection():                                               # encapsular la conexión, reutilizable,interactuar con la BD
    conn = pyodbc.connect(
        'DRIVER={SQL Server};'
        'SERVER=LAPTOP-DAYANNA\\SQLEXPRESS;' 
        'DATABASE=BD1;'
        'Trusted_Connection=yes;'                                    # autenticación de Windows
    )
    return conn

def rows_to_dicts(cursor):
    """Convierte resultados de pyodbc a lista de diccionarios."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# -------------------------------------------------------------------
#  DASHBOARD
# -------------------------------------------------------------------
@app.route("/")                                                                                                     #asocia una funcion de python a una ruta URL
def dashboard():
    conn = get_connection()                                                                                         #llama a la función de conexión
    cur = conn.cursor()                                                                                             #crear un cursor para ejecutar consultas SQL

    # pedidos del día
    cur.execute("""                    
        SELECT COUNT(*) 
        FROM SDR_T_Pedido
        WHERE Fecha_pedido = CONVERT(date, GETDATE())
    """)
    total_hoy = cur.fetchone()[0]

    # pendientes
    cur.execute("""
        SELECT COUNT(*)
        FROM SDR_T_Pedido P
        JOIN SDR_M_Estado_Pedido E ON P.idEstado_pedido = E.id_estado_pedido
        WHERE E.descripcion = 'Pendiente'
    """)
    total_pendientes = cur.fetchone()[0]

    # entregados
    cur.execute("""
        SELECT COUNT(*)
        FROM SDR_T_Pedido P
        JOIN SDR_M_Estado_Pedido E ON P.idEstado_pedido = E.id_estado_pedido
        WHERE E.descripcion = 'Entregado'
    """)
    total_entregados = cur.fetchone()[0]

    conn.close()
    return render_template(
        "dashboard.html",
        total_hoy=total_hoy,
        total_pendientes=total_pendientes,
        total_entregados=total_entregados
    )

# -------------------------------------------------------------------
#  LISTADO DE PEDIDOS (READ)
# -------------------------------------------------------------------
@app.route("/pedidos")
def pedidos_list():               
    conn = get_connection()       # conexión sql server
    cur = conn.cursor()           # cursor para ejecutar consultas
    cur.execute("""
        SELECT 
            P.id_pedido,
            C.Nombre + ' ' + C.Apellido AS Cliente,
            TP.descripcion AS TipoPedido,
            EP.descripcion AS Estado,
            R.Nombre AS Restaurante,
            M.Descripcion AS Menu,
            P.Fecha_pedido,
            P.Total_pagar
        FROM SDR_T_Pedido P
        JOIN SDR_M_Cliente C ON P.id_cliente = C.id_cliente
        JOIN SDR_M_Tipo_Pedido TP ON P.id_tipo_pedido = TP.id_tipo_pedido
        JOIN SDR_M_Estado_Pedido EP ON P.idEstado_pedido = EP.id_estado_pedido
        JOIN SDR_M_Restaurante R ON P.idRestaurante = R.idRestaurante
        JOIN SDR_M_Menu M ON P.idMenu = M.idMenu
        ORDER BY P.id_pedido DESC
    """)
    
    pedidos = rows_to_dicts(cur)
    
    # Convertir fechas a formato DD/MM/YYYY
    for pedido in pedidos:
        if pedido.get('Fecha_pedido'):
            fecha = pedido['Fecha_pedido']
            # Si es datetime object
            if hasattr(fecha, 'strftime'):
                pedido['Fecha_pedido'] = fecha.strftime('%d/%m/%Y')
            # Si es string tipo "2025-11-21"
            elif isinstance(fecha, str) and '-' in fecha:
                año, mes, dia = fecha.split('-')
                pedido['Fecha_pedido'] = f"{dia}/{mes}/{año}"
    
    conn.close()
    return render_template("pedidos_list.html", pedidos=pedidos)




#(pedido cambiar estado)

@app.route("/pedidos/cambiar_estado", methods=["POST"])
def pedido_cambiar_estado():
    """Cambia el estado de un pedido desde la tabla"""
    id_pedido = request.form.get("id_pedido")
    nuevo_estado = request.form.get("id_estado_pedido")

    if not id_pedido or not nuevo_estado:
        flash("Datos incompletos para cambiar el estado", "danger")
        return redirect(url_for("pedidos_list"))

    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE SDR_T_Pedido
            SET idEstado_pedido = ?
            WHERE id_pedido = ?
        """, (nuevo_estado, id_pedido))
        
        conn.commit()
        flash(f"Estado del pedido #{id_pedido} actualizado correctamente", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error al actualizar el estado: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for("pedidos_list"))


# -------------------------------------------------------------------
#  CARGAR MAESTROS PARA EL FORMULARIO 
# -------------------------------------------------------------------
def cargar_tablas_maestras():
    conn = get_connection()
    cur = conn.cursor()

    def get_all(sql):
        cur.execute(sql)
        return rows_to_dicts(cur)

    clientes      = get_all("SELECT id_cliente, Nombre + ' ' + Apellido AS NombreCompleto FROM SDR_M_Cliente ORDER BY Nombre, Apellido")
    empleados     = get_all("SELECT id_empleado, Nombre + ' ' + Apellido AS NombreCompleto FROM SDR_M_Empleado ORDER BY Nombre, Apellido")
    estados       = get_all("SELECT id_estado_pedido, descripcion FROM SDR_M_Estado_Pedido")
    tipos         = get_all("SELECT id_tipo_pedido, descripcion FROM SDR_M_Tipo_Pedido")
    menus         = get_all("SELECT idMenu, Descripcion, Precio, idRestaurante FROM SDR_M_Menu ORDER BY Descripcion")
    restaurantes  = get_all("SELECT idRestaurante, Nombre FROM SDR_M_Restaurante")
    referencias   = get_all("SELECT idReferencia, descripcion FROM SDR_M_Referencia")
    metodos_pago  = get_all("SELECT idMetodo_de_pago, descripcion FROM SDR_M_Metodo_de_pago")
    costos_pedido = get_all("SELECT id_costo_pedido, descripcion FROM SDR_M_Costo_Pedido")
    costos_entrega= get_all("SELECT id_costo_entrega, descripcion FROM SDR_M_Costo_Entrega")
    repartidores  = get_all("SELECT idRepartidor, Nombre + ' ' + Apellido AS NombreCompleto FROM SDR_M_Repartidor ORDER BY Nombre, Apellido")

    conn.close()

    return dict(
        clientes=clientes,
        empleados=empleados,
        estados=estados,
        tipos=tipos,
        menus=menus,
        restaurantes=restaurantes,
        referencias=referencias,
        metodos_pago=metodos_pago,
        costos_pedido=costos_pedido,
        costos_entrega=costos_entrega,
        repartidores=repartidores
    )

# -------------------------------------------------------------------
#  NUEVO PEDIDO (CREATE)
# -------------------------------------------------------------------
@app.route("/pedidos/nuevo", methods=["GET", "POST"])
def pedido_nuevo():

    # ← Capturar menú seleccionado desde la URL
    menu_id = request.args.get("menu_id")

    if request.method == "POST":
        conn = get_connection()
        cur = conn.cursor()
        pedido = None

        # ============ MANEJAR CLIENTE (NUEVO O EXISTENTE) ============
        nombre_cliente = request.form.get("nombre_cliente")
        id_cliente = request.form.get("id_cliente")
        
        if not id_cliente or id_cliente == '':
            # Cliente nuevo - crear en la base de datos
            cur.execute("SELECT ISNULL(MAX(id_cliente), 0) + 1 FROM SDR_M_Cliente")
            nuevo_id_cliente = cur.fetchone()[0]
            
            # Dividir nombre completo en Nombre y Apellido
            partes_nombre = nombre_cliente.strip().split(' ', 1)
            nombre = partes_nombre[0]
            apellido = partes_nombre[1] if len(partes_nombre) > 1 else ''
            
            cur.execute("""
                INSERT INTO SDR_M_Cliente (id_cliente, Nombre, Apellido)
                VALUES (?, ?, ?)
            """, (nuevo_id_cliente, nombre, apellido))
            conn.commit()
            
            id_cliente = nuevo_id_cliente
        else:
            # Cliente existente
            id_cliente = int(id_cliente)
        # ============ FIN MANEJO CLIENTE ============

        # generar id_pedido = MAX + 1
        cur.execute("SELECT ISNULL(MAX(id_pedido), 0) + 1 FROM SDR_T_Pedido")
        nuevo_id = cur.fetchone()[0]

        # Resto de campos del formulario
        id_empleado        = int(request.form["id_empleado"])
        id_estado_pedido   = int(request.form["id_estado_pedido"])
        id_costo_pedido    = int(request.form["id_costo_pedido"])
        id_tipo_pedido     = int(request.form["id_tipo_pedido"])
        id_menu            = int(request.form["id_menu"])
        id_restaurante     = int(request.form["id_restaurante"])
        id_referencia      = int(request.form["id_referencia"]) if request.form.get("id_referencia") else None
        id_metodo_pago     = int(request.form["id_metodo_pago"])
        id_costo_entrega   = int(request.form["id_costo_entrega"]) if request.form.get("id_costo_entrega") else None
        id_repartidor      = int(request.form["id_repartidor"]) if request.form.get("id_repartidor") else None
        fecha_pedido       = request.form["fecha_pedido"]
        fecha_entrega      = request.form["fecha_entrega"]
        total_pedido       = float(request.form["total_pedido"])
        costo_servicio     = float(request.form["costo_servicio"]) if request.form.get("costo_servicio") else 0.0
        total_pagar        = float(request.form["total_pagar"])

        sql = """
        INSERT INTO SDR_T_Pedido
        (id_pedido, id_cliente, idEmpleado, idEstado_pedido, id_costo_pedido,
         id_tipo_pedido, idMenu, idRestaurante, idReferencia,
         id_comprobante_de_entrega, idMetodo_de_pago, id_costo_entrega,
         idRepartidor, Fecha_pedido, Fecha_entrega, Total_pedido,
         Costo_servicio, Total_pagar)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            nuevo_id, id_cliente, id_empleado, id_estado_pedido, id_costo_pedido,
            id_tipo_pedido, id_menu, id_restaurante, id_referencia,
            None,
            id_metodo_pago, id_costo_entrega,
            id_repartidor, fecha_pedido, fecha_entrega, total_pedido,
            costo_servicio, total_pagar
        )

        cur.execute(sql, params)
        conn.commit()
        conn.close()
        flash(f"Pedido {nuevo_id} creado correctamente", "success")
        return redirect(url_for("pedido_nuevo"))

    # === GET ===
    maestras = cargar_tablas_maestras()

    maestras = cargar_tablas_maestras()

    return render_template(
        "pedido_form.html",
        modo="nuevo",
        pedido=None,
        menu_id_seleccionado=menu_id,  # ← AGREGAR ESTA LÍNEA
        **maestras
    )


# -------------------------------------------------------------------
#  EDITAR PEDIDO (UPDATE)
# -------------------------------------------------------------------
@app.route("/pedidos/editar/<int:id_pedido>", methods=["GET", "POST"])
def pedido_editar(id_pedido):
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        # ============ MANEJAR CLIENTE (NUEVO O EXISTENTE) ============
        nombre_cliente = request.form.get("nombre_cliente")
        id_cliente = request.form.get("id_cliente")
        
        if not id_cliente or id_cliente == '':
            # Cliente nuevo - crear en la base de datos
            cur.execute("SELECT ISNULL(MAX(id_cliente), 0) + 1 FROM SDR_M_Cliente")
            nuevo_id_cliente = cur.fetchone()[0]
            
            # Dividir nombre completo en Nombre y Apellido
            partes_nombre = nombre_cliente.strip().split(' ', 1)
            nombre = partes_nombre[0]
            apellido = partes_nombre[1] if len(partes_nombre) > 1 else ''
            
            cur.execute("""
                INSERT INTO SDR_M_Cliente (id_cliente, Nombre, Apellido)
                VALUES (?, ?, ?)
            """, (nuevo_id_cliente, nombre, apellido))
            conn.commit()
            
            id_cliente = nuevo_id_cliente
        else:
            # Cliente existente
            id_cliente = int(id_cliente)
        # ============ FIN MANEJO CLIENTE ============
        
        id_empleado        = int(request.form["id_empleado"])
        id_estado_pedido   = int(request.form["id_estado_pedido"])
        id_costo_pedido    = int(request.form["id_costo_pedido"])
        id_tipo_pedido     = int(request.form["id_tipo_pedido"])
        id_menu            = int(request.form["id_menu"])
        id_restaurante     = int(request.form["id_restaurante"])
        id_referencia      = int(request.form["id_referencia"]) if request.form.get("id_referencia") else None
        id_metodo_pago     = int(request.form["id_metodo_pago"])
        
        # ⭐ CORREGIDO: Permitir valores vacíos
        id_costo_entrega   = int(request.form["id_costo_entrega"]) if request.form.get("id_costo_entrega") else None
        id_repartidor      = int(request.form["id_repartidor"]) if request.form.get("id_repartidor") else None
        
        fecha_pedido       = request.form["fecha_pedido"]
        fecha_entrega      = request.form["fecha_entrega"]
        total_pedido       = float(request.form["total_pedido"])
        costo_servicio     = float(request.form["costo_servicio"]) if request.form.get("costo_servicio") else 0.0
        total_pagar        = float(request.form["total_pagar"])

        sql = """
        UPDATE SDR_T_Pedido
        SET id_cliente = ?,
            idEmpleado = ?,
            idEstado_pedido = ?,
            id_costo_pedido = ?,
            id_tipo_pedido = ?,
            idMenu = ?,
            idRestaurante = ?,
            idReferencia = ?,
            idMetodo_de_pago = ?,
            id_costo_entrega = ?,
            idRepartidor = ?,
            Fecha_pedido = ?,
            Fecha_entrega = ?,
            Total_pedido = ?,
            Costo_servicio = ?,
            Total_pagar = ?
        WHERE id_pedido = ?
        """
        params = (
            id_cliente, id_empleado, id_estado_pedido, id_costo_pedido,
            id_tipo_pedido, id_menu, id_restaurante, id_referencia,
            id_metodo_pago, id_costo_entrega, id_repartidor,
            fecha_pedido, fecha_entrega, total_pedido,
            costo_servicio, total_pagar, id_pedido
        )

        cur.execute(sql, params)
        conn.commit()
        conn.close()
        flash(f"Pedido {id_pedido} actualizado", "success")
        return redirect(url_for("pedidos_list"))

    # GET: cargar datos del pedido
    cur.execute("""
        SELECT p.*, 
           c.Nombre + ' ' + c.Apellido AS nombre_cliente
    FROM SDR_T_Pedido p
    LEFT JOIN SDR_M_Cliente c ON p.id_cliente = c.id_cliente
    WHERE p.id_pedido = ?
    """, (id_pedido,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("Pedido no encontrado", "warning")
        return redirect(url_for("pedidos_list"))

    cols = [c[0] for c in cur.description]
    pedido = dict(zip(cols, row))
    conn.close()

    maestras = cargar_tablas_maestras()
    return render_template("pedido_form.html", modo="editar", pedido=pedido, **maestras)
# -------------------------------------------------------------------
#  ELIMINAR PEDIDO (DELETE)
# -------------------------------------------------------------------
@app.route("/pedidos/eliminar/<int:id_pedido>", methods=["POST"])
def pedido_eliminar(id_pedido):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM SDR_T_Pago WHERE id_pedido = ?", (id_pedido,))
    cur.execute("DELETE FROM SDR_T_Descripcion_Pedido WHERE id_pedido = ?", (id_pedido,))
    cur.execute("DELETE FROM SDR_T_Pedido WHERE id_pedido = ?", (id_pedido,))
    conn.commit()
    conn.close()
    flash(f"Pedido {id_pedido} eliminado", "warning")
    return redirect(url_for("pedidos_list"))

#------------------------------------------------------------------
#Imprimir PDF de la orden de pedido
#-------------------------------------------------------------------
@app.route("/pedidos/factura_pdf/<int:id_pedido>")
def factura_pdf(id_pedido):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    SELECT 
        P.id_pedido,
        C.Nombre + ' ' + C.Apellido AS Cliente,
        C.Telefono,
        M.Descripcion AS Producto,
        P.Total_pedido,
        P.Costo_servicio,
        P.Total_pagar,
        P.Fecha_pedido
    FROM SDR_T_Pedido P
    JOIN SDR_M_Cliente C ON P.id_cliente = C.id_cliente
    JOIN SDR_M_Menu M ON P.idMenu = M.idMenu
    WHERE P.id_pedido = ?
    """, (id_pedido,))

    row = cur.fetchone()
    
    if not row:
        conn.close()
        flash("Pedido no encontrado", "danger")
        return redirect(url_for("pedidos_list"))
    
    cols = [c[0] for c in cur.description]
    f = dict(zip(cols, row))
    conn.close()

    # ------------ CREAR PDF -----------------
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    # Paleta de colores estilo beige
    color_principal = colors.HexColor("#d7c1a3")
    negro = colors.black

    # Fondo superior decorativo
    pdf.setFillColor(color_principal)
    pdf.rect(0, 720, 850, 120, fill=True, stroke=False)

    # Título FACTURA
    pdf.setFont("Helvetica-Bold", 36)
    pdf.setFillColor(negro)
    pdf.drawString(40, 760, "FACTURA")

    # ---- LOGO GooDPedidos ----
    logo_path = "static/img/logo.png"
    try:
        pdf.drawImage(logo_path, 430, 735, width=130, height=40, mask="auto")
    except:
        print("⚠ No se pudo cargar el logo")

    # ----------- DATOS DEL CLIENTE ----------
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, 710, "DATOS DEL CLIENTE")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, 690, f"{f['Cliente']}")
    pdf.drawString(40, 675, f"Dirección: {f.get('Direccion', 'No registrada')}")
    pdf.drawString(40, 660, f"Teléfono: {f.get('Telefono', 'Sin teléfono')}")

    # ----------- EMPRESA EMISORA ------------
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(350, 710, "ENTIDAD EMISORA")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(350, 690, "GooDPedidos")
    pdf.drawString(350, 675, "Quito - Ecuador")
    pdf.drawString(350, 660, "help@goodpedidos.com")
    pdf.drawString(350, 645, "Tel: 0999999999")

    # ----------- NÚMERO Y FECHA -------------
    fecha_str = f['Fecha_pedido']
    if hasattr(fecha_str, 'strftime'):
        fecha_str = fecha_str.strftime('%d/%m/%Y')
    elif isinstance(fecha_str, str) and '-' in fecha_str:
        partes = fecha_str.split('-')
        if len(partes) == 3:
            fecha_str = f"{partes[2]}/{partes[1]}/{partes[0]}"
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, 630, f"N° FACTURA: GP-{f['id_pedido']}")
    pdf.drawString(40, 615, f"FECHA: {fecha_str}")

    # ----------- TABLA DE PRODUCTOS ---------
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(40, 590, "CANTIDAD")
    pdf.drawString(140, 590, "DESCRIPCIÓN")
    pdf.drawString(330, 590, "PRECIO UNIT.")
    pdf.drawString(450, 590, "IMPORTE")

    pdf.line(40, 585, 550, 585)

    pdf.setFont("Helvetica", 11)
    y = 560
    cantidad = 1
    
    # 🔥 USAR LOS VALORES REALES DE LA BASE DE DATOS
    subtotal = float(f['Total_pedido']) if f['Total_pedido'] else 0.0
    costo_servicio = float(f['Costo_servicio']) if f['Costo_servicio'] else 0.0
    total_pagar = float(f['Total_pagar']) if f['Total_pagar'] else 0.0

    pdf.drawString(40, y, str(cantidad))
    pdf.drawString(140, y, f["Producto"])
    pdf.drawString(330, y, f"${subtotal:.2f}")
    pdf.drawString(450, y, f"${subtotal:.2f}")

    # ----------- RESUMEN DE PAGO ------------
    y -= 60
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(330, y, "Subtotal:")
    pdf.drawString(450, y, f"${subtotal:.2f}")

    y -= 20
    pdf.drawString(330, y, "Servicio:")
    pdf.drawString(450, y, f"${costo_servicio:.2f}")

    y -= 20
    pdf.drawString(330, y, "TOTAL:")
    pdf.drawString(450, y, f"${total_pagar:.2f}")

    # ----------- PIE DE PÁGINA --------------
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, 80, "Gracias por usar GooDPedidos - ¡Buen provecho!")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        mimetype="application/pdf",
        download_name=f"Factura_{f['id_pedido']}.pdf"
    )


# -------------------------------------------------------------------
#  REPORTES / CONSULTAS
# -------------------------------------------------------------------
@app.route("/reportes")
def reportes():
    conn = get_connection()
    cur = conn.cursor()

    # 1) Pedidos facturados en 2024
    cur.execute("""
        SELECT P.id_pedido,
               C.Nombre + ' ' + C.Apellido AS Cliente,
               PG.Monto,
               PG.Fecha_de_pago
        FROM SDR_T_Pago PG
        JOIN SDR_T_Pedido P ON PG.id_pedido = P.id_pedido
        JOIN SDR_M_Cliente C ON P.id_cliente = C.id_cliente
        WHERE YEAR(PG.Fecha_de_pago) = 2024
    """)
    pedidos_2024 = rows_to_dicts(cur)

    # 2) Métodos de pago más usados
    cur.execute("""
        SELECT M.descripcion AS MetodoDePago,
               COUNT(*) AS TotalUsos
        FROM SDR_T_Pago PG
        JOIN SDR_M_Metodo_de_pago M ON PG.idMetodo_de_pago = M.idMetodo_de_pago
        GROUP BY M.descripcion
        ORDER BY TotalUsos DESC
    """)
    metodos_mas_usados = rows_to_dicts(cur)

    # 3) Pedido con monto más alto y qué compró
    cur.execute("""
        SELECT TOP 1
            PG.id_pedido,
            PG.Monto AS Costo,
            PG.Fecha_de_pago,
            M.Descripcion AS ProductoComprado
        FROM SDR_T_Pago PG
        JOIN SDR_T_Pedido P ON PG.id_pedido = P.id_pedido
        JOIN SDR_M_Menu M ON P.idMenu = M.idMenu
        ORDER BY PG.Monto DESC
    """)
    pedido_mas_caro = rows_to_dicts(cur)

    # 4) Clientes que gastaron más
    cur.execute("""
        SELECT TOP 10
            C.Nombre,
            C.Apellido,
            SUM(PG.Monto) AS TotalGastado
        FROM SDR_M_Cliente C
        JOIN SDR_T_Pedido P ON C.id_cliente = P.id_cliente
        JOIN SDR_T_Pago PG ON PG.id_pedido = P.id_pedido
        GROUP BY C.Nombre, C.Apellido
        ORDER BY TotalGastado DESC
    """)
    clientes_top = rows_to_dicts(cur)

    conn.close()
    return render_template(
        "reportes.html",
        pedidos_2024=pedidos_2024,
        metodos_mas_usados=metodos_mas_usados,
        pedido_mas_caro=pedido_mas_caro,
        clientes_top=clientes_top
    )


@app.route("/menu")

def ver_menu():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT idMenu, Descripcion FROM SDR_M_Menu")
    menus = rows_to_dicts(cur)
    conn.close()
    return render_template("menu.html", menus=menus)



# -------------------------------------------------------------------

@app.route("/menus")
def menus_list():
    conn = get_connection()
    cur = conn.cursor()

    # ===== DEBUG =====
    cur.execute("SELECT DB_NAME()")
    print("🔥 Base actual realmente usada por Flask:", cur.fetchone()[0])
    # ==================

    cur.execute("""
        SELECT 
            M.idMenu,
            M.Descripcion,
            M.idRestaurante,
            M.Imagen,
            M.Precio
        FROM SDR_M_Menu M
        ORDER BY M.idMenu
    """)

    menus = rows_to_dicts(cur)
    conn.close()
    return render_template("menu_list.html", menus=menus)



if __name__ == "__main__":
    app.run(debug=True)