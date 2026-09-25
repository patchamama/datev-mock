# DATEV Desktop API Mock

[English](README.md) · **Deutsch** · [Español](README.es.md)

Ein lokaler Mock der DATEV Desktop API für Entwicklung und Integrationstests
ohne eine echte DATEV-Installation. Dieses Repository bietet zwei Backends:
die FastAPI-Referenzimplementierung und eine eigenständige Java-21- /
Spring-Boot-Alternative.

## Schnellstart

### FastAPI (vollständige Referenzimplementierung)

- Windows: `start.bat`
- Linux/macOS: `./start.sh`

Die Skripte richten bei Bedarf ein projektlokales Python ein, installieren die
Abhängigkeiten, erstellen ein selbstsigniertes Zertifikat und starten HTTPS auf
`https://127.0.0.1:58452`. Öffne anschließend `/admin` oder `/docs` und
akzeptiere die Zertifikatswarnung einmalig.

### Spring Boot (Java-Backend)

- Windows: `start_java_datev_mock.bat`
- Linux/macOS: `./start_java_datev_mock.sh`

Die Java-Starter erkennen ein JDK 21+, verwenden es wenn verfügbar oder laden
sonst Eclipse Temurin 21 projektlokal herunter. Sie bauen das JAR bei Bedarf
und starten standardmäßig HTTP auf `http://127.0.0.1:58553`. Mit `--port PORT`
oder `DATEV_MOCK_JAVA_PORT` lässt sich der Port ändern.

## Backend auswählen

| Backend | Geeignet für | Hinweis |
|---|---|---|
| **FastAPI / Python** | Vollständigen lokalen Mock und integrierte Administration | Referenzimplementierung mit 75 dokumentierten Routen und der HTML-Seite `/admin`. |
| **Spring Boot / Java 21** | JVM-nahe Integrationen und JAR-basierte Auslieferung | 63 von 75 Routen; bewusst kein eigenes HTML-`/admin`. |

Beide Implementierungen stellen deterministische Testdaten, DATEV-nahe
JSON/XML-Antworten, SQLite-Write-Overlays, Einstellungen und Custom Overrides
bereit. Das statische SB10-Routeninventar und die dokumentierten Routenlücken stehen
in [spring-boot/PARITY.md](spring-boot/PARITY.md).

## Java-Backend verwenden

Das Java-Backend liegt vollständig unter [`spring-boot/`](spring-boot/) und
ist unabhängig von der Python-Anwendung. Für manuelle Builds wird Java 21
benötigt:

```text
cd spring-boot
.\mvnw.cmd clean package
java -jar target/datev-mock-0.1.0-SNAPSHOT.jar --server.port=58553
```

Es läuft absichtlich über HTTP. Die gemeinsame Admin-Oberfläche wird nicht vom
Java-Service ausgeliefert: öffne stattdessen die
[GitHub-Pages-App](https://patchamama.github.io/datev-mock/app/) oder
`frontend/admin.html` und setze **API base URL** auf
`http://127.0.0.1:58553`. Die eigenständige Oberfläche speichert strukturierte Verbindungseinstellungen und enthält einen Endpoint-E2E-Runner mit sichtbarem Fortschritt für das konfigurierte Ziel. Der [Java-Runbook](spring-boot/RUNBOOK.md) beschreibt
Build, Offline-Setup, Konfiguration und Smoke-Tests. Releases enthalten zudem
ein `datev-mock-java-<version>.zip` mit JAR und Startskripten.

## Tests

```text
# FastAPI
.venv\Scripts\python -m pytest tests/ -v

# Spring Boot
cd spring-boot
.\mvnw.cmd test
```

Die zuletzt dokumentierten Suiten umfassen 383 Python- und 168 Java-Tests.

## Projektstruktur

```text
app/                         FastAPI-Referenzimplementierung
spring-boot/                 Java-21-/Spring-Boot-Backend
  src/main/java/.../web/     REST-Controller
  src/main/java/.../store/   SQLite-Speicher und Referenzvalidierung
  src/main/java/.../scoped/  Deterministische, bereichsbezogene Testdaten
  src/main/java/.../xml/     DATEV-kompatible XML-Ausgabe
  src/test/                  Spring-Boot-Tests
  PARITY.md                  Routenvergleich und bekannte Lücken
  RUNBOOK.md                 Java-Build-, Start- und Smoke-Test-Anleitung
frontend/admin.html          Gemeinsame, konfigurierbare Admin-Oberfläche
static-demo/                 Lesedemo für GitHub Pages
start*.bat / start*.sh       Python-Starter
start_java_datev_mock.*      Java-Starter mit JDK-21-Erkennung
```

## Technologie

| Bereich | Technologie |
|---|---|
| FastAPI-Backend | Python 3.12+, FastAPI, Uvicorn, pytest |
| Java-Backend | Java 21, Spring Boot 3.3.5, Spring Web, Actuator, SQLite JDBC, Maven Wrapper |
| Frontend | Bootstrap 5, Vanilla JavaScript, highlight.js; kein Build-Schritt |
| Persistenz | In-Memory-Datensätze und Overrides; SQLite für Write-Overlays; `settings.json` für Einstellungen |
| Auslieferung | Python-Starter und eigenständige Java-Starter; GitHub Releases enthalten EXE bzw. Java-ZIP |

## Weitere Dokumentation

Die englische README enthält die vollständige Endpoint-Liste, Entscheidungen zu
XML/JSON, Schreiboperationen, TLS, Overrides und die Entwicklungshistorie:
[README.md](README.md). Für Java-spezifische Parität und Betrieb sind
[PARITY.md](spring-boot/PARITY.md) und [RUNBOOK.md](spring-boot/RUNBOOK.md)
die maßgeblichen Quellen.
