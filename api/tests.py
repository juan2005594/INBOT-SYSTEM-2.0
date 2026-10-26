"""
========================================================================================
SISTEMA DE GESTIÓN INBOT SYSTEM - BATERÍA DE PRUEBAS UNITARIAS Y DE INTEGRACIÓN (TESTS)
========================================================================================

¿QUÉ SON ESTAS PRUEBAS UNITARIAS?
Son pruebas automáticas escritas en Python utilizando el framework de testing de Django
y Django REST Framework (APITestCase). Su objetivo es garantizar la calidad del software,
comprobando que cada módulo (modelos, base de datos, cálculo de precios, inventario,
seguridad, endpoints REST y carga de imágenes) funcione de forma 100% correcta sin errores.

ESTRUCTURA DE CADA PRUEBA:
1. setUp(): Prepara el entorno (crea usuarios de prueba, categorías, proveedores y productos temporales).
2. test_*(): Ejecuta la acción que se desea probar (ej. hacer una venta, subir una foto, calcular precio).
3. self.assert*(): Comprueba que el resultado obtenido sea exactamente el resultado esperado (Asserts).
========================================================================================
"""

import io
from decimal import Decimal
from PIL import Image

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    Categoria, Proveedor, Producto,
    FacturaCompra, DetalleFacturaCompra,
    Venta, DetalleVenta
)


# ======================================================================================
# BLOQUE 1: PRUEBAS UNITARIAS DE MODELOS Y LÓGICA DE NEGOCIO (ORM DE DJANGO)
# ======================================================================================

class ProductoModelTest(TestCase):
    """
    OBJETIVO DE ESTA CLASE:
    Validar la persistencia de datos del producto y la lógica interna de cálculo
    automático de precios en el método save() del modelo Producto.
    """

    def setUp(self):
        """
        PASO 1: PREPARACIÓN DE DATOS (setUp)
        Se ejecuta antes de cada prueba. Crea una categoría y un proveedor
        en la base de datos de pruebas temporal para asociarlos al producto.
        """
        # Creamos una categoría de prueba
        self.categoria = Categoria.objects.create(
            nombre="Aseo y Limpieza",
            descripcion="Artículos para limpieza y desinfección"
        )

        # Creamos un proveedor de prueba
        self.proveedor = Proveedor.objects.create(
            nombre="Distribuidora Los Andes",
            nit="900123456-1",
            telefono="3109876543",
            direccion="Calle 100 # 15-20",
            email="ventas@losandes.com"
        )

        # Creamos el producto de prueba con un costo de $2.000 y 40% de margen de ganancia
        self.producto = Producto.objects.create(
            codigo_barras="7701234567890",
            nombre="Jabón Líquido Antibacterial 500ml",
            descripcion="Jabón con fragancia floral",
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_compra=Decimal("2000.00"),
            porcentaje_ganancia=Decimal("40.00"),
            stock_actual=30,
            stock_minimo=5
        )

    def test_creacion_producto_y_calculo_precio_venta(self):
        """
        CASO DE PRUEBA:
        Verifica que al guardar un producto, el sistema calcule automáticamente el
        precio de venta basándose en la fórmula:
        precio_venta = precio_compra * (1 + porcentaje_ganancia / 100)
        
        Cálculo matemático esperado:
        2000 * (1 + 0.40) = $2.800
        """
        # Verificamos que el nombre y stock se hayan guardado fielmente
        self.assertEqual(self.producto.nombre, "Jabón Líquido Antibacterial 500ml")
        self.assertEqual(self.producto.stock_actual, 30)

        # Verificamos que el precio de venta calculado automáticamente sea exactamente $2.800
        self.assertEqual(self.producto.precio_venta, Decimal("2800.00"))

    def test_representacion_en_texto_del_producto(self):
        """
        CASO DE PRUEBA:
        Verifica que el método especial __str__() del modelo devuelva el nombre del producto
        junto con su código de barras, facilitando su identificación en listas desplegables.
        """
        texto_esperado = "Jabón Líquido Antibacterial 500ml - 7701234567890"
        self.assertEqual(str(self.producto), texto_esperado)


class VentaModelTest(TestCase):
    """
    OBJETIVO DE ESTA CLASE:
    Validar la estructura y persistencia de una Venta en la base de datos.
    """

    def setUp(self):
        """Se crea una venta de ejemplo con fecha, método de pago y monto total."""
        self.venta = Venta.objects.create(
            total=Decimal("45000.00"),
            metodo_pago="Efectivo",
            vendedor="Pablo Vendedor"
        )

    def test_atributos_de_venta(self):
        """Comprueba que los datos de la venta coincidan con los ingresados."""
        self.assertEqual(self.venta.total, Decimal("45000.00"))
        self.assertEqual(self.venta.metodo_pago, "Efectivo")
        self.assertEqual(self.venta.vendedor, "Pablo Vendedor")


# ======================================================================================
# BLOQUE 2: PRUEBAS DE LA API REST (ENDPOINTS, SEGURIDAD, FOTOGRAFÍAS Y TRANSACCIONES)
# ======================================================================================

class CoreAPITests(APITestCase):
    """
    OBJETIVO DE ESTA CLASE:
    Evaluar los endpoints de la API Web (Django REST Framework) simulando peticiones
    reales HTTP (GET, POST, multipart/form-data) tal como las realiza el Frontend o la App Móvil.
    """

    def setUp(self):
        """
        PREPARACIÓN DEL ENTORNO DE PRUEBAS PARA LA API:
        1. Crea un usuario administrador con permisos.
        2. Realiza login en el cliente de pruebas HTTP.
        3. Crea entidades base (categoría, proveedor, producto) necesarias para los endpoints.
        """
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='testpassword123'
        )
        # Autenticamos el cliente de pruebas
        self.client.login(username='admin_test', password='testpassword123')

        # Categoría y Proveedor iniciales
        self.categoria = Categoria.objects.create(nombre='Bebidas', descripcion='Gaseosas y jugos')
        self.proveedor = Proveedor.objects.create(
            nombre='Bebidas del Valle',
            nit='900987654',
            telefono='3150001122',
            direccion='Carrera 15 # 30-10',
            email='ventas@bebidasvalle.com'
        )

        # Producto inicial en inventario
        self.producto = Producto.objects.create(
            codigo_barras='770111222',
            nombre='Jugo de Naranja 1L',
            descripcion='Jugo natural pasteurizado',
            categoria=self.categoria,
            proveedor=self.proveedor,
            precio_compra=Decimal('3000.00'),
            porcentaje_ganancia=Decimal('30.00'),
            stock_actual=50,
            stock_minimo=10
        )

    def test_01_autenticacion_login_api(self):
        """
        PRUEBA 1: AUTENTICACIÓN
        Verifica que al enviar credenciales correctas a /core-api/login/,
        el servidor responda con código HTTP 200 (OK) y entregue un Token de acceso seguro.
        """
        url = reverse('core_api:api_login')
        data = {
            'username': 'admin_test',
            'password': 'testpassword123'
        }
        response = self.client.post(url, data, format='json')
        
        # 1. Comprobar que responde HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 2. Comprobar que el token exista en la respuesta
        self.assertIn('token', response.data)

    def test_02_listar_productos_catalogo(self):
        """
        PRUEBA 2: CONSULTA DE CATÁLOGO (GET)
        Verifica que la petición GET /core-api/productos/ entregue la lista paginada
        de productos registrados para que el catálogo web pueda renderizarlos.
        """
        url = reverse('core_api:producto-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        # Al menos debe contener el producto que creamos en setUp
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_03_crear_producto_via_api(self):
        """
        PRUEBA 3: REGISTRO DE NUEVO PRODUCTO (POST)
        Verifica que mediante una petición POST con los datos del producto,
        la API cree el registro en la base de datos con respuesta HTTP 201 Created.
        """
        url = reverse('core_api:producto-list')
        nuevo_producto_data = {
            'codigo_barras': '770999888',
            'nombre': 'Agua Mineral Manantial 600ml',
            'descripcion': 'Agua natural sin gas',
            'categoria': self.categoria.id,
            'proveedor': self.proveedor.id,
            'precio_compra': '1500.00',
            'porcentaje_ganancia': '40.00',
            'stock_actual': 40,
            'stock_minimo': 5
        }
        response = self.client.post(url, nuevo_producto_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Comprobamos en la base de datos que el producto exista
        self.assertTrue(Producto.objects.filter(codigo_barras='770999888').exists())

    def test_04_subir_fotografia_a_producto_existente(self):
        """
        PRUEBA 4: SUBIDA DE FOTOGRAFÍA (NUEVA CARACTERÍSTICA)
        Verifica que se pueda adjuntar una imagen a un producto ya registrado en el inventario
        utilizando el endpoint /core-api/productos/{id}/subir_imagen/ con multipart/form-data.
        """
        url = reverse('core_api:producto-subir-imagen', args=[self.producto.id])
        
        # Creamos una imagen sintética directamente en memoria RAM usando la librería Pillow
        imagen_en_memoria = io.BytesIO()
        img = Image.new('RGB', (120, 120), color=(50, 120, 200))
        img.save(imagen_en_memoria, format='JPEG')
        imagen_en_memoria.seek(0)
        imagen_en_memoria.name = 'foto_producto_prueba.jpg'

        # Enviamos la imagen mediante multipart/form-data
        response = self.client.post(url, {'imagen': imagen_en_memoria}, format='multipart')

        # 1. El endpoint debe responder HTTP 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 2. Refrescamos el objeto desde la base de datos y comprobamos que la imagen esté asignada
        self.producto.refresh_from_db()
        self.assertTrue(bool(self.producto.imagen))
        self.assertIn('foto_producto_prueba', self.producto.imagen.name)

    def test_05_factura_compra_incrementa_inventario(self):
        """
        PRUEBA 5: GESTIÓN DE COMPRAS E INCREMENTO DE STOCK
        Verifica que al registrar una Factura de Compra de 20 unidades del producto,
        el sistema aumente automáticamente el stock_actual de 50 a 70 unidades.
        """
        url = reverse('core_api:facturacompra-list')
        stock_antes_de_comprar = self.producto.stock_actual  # 50 unidades

        factura_data = {
            'numero_factura': 'FC-2026-001',
            'proveedor': self.proveedor.id,
            'fecha_compra': '2026-10-25',
            'detalles': [
                {
                    'producto': self.producto.id,
                    'cantidad': 20,
                    'precio_unitario': '2800.00'
                }
            ]
        }
        response = self.client.post(url, factura_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Comprobamos que el stock aumentó exactamente en 20 unidades
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_antes_de_comprar + 20)

    def test_06_registrar_venta_descuenta_inventario(self):
        """
        PRUEBA 6: GESTIÓN DE VENTAS Y DESCUENTO DE STOCK
        Verifica que al procesar una venta de 5 unidades, el sistema:
        1. Cree la factura de venta correctamente (HTTP 201).
        2. Reste automáticamente las 5 unidades del stock actual (50 - 5 = 45).
        """
        url = reverse('core_api:venta-list')
        stock_antes_de_vender = self.producto.stock_actual  # 50 unidades

        venta_data = {
            'fecha_venta': '2026-10-25',
            'metodo_pago': 'Efectivo',
            'vendedor': 'Pablo Sanchez',
            'detalles': [
                {
                    'producto': self.producto.id,
                    'cantidad': 5,
                    'precio_unitario': str(self.producto.precio_venta)
                }
            ]
        }
        response = self.client.post(url, venta_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Comprobamos que el stock disminuyó en 5 unidades
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_antes_de_vender - 5)

    def test_07_seguridad_rechazar_venta_con_stock_insuficiente(self):
        """
        PRUEBA 7: REGLA DE NEGOCIO Y CONTROL DE INVENTARIO
        Verifica que el sistema impida realizar una venta si el vendedor intenta
        vender más unidades de las que realmente existen en bodega (Stock insuficiente).
        Debe responder con error HTTP 400 Bad Request.
        """
        url = reverse('core_api:venta-list')
        venta_invalida_data = {
            'fecha_venta': '2026-10-25',
            'metodo_pago': 'Efectivo',
            'vendedor': 'Pablo Sanchez',
            'detalles': [
                {
                    'producto': self.producto.id,
                    'cantidad': 9999,  # Cantidad que supera por mucho las 50 unidades en bodega
                    'precio_unitario': str(self.producto.precio_venta)
                }
            ]
        }
        response = self.client.post(url, venta_invalida_data, format='json')

        # La API debe rechazar la transacción con código 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
