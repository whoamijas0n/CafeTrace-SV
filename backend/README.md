# ☕ CaféTrace SV — Backend API & Motor Geoespacial EUDR

Plataforma tecnológica geoespacial y de trazabilidad agrícola diseñada para el sector cafetalero de **El Salvador**, orientada al cumplimiento de la normativa **EUDR (Reglamento UE 2023/1115)** y la interoperabilidad de expedientes digitales de café de especialidad.

---

## 🛠️ Stack Tecnológico

* **Runtime**: Python 3.11+
* **Framework Web**: FastAPI (Asíncrono con ASGI)
* **Validación de Datos**: Pydantic v2 (`ConfigDict`, `@field_validator`, GeoJSON RFC 7946)
* **ORM & Persistencia**: SQLAlchemy 2.0 (Declarativo moderno `Mapped`, `mapped_column`) + GeoAlchemy2 + asyncpg
* **Motor Geoespacial**: PostgreSQL 15+ con extensión PostGIS (`EPSG:4326` WGS84)
* **Seguridad & Auth**: Passlib (Argon2id + Bcrypt) y JWT (`python-jose`)
* **Contenedores**: Docker & Docker Compose multi-stage

---

## 🗺️ Reglas Geoespaciales Críticas

1. **Sistema de Referencia de Coordenadas (CRS)**: WGS84 (`EPSG:4326`).
2. **Orden de Coordenadas (RFC 7946)**: Estrictamente `[longitud, latitud]` (X, Y).
3. **Límites Geográficos (El Salvador)**: Longitud `[-90.25 a -87.55]`, Latitud `[13.10 a 14.55]`.
4. **Polígonos Cerrados**: Mínimo 4 coordenadas donde el primer y último vértice son idénticos.
5. **Cálculo de Área**: Superficie geodésica exacta en hectáreas calculada en PostGIS mediante:
   $$\text{area\_ha} = \frac{\text{ST\_Area}(\text{geometry}::\text{geography})}{10000.0}$$

---

## 🚀 Despliegue Rápido con Docker Compose

La forma recomendada de levantar el entorno completo (FastAPI + PostgreSQL 15 + PostGIS) es mediante Docker Compose:

```bash
cd backend

# 1. Copiar archivo de variables de entorno
cp .env.example .env

# 2. Construir y levantar los contenedores en segundo plano
docker-compose up -d --build

# 3. Inicializar extensiones PostGIS y tablas en la base de datos
docker-compose exec backend python scripts/init_db.py

# 4. Ver logs en tiempo real
docker-compose logs -f backend
```

Una vez levantado:
* **API Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **API Redoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 💻 Desarrollo Local (Sin Docker para el Backend)

Si prefieres ejecutar el servidor FastAPI localmente conectándote a una instancia de PostgreSQL/PostGIS (local o Supabase):

```bash
cd backend

# 1. Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Linux/macOS
# venv\Scripts\activate   # En Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Edita .env con tus credenciales de PostgreSQL/PostGIS

# 4. Inicializar base de datos y extensiones
python scripts/init_db.py

# 5. Iniciar servidor de desarrollo con recarga automática
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📡 Contratos de la API REST (V1)

Todos los endpoints están prefijados bajo `/api/v1`.

### 1. Autenticación & Usuarios (`/api/v1/auth`)
| Método | Endpoint | Descripción | Autenticación |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Registro de nuevos usuarios (`ADMIN`, `PRODUCTOR`, `TECNICO`) | Pública |
| `POST` | `/api/v1/auth/login` | Login estándar OAuth2 (`username`, `password`), retorna JWT Bearer | Pública |
| `GET` | `/api/v1/auth/me` | Retorna los datos del usuario autenticado | Bearer Token |

### 2. Productores (`/api/v1/producers`)
| Método | Endpoint | Descripción | Autenticación |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/producers` | Registro de perfil de productor | Bearer Token |
| `GET` | `/api/v1/producers/me` | Obtiene el perfil de productor del usuario logueado | Bearer Token |
| `PUT` | `/api/v1/producers/me` | Actualiza los datos del perfil de productor | Bearer Token |
| `GET` | `/api/v1/producers/{id}` | Obtiene detalle de un productor específico | Bearer Token |

### 3. Fincas Cafetaleras (`/api/v1/farms`)
| Método | Endpoint | Descripción | Autenticación |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/farms` | Registra una finca asociada al productor autenticado | Bearer Token |
| `GET` | `/api/v1/farms` | Lista fincas del productor con conteo de parcelas y hectáreas | Bearer Token |
| `GET` | `/api/v1/farms/{id}` | Detalle de una finca específica | Bearer Token |
| `PUT` | `/api/v1/farms/{id}` | Actualiza datos de la finca | Bearer Token |
| `DELETE`| `/api/v1/farms/{id}` | Elimina una finca y sus parcelas en cascada | Bearer Token |

### 4. Parcelas & GIS Espacial (`/api/v1/plots`)
| Método | Endpoint | Descripción | Autenticación |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/plots` | Crea parcela con polígono GeoJSON y calcula área en PostGIS | Bearer Token |
| `GET` | `/api/v1/plots/farm/{farm_id}` | Lista parcelas de una finca con geometrías GeoJSON | Bearer Token |
| `GET` | `/api/v1/plots/{id}` | Detalle de una parcela | Bearer Token |
| `GET` | `/api/v1/plots/{id}/geojson` | Retorna `Feature` GeoJSON (RFC 7946) para MapLibre GL | Pública / Token |
| `GET` | `/api/v1/plots/farm/{farm_id}/geojson` | Retorna `FeatureCollection` GeoJSON de la finca | Pública / Token |
| `DELETE`| `/api/v1/plots/{id}` | Elimina una parcela y su geometría | Bearer Token |

---

## 🗺️ Ejemplo de Payload Espacial (`POST /api/v1/plots`)

```json
{
  "farm_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "Tablón Los Cedros",
  "coffee_variety": "Bourbon",
  "geojson": {
    "type": "Polygon",
    "coordinates": [
      [
        [-89.65432, 13.84567],
        [-89.65100, 13.84567],
        [-89.65100, 13.84200],
        [-89.65432, 13.84200],
        [-89.65432, 13.84567]
      ]
    ]
  }
}
```

---

## 🧪 Estructura del Directorio Backend

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py                 # Inyección de dependencias (DB, Auth, RBAC)
│   │   └── v1/
│   │       ├── api.py              # Router central de endpoints v1
│   │       └── endpoints/
│   │           ├── auth.py         # Registro, Login, JWT
│   │           ├── producers.py    # CRUD de Productores
│   │           ├── farms.py        # CRUD de Fincas
│   │           └── plots.py        # Parcelas, PostGIS, MapLibre GeoJSON
│   ├── core/
│   │   ├── config.py               # Pydantic Settings, DB URI, CORS
│   │   └── security.py             # Argon2/Bcrypt & JWT tokens
│   ├── db/
│   │   ├── base.py                 # Declarative Base SQLAlchemy 2.0
│   │   └── session.py              # async_engine & async_sessionmaker
│   ├── models/                     # Modelos ORM SQLAlchemy 2.0
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── producer.py
│   │   ├── farm.py
│   │   └── plot.py
│   ├── schemas/                    # DTOs & Validación Pydantic v2
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── producer.py
│   │   ├── farm.py
│   │   └── plot.py
│   ├── services/                   # Lógica Geoespacial & Utilidades
│   │   ├── __init__.py
│   │   └── gis_service.py
│   └── main.py                     # Inicialización FastAPI, Middlewares, Health
├── scripts/
│   └── init_db.py                  # Inicialización PostGIS y Superadmin
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```
