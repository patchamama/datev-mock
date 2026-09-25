#!/usr/bin/env bash
#
# Java (Spring Boot) DATEV-Mock launcher (Linux/macOS)
#
# This starts the *Java* mock (spring-boot/). For the Python/FastAPI mock,
# use the separate start.sh at the repo root instead -- the two are
# independent backends and this script never touches start.sh.
#
# Java 21+ detection order (stops at the first Java 21+ hit):
#   a) JAVA_HOME environment variable, if set and it contains a working
#      java binary. (This project's own well-known default install
#      location is C:\ELO\java on Windows -- no equivalent well-known
#      default location for this project is documented anywhere in this
#      repo for Linux/macOS, so that specific check is intentionally
#      skipped here; see start_java_datev_mock.bat for the Windows check.)
#   b) java already resolvable via PATH
#   c) Common OS-default install locations:
#        Linux:  /usr/lib/jvm/*, `update-alternatives --list java`
#        macOS:  /Library/Java/JavaVirtualMachines/*, `/usr/libexec/java_home -v 21`
# Only if none of the above yields Java 21+, a portable JDK 21 build
# (Eclipse Temurin/Adoptium) is downloaded into the project-local,
# gitignored spring-boot/.jdk21-portable/ and used for this launch only --
# nothing is installed system-wide and JAVA_HOME/PATH outside this
# script's own process are never touched.
#
# If spring-boot/target/datev-mock-*.jar doesn't exist yet, it is built
# first with the resolved Java. Note: this repo only commits the Windows
# Maven Wrapper script (spring-boot/mvnw.cmd), not a POSIX mvnw -- so
# instead of shelling out to a nonexistent mvnw, this script invokes the
# same wrapper jar (spring-boot/.mvn/wrapper/maven-wrapper.jar) directly,
# exactly the way mvnw.cmd itself does under the hood.

set -e

cd "$(dirname "${BASH_SOURCE[0]:-$0}")"
REPO_ROOT="$(pwd)"
SPRING_DIR="$REPO_ROOT/spring-boot"

PORT="${DATEV_MOCK_JAVA_PORT:-58553}"

while [ $# -gt 0 ]; do
    case "$1" in
        --port)
            PORT="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown argument \"$1\""
            echo "Usage: $0 [--port PORT]"
            echo "       (or set the DATEV_MOCK_JAVA_PORT environment variable)"
            exit 1
            ;;
    esac
done

JAVA_EXE=""
JAVA_HOME_RESOLVED=""
JAVA_MAJOR=""

# Runs "<candidate> -version", parses the major version, and returns 0
# (setting JAVA_MAJOR) only when it is Java 21 or newer.
check_java_version() {
    candidate="$1"
    raw="$("$candidate" -version 2>&1 | grep -i version | head -n1 || true)"
    ver="$(echo "$raw" | sed -n 's/.*version "\([^"]*\)".*/\1/p')"
    if [ -z "$ver" ]; then
        return 1
    fi
    major="$(echo "$ver" | cut -d. -f1)"
    minor="$(echo "$ver" | cut -d. -f2)"
    if [ "$major" = "1" ]; then
        major="$minor"
    fi
    case "$major" in
        ''|*[!0-9]*) return 1 ;;
    esac
    if [ "$major" -ge 21 ]; then
        JAVA_MAJOR="$major"
        return 0
    fi
    return 1
}

echo "[1/4] Detecting a usable Java 21+ install..."

# a) JAVA_HOME
if [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
    if check_java_version "$JAVA_HOME/bin/java"; then
        JAVA_EXE="$JAVA_HOME/bin/java"
        JAVA_HOME_RESOLVED="$JAVA_HOME"
        echo "      Found Java $JAVA_MAJOR via JAVA_HOME ($JAVA_HOME)."
    fi
fi

# b) java on PATH
if [ -z "$JAVA_EXE" ] && command -v java >/dev/null 2>&1; then
    PATH_JAVA="$(command -v java)"
    if check_java_version "$PATH_JAVA"; then
        JAVA_EXE="$PATH_JAVA"
        JAVA_HOME_RESOLVED="$(cd "$(dirname "$PATH_JAVA")/.." && pwd)"
        echo "      Found Java $JAVA_MAJOR on PATH ($PATH_JAVA)."
    fi
fi

# c) common OS-default install locations
if [ -z "$JAVA_EXE" ]; then
    OS_NAME="$(uname -s)"
    case "$OS_NAME" in
        Linux)
            for d in /usr/lib/jvm/*/; do
                [ -x "${d}bin/java" ] || continue
                if check_java_version "${d}bin/java"; then
                    JAVA_EXE="${d}bin/java"
                    JAVA_HOME_RESOLVED="${d%/}"
                    echo "      Found Java $JAVA_MAJOR at $JAVA_HOME_RESOLVED."
                    break
                fi
            done
            if [ -z "$JAVA_EXE" ] && command -v update-alternatives >/dev/null 2>&1; then
                for cand in $(update-alternatives --list java 2>/dev/null || true); do
                    if check_java_version "$cand"; then
                        JAVA_EXE="$cand"
                        JAVA_HOME_RESOLVED="$(cd "$(dirname "$cand")/.." && pwd)"
                        echo "      Found Java $JAVA_MAJOR via update-alternatives ($cand)."
                        break
                    fi
                done
            fi
            ;;
        Darwin)
            for d in /Library/Java/JavaVirtualMachines/*/Contents/Home/; do
                [ -x "${d}bin/java" ] || continue
                if check_java_version "${d}bin/java"; then
                    JAVA_EXE="${d}bin/java"
                    JAVA_HOME_RESOLVED="${d%/}"
                    echo "      Found Java $JAVA_MAJOR at $JAVA_HOME_RESOLVED."
                    break
                fi
            done
            if [ -z "$JAVA_EXE" ] && [ -x /usr/libexec/java_home ]; then
                CAND_HOME="$(/usr/libexec/java_home -v 21 2>/dev/null || true)"
                if [ -n "$CAND_HOME" ] && [ -x "$CAND_HOME/bin/java" ] && check_java_version "$CAND_HOME/bin/java"; then
                    JAVA_EXE="$CAND_HOME/bin/java"
                    JAVA_HOME_RESOLVED="$CAND_HOME"
                    echo "      Found Java $JAVA_MAJOR via java_home ($CAND_HOME)."
                fi
            fi
            ;;
    esac
fi

if [ -z "$JAVA_EXE" ]; then
    echo "      No usable Java 21+ install found anywhere on this machine."

    echo "[2/4] Bootstrapping a portable, project-local JDK 21 (no system install)..."
    PORTABLE_JDK_DIR="$SPRING_DIR/.jdk21-portable"
    EXISTING_JAVA="$(find "$PORTABLE_JDK_DIR" -type f -name java -path '*/bin/java' 2>/dev/null | head -n1 || true)"
    if [ -n "$EXISTING_JAVA" ]; then
        echo "      Reusing previously bootstrapped portable JDK in spring-boot/.jdk21-portable/ ..."
        JAVA_EXE="$EXISTING_JAVA"
        JAVA_HOME_RESOLVED="$(cd "$(dirname "$EXISTING_JAVA")/.." && pwd)"
    else
        OS_NAME="$(uname -s)"
        ARCH_NAME="$(uname -m)"
        case "$OS_NAME" in
            Linux) JDK_OS="linux" ;;
            Darwin) JDK_OS="mac" ;;
            *) JDK_OS="" ;;
        esac
        case "$ARCH_NAME" in
            x86_64|amd64) JDK_ARCH="x64" ;;
            aarch64|arm64) JDK_ARCH="aarch64" ;;
            *) JDK_ARCH="" ;;
        esac
        if [ -z "$JDK_OS" ] || [ -z "$JDK_ARCH" ]; then
            echo "ERROR: Could not determine a supported platform for automatic portable"
            echo "       JDK download (OS='$OS_NAME', arch='$ARCH_NAME')."
            echo "       Please install Java 21 yourself (or set JAVA_HOME) and re-run."
            exit 1
        fi
        if ! command -v curl >/dev/null 2>&1; then
            echo "ERROR: curl is required to bootstrap a portable JDK but was not found."
            echo "       Please install Java 21 yourself and re-run this script."
            exit 1
        fi

        JDK_URL="https://api.adoptium.net/v3/binary/latest/21/ga/${JDK_OS}/${JDK_ARCH}/jdk/hotspot/normal/eclipse"
        echo "      Downloading portable JDK 21 ($JDK_OS/$JDK_ARCH) from Eclipse Temurin/Adoptium ..."
        echo "      $JDK_URL"

        TMP_TARBALL="$(mktemp -t datev-mock-jdk21-XXXXXX.tar.gz)"
        if ! curl -fsSL "$JDK_URL" -o "$TMP_TARBALL"; then
            echo "ERROR: Failed to download the portable JDK 21 from $JDK_URL."
            rm -f "$TMP_TARBALL"
            exit 1
        fi

        rm -rf "$PORTABLE_JDK_DIR"
        mkdir -p "$PORTABLE_JDK_DIR"
        echo "      Extracting portable JDK into spring-boot/.jdk21-portable/ ..."
        if ! tar -xzf "$TMP_TARBALL" -C "$PORTABLE_JDK_DIR"; then
            echo "ERROR: Failed to extract the portable JDK 21 archive."
            rm -f "$TMP_TARBALL"
            exit 1
        fi
        rm -f "$TMP_TARBALL"

        # Adoptium tarballs nest the JVM one or two levels deep (a top-level
        # jdk-*/ on Linux, jdk-*/Contents/Home/ on macOS) -- search for it
        # instead of assuming a fixed depth.
        EXISTING_JAVA="$(find "$PORTABLE_JDK_DIR" -type f -name java -path '*/bin/java' 2>/dev/null | head -n1 || true)"
        if [ -z "$EXISTING_JAVA" ]; then
            echo "ERROR: Portable JDK extraction did not produce a bin/java executable."
            exit 1
        fi
        JAVA_EXE="$EXISTING_JAVA"
        JAVA_HOME_RESOLVED="$(cd "$(dirname "$EXISTING_JAVA")/.." && pwd)"
    fi
fi

check_java_version "$JAVA_EXE" || true
echo ""
echo "Using Java $JAVA_MAJOR at $JAVA_EXE"
echo ""

echo "[3/4] Locating the Spring Boot jar..."
JAR_PATH=""
for f in "$SPRING_DIR"/target/datev-mock-*.jar; do
    [ -e "$f" ] || continue
    JAR_PATH="$f"
    break
done

if [ -z "$JAR_PATH" ]; then
    echo "      No jar found in spring-boot/target/ -- building it now..."
    WRAPPER_JAR="$SPRING_DIR/.mvn/wrapper/maven-wrapper.jar"
    WRAPPER_PROPS="$SPRING_DIR/.mvn/wrapper/maven-wrapper.properties"
    if [ ! -f "$WRAPPER_JAR" ]; then
        # Mirrors mvnw.cmd's own self-bootstrap: download the wrapper jar
        # from wrapperUrl in maven-wrapper.properties (this repo does not
        # commit the jar itself, only mvnw.cmd does this download today).
        WRAPPER_URL="$(sed -n 's/^wrapperUrl=//p' "$WRAPPER_PROPS" 2>/dev/null)"
        if [ -z "$WRAPPER_URL" ]; then
            echo "ERROR: Could not find wrapperUrl in $WRAPPER_PROPS."
            exit 1
        fi
        echo "      Downloading Maven Wrapper jar..."
        if ! curl -fsSL "$WRAPPER_URL" -o "$WRAPPER_JAR"; then
            echo "ERROR: Failed to download the Maven wrapper jar from $WRAPPER_URL."
            exit 1
        fi
    fi
    export JAVA_HOME="$JAVA_HOME_RESOLVED"
    (
        cd "$SPRING_DIR"
        "$JAVA_EXE" -classpath "$WRAPPER_JAR" \
            -Dmaven.multiModuleProjectDirectory="$SPRING_DIR" \
            org.apache.maven.wrapper.MavenWrapperMain clean package
    )
    for f in "$SPRING_DIR"/target/datev-mock-*.jar; do
        [ -e "$f" ] || continue
        JAR_PATH="$f"
        break
    done
    if [ -z "$JAR_PATH" ]; then
        echo "ERROR: Build succeeded but no spring-boot/target/datev-mock-*.jar was found."
        exit 1
    fi
else
    echo "      Found existing jar: $JAR_PATH"
fi

echo "[4/4] Starting the Java DATEV mock..."
echo "      Java:    $JAVA_EXE (version $JAVA_MAJOR)"
echo "      Jar:     $JAR_PATH"
echo "      Port:    $PORT"
echo "      (override the port with --port PORT or the DATEV_MOCK_JAVA_PORT env var)"
echo ""

exec "$JAVA_EXE" -jar "$JAR_PATH" --server.port="$PORT"
