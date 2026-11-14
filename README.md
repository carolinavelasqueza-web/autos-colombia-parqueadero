# Sistema de Información - Parqueadero Autos Colombia

## Descripción
Sistema web para la gestión integral del parqueadero **Autos Colombia**, desarrollado como evidencia de aprendizaje para la asignatura de **Ingeniería de Software** – Institución Universitaria Digital de Antioquia.

* **Iteración 1:** Gestión de la entrada y salida de vehículos.
* **Iteración 2:** Gestión de usuarios (autenticación JWT por roles, administración de clientes y operadores) y gestión de celdas (administración de espacios, disponibilidad por tipo, control por puertas, generación de fichos y reasignación transaccional de celdas).

## 👥 Autores
* **Carolina Velásquez Ávila**
* **Johnatan Darío Vélez Betancur**
* **Elisabeth Martínez Hernández**

Estudiantes de Ingeniería de Software  
Noviembre 2026

## 🛠️ Tecnologías Utilizadas
* **Backend:** Python 3.13 + FastAPI
* **Frontend:** Angular + TypeScript
* **Base de Datos:** PostgreSQL 13+
* **Migraciones:** Alembic (revisiones `0001` a `0009`)
* **Pruebas automatizadas:** `pytest` (Backend) y `Vitest` (Frontend)
* **Control de versiones:** Git + GitHub

## 🚀 Funcionalidades de la Iteración 2

### 1. Gestión de Usuarios (Sesión, Clientes y Operadores)
* **Autenticación y roles:** Inicio y cierre de sesión con tokens JWT (`POST /auth/login`, `POST /auth/logout`) y control de acceso diferenciado para `ADMINISTRADOR` y `OPERADOR`.
* **Gestión de clientes:** Registro, consulta paginada con filtro de estado, actualización parcial y baja/reactivación lógica (`activo = false/true`) conservando su historial y vehículos asociados. Disponible para administradores y operadores.
* **Gestión de operadores:** Registro con contraseñas cifradas mediante `bcrypt`, consulta, edición de rol/estado y desactivación protegida (impide autodesactivación o dejar el sistema sin administradores activos). Exclusivo para `ADMINISTRADOR`.

### 2. Gestión de Celdas y Control de Acceso
* **Administración de celdas:** Precarga de 80 celdas base (`C-01` a `C-70` para automóviles/camionetas y `M-01` a `M-10` para motos), creación de celdas adicionales, edición (con código inmutable en celdas base), desactivación/eliminación según historial y reactivación.
* **Control de acceso y capacidad:** Consulta de disponibilidad en tiempo real por tipo de vehículo, asignación automática de celda libre compatible, generación de comprobante/ficho único (`AC-YYYYMMDD-XXXX`) y selección obligatoria de puerta activa (`NORTE` / `SUR`).
* **Reasignación de celdas:** Cambio transaccional de celda (`POST /estancias/{id}/reasignar`) para vehículos con estancia activa hacia otra celda libre y compatible, registrando motivo opcional en `estancia_reasignacion` y trazabilidad en `auditoria`.

## 📌 Endpoints Principales de la API

| Método y ruta | Descripción y permisos |
| :--- | :--- |
| `POST /auth/login` · `POST /auth/logout` | Autenticación JWT y revocación de sesión |
| `GET / POST / PATCH /clientes` | Gestión de clientes (`ADMINISTRADOR` y `OPERADOR`) |
| `GET / POST / PATCH / DELETE /operadores` | Gestión de personal (exclusivo `ADMINISTRADOR`) |
| `GET / POST / PATCH / DELETE /celdas` | Gestión de celdas (lectura ambos roles; escritura `ADMINISTRADOR`) |
| `GET /celdas/disponibilidad` | Resumen de ocupación y celdas libres por tipo |
| `GET /puertas` | Listado de puertas activas para entrada y salida |
| `POST /estancias/entrada` | Registro de entrada con asignación automática de celda y ficho |
| `POST /estancias/salida` | Registro de salida validando código de ficho y puerta |
| `POST /estancias/{id}/reasignar` | Reasignación transaccional de celda con auditoría |
| `GET /estancias/vehiculo/{placa}` | Consulta del estado actual del vehículo y su estancia |

## ⚙️ Configuración Local

### Requisitos previos
* Python 3.13+
* Node.js 24+
* PostgreSQL 13+
* Git

### Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/carolinavelasqueza-web/autos-colombia-parqueadero.git](https://github.com/carolinavelasqueza-web/autos-colombia-parqueadero.git)
   cd autos-colombia-parqueadero
