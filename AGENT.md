# AGENT.MD — Contexto de Desarrollo y Directrices del Sistema (Backend-First)

## 📌 1. Visión General del Proyecto: CaféTrace SV

**CaféTrace SV** es una plataforma tecnológica geoespacial y de trazabilidad agrícola diseñada para el sector cafetalero de **El Salvador**. Su objetivo principal es resolver la fragmentación documental de pequeños y medianos productores, facilitando la preparación técnica y el cumplimiento del **Reglamento Europeo sobre Productos Libres de Deforestación (EUDR - Regulation (EU) 2023/1115)**, que entra en vigor el **30 de diciembre de 2026**.

### 🎯 Propuesta de Valor y Enfoque Técnico
- **No busca duplicar ni reemplazar** los sistemas oficiales del Instituto Salvadoreño del Café (ISC) ni el sistema central de la Comisión Europea.
- **Capa de simplificación e interoperabilidad**: Transforma el trazado de parcelas y registros de cosechas en expedientes digitales estructurados, códigos QR de consulta pública y archivos **GeoJSON estándar (WGS84 / EPSG:4326)** listos para la exportación y procesos de debida diligencia (*Due Diligence*).
- **Flujo Central de Trazabilidad**:
  $$\text{Productor} \longrightarrow \text{Finca} \longrightarrow \text{Parcela (Polígono PostGIS)} \longrightarrow \text{Cosecha} \longrightarrow \text{Lote Comercial} \longrightarrow \text{QR / GeoJSON EUDR}$$

---

## 🛠️ 2. Arquitectura Global y Stack Tecnológico

La solución opera bajo una arquitectura desacoplada **API REST Asíncrona ↔ Base de Datos Espacial ↔ SPA Frontend**.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       PORTAL WEB (FRONTEND CLIENT)                      │
│      Next.js 14 (App Router) + TypeScript + Tailwind CSS + Lucide Icons │
│       MapLibre GL JS (Visor Cartográfico) + Turf.js (Geometría Client)   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                             REST API / JSON / GeoJSON
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                       BACKEND CORE (DOMINIO DEL AGENTE)                 │
│      FastAPI (Python 3.11+) + Pydantic v2 + SQLAlchemy 2.0 (Async)      │
│      GeoAlchemy2 + Shapely (Motor GIS) + JWT/Argon2id (Seguridad)       │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                            PostGIS Spatial Queries
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                    BASE DE DATOS ESPACIAL & STORAGE                     │
│      PostgreSQL 15+ con Extensión PostGIS habilitada (vía Supabase)     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Tabla de Tecnologías y Responsabilidades

| Capa | Tecnología | Rol en el Proyecto y Consideraciones de Compatibilidad |
| :--- | :--- | :--- |
| **Backend API** | **FastAPI (Python 3.11+)** | Routing asíncrono, inyección de dependencias, endpoints OpenAPI/Swagger interactivos en `/docs`. |
| **Validación de Datos** | **Pydantic v2** | Serialización estricta, parseo de esquemas GeoJSON RFC 7946, validación de coordenadas y DTOs. |
| **ORM & GIS Backend** | **SQLAlchemy 2.0 + GeoAlchemy2 + asyncpg** | Mapeo objeto-relacional asíncrono con soporte nativo de tipos `Geometry(Polygon, 4326)`. |
| **Base de Datos** | **PostgreSQL + PostGIS (Supabase)** | Almacenamiento geoespacial, cálculo geodésico de áreas con `ST_Area(geography)`, exportación nativa `ST_AsGeoJSON`. |
| **Autenticación & Auth** | **JWT (python-jose) + Passlib (Argon2id / Bcrypt)** | Tokens Bearer en cabecera `Authorization: Bearer <token>`, roles: `ADMIN`, `PRODUCTOR`, `TECNICO`. |
| **Frontend (Referencia)** | **Next.js 14 + TypeScript** | Consumirá los endpoints. Todos los contratos deben tener tipado predecible (evitar campos dinámicos no tipados). |
| **Mapas Frontend** | **MapLibre GL JS + Turf.js** | Requiere coordenadas en formato GeoJSON `[longitud, latitud]`. |

---

## 🗺️ 3. Reglas Geoespaciales Críticas (¡ATENCIÓN AGENTE!)

1. **Sistema de Referencia de Coordenadas (CRS)**:
   - Todo debe manejarse bajo **WGS84 (EPSG:4326)**.
   - En base de datos la columna es `GEOMETRY(POLYGON, 4326)`.
2. **Orden de Coordenadas (Estándar GeoJSON RFC 7946)**:
   - Las coordenadas deben ser estrictamente `[longitud, latitud]` (X, Y).
   - **NUNCA** invertir a `[latitud, longitud]`, ya que romperá el renderizado en MapLibre GL y los cálculos de PostGIS.
   - El Salvador se ubica aproximadamente en: Longitud `[-90.15 a -87.68]`, Latitud `[13.15 a 14.45]`.
3. **Polígonos Válidos y Cerrados**:
   - El primer y el último vértice de un polígono deben ser **idénticos** (ej: 4 coordenadas representan un triángulo cerrado).
   - La superficie en hectáreas se calcula en PostGIS convirtiendo la geometría a geografía para considerar la curvatura terrestre:
     $$\text{area\_ha} = \frac{\text{ST\_Area}(\text{geometry}::\text{geography})}{10000.0}$$

---

## 🗄️ 4. Esquema Relacional y Modelo PostGIS (DDL)

```sql
-- Habilitar extensión espacial y de UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 1. USUARIOS Y AUTENTICACIÓN
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'PRODUCTOR', -- 'ADMIN', 'PRODUCTOR', 'TECNICO'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. PRODUCTORES
CREATE TABLE producers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    document_id VARCHAR(50) NOT NULL, -- DUI / NIT / Pasaporte
    phone VARCHAR(30),
    department VARCHAR(50) NOT NULL,   -- ej: Usulután, Santa Ana
    municipality VARCHAR(80) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. FINCAS
CREATE TABLE farms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    producer_id UUID NOT NULL REFERENCES producers(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    department VARCHAR(50) NOT NULL,
    municipality VARCHAR(80) NOT NULL,
    canton_village VARCHAR(120),
    altitude_masl INTEGER, -- Metros sobre el nivel del mar
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. PARCELAS (CON POLÍGONO POSTGIS)
CREATE TABLE plots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    farm_id UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    coffee_variety VARCHAR(60) NOT NULL, -- Bourbon, Pacamara, Cuscatleco, Pacas, Geisha
    area_hectares NUMERIC(10, 4) NOT NULL,
    geometry GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_plots_geometry ON plots USING GIST(geometry);

-- 5. COSECHAS
CREATE TABLE harvests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plot_id UUID NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
    harvest_date DATE NOT NULL,
    weight_kg NUMERIC(10, 2) NOT NULL,
    moisture_percentage NUMERIC(5, 2),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. LOTES DE CAFÉ Y TRAZABILIDAD
CREATE TABLE coffee_lots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    harvest_id UUID NOT NULL REFERENCES harvests(id) ON DELETE CASCADE,
    lot_code VARCHAR(60) UNIQUE NOT NULL, -- ej: SV-USU-2026-LOT01
    qr_uuid UUID UNIQUE DEFAULT uuid_generate_v4(),
    processing_method VARCHAR(50) NOT NULL, -- Lavado, Honey, Natural
    cupping_score NUMERIC(5, 2),
    export_ready BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 📡 5. Especificación de Contratos API REST (Endpoints Clave)

Todos los endpoints responden bajo el prefijo `/api/v1`.

### 5.1. Autenticación (`/api/v1/auth`)
* `POST /auth/register` $
ightarrow$ `{ email, password, full_name, role }` $
ightarrow$ Retorna `UserOut`.
* `POST /auth/login` $
ightarrow$ Formulario OAuth2 `username` (email) + `password` $
ightarrow$ Retorna `{ access_token, token_type: "bearer" }`.
* `GET /auth/me` (Protected) $
ightarrow$ Datos del usuario actual.

### 5.2. Fincas y Parcelas Espaciales (`/api/v1/farms`, `/api/v1/plots`)
* `POST /farms` $
ightarrow$ Crear finca asociada al productor autenticado.
* `GET /farms` $
ightarrow$ Listar fincas del productor con conteo de parcelas y estado EUDR.
* `POST /plots` $
ightarrow$ **Creación Espacial de Parcela**:
  ```json
  // Request Body
  {
    "farm_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "name": "Tablón Los Cedros",
    "coffee_variety": "Bourbon",
    "geojson": {
      "type": "Polygon",
      "coordinates": [
        [
          [-88.54321, 13.43210],
          [-88.54100, 13.43210],
          [-88.54100, 13.43000],
          [-88.54321, 13.43000],
          [-88.54321, 13.43210]
        ]
      ]
    }
  }
  ```
  *Lógica Backend*:
  1. Validar polígono cerrado.
  2. Guardar geometría en PostGIS con `ST_GeomFromGeoJSON`.
  3. Calcular automáticamente `area_hectares` con `ST_Area(geography) / 10000`.
  4. Retornar `PlotOut` con ID, nombre, área calculada y GeoJSON formateado.

* `GET /plots/{id}/geojson` $
ightarrow$ Retorna un **Feature GeoJSON (RFC 7946)**:
  ```json
  {
    "type": "Feature",
    "properties": {
      "plot_id": "c1f77d34-...",
      "farm_name": "Finca El Espino",
      "producer_name": "Jason Velásquez",
      "variety": "Bourbon",
      "area_hectares": 3.72
    },
    "geometry": {
      "type": "Polygon",
      "coordinates": [...]
    }
  }
  ```

### 5.3. Trazabilidad Pública y QR (`/api/v1/trace`)
* `GET /trace/{qr_uuid}` (**Público - Sin Autenticación**):
  - Retorna el expediente completo de trazabilidad:
    - Datos del Productor (Nombre, Municipio, Departamento).
    - Datos de la Finca (Nombre, Altitud).
    - Parcela de origen y polígono georreferenciado simplificado.
    - Datos de Cosecha (Fecha, Proceso, Variedad).
    - Código de Lote y sello digital de verificación.

### 5.4. Motor de Preparación EUDR (`/api/v1/eudr`)
* `GET /eudr/farms/{farm_id}/status` $
ightarrow$ Evalúa las siguientes reglas de negocio y devuelve:
  ```json
  {
    "farm_id": "9b1deb4d-...",
    "readiness_score": 85,
    "status": "APTO_CON_OBSERVACIONES", // "COMPLETO", "INCOMPLETO", "CRITICO"
    "checklist": {
      "producer_data_complete": true,
      "plots_georeferenced": true,
      "polygons_valid": true,
      "harvests_registered": true,
      "has_recent_harvest": false
    },
    "missing_requirements": [
      "Falta registrar fecha de cosecha para la parcela Tablón Los Cedros"
    ]
  }
  ```
* `GET /eudr/farms/{farm_id}/export-geojson` $
ightarrow$ Descarga directa de archivo `FeatureCollection` con todos los metadatos exigidos por importadores europeos.

---

## 📁 6. Estructura de Directorios Recomendada para el Backend

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py                 # Dependencias (get_db, get_current_user, RBAC)
│   │   └── v1/
│   │       ├── api.py              # Enrutador principal de endpoints v1
│   │       └── endpoints/
│   │           ├── auth.py         # Login, Registro, JWT
│   │           ├── producers.py    # CRUD de Productores
│   │           ├── farms.py        # CRUD de Fincas
│   │           ├── plots.py        # Parcelas, PostGIS, GeoJSON
│   │           ├── harvests.py     # Cosechas y Lotes
│   │           ├── trace.py        # Trazabilidad pública por QR
│   │           └── eudr.py         # Motor de preparación EUDR & exportador
│   ├── core/
│   │   ├── config.py               # Settings (Pydantic BaseSettings, CORS, DB_URL)
│   │   └── security.py             # Hasheo de contraseñas (Passlib) y JWT logic
│   ├── db/
│   │   ├── base.py                 # Declarative Base de SQLAlchemy
│   │   └── session.py              # async_sessionmaker & engine
│   ├── models/                     # Modelos ORM SQLAlchemy + GeoAlchemy2
│   │   ├── user.py
│   │   ├── producer.py
│   │   ├── farm.py
│   │   ├── plot.py
│   │   ├── harvest.py
│   │   └── lot.py
│   ├── schemas/                    # Modelos Pydantic (Request/Response DTOs)
│   │   ├── user.py
│   │   ├── farm.py
│   │   ├── plot.py                 # Validación GeoJSON y coordenadas
│   │   ├── trace.py
│   │   └── eudr.py
│   ├── services/                   # Lógica de negocio pura
│   │   ├── gis_service.py          # Transformaciones geométricas y cálculos
│   │   └── eudr_service.py         # Evaluador de cumplimiento normativo
│   └── main.py                     # Instancia FastAPI, Middlewares, CORS
├── alembic/                        # Migraciones de base de datos
├── tests/                          # Tests unitarios y de integración de endpoints
├── Dockerfile                      # Contenedor optimizado de producción
├── docker-compose.yml              # Configuración local con PostgreSQL/PostGIS
├── requirements.txt
└── README.md
```

---

## ⚙️ 7. Convenciones de Código y Buenas Prácticas Backend

1. **Gestión de CORS**:
   - Configurar `CORSMiddleware` en `main.py` para permitir `http://localhost:3000` (Next.js local) y el dominio de Vercel en producción.
2. **Manejo de Geometrías con GeoAlchemy2 y Pydantic**:
   - Usar `geoalchemy2.shape.to_shape` o funciones nativas SQL (`ST_AsGeoJSON`) para serializar geometrías hacia el cliente.
   - En schemas de entrada, utilizar `geojson_pydantic` o schemas Pydantic con estructura `{ "type": "Polygon", "coordinates": List[List[List[float]]] }`.
3. **Manejo de Errores HTTP**:
   - Lanzar siempre `HTTPException(status_code=4xx, detail="Mensaje descriptivo")`.
   - Polígonos no cerrados o de menos de 4 vértices deben retornar `422 Unprocessable Entity` con explicación clara.
4. **Seed Data para El Salvador**:
   - Proveer un script `scripts/seed_data.py` con datos de ejemplo realistas de zonas cafetaleras:
     - Departamentos: *Usulután, Santa Ana, Sonsonate, Ahuachapán*.
     - Variedades: *Bourbon, Pacamara, Cuscatleco, Pacas, Geisha*.
     - Rangos de altitud: *900 a 1600 msnm*.

---

## 🚀 8. Instrucciones de Operación para el LLM en Modo Agente

Cuando se te solicite implementar código para este backend:
1. **Verifica siempre la compatibilidad del contrato** con el frontend Next.js (nombres de llaves en `camelCase` o `snake_case` consistentes; preferir `snake_case` en API estándar o mapear limpiamente).
2. **Prioriza la robustez de las consultas PostGIS** antes de añadir librerías pesadas externas.
3. **Mantén el foco en el MVP de 6 días**: No añadas microservicios, brokers de mensajería (Kafka/RabbitMQ) ni bases de datos NoSQL. Toda la persistencia espacial y relacional se resuelve eficientemente en PostgreSQL + PostGIS.
4. **Asegura endpoints idempotentes y documentados** con sus respectivos tipos de retorno para que Swagger UI (`/docs`) sirva como documentación viva para el desarrollador frontend.
