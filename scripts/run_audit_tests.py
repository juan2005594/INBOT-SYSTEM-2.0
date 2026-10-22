import os
import sys
import json
import requests
import io
from PIL import Image

BASE_URL = "http://127.0.0.1:8000"
CORE_API = f"{BASE_URL}/core-api"
MOBILE_API = f"{BASE_URL}/mobile-api"

results = []

def record(test_id, category, name, expected, actual_status, status_desc, details, passed):
    res = {
        "id": test_id,
        "category": category,
        "name": name,
        "expected": expected,
        "http_code": actual_status,
        "status_desc": status_desc,
        "passed": passed,
        "details": details
    }
    results.append(res)
    print(f"[{'PASS' if passed else 'FAIL'}] {test_id}: {name} -> HTTP {actual_status} ({status_desc})")

print("=== INICIANDO BATERIA DE PRUEBAS DE SEGURIDAD Y AUDITORIA ===")

# --- 1. AUTENTICACION Y CONTROL DE ACCESO ---

# T01: Login correcto (Admin)
r = requests.post(f"{CORE_API}/login/", json={"username": "admin", "password": "admin123"})
admin_token = r.json().get("token") if r.status_code == 200 else None
record("T01", "Autenticación", "Login correcto (Admin)", "HTTP 200, Token retornado", r.status_code, "OK", r.text[:120], r.status_code == 200 and admin_token is not None)

# T02: Login correcto (Vendedor)
r = requests.post(f"{CORE_API}/login/", json={"username": "Vendedor", "password": "vendedor123"})
vendedor_token = r.json().get("token") if r.status_code == 200 else None
record("T02", "Autenticación", "Login correcto (Vendedor)", "HTTP 200, Token retornado", r.status_code, "OK", r.text[:120], r.status_code == 200 and vendedor_token is not None)

# T03: Password incorrecta
r = requests.post(f"{CORE_API}/login/", json={"username": "admin", "password": "wrongpassword999"})
record("T03", "Autenticación", "Login con contraseña incorrecta", "HTTP 400 Rechazado", r.status_code, "Bad Request", r.text[:120], r.status_code == 400)

# T04: Usuario inexistente
r = requests.post(f"{CORE_API}/login/", json={"username": "usuario_falso_99", "password": "password123"})
record("T04", "Autenticación", "Login usuario inexistente", "HTTP 400 Rechazado", r.status_code, "Bad Request", r.text[:120], r.status_code == 400)

# T05: Campos vacíos en login
r = requests.post(f"{CORE_API}/login/", json={"username": "", "password": ""})
record("T05", "Validación", "Login con campos vacíos", "HTTP 400 Validación fallida", r.status_code, "Bad Request", r.text[:120], r.status_code == 400)

# T06: Endpoint protegido sin token
r = requests.get(f"{CORE_API}/productos/stock_bajo/")
record("T06", "Autorización", "Consulta stock_bajo sin token", "HTTP 401 / 403 Rechazado", r.status_code, "Unauthorized/Forbidden", r.text[:120], r.status_code in (401, 403))

# T07: Endpoint protegido con token inválido
r = requests.get(f"{CORE_API}/productos/stock_bajo/", headers={"Authorization": "Token token_invalido_xyz123"})
record("T07", "Autorización", "Consulta stock_bajo con token inválido", "HTTP 401 Rechazado", r.status_code, "Unauthorized", r.text[:120], r.status_code == 401)

# T08: Endpoint protegido con token válido (Admin)
r = requests.get(f"{CORE_API}/productos/stock_bajo/", headers={"Authorization": f"Token {admin_token}"})
record("T08", "Autorización", "Consulta stock_bajo con token válido", "HTTP 200 Permitido", r.status_code, "OK", f"Items recibidos: {len(r.json()) if r.status_code == 200 else 0}", r.status_code == 200)

# T09: Control de acceso por rol (RBAC): Vendedor intentando crear un producto (restringido a Bodeguero/Admin)
r = requests.post(f"{CORE_API}/productos/", json={
    "codigo_barras": "TEST9999",
    "nombre": "Producto No Autorizado",
    "descripcion": "Test RBAC",
    "categoria": 1,
    "proveedor": 1,
    "precio_compra": 1000,
    "porcentaje_ganancia": 20,
    "stock_actual": 10,
    "stock_minimo": 2
}, headers={"Authorization": f"Token {vendedor_token}"})
record("T09", "Autorización", "Vendedor intenta crear producto (RBAC)", "HTTP 403 Prohibido", r.status_code, "Forbidden", r.text[:120], r.status_code == 403)

# T10: Dashboard sin autenticación
# Nota: dashboard es una TemplateView directa sin LoginRequiredMixin
r = requests.get(f"{BASE_URL}/dashboard/")
record("T10", "Autorización", "Acceso a /dashboard/ sin sesión web", "HTTP 302 Redirigir a login", r.status_code, "OK" if r.status_code == 200 else "Redirect", f"Status: {r.status_code}", r.status_code in (302, 401, 403))

# T11: Panel Admin Django sin autenticación
r = requests.get(f"{BASE_URL}/admin/", allow_redirects=False)
record("T11", "Autorización", "Acceso a /admin/ sin sesión", "HTTP 302 Redirección a login", r.status_code, "Found (Redirect)", r.headers.get("Location", ""), r.status_code == 302)

# --- 2. VALIDACIONES DE FORMULARIO Y PROTECCION DE SOLICITUDES ---

# T12: Validación de datos obligatorios al crear categoría (sin nombre)
r = requests.post(f"{CORE_API}/categorias/", json={"descripcion": "Sin nombre"}, headers={"Authorization": f"Token {admin_token}"})
record("T12", "Validación", "Crear categoría sin campo obligatorio 'nombre'", "HTTP 400 Bad Request", r.status_code, "Bad Request", r.text[:120], r.status_code == 400 and "nombre" in r.text)

# T13: Validación de formato de email en Proveedor
r = requests.post(f"{CORE_API}/proveedores/", json={
    "nombre": "Proveedor Invalido",
    "nit": "999888777",
    "telefono": "3001234567",
    "direccion": "Calle 123",
    "email": "correo_no_valido_sin_arroba"
}, headers={"Authorization": f"Token {admin_token}"})
record("T13", "Validación", "Crear proveedor con email con formato inválido", "HTTP 400 Bad Request", r.status_code, "Bad Request", r.text[:120], r.status_code == 400 and "email" in r.text)

# T14: Validación de longitud máxima en NIT (> 20 caracteres)
r = requests.post(f"{CORE_API}/proveedores/", json={
    "nombre": "Proveedor Longitud Excedida",
    "nit": "123456789012345678901234567890", # 30 caracteres
    "telefono": "3001234567",
    "direccion": "Calle 123",
    "email": "test@valido.com"
}, headers={"Authorization": f"Token {admin_token}"})
record("T14", "Validación", "Crear proveedor con NIT superior a longitud máxima (20)", "HTTP 400 Bad Request", r.status_code, "Bad Request", r.text[:120], r.status_code == 400 and "nit" in r.text)

# T15: Validación de valores inválidos (porcentaje de ganancia negativo)
r = requests.post(f"{CORE_API}/productos/", json={
    "codigo_barras": "TEST_NEG",
    "nombre": "Producto Negativo",
    "descripcion": "Test",
    "categoria": 1,
    "proveedor": 1,
    "precio_compra": 1000,
    "porcentaje_ganancia": -15.0, # Inválido
    "stock_actual": 10,
    "stock_minimo": 2
}, headers={"Authorization": f"Token {admin_token}"})
record("T15", "Validación", "Crear producto con ganancia negativa (MinValueValidator)", "HTTP 400 Bad Request", r.status_code, "Bad Request", r.text[:120], r.status_code == 400 and "porcentaje_ganancia" in r.text)

# T16: Validación de protección CSRF en solicitudes web POST sin token
r = requests.post(f"{BASE_URL}/admin/login/", data={"username": "admin", "password": "admin123"})
record("T16", "Protección CSRF", "POST a formulario web sin token CSRF", "HTTP 403 Forbidden (CSRF Failed)", r.status_code, "Forbidden", r.text[:120], r.status_code == 403)

# --- 3. EVALUACION DE GESTION DE ARCHIVOS E IMAGENES ---

# Crear una imagen válida en memoria (PNG)
img_byte_arr = io.BytesIO()
test_image = Image.new('RGB', (100, 100), color='blue')
test_image.save(img_byte_arr, format='PNG')
img_byte_arr.seek(0)

# T17: Subida de imagen válida PNG en mobile-api/chat/validar-imagen/
r = requests.post(f"{MOBILE_API}/chat/validar-imagen/", 
                  files={"imagen": ("test_valido.png", img_byte_arr, "image/png")},
                  headers={"Authorization": f"Token {admin_token}"})
record("T17", "Gestión Archivos", "Subida de imagen válida PNG", "HTTP 200 OK", r.status_code, "OK", r.text[:120], r.status_code == 200)

# T18: Intento de subida de archivo no permitido (.exe simulado / texto plano disfrazado)
fake_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00BinaryExecutableContentHere")
r = requests.post(f"{MOBILE_API}/chat/validar-imagen/", 
                  files={"imagen": ("malicious.exe", fake_exe, "application/x-msdownload")},
                  headers={"Authorization": f"Token {admin_token}"})
record("T18", "Gestión Archivos", "Subida de archivo no permitido (ejecutable)", "Rechazado o error validación", r.status_code, "Result", r.text[:120], "error" in r.text.lower() or r.status_code >= 400)

# T19: Intento de subida de imagen excesivamente grande (Simulación > 10MB)
huge_file = io.BytesIO(b"0" * (12 * 1024 * 1024)) # 12 MB
r = requests.post(f"{MOBILE_API}/chat/validar-imagen/", 
                  files={"imagen": ("huge_image.png", huge_file, "image/png")},
                  headers={"Authorization": f"Token {admin_token}"})
record("T19", "Gestión Archivos", "Subida de archivo > 10MB sin límite explícito", "Control de tamaño / Error", r.status_code, "Result", r.text[:120], r.status_code in (400, 413))

# --- 4. CIERRE DE SESION (LOGOUT) ---

# T20: Logout con token válido
r = requests.post(f"{CORE_API}/logout/", headers={"Authorization": f"Token {admin_token}"})
record("T20", "Autenticación", "Cierre de sesión API con token válido", "HTTP 204 No Content", r.status_code, "No Content", "Token revocado", r.status_code == 204)

# T21: Verificación de token después de logout
r = requests.get(f"{CORE_API}/productos/stock_bajo/", headers={"Authorization": f"Token {admin_token}"})
record("T21", "Autenticación", "Uso de token revocado tras logout", "HTTP 401 Unauthorized", r.status_code, "Unauthorized", r.text[:120], r.status_code == 401)

# Guardar resultados en JSON
with open("../logs/audit_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nBatería completada. Total pruebas: {len(results)}. Guardado en logs/audit_results.json")
