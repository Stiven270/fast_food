// Arreglo global para almacenar los productos del carrito
let carrito = JSON.parse(localStorage.getItem('carrito')) || [];

// Función para guardar el estado actual en LocalStorage y actualizar la vista
function actualizarInterfaz() {
    const contador = document.getElementById('cart-count');

    // Contamos el total de ítems en el carrito
    const totalItems = carrito.reduce((sum, item) => sum + item.cantidad, 0);

    if (contador) contador.innerText = totalItems;

    localStorage.setItem('carrito', JSON.stringify(carrito));
}

// Función para agregar un producto al carrito
function agregarAlCarrito(id, nombre, precio) {
    // Verificar si el producto ya estaba en el carrito
    const existe = carrito.find(item => item.id === id);
    
    if (existe) {
        existe.cantidad += 1;
    } else {
        carrito.push({
            id: id,
            nombre: nombre,
            precio: precio,
            cantidad: 1
        });
    }
    
    actualizarInterfaz();
    
    // Efecto visual rápido de confirmación (Opcional)
    alert(`¡${nombre} agregado al pedido!`);
}

// Inicializar el contador al cargar la página por primera vez
document.addEventListener('DOMContentLoaded', () => {
    actualizarInterfaz();
}
);
// Función para mostrar la ventana flotante del carrito
function abrirCarrito() {
    const modal = document.getElementById('cart-modal');
    if (modal) modal.classList.remove('hidden');
    renderizarCarrito();
}

// Función para ocultar la ventana flotante
function cerrarCarrito() {
    const modal = document.getElementById('cart-modal');
    if (modal) modal.classList.add('hidden');
}

// Función para renderizar los productos dentro del contenedor flotante
function renderizarCarrito() {
    const container = document.getElementById('cart-items-container');
    const totalLabel = document.getElementById('cart-total-price');
    
    if (!container || !totalLabel) return;

    // Si el carrito está vacío, mostramos un mensaje plano
    if (carrito.length === 0) {
        container.innerHTML = `<p class="text-gray-400 text-center italic py-8">Tu carrito está vacío.</p>`;
        totalLabel.innerText = "$0";
        return;
    }

    // Inyectamos cada producto dinámicamente con estilos limpios
    container.innerHTML = '';
    let totalGeneral = 0;

    carrito.forEach(item => {
        const subtotal = item.precio * item.cantidad;
        totalGeneral += subtotal;

        container.innerHTML += `
            <div class="flex justify-between items-center bg-gray-50 p-3 rounded-xl border border-gray-100 shadow-sm">
                <div class="flex-1 pr-3">
                    <h4 class="font-bold text-gray-800 text-sm leading-tight">${item.nombre}</h4>
                    <p class="text-xs text-gray-500 mt-0.5">$${item.precio.toLocaleString()} c/u</p>
                </div>
                <div class="flex items-center gap-3">
                    <span class="text-xs font-bold text-gray-600 bg-gray-200 px-2 py-1 rounded-md">x${item.cantidad}</span>
                    <span class="text-sm font-extrabold text-gray-900">$${subtotal.toLocaleString()}</span>
                    <button onclick="eliminarDelCarrito(${item.id})" class="text-red-500 hover:text-red-700 text-sm font-bold pl-2">
                        🗑️
                    </button>
                </div>
            </div>
        `;
    });

    totalLabel.innerText = `$${totalGeneral.toLocaleString()}`;
}

// Función para eliminar o mermar la cantidad de un ítem
function eliminarDelCarrito(id) {
    const existe = carrito.find(item => item.id === id);
    if (!existe) return;

    if (existe.cantidad > 1) {
        existe.cantidad -= 1;
    } else {
        carrito = carrito.filter(item => item.id !== id);
    }

    actualizarInterfaz();
    renderizarCarrito(); // Refrescamos la vista del modal en tiempo real
}

// Función para cuando el usuario hunda "Confirmar mi Pedido"
function procederAlCheckout() {
    if (carrito.length === 0) {
        alert("Agrega al menos un producto para confirmar tu pedido.");
        return;
    }
    // Redirige a la nueva pantalla de checkout que creamos en Flask
    window.location.href = '/checkout';
}