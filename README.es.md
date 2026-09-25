# DATEV Desktop API Mock

[English](README.md) · [Deutsch](README.de.md) · **Español**

Un mock local de la API Desktop de DATEV para desarrollo y pruebas de
integración sin una instalación real de DATEV. El repositorio ofrece dos
backends: la implementación de referencia con FastAPI y una alternativa
independiente con Java 21 y Spring Boot.

## Inicio rápido

### FastAPI (implementación de referencia completa)

- Windows: `start.bat`
- Linux/macOS: `./start.sh`

Los scripts preparan Python localmente cuando hace falta, instalan las
dependencias, generan un certificado autofirmado e inician HTTPS en
`https://127.0.0.1:58452`. Después, abre `/admin` o `/docs` y acepta una vez la
advertencia del certificado.

### Spring Boot (backend Java)

- Windows: `start_java_datev_mock.bat`
- Linux/macOS: `./start_java_datev_mock.sh`

Los lanzadores de Java detectan un JDK 21+ y lo usan si existe; de lo
contrario, descargan Eclipse Temurin 21 dentro del proyecto. Construyen el JAR
si es necesario e inician HTTP en `http://127.0.0.1:58553` de forma
predeterminada. Usa `--port PORT` o `DATEV_MOCK_JAVA_PORT` para cambiar el
puerto.

## Elegir un backend

| Backend | Recomendado para | Nota |
|---|---|---|
| **FastAPI / Python** | Mock local completo y administración integrada | Implementación de referencia con 75 rutas documentadas y la página HTML `/admin`. |
| **Spring Boot / Java 21** | Integraciones orientadas a la JVM y distribución como JAR | 63 de 75 rutas; deliberadamente no publica un HTML `/admin` propio. |

Ambas implementaciones incluyen datos deterministas, respuestas JSON/XML con
forma DATEV donde están modeladas, overlays de escritura SQLite, ajustes y
custom overrides. El inventario estático de rutas de SB10 y las brechas de rutas
documentadas están en [spring-boot/PARITY.md](spring-boot/PARITY.md).

## Usar el backend Java

El backend Java vive íntegramente en [`spring-boot/`](spring-boot/) y es
independiente de la aplicación Python. Para builds manuales se requiere Java
21:

```text
cd spring-boot
.\mvnw.cmd clean package
java -jar target/datev-mock-0.1.0-SNAPSHOT.jar --server.port=58553
```

Funciona intencionalmente sobre HTTP. El servicio Java no entrega la interfaz
de administración compartida: abre la
[app de GitHub Pages](https://patchamama.github.io/datev-mock/app/) o
`frontend/admin.html`, y configura **API base URL** como
`http://127.0.0.1:58553`. La interfaz independiente guarda ajustes de conexión estructurados e incluye un ejecutor E2E de endpoints con progreso visible para el destino configurado. El [runbook de Java](spring-boot/RUNBOOK.md) documenta
el build, el uso sin conexión, la configuración y las pruebas smoke. Los
releases también incluyen `datev-mock-java-<version>.zip` con el JAR y los
lanzadores.

## Pruebas

```text
# FastAPI
.venv\Scripts\python -m pytest tests/ -v

# Spring Boot
cd spring-boot
.\mvnw.cmd test
```

Las suites documentadas más recientes contienen 383 pruebas Python y 168
pruebas Java.

## Estructura del proyecto

```text
app/                         Implementación de referencia FastAPI
spring-boot/                 Backend Java 21 / Spring Boot
  src/main/java/.../web/     Controladores REST
  src/main/java/.../store/   Persistencia SQLite y validación de referencias
  src/main/java/.../scoped/  Datos de prueba deterministas por ámbito
  src/main/java/.../xml/     Renderizado XML compatible con DATEV
  src/test/                  Pruebas de Spring Boot
  PARITY.md                  Inventario de rutas y brechas conocidas
  RUNBOOK.md                 Guía de build, ejecución y smoke tests de Java
frontend/admin.html          Interfaz administrativa compartida y configurable
static-demo/                 Demo de solo lectura para GitHub Pages
start*.bat / start*.sh       Lanzadores Python
start_java_datev_mock.*      Lanzadores Java con detección de JDK 21
```

## Tecnología

| Área | Tecnología |
|---|---|
| Backend FastAPI | Python 3.12+, FastAPI, Uvicorn, pytest |
| Backend Java | Java 21, Spring Boot 3.3.5, Spring Web, Actuator, SQLite JDBC, Maven Wrapper |
| Frontend | Bootstrap 5, JavaScript nativo, highlight.js; sin paso de build |
| Persistencia | Conjuntos en memoria y overrides; SQLite para overlays de escritura; `settings.json` para preferencias |
| Distribución | Lanzadores Python y Java independientes; GitHub Releases publica el EXE y el ZIP de Java |

## Más documentación

El README en inglés contiene la lista completa de endpoints, decisiones sobre
XML/JSON, operaciones de escritura, TLS, overrides e historial del proyecto:
[README.md](README.md). Para la paridad y operación específicas de Java, las
fuentes de referencia son [PARITY.md](spring-boot/PARITY.md) y
[RUNBOOK.md](spring-boot/RUNBOOK.md).
