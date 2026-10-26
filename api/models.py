from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import F
from decimal import Decimal, ROUND_HALF_UP

# Create your models here.

class Item(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"

class Proveedor(models.Model):
    nombre = models.CharField(max_length=200)
    nit = models.CharField(max_length=20, unique=True)
    telefono = models.CharField(max_length=20)
    direccion = models.TextField()
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    codigo_barras = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    precio_compra = models.DecimalField(max_digits=10, decimal_places=2)
    porcentaje_ganancia = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    stock_actual = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    stock_minimo = models.IntegerField(default=5, validators=[MinValueValidator(0)])
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} - {self.codigo_barras}"

    def save(self, *args, **kwargs):
        # Calcular precio de venta basado en el porcentaje de ganancia
        self.precio_venta = self.precio_compra * (1 + self.porcentaje_ganancia / 100)
        super().save(*args, **kwargs)

class FacturaCompra(models.Model):
    numero_factura = models.CharField(max_length=50, unique=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    fecha_compra = models.DateField()
    total = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Factura {self.numero_factura} - {self.proveedor.nombre}"

class DetalleFacturaCompra(models.Model):
    factura = models.ForeignKey(FacturaCompra, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.producto.nombre} - {self.cantidad} unidades"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
        if is_new:
            # Actualizar stock del producto de forma atómica
            Producto.objects.filter(id=self.producto.id).update(stock_actual=F('stock_actual') + self.cantidad)

class Venta(models.Model):
    fecha_venta = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, editable=False)
    metodo_pago = models.CharField(max_length=50)
    vendedor = models.CharField(max_length=100)

    def __str__(self):
        return f"Venta {self.id} - {self.fecha_venta}"

class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.producto.nombre} - {self.cantidad} unidades"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # Asegurar que subtotal se calcula con Decimal y se cuantifica a 2 decimales
        self.subtotal = (Decimal(str(self.cantidad)) * Decimal(str(self.precio_unitario))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)
        if is_new:
            # Actualizar stock del producto de forma atómica
            print(f"DEBUG: Actualizando stock para Producto ID: {self.producto.id}")
            print(f"DEBUG: Stock actual antes de la venta: {self.producto.stock_actual}")
            print(f"DEBUG: Cantidad vendida: {self.cantidad}")
            Producto.objects.filter(id=self.producto.id).update(stock_actual=F('stock_actual') - self.cantidad)
