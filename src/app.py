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

        # LÓGICA DEL DOMICILIO: Evaluamos el método de entrega enviado por JS
        if metodo_entrega == 'domicilio':
            costo_envio = int(os.getenv("COSTO_DOMICILIO", 5000)) # Lee los 5000 del .env o por defecto
            entrega_texto = f"🏍️ **Entrega:** Domicilio\n📍 **Dirección:** {direccion}\n🗺️ **GPS:** {ubicacion_gps}"
        else:
            costo_envio = 0
            entrega_texto = "🏃‍♂️ **Entrega:** Retiro en Local (Cliente recoge)"

        # El total real es el subtotal de comida más el recargo de envío
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
                "total": total_general # Ahora sí guarda el total con el envío incluido
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

# 6. ARRANQUE DEL SERVIDOR
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)