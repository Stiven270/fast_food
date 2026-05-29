import os
import requests
from flask import Flask, render_template, request, jsonify, session, redirect
from dotenv import load_dotenv

# 1. IMPORTAMOS EL CLIENTE DE SUPABASE
from supabase_client import supabase 

load_dotenv()

# ==========================================
# 2. DEFINIMOS LA APLICACIÓN FLASK CONFIGURANDO RUTA DE PLANTILLAS
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "una_clave_super_secreta_y_larga_12345")

# 3. RUTA PRINCIPAL (Menú dinámico)
@app.route('/')
def home():
    try:
        respuesta = supabase.table("productos").select("*").execute()
        comidas = respuesta.data
    except Exception as e:
        print(f"Error al conectar con Supabase: {e}")
        comidas = []
        
    # Verificamos si este navegador tiene un pedido activo guardado para el Banner
    pedido_activo_id = session.get('pedido_activo_id')
        
    return render_template('index.html', productos=comidas, pedido_activo_id=pedido_activo_id)

# 4. RUTA DEL CHECKOUT
@app.route('/checkout')
def checkout():
    return render_template('checkout.html')

# ==========================================
# RUTA DE SEGUIMIENTO PARA EL CLIENTE (CON SEGURIDAD INTEGELENTE)
# ==========================================
@app.route('/seguimiento/<int:pedido_id>')
def seguimiento_pedido(pedido_id):
    # 🔐 SEGURIDAD ULTRA ESTRICTA:
    pedido_en_sesion = session.get('pedido_activo_id')
    es_admin = session.get('usuario_autenticado')  # Verifica si el de la cocina está logueado
    
    # Imprime en la consola para que veas qué está pasando en tiempo real al hacer pruebas
    print(f"🔒 AUDITORÍA URL: Intenta ver #{pedido_id} | En Sesión tiene: {pedido_en_sesion} | ¿Es Cocina?: {es_admin}")

    # SI NO es el administrador de la cocina, aplicamos las reglas del cliente:
    if not es_admin:
        # Regala acceso limpio solo si el ID de la URL es EXACTAMENTE el que tiene en sesión
        if pedido_en_sesion is None or int(pedido_en_sesion) != int(pedido_id):
            return "<h3>🚫 Acceso denegado: No tienes permiso para ver este pedido.</h3>", 403
        
    try:
        respuesta = supabase.table("pedidos").select("*").eq("id", pedido_id).execute()
        
        if not respuesta.data:
            return "<h3>⚠️ El pedido solicitado no existe o fue cancelado.</h3>", 404
            
        pedido_datos = respuesta.data[0]
        
        # Guardamos/aseguramos el ID actual en la sesión del cliente
        session['pedido_activo_id'] = pedido_id
        
        # ==========================================
        # 📊 SINCRO DE ESTADOS: 4 OPCIONES INDEPENDIENTES
        # ==========================================
        estado_actual = pedido_datos.get("estado", "Pendiente")
        paso_barra = 1  
        
        estado_limpio = estado_actual.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").strip()
        
        if "preparacion" in estado_limpio or "cocina" in estado_limpio:
            paso_barra = 2  
        elif "despachado" in estado_limpio or "camino" in estado_limpio or "reparto" in estado_limpio:
            paso_barra = 3  
        elif "entregado" in estado_limpio or "finalizado" in estado_limpio:
            paso_barra = 4  
        else:
            paso_barra = 1  

        return render_template('seguimiento.html', pedido=pedido_datos, paso=paso_barra)

    except Exception as e:
        print(f"Error al buscar seguimiento en Supabase: {e}")
        return "<h3>⚠️ Ocurrió un error al cargar el seguimiento.</h3>", 500

# 5. RUTA PARA ENVIAR EL PEDIDO (Telegram + Supabase)
@app.route('/api/enviar-pedido', methods=['POST'])
def enviar_pedido_api():
    try:
        datos = request.get_json()
        
        nombre = datos.get('nombre')
        telefono = datos.get('telefono')
        metodo_entrega = datos.get('metodo_entrega', 'domicilio') 
        direccion = datos.get('direccion')
        ubicacion_gps = datos.get('ubicacion_gps', 'No compartida')
        notes = datos.get('notas', 'Ninguna')
        productos = datos.get('carrito', [])
        
        # Calcular el subtotal de los productos
        subtotal_productos = 0
        for p in productos:
            subtotal_productos += p['precio'] * p['cantidad']

        # LÓGICA DEL DOMICILIO CON TARIFA DINÁMICA NOCTURNA
        if metodo_entrega == 'domicilio':
            from datetime import datetime
            import pytz 
            
            zona_co = pytz.timezone('America/Bogota')
            hora_actual = datetime.now(zona_co).hour  
            
            if 20 <= hora_actual < 23:
                costo_envio = 6000
                entrega_texto = f"🌙 *Entrega:* Domicilio (Tarifa Nocturna 8pm-11pm)\n📍 *Dirección:* {direccion}\n🗺️ *GPS:* {ubicacion_gps}"
            else:
                costo_envio = int(os.getenv("COSTO_DOMICILIO", 5000)) 
                entrega_texto = f"🏍️ *Entrega:* Domicilio\n📍 *Dirección:* {direccion}\n🗺️ *GPS:* {ubicacion_gps}"
        else:
            costo_envio = 0
            entrega_texto = "🏃‍♂️ *Entrega:* Retiro en Local (Cliente recoge)"

        total_general = subtotal_productos + costo_envio

        # Guardar en la tabla 'pedidos' de Supabase
        id_generado = None
        try:
            pedido_db = {
                "cliente_nombre": nombre,
                "cliente_telefono": telefono,
                "cliente_direccion": direccion if metodo_entrega == 'domicilio' else "Retiro en Local",
                "ubicacion_gps": ubicacion_gps if metodo_entrega == 'domicilio' else "N/A",
                "notas": notes,
                "productos_detalle": productos,
                "total": total_general,
                "estado": "Pendiente"
            }
            insert_query = supabase.table("pedidos").insert(pedido_db).execute()
            id_generado = insert_query.data[0]['id'] if insert_query.data else None
            print(f"📝 Pedido #{id_generado} respaldado con éxito en Supabase")
            
            # 🌟 SINCRONIZACIÓN INMEDIATA: Guardamos el ID en la sesión en el momento exacto de la compra
            session['pedido_activo_id'] = id_generado
            
        except Exception as db_error:
            print(f"⚠️ Error al guardar en la base de datos: {db_error}")

        # Armar el mensaje dinámico para Telegram
        mensaje = f"🔔 *¡NUEVO PEDIDO RECIBIDO!* 🍔\n\n"
        if id_generado:
            mensaje += f"🆔 *Pedido ID:* #{id_generado}\n"
        mensaje += f"👤 *Cliente:* {nombre}\n"
        mensaje += f"📞 *Teléfono:* {telefono}\n"
        mensaje += f"{entrega_texto}\n"
        
        if notes and notes != "Ninguna":
            mensaje += f"📝 *Notas:* {notes}\n"
            
        mensaje += f"\n🛒 *DETALLE DEL PEDIDO:*\n"
        for p in productos:
            subtotal_item = p['precio'] * p['cantidad']
            mensaje += f"• {p['nombre']} x{p['cantidad']} — ${subtotal_item:,}\n"
            
        if costo_envio > 0:
            mensaje += f"\n📦 *Recargo Envío:* ${costo_envio:,}\n"
            
        mensaje += f"💰 *TOTAL A COBRAR:* ${total_general:,}\n"
        mensaje += f"💵 *Método:* Pago contra entrega"
        
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        url_telegram = f"https://api.telegram.org/bot{token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url_telegram, json=payload)
        
        if response.status_code == 200:
            return jsonify({
                "status": "success", 
                "message": "Pedido processed con éxito",
                "pedido_id": id_generado  
            }), 200
        else:
            print(f"Error Telegram: {response.text}")
            return jsonify({"status": "error", "message": "Error al conectar con Telegram"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# API PARA EL PANEL DE COCINA (FETCH JS)
# ==========================================
@app.route('/api/pedidos', methods=['GET'])
def obtener_pedidos_api():
    if not session.get('usuario_autenticado'):
        return jsonify({"status": "error", "message": "No autorizado"}), 401

    try:
        # Corregido: Uso de diccionario 'options' para evitar excepciones del builder en Supabase
        respuesta = supabase.table("pedidos").select("*").order("created_at", desc=True).execute()
        pedidos_db = respuesta.data
        
        pedidos_adaptados = []
        for p in pedidos_db:
            pedido_formateado = {
                "id": p.get("id"),
                "nombre": p.get("cliente_nombre"),
                "telefono": p.get("cliente_telefono"),
                "direccion": p.get("cliente_direccion"),
                "ubicacion_gps": p.get("ubicacion_gps"),
                "notas": p.get("notas"),
                "carrito": p.get("productos_detalle"),
                "total": p.get("total"),
                "estado": p.get("estado") if p.get("estado") else "Pendiente",
                "metodo_entrega": "domicilio" if p.get("cliente_direccion") and p.get("cliente_direccion") != "Retiro en Local" else "retiro" 
            }
            pedidos_adaptados.append(pedido_formateado)
            
        return jsonify(pedidos_adaptados), 200
        
    except Exception as e:
        print(f"Error en la API de pedidos: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# 🔐 SISTEMA DE AUTENTICACIÓN (LOGIN)
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('username')
        contrasena = request.form.get('password')
        
        USER_CORRECTO = os.getenv("ADMIN_USER", "cocina")
        PASS_CORRECTO = os.getenv("ADMIN_PASSWORD", "admin1234")
        
        if usuario == USER_CORRECTO and contrasena == PASS_CORRECTO:
            session['usuario_autenticado'] = True
            return redirect('/cocina')
        else:
            return render_template('login.html', error="Credenciales incorrectas")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario_autenticado', None)
    return redirect('/login')

# ==========================================
# 7. PANEL DE ADMINISTRACIÓN DE LA COCINA
# ==========================================
@app.route('/cocina')
def panel_cocina():
    if not session.get('usuario_autenticado'):
        return redirect('/login')
        
    try:
        # Corregido: Uso de diccionario 'options' para evitar excepciones del builder en Supabase
        respuesta = supabase.table("pedidos").select("*").order("created_at", desc=True).execute()
        pedidos_lista = respuesta.data
    except Exception as e:
        print(f"Error al traer pedidos de Supabase: {e}")
        pedidos_lista = []
        
    return render_template('cocina.html', pedidos=pedidos_lista)


@app.route('/api/pedidos/<int:pedido_id>/estado', methods=['PUT'])
def cambiar_estado_pedido(pedido_id):
    if not session.get('usuario_autenticado'):
        return jsonify({"status": "error", "message": "No autorizado"}), 401

    try:
        datos = request.get_json()
        nuevo_estado = datos.get('estado')
        
        if not nuevo_estado:
            return jsonify({"status": "error", "message": "Falta el estado"}), 400
            
        supabase.table("pedidos").update({"estado": nuevo_estado}).eq("id", pedido_id).execute()
        return jsonify({"status": "success", "message": f"Pedido #{pedido_id} actualizado a {nuevo_estado}"}), 200
        
    except Exception as e:
        print(f"Error al actualizar estado en Supabase: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 6. ARRANQUE DEL SERVIDOR
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)