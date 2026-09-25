# Spring Boot DATEV mock — build, run, and smoke-test runbook

This is the standalone Java replacement for the FastAPI DATEV mock, living
entirely under `spring-boot/`. It builds and runs independently of the
root FastAPI application — no root-level file needs to change to build, run,
or configure it.

## Prerequisite: Java 21

A JDK 21 is required (the Maven Wrapper and `pom.xml` both target it).
Verified working build during this project: Zulu OpenJDK 21.0.1 at
`C:\ELO\java` (`java -version` reports `openjdk version "21.0.1"`). Any
Java 21 distribution works; set `JAVA_HOME` to point at it before building.

```
set JAVA_HOME=C:\path\to\your\jdk21
```

## Build

From `spring-boot/`, using the bundled Maven Wrapper:

```
cd spring-boot
mvnw.cmd clean package
```

This runs the full test suite (151 tests) before packaging and produces
`target/datev-mock-0.1.0-SNAPSHOT.jar`.

**Windows environment note:** if your shell has
`NoDefaultCurrentDirectoryInExePath=1` set (a common hardening default —
check with `echo %NoDefaultCurrentDirectoryInExePath%`), a bare `mvnw.cmd`
invocation from cmd.exe will fail with "command not found" even though the
file exists in the current directory, because cmd no longer searches the
current directory for executables by default. Use an explicit relative path
instead: `.\mvnw.cmd clean package`.

**Offline environments:** the wrapper needs network access on first run to
download `maven-wrapper.jar` and any not-yet-cached plugin (e.g.
`maven-clean-plugin`). If you must build fully offline, run once online
first to populate `~/.m2`, then subsequent builds can add `-o`.

Skip tests for a faster iterative build (not for the release/verification
build): `mvnw.cmd clean package -DskipTests`.

## Run

```
java -jar target/datev-mock-0.1.0-SNAPSHOT.jar
```

By default this starts on Spring Boot's default port `8080` — there is no
committed `application.properties`/`.yml`, so every setting is either a
Spring Boot default or passed on the command line. To pick a specific port
(recommended, since the FastAPI mock's own default is `58452` and you may
want both running side by side):

```
java -jar target/datev-mock-0.1.0-SNAPSHOT.jar --server.port=58553
```

This backend is plain HTTP, unlike the FastAPI mock's self-signed HTTPS —
there is no TLS setup here (not in this epic's scope; see PARITY.md's
honest-gaps list).

## Configuration knobs

- `--server.port=<port>`: the only currently-used Spring Boot override; every
  other endpoint behavior (mock data generation, override precedence,
  SQLite write overlays) is fixed at the application-code level, matching
  the FastAPI original's own lack of a settings file for this behavior.
- `datev_mock.db*` (SQLite write-overlay store) and `settings.json`
  (admin-editable settings persistence) are created next to wherever the
  JVM's working directory is when you launch the jar, and are gitignored.
  Delete them to reset all persisted state to defaults.
- CORS: `CorsConfig` allows `http(s)://localhost` / `http(s)://127.0.0.1`
  with any or no port — this lets the shared `/admin` frontend (served by
  FastAPI) call this backend's `/admin/api/*` endpoints cross-origin when
  its configurable "API base URL" setting points here (e.g.
  `http://127.0.0.1:58553`). Adding a genuinely different host/scheme
  requires a code change to `CorsConfig`'s pattern list (see PARITY.md).

## Smoke test

After starting the jar (adjust the port to whatever you launched with):

```
curl http://127.0.0.1:58553/actuator/health
# {"status":"UP"}

curl http://127.0.0.1:58553/datev/api/dms/v1/domains
# JSON array of DMS domain nodes
```

Both were run against a freshly built jar as part of this runbook's own
verification: `clean package` → 151/151 tests, `BUILD SUCCESS`, jar launched
on port `58601`, both requests returned HTTP 200 with the expected bodies,
then the process was stopped.

To exercise the admin API end-to-end instead of just two routes, point the
shared `/admin` frontend's "API base URL" setting (started separately from
the FastAPI mock) at this backend's `http://127.0.0.1:<port>` and use the
page normally — see the root `README.md` and `odd/tasks/
datev-mock-spring-boot-migration.md`'s SB9 entry for that frontend's own
setup.

## Full test suite (not just the smoke test)

```
mvnw.cmd test
```

Expected: `Tests run: 151, Failures: 0, Errors: 0`, `BUILD SUCCESS`. See
`PARITY.md` for how this suite's coverage maps against the FastAPI original's
own 375-test suite, route by route.
