from rest_framework import serializers
from .models import (
    Categoria, Proveedor, Producto, 
    FacturaCompra, DetalleFacturaCompra,
    Venta, DetalleVenta
)
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction

class CategoriaSerializer(serializers.ModelSerializer):
    # Serializador para el modelo Categoria.
    # Convierte instancias de Categoria a JSON y viceversa.
    # Incluye todos los campos del modelo Categoria.
    class Meta:
        model = Categoria
        fields = '__all__'

class ProveedorSerializer(serializers.ModelSerializer):
    # Serializador para el modelo Proveedor.
    # Convierte instancias de Proveedor a JSON y viceversa.
    # Incluye todos los campos del modelo Proveedor.
    class Meta:
        model = Proveedor
        fields = '__all__'

class ProductoSerializer(serializers.ModelSerializer):
    # Serializador para el modelo Producto.
    # Convierte instancias de Producto a JSON y viceversa.
    # Incluye el nombre de la categoría y del proveedor para lectura.
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)

    class Meta:
        model = Producto
        fields = '__all__'
        read_only_fields = ('precio_venta', 'fecha_creacion', 'fecha_actualizacion')

class DetalleFacturaCompraSerializer(serializers.ModelSerializer):
    # Serializador para el modelo DetalleFacturaCompra.
    # Maneja los detalles de los productos en una factura de compra.
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    codigo_barras = serializers.CharField(source='producto.codigo_barras', read_only=True)
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all(), required=False, allow_null=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = DetalleFacturaCompra
        # Listar explícitamente los campos que se esperan recibir del frontend para la creación
        fields = ['id', 'producto', 'producto_nombre', 'codigo_barras', 'cantidad', 'precio_unitario', 'subtotal']
        # Definir los campos que son de solo lectura (se envían en la respuesta, pero no se esperan en la entrada)
        read_only_fields = ('id', 'producto_nombre', 'codigo_barras', 'subtotal')

class FacturaCompraSerializer(serializers.ModelSerializer):
    # Serializador para el modelo FacturaCompra.
    # Permite serializar y deserializar facturas de compra.
    # Incluye los detalles de la factura anidados (solo lectura) y el nombre del proveedor.
    detalles = DetalleFacturaCompraSerializer(many=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    # Campo para porcentaje de ganancia global que se aplicará a todos los productos nuevos
    porcentaje_ganancia_global = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, write_only=True)

    class Meta:
        model = FacturaCompra
        fields = '__all__'
        read_only_fields = ('fecha_creacion',)

    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles')
        if 'total' not in validated_data:
            validated_data['total'] = Decimal('0.00')
        factura_compra = FacturaCompra.objects.create(**validated_data)
        total_calculado = 0
        for detalle_data in detalles_data:
            print(f"DEBUG SERIALIZER: Procesando detalle_data: {detalle_data}")
            # 'producto' en detalle_data ya es una instancia del modelo Producto
            producto = detalle_data.get('producto')
            print(f"DEBUG SERIALIZER: Producto instanciado: {producto}")

            # Calcular subtotal si no viene del frontend o asegurar que es correcto
            cantidad = detalle_data.get('cantidad')
            precio_unitario = detalle_data.get('precio_unitario')
            print(f"DEBUG SERIALIZER: Cantidad: {cantidad}, Precio Unitario: {precio_unitario}")
            
            try:
                # Crear el detalle de la factura
                detalle_compra = DetalleFacturaCompra.objects.create(
                    factura=factura_compra,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario
                )
                print(f"DEBUG SERIALIZER: Detalle de compra creado: {detalle_compra}")
                
                # Calcular y asignar el subtotal al detalle después de la creación
                detalle_compra.subtotal = cantidad * precio_unitario
                detalle_compra.save()
                print(f"DEBUG SERIALIZER: Subtotal calculado y guardado: {detalle_compra.subtotal}")
                
                total_calculado += detalle_compra.subtotal
            except Exception as e:
                print(f"DEBUG SERIALIZER: Error al crear o guardar detalle de compra: {e}")
                raise # Re-lanza la excepción para que Django la maneje
        
        print(f"DEBUG SERIALIZER: Total calculado para FacturaCompra: {total_calculado}")
        factura_compra.total = total_calculado
        factura_compra.save()
        print(f"DEBUG SERIALIZER: FacturaCompra guardada con total: {factura_compra.total}")
        return factura_compra

class DetalleVentaSerializer(serializers.ModelSerializer):
    # Serializador para el modelo DetalleVenta.
    # Maneja los detalles de los productos en una venta.
    # Incluye el nombre del producto y el código de barras para lectura.
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    codigo_barras = serializers.CharField(source='producto.codigo_barras', read_only=True)
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all())
    cantidad = serializers.IntegerField()
    # precio_unitario ya no se recibe del frontend, se toma de Producto.precio_venta
    precio_unitario = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, source='producto.precio_venta')
    id = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = DetalleVenta
        # Only include fields that are received from the client for each detail
        # precio_unitario no se recibe del cliente, se calcula en el backend.
        fields = ['id', 'producto', 'cantidad', 'precio_unitario', 'producto_nombre', 'codigo_barras']
        read_only_fields = ('subtotal', 'producto_nombre', 'codigo_barras', 'venta', 'precio_unitario')

class VentaSerializer(serializers.ModelSerializer):
    # Serializador para el modelo Venta.
    # Permite serializar y deserializar ventas.
    # Incluye los detalles de la venta anidados.
    detalles = DetalleVentaSerializer(many=True)

    # Opcional: enviar factura y comprobante por correo (solo si el vendedor lo solicita).
    enviar_factura_por_correo = serializers.BooleanField(required=False, write_only=True, default=False)
    correo_cliente = serializers.EmailField(required=False, write_only=True, allow_blank=True, allow_null=True)
    nombre_cliente = serializers.CharField(required=False, write_only=True, allow_blank=True, allow_null=True)
    documento_cliente = serializers.CharField(required=False, write_only=True, allow_blank=True, allow_null=True)

    class Meta:
        model = Venta
        # Listar explícitamente los campos de salida. 'total' se calcula en el backend.
        fields = (
            'id',
            'fecha_venta',
            'metodo_pago',
            'vendedor',
            'total',
            'detalles',
            # Campos opcionales de envío (write_only)
            'enviar_factura_por_correo',
            'correo_cliente',
            'nombre_cliente',
            'documento_cliente',
        )
        read_only_fields = ('total',)  # 'total' es de solo lectura (salida).

    def validate(self, attrs):
        """
        Si el vendedor solicita envío por correo, el correo del cliente es obligatorio.
        """
        enviar = attrs.get('enviar_factura_por_correo', False)
        correo = attrs.get('correo_cliente', None)
        if enviar and not correo:
            raise serializers.ValidationError({
                'correo_cliente': 'El correo del cliente es obligatorio si solicita envío de factura/comprobante.'
            })
        return attrs

    def create(self, validated_data):
        from api.utils.inventory_validator import validar_stock_disponible, validar_precio_venta
        from api.models import Producto, DetalleVenta
        from rest_framework.exceptions import ValidationError

        print(f"DEBUG: VentaSerializer.create - Datos validados (antes de pop): {validated_data}")
        detalles_data = validated_data.pop('detalles', [])
        print(f"DEBUG: VentaSerializer.create - Datos de detalles extraídos: {detalles_data}")

        # Extraer datos opcionales de envío (no pertenecen al modelo Venta).
        enviar_factura_por_correo = validated_data.pop('enviar_factura_por_correo', False)
        correo_cliente = validated_data.pop('correo_cliente', None)
        nombre_cliente = validated_data.pop('nombre_cliente', None)
        documento_cliente = validated_data.pop('documento_cliente', None)

        # Iniciar una transacción atómica para asegurar la consistencia
        with transaction.atomic():
            # Calcular el total de la venta de forma preliminar antes de crear la instancia de Venta
            total_calculado_preliminar = Decimal('0.00')
            for i, detalle_data in enumerate(detalles_data):
                producto = detalle_data.get('producto') # This will now be a Product instance
                cantidad_solicitada = detalle_data.get('cantidad')
                # Obtener precio_unitario directamente del objeto producto, no de detalle_data
                precio_unitario_venta = producto.precio_venta

                # Calcular el subtotal para la validación y el total preliminar
                subtotal_detalle = (Decimal(str(cantidad_solicitada)) * precio_unitario_venta).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_calculado_preliminar += subtotal_detalle

                print(f"DEBUG: VentaSerializer.create - Validando Detalle {i+1}: {detalle_data}")
                print(f"DEBUG: VentaSerializer.create - Producto ID: {producto.id}, Cantidad: {cantidad_solicitada}, Precio Unitario (del producto): {precio_unitario_venta}, Subtotal Preliminar: {subtotal_detalle}")

                es_valido_stock, mensaje_stock = validar_stock_disponible(producto.id, cantidad_solicitada)
                if not es_valido_stock:
                    print(f"DEBUG: VentaSerializer.create - Validación de stock falló: {mensaje_stock}")
                    raise ValidationError({'detalles': f"Detalle {i+1}: {mensaje_stock}"})
                
                # La validación de precio se basa en el precio de venta del producto, no en la entrada del usuario.
                # Ya que precio_unitario es read_only, esta validación podría ser redundante si el precio siempre viene del backend.
                # Sin embargo, la mantengo si en algún escenario se podría manipular.
                es_valido_precio, mensaje_precio = validar_precio_venta(producto.id, precio_unitario_venta)
                if not es_valido_precio:
                    print(f"DEBUG: VentaSerializer.create - Validación de precio falló: {mensaje_precio}")
                    raise ValidationError({'detalles': f"Detalle {i+1}: {mensaje_precio}"})

            print("DEBUG: VentaSerializer.create - Todas las validaciones de detalles pasaron.")
            
            # Remove 'total' from validated_data if it somehow ended up there (it shouldn't if read_only=True)
            validated_data.pop('total', None)

            # Create Venta instance
            print("DEBUG: VentaSerializer.create - Intentando crear instancia de Venta...")
            venta = Venta.objects.create(**validated_data)
            print(f"DEBUG: VentaSerializer.create - Instancia de Venta creada con ID: {venta.id}")

            # Now process the details of the sale
            for detalle_data in detalles_data:
                print(f"DEBUG: VentaSerializer.create - Procesando detalle para guardar: {detalle_data}")
                detalle_data['venta'] = venta # Assign the created venta instance
                # Asegurar que el precio_unitario para DetalleVenta se tome del producto, no de los datos entrantes
                detalle_data['precio_unitario'] = detalle_data['producto'].precio_venta
                detalle = DetalleVenta.objects.create(**detalle_data)
                print(f"DEBUG: VentaSerializer.create - Detalle de venta guardado. Subtotal: {detalle.subtotal}")

            # Assign the calculated total to the Venta instance and save it
            print(f"DEBUG: VentaSerializer.create - Asignando total {total_calculado_preliminar} a Venta ID: {venta.id}")
            venta.total = total_calculado_preliminar.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            venta.save()

            print(f"DEBUG: VentaSerializer.create - Venta final guardada con ID: {venta.id}, Total: {venta.total}")

            # Envío de correo opcional (mejor esfuerzo). Nunca debe impedir registrar la venta.
            if enviar_factura_por_correo and correo_cliente:
                venta_id = venta.id
                email_destino = correo_cliente
                cliente_nombre = nombre_cliente
                cliente_documento = documento_cliente

                # Ejecutar luego del commit para evitar inconsistencias si algo falla en la transacción.
                from api.utils.sale_email import send_venta_invoice_email
                transaction.on_commit(
                    lambda: send_venta_invoice_email(
                        venta_id=venta_id,
                        correo_cliente=email_destino,
                        nombre_cliente=cliente_nombre,
                        documento_cliente=cliente_documento,
                    )
                )

            return venta

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)