import os
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# 1. IMPORTAMOS EL CLIENTE DE SUPABASE
from supabase_client import supabase 

load_dotenv()

# 2. DEFINIMOS LA APLICACIÓN FLASK
app = Flask(__name__)

# 3. RUTA PRINCIPAL (Menú dinámico)
@app.route('/')
def home():
    try:
        respuesta = supabase.table("productos").select("*").execute()
        comidas = respuesta.data
    except Exception as e:
        print(f"Error al conectar con Supabase: {e}")
        comidas = []
        
    return render_template('index.html', productos=comidas)

# 4. RUTA DEL CHECKOUT
@app.route('/checkout')
def checkout():
    return render_template('checkout.html')

# 5. RUTA PARA ENVIAR EL PEDIDO (Telegram + Supabase)
@app.route('/api/enviar-pedido', methods=['POST'])
def enviar_pedido_api():
    try:
        datos = request.get_json()
        
        nombre = datos.get('nombre')
        telefono = datos.get('telefono')
        metodo_entrega = datos.get('metodo_entrega', 'domicilio') # Capturamos si es domicilio o local
        direccion = datos.get('direccion')
        ubicacion_gps = datos.get('ubicacion_gps', 'No compartida')
        notas = datos.get('notas', 'Ninguna')
        productos = datos.get('carrito', [])
        
# Calcular el subtotal de los productos
        subtotal_productos = 0
        for p in productos:
            subtotal_productos += p['precio'] * p['cantidad']

        # LÓGICA DEL DOMICILIO CON TARIFA DINÁMICA NOCTURNA
        if metodo_entrega == 'domicilio':
            from datetime import datetime
            import pytz # Librería opcional pero recomendada para asegurar la hora de Colombia
            
            # Definimos la zona horaria de Colombia para que no use la hora UTC de los servidores de Render
            zona_co = pytz.timezone('America/Bogota')
            hora_actual = datetime.now(zona_co).hour  # Captura solo la hora militar (0 a 23)
            
            # Evaluamos si la hora está entre las 20:00 (8 PM) y las 21:59 (antes de las 10 PM)
            # Si quieres incluir las 10:00 PM en punto exacto, puedes dejarlo como: 20 <= hora_actual <= 22
            if 20 <= hora_actual < 23:
                costo_envio = 6000
                entrega_texto = f"🌙 *Entrega:* Domicilio (Tarifa Nocturna 8pm-11pm)\n📍 *Dirección:* {direccion}\n🗺️ *GPS:* {ubicacion_gps}"
            else:
                costo_envio = int(os.getenv("COSTO_DOMICILIO", 5000)) # Tarifa normal de $5.000
                entrega_texto = f"🏍️ *Entrega:* Domicilio\n📍 *Dirección:* {direccion}\n🗺️ *GPS:* {ubicacion_gps}"
        else:
            costo_envio = 0
            entrega_texto = "🏃‍♂️ *Entrega:* Retiro en Local (Cliente recoge)"

        # El total real se calcula de forma transparente con la variable asignada arriba
        total_general = subtotal_productos + costo_envio

        # Guardar en la tabla 'pedidos' de Supabase
        try:
            pedido_db = {
                "cliente_nombre": nombre,
                "cliente_telefono": telefono,
                "cliente_direccion": direccion,
                "ubicacion_gps": ubicacion_gps if metodo_entrega == 'domicilio' else "N/A",
                "notas": notas,
                "productos_detalle": productos,
                "total": total_general,
                "estado": "Pendiente"  # <-- AGREGA ESTA LÍNEA AQUÍ
            }
            supabase.table("pedidos").insert(pedido_db).execute()
            print("📝 Pedido respaldado con éxito en Supabase")
        except Exception as db_error:
            print(f"⚠️ Error al guardar en la base de datos: {db_error}")

        # Armar el mensaje dinámico para Telegram (Cambiamos a Markdown normal para evitar fallos de doble asterisco)
        mensaje = f"🔔 *¡NUEVO PEDIDO RECIBIDO!* 🍔\n\n"
        mensaje += f"👤 *Cliente:* {nombre}\n"
        mensaje += f"📞 *Teléfono:* {telefono}\n"
        mensaje += f"{entrega_texto}\n" # Inyecta la dirección y GPS solo si aplica
        
        if notas and notas != "Ninguna":
            mensaje += f"📝 *Notas:* {notas}\n"
            
        mensaje += f"\n🛒 *DETALLE DEL PEDIDO:*\n"
        for p in productos:
            subtotal_item = p['precio'] * p['cantidad']
            mensaje += f"• {p['nombre']} x{p['cantidad']} — ${subtotal_item:,}\n"
            
        # Si fue domicilio, le pintamos el desglose del recargo en el ticket de Telegram
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
            return jsonify({"status": "success", "message": "Pedido procesado con éxito"}), 200
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
    try:
        # Traemos los pedidos de Supabase
        respuesta = supabase.table("pedidos").select("*").order("created_at", desc=True).execute()
        pedidos_db = respuesta.data
        
        pedidos_adaptados = []
        
        # Mapeamos los nombres de Supabase a los que espera tu JavaScript actual
        for p in pedidos_db:
            pedido_formateado = {
                "id": p.get("id"),
                "nombre": p.get("cliente_nombre"),       # Mapeado a pedido.nombre
                "telefono": p.get("cliente_telefono"),   # Mapeado a pedido.telefono
                "direccion": p.get("cliente_direccion"), # Mapeado a pedido.direccion
                "ubicacion_gps": p.get("ubicacion_gps"),
                "notas": p.get("notas"),
                "carrito": p.get("productos_detalle"),   # Mapeado a pedido.carrito
                "total": p.get("total"),
                "estado": p.get("estado") if p.get("estado") else "Pendiente",
                "metodo_entrega": "domicilio" if p.get("cliente_direccion") else "retiro" 
            }
            pedidos_adaptados.append(pedido_formateado)
            
        return jsonify(pedidos_adaptados), 200
        
    except Exception as e:
        print(f"Error en la API de pedidos: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
# ==========================================
# 7. PANEL DE ADMINISTRACIÓN DE LA COCINA
# ==========================================

@app.route('/cocina')
def panel_cocina():
    try:
        # Traemos todos los pedidos ordenados del más reciente al más viejo
        respuesta = supabase.table("pedidos").select("*").order("created_at", desc=True).execute()
        pedidos_lista = respuesta.data
    except Exception as e:
        print(f"Error al traer pedidos de Supabase: {e}")
        pedidos_lista = []
        
    return render_template('cocina.html', pedidos=pedidos_lista)


@app.route('/api/pedidos/<int:pedido_id>/estado', methods=['PUT'])
def cambiar_estado_pedido(pedido_id):
    try:
        datos = request.get_json()
        nuevo_estado = datos.get('estado')
        
        if not nuevo_estado:
            return jsonify({"status": "error", "message": "Falta el estado"}), 400
            
        # Actualizamos la columna 'estado' en la fila del pedido correspondiente
        supabase.table("pedidos").update({"estado": nuevo_estado}).eq("id", pedido_id).execute()
        
        return jsonify({"status": "success", "message": f"Pedido #{pedido_id} actualizado a {nuevo_estado}"}), 200
        
    except Exception as e:
        print(f"Error al actualizar estado en Supabase: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
# 6. ARRANQUE DEL SERVIDOR
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)