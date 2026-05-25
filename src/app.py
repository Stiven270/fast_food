import os
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# 1. IMPORTAMOS EL CLIENTE DE SUPABASE
from supabase_client import supabase 

load_dotenv()

# 2. DEFINIMOS LA APLICACIÓN FLASK (¡Esto tiene que ir arriba de cualquier ruta!)
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
        direccion = datos.get('direccion')
        ubicacion_gps = datos.get('ubicacion_gps')
        notas = datos.get('notas', 'Ninguna')
        productos = datos.get('productos', [])
        
        # Calcular el total general
        total_general = 0
        for p in productos:
            total_general += p['precio'] * p['cantidad']

        # Guardar en la tabla 'pedidos' de Supabase
        try:
            pedido_db = {
                "cliente_nombre": nombre,
                "cliente_telefono": telefono,
                "cliente_direccion": direccion,
                "ubicacion_gps": ubicacion_gps,
                "notas": notas,
                "productos_detalle": productos,
                "total": total_general
            }
            supabase.table("pedidos").insert(pedido_db).execute()
            print("📝 Pedido respaldado con éxito en Supabase")
        except Exception as db_error:
            print(f"⚠️ Error al guardar en la base de datos: {db_error}")

        # Armar el mensaje para Telegram
        mensaje = f"🔔 **¡NUEVO PEDIDO RECIBIDO!** 🍔\n\n"
        mensaje += f"👤 **Cliente:** {nombre}\n"
        mensaje += f"📞 **Teléfono:** {telefono}\n"
        mensaje += f"📍 **Dirección:** {direccion}\n"
        mensaje += f"🗺️ **GPS:** {ubicacion_gps}\n"
        mensaje += f"📝 **Notas:** {notas}\n\n"
        mensaje += f"🛒 **DETALLE DEL PEDIDO:**\n"
        
        for p in productos:
            subtotal = p['precio'] * p['cantidad']
            mensaje += f"• {p['nombre']} x{p['cantidad']} — ${subtotal:,}\n"
            
        mensaje += f"\n💰 **TOTAL A COBRAR:** ${total_general:,}"
        
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
            return jsonify({"status": "error", "message": "Error al conectar con Telegram"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 6. ARRANQUE DEL SERVIDOR
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)