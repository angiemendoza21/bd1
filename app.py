import pyodbc
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, render_template, request, redirect, url_for, flash
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from io import BytesIO
from flask import send_file

app = Flask(__name__)
app.secret_key = "cambia_esta_clave"
IVA_RATE = Decimal("0.15")

# -------------------------------------------------------------------
#  CONEXIÓN A SQL SERVER (BD1)
# -------------------------------------------------------------------
def get_connection():
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=JOEL2004\\SQLEXPRESS;'
        'DATABASE=BD1;'
        'Trusted_Connection=yes;'
        'TrustServerCertificate=yes;'
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
    selected_menu_ids = []

    def _append_from_raw(raw_value):
        if raw_value is None:
            return
        for piece in str(raw_value).split(','):
            piece = piece.strip()
            if piece.isdigit():
                selected_menu_ids.append(int(piece))

    if request.args:
        for value in request.args.getlist("menu_id"):
            _append_from_raw(value)
        _append_from_raw(request.args.get("menu_id"))
        _append_from_raw(request.args.get("menu_ids"))

    if request.method == "POST":
        conn = get_connection()
        cur = conn.cursor()
        pedido = None

        selected_menu_ids_form = []
        for raw_menu_id in request.form.getlist("selected_menu_ids"):
            raw_menu_id = raw_menu_id.strip()
            if raw_menu_id.isdigit():
                selected_menu_ids_form.append(int(raw_menu_id))

        id_menu_form_value = request.form.get("id_menu")

        if not selected_menu_ids_form and not id_menu_form_value:
            conn.close()
            flash("Selecciona al menos un menú antes de guardar el pedido.", "danger")
            return redirect(url_for("pedido_nuevo"))

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

        if selected_menu_ids_form:
            id_menu = selected_menu_ids_form[0]
        else:
            id_menu = int(id_menu_form_value)

        id_restaurante_raw = request.form.get("id_restaurante")
        if id_restaurante_raw:
            id_restaurante = int(id_restaurante_raw)
        elif selected_menu_ids_form:
            cur.execute(
                "SELECT TOP 1 idRestaurante FROM SDR_M_Menu WHERE idMenu = ?",
                (selected_menu_ids_form[0],)
            )
            fetched = cur.fetchone()
            id_restaurante = fetched[0] if fetched else None
        else:
            id_restaurante = None

        if id_restaurante is None:
            conn.rollback()
            conn.close()
            flash("No se pudo determinar el restaurante principal del pedido. Selecciona nuevamente los menús.", "danger")
            if selected_menu_ids_form:
                menu_ids_query = ",".join(str(mid) for mid in selected_menu_ids_form)
                return redirect(url_for("pedido_nuevo", menu_ids=menu_ids_query))
            return redirect(url_for("pedido_nuevo"))

        id_referencia      = int(request.form["id_referencia"]) if request.form.get("id_referencia") else None
        id_metodo_pago     = int(request.form["id_metodo_pago"])
        id_costo_entrega   = int(request.form["id_costo_entrega"]) if request.form.get("id_costo_entrega") else None
        id_repartidor      = int(request.form["id_repartidor"]) if request.form.get("id_repartidor") else None
        direccion_entrega_raw = (request.form.get("direccion_entrega") or "").strip()
        direccion_entrega  = direccion_entrega_raw if direccion_entrega_raw else None
        fecha_pedido       = request.form.get("fecha_pedido")
        fecha_entrega_raw  = (request.form.get("fecha_entrega") or "").strip()
        hora_entrega_raw   = (request.form.get("hora_entrega") or "").strip()
        fecha_entrega      = fecha_entrega_raw if fecha_entrega_raw else None
        if fecha_entrega and hora_entrega_raw:
            fecha_entrega = f"{fecha_entrega} {hora_entrega_raw}"
        total_pedido       = float(request.form["total_pedido"])
        costo_servicio     = float(request.form["costo_servicio"]) if request.form.get("costo_servicio") else 0.0

        base_total = Decimal(str(total_pedido)) + Decimal(str(costo_servicio))
        total_pagar_decimal = (base_total * (Decimal("1") + IVA_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_pagar = float(total_pagar_decimal)

        sql = """
        INSERT INTO SDR_T_Pedido
        (id_pedido, id_cliente, idEmpleado, idEstado_pedido, id_costo_pedido,
         id_tipo_pedido, idMenu, idRestaurante, idReferencia,
         id_comprobante_de_entrega, idMetodo_de_pago, id_costo_entrega,
         idRepartidor, Fecha_pedido, Fecha_entrega, Direccion_entrega, Total_pedido,
         Costo_servicio, Total_pagar)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            nuevo_id, id_cliente, id_empleado, id_estado_pedido, id_costo_pedido,
            id_tipo_pedido, id_menu, id_restaurante, id_referencia,
            None,
            id_metodo_pago, id_costo_entrega,
            id_repartidor, fecha_pedido, fecha_entrega, direccion_entrega, total_pedido,
            costo_servicio, total_pagar
        )

        cur.execute(sql, params)

        detalle_menu_ids = selected_menu_ids_form if selected_menu_ids_form else [id_menu]
        if detalle_menu_ids:
            cur.execute("SELECT ISNULL(MAX(id_descripcion_pedido), 0) FROM SDR_T_Descripcion_Pedido")
            max_detalle_id = cur.fetchone()[0] or 0
            siguiente_detalle_id = max_detalle_id + 1

            for menu_detalle_id in detalle_menu_ids:
                cur.execute(
                    """
                    SELECT M.Descripcion, ISNULL(R.Nombre, '') AS Restaurante
                    FROM SDR_M_Menu M
                    LEFT JOIN SDR_M_Restaurante R ON M.idRestaurante = R.idRestaurante
                    WHERE M.idMenu = ?
                    """,
                    (menu_detalle_id,)
                )
                menu_detalle = cur.fetchone()
                if menu_detalle:
                    descripcion_menu, restaurante_menu = menu_detalle
                    descripcion_detalle = descripcion_menu
                    if restaurante_menu:
                        descripcion_detalle = f"{descripcion_menu} - {restaurante_menu}"
                else:
                    descripcion_detalle = "Menú sin detalle"

                cur.execute(
                    """
                    INSERT INTO SDR_T_Descripcion_Pedido (id_descripcion_pedido, id_pedido, id_menu, Descripcion)
                    VALUES (?, ?, ?, ?)
                    """,
                    (siguiente_detalle_id, nuevo_id, menu_detalle_id, descripcion_detalle)
                )
                siguiente_detalle_id += 1

        conn.commit()
        conn.close()
        flash(f"Pedido {nuevo_id} creado correctamente", "success")
        return redirect(url_for("pedido_nuevo"))

    # === GET ===
    maestras = cargar_tablas_maestras()
    restaurantes_map = {r["idRestaurante"]: r["Nombre"] for r in maestras["restaurantes"]}
    menus_seleccionados = []
    subtotal_preseleccionado = Decimal("0")
    restaurantes_seleccionados = []
    restaurantes_vistos = set()

    if selected_menu_ids:
        menu_counts = {}
        ordered_ids = []
        for menu_id in selected_menu_ids:
            if menu_id not in menu_counts:
                ordered_ids.append(menu_id)
                menu_counts[menu_id] = 0
            menu_counts[menu_id] += 1

        for menu_id in ordered_ids:
            menu = next((m for m in maestras["menus"] if m["idMenu"] == menu_id), None)
            if not menu:
                continue
            cantidad = menu_counts.get(menu_id, 1)
            precio_decimal = Decimal(str(menu.get("Precio", 0)))
            total_menu = precio_decimal * Decimal(cantidad)
            subtotal_preseleccionado += total_menu
            nombre_restaurante = restaurantes_map.get(menu.get("idRestaurante"))
            if menu.get("idRestaurante") and menu["idRestaurante"] not in restaurantes_vistos:
                restaurantes_seleccionados.append({
                    "idRestaurante": menu["idRestaurante"],
                    "Nombre": nombre_restaurante
                })
                restaurantes_vistos.add(menu["idRestaurante"])

            menus_seleccionados.append({
                "idMenu": menu["idMenu"],
                "Descripcion": menu.get("Descripcion"),
                "Precio": float(precio_decimal),
                "PrecioTexto": f"{precio_decimal:.2f}",
                "Subtotal": float(total_menu),
                "SubtotalTexto": f"{total_menu:.2f}",
                "Cantidad": cantidad,
                "idRestaurante": menu.get("idRestaurante"),
                "Restaurante": nombre_restaurante
            })

    menu_id = selected_menu_ids[0] if selected_menu_ids else None

    return render_template(
        "pedido_form.html",
        modo="nuevo",
        pedido=None,
        menu_id_seleccionado=menu_id,
        menus_seleccionados=menus_seleccionados,
        restaurantes_seleccionados=restaurantes_seleccionados,
        subtotal_preseleccionado=float(subtotal_preseleccionado),
        iva_rate=float(IVA_RATE),
        tiene_menus_seleccionados=bool(menus_seleccionados),
        fecha_entrega_value="",
        hora_entrega_value="",
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
        direccion_entrega_raw = (request.form.get("direccion_entrega") or "").strip()
        direccion_entrega  = direccion_entrega_raw if direccion_entrega_raw else None
        
        fecha_pedido       = request.form.get("fecha_pedido")
        fecha_entrega_raw  = (request.form.get("fecha_entrega") or "").strip()
        hora_entrega_raw   = (request.form.get("hora_entrega") or "").strip()
        fecha_entrega      = fecha_entrega_raw if fecha_entrega_raw else None
        if fecha_entrega and hora_entrega_raw:
            fecha_entrega = f"{fecha_entrega} {hora_entrega_raw}"
        total_pedido       = float(request.form["total_pedido"])
        costo_servicio     = float(request.form["costo_servicio"]) if request.form.get("costo_servicio") else 0.0

        base_total = Decimal(str(total_pedido)) + Decimal(str(costo_servicio))
        total_pagar_decimal = (base_total * (Decimal("1") + IVA_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_pagar        = float(total_pagar_decimal)

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
            Direccion_entrega = ?,
            Total_pedido = ?,
            Costo_servicio = ?,
            Total_pagar = ?
        WHERE id_pedido = ?
        """
        params = (
            id_cliente, id_empleado, id_estado_pedido, id_costo_pedido,
            id_tipo_pedido, id_menu, id_restaurante, id_referencia,
            id_metodo_pago, id_costo_entrega, id_repartidor,
            fecha_pedido, fecha_entrega, direccion_entrega, total_pedido,
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

    fecha_entrega_value = ""
    hora_entrega_value = ""
    fecha_entrega_raw = pedido.get("Fecha_entrega")
    if fecha_entrega_raw:
        if hasattr(fecha_entrega_raw, "strftime"):
            fecha_entrega_value = fecha_entrega_raw.strftime("%Y-%m-%d")
            hora_entrega_value = fecha_entrega_raw.strftime("%H:%M")
        elif isinstance(fecha_entrega_raw, str):
            fecha_part = fecha_entrega_raw.strip()
            time_part = ""
            if "T" in fecha_part:
                fecha_part, time_part = fecha_part.split("T", 1)
            elif " " in fecha_part:
                fecha_part, time_part = fecha_part.split(" ", 1)
            if fecha_part:
                fecha_entrega_value = fecha_part
            if time_part:
                hora_entrega_value = time_part[:5]

    maestras = cargar_tablas_maestras()
    return render_template(
        "pedido_form.html",
        modo="editar",
        pedido=pedido,
        menus_seleccionados=None,
        restaurantes_seleccionados=None,
        subtotal_preseleccionado=0.0,
        iva_rate=float(IVA_RATE),
        tiene_menus_seleccionados=False,
        fecha_entrega_value=fecha_entrega_value,
        hora_entrega_value=hora_entrega_value,
        **maestras
    )
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
        P.Direccion_entrega,
        P.Total_pedido,
        P.Costo_servicio,
        P.Total_pagar,
        P.Fecha_pedido
    FROM SDR_T_Pedido P
    JOIN SDR_M_Cliente C ON P.id_cliente = C.id_cliente
    WHERE P.id_pedido = ?
    """, (id_pedido,))

    row = cur.fetchone()

    if not row:
        conn.close()
        flash("Pedido no encontrado", "danger")
        return redirect(url_for("pedidos_list"))

    cols = [c[0] for c in cur.description]
    pedido_data = dict(zip(cols, row))

    cur.execute(
        """
        SELECT 
            D.id_descripcion_pedido,
            ISNULL(M.Descripcion, D.Descripcion) AS MenuDescripcion,
            M.Precio,
            R.Nombre AS Restaurante
        FROM SDR_T_Descripcion_Pedido D
        LEFT JOIN SDR_M_Menu M ON D.id_menu = M.idMenu
        LEFT JOIN SDR_M_Restaurante R ON M.idRestaurante = R.idRestaurante
        WHERE D.id_pedido = ?
        ORDER BY D.id_descripcion_pedido
        """,
        (id_pedido,)
    )
    detalles = rows_to_dicts(cur)

    if not detalles:
        cur.execute(
            """
            SELECT 
                M.Descripcion AS MenuDescripcion,
                M.Precio,
                R.Nombre AS Restaurante
            FROM SDR_T_Pedido P
            LEFT JOIN SDR_M_Menu M ON P.idMenu = M.idMenu
            LEFT JOIN SDR_M_Restaurante R ON M.idRestaurante = R.idRestaurante
            WHERE P.id_pedido = ?
            """,
            (id_pedido,)
        )
        detalles = rows_to_dicts(cur)

    conn.close()

    items = []
    subtotal_items = Decimal("0")
    for detalle in detalles:
        descripcion_menu = detalle.get("MenuDescripcion") or "Producto"
        restaurante = detalle.get("Restaurante") or "Sin restaurante"
        precio = detalle.get("Precio")
        try:
            precio_decimal = Decimal(str(precio)) if precio is not None else Decimal("0")
        except Exception:
            precio_decimal = Decimal("0")
        subtotal_items += precio_decimal
        items.append({
            "descripcion": descripcion_menu,
            "restaurante": restaurante,
            "precio": precio_decimal
        })

    subtotal_registrado = Decimal(str(pedido_data.get("Total_pedido") or 0))
    if subtotal_items == 0 and subtotal_registrado:
        subtotal_items = Decimal(str(subtotal_registrado))

    costo_servicio = Decimal(str(pedido_data.get("Costo_servicio") or 0))
    total_pagar = Decimal(str(pedido_data.get("Total_pagar") or 0))
    base_sin_iva = subtotal_items + costo_servicio
    iva_decimal = (total_pagar - base_sin_iva) if total_pagar > base_sin_iva else Decimal("0")
    iva_decimal = iva_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    subtotal_items = subtotal_items.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    costo_servicio = costo_servicio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_pagar = total_pagar.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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
    pdf.drawString(40, 690, f"{pedido_data['Cliente']}")
    direccion_cliente = pedido_data.get('Direccion_entrega') or pedido_data.get('Direccion') or 'No registrada'
    pdf.drawString(40, 675, f"Dirección: {direccion_cliente}")
    pdf.drawString(40, 660, f"Teléfono: {pedido_data.get('Telefono', 'Sin teléfono')}")

    # ----------- EMPRESA EMISORA ------------
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(350, 710, "ENTIDAD EMISORA")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(350, 690, "GooDPedidos")
    pdf.drawString(350, 675, "Quito - Ecuador")
    pdf.drawString(350, 660, "help@goodpedidos.com")
    pdf.drawString(350, 645, "Tel: 0999999999")

    # ----------- NÚMERO Y FECHA -------------
    fecha_str = pedido_data['Fecha_pedido']
    if hasattr(fecha_str, 'strftime'):
        fecha_str = fecha_str.strftime('%d/%m/%Y')
    elif isinstance(fecha_str, str) and '-' in fecha_str:
        partes = fecha_str.split('-')
        if len(partes) == 3:
            fecha_str = f"{partes[2]}/{partes[1]}/{partes[0]}"
    
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, 630, f"N° FACTURA: GP-{pedido_data['id_pedido']}")
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
    linea_altura = 32

    if not items:
        items.append({
            "descripcion": "Productos del pedido",
            "restaurante": "",
            "precio": subtotal_items
        })

    pdf.setFont("Helvetica", 11)
    for item in items:
        pdf.setFont("Helvetica", 11)
        pdf.drawString(40, y, "1")
        descripcion_linea = item["descripcion"]
        pdf.drawString(140, y, descripcion_linea)
        if item["restaurante"]:
            pdf.setFont("Helvetica-Oblique", 9)
            pdf.drawString(140, y - 12, f"Restaurante: {item['restaurante']}")
            pdf.setFont("Helvetica", 11)
        precio_float = float(item["precio"])
        pdf.drawString(330, y, f"${precio_float:.2f}")
        pdf.drawString(450, y, f"${precio_float:.2f}")
        y -= linea_altura

    # ----------- RESUMEN DE PAGO ------------
    y -= 20
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(330, y, "Subtotal:")
    pdf.drawString(450, y, f"${float(subtotal_items):.2f}")

    y -= 20
    pdf.drawString(330, y, "Servicio:")
    pdf.drawString(450, y, f"${float(costo_servicio):.2f}")

    y -= 20
    pdf.drawString(330, y, "IVA:")
    pdf.drawString(450, y, f"${float(iva_decimal):.2f}")

    y -= 20
    pdf.drawString(330, y, "TOTAL:")
    pdf.drawString(450, y, f"${float(total_pagar):.2f}")

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
        download_name=f"Factura_{pedido_data['id_pedido']}.pdf"
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
            ISNULL(R.Nombre, '') AS NombreRestaurante,
            M.Imagen,
            M.Precio
        FROM SDR_M_Menu M
        LEFT JOIN SDR_M_Restaurante R ON M.idRestaurante = R.idRestaurante
        ORDER BY M.idMenu
    """)

    menus = rows_to_dicts(cur)
    conn.close()
    return render_template("menu_list.html", menus=menus)



if __name__ == "__main__":
    app.run(debug=True)