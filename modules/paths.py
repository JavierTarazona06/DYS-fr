import os, sys, shutil

def base_dir() -> str:
    """Project base dir (PyInstaller-friendly)."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def find_java() -> str:
    """Prefer bundled JRE, then LT_JAVA, JAVA_HOME, PATH."""
    base = base_dir()

    local_jre = os.path.join(base, "jre", "bin", "java.exe" if os.name == "nt" else "java")
    if os.path.isfile(local_jre):
        return local_jre

    env_java = os.environ.get("LT_JAVA")
    if env_java and os.path.isfile(env_java):
        return env_java

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        cand = os.path.join(java_home, "bin", "java.exe" if os.name == "nt" else "java")
        if os.path.isfile(cand):
            return cand

    which = shutil.which("java")
    if which:
        return which

    raise RuntimeError("Java 17+ not found. Install Temurin/OpenJDK 17 or bundle ./jre/")

def find_lt_jar() -> str:
    """Find the LanguageTool server JAR."""
    base = base_dir()

    env_jar = os.environ.get("LT_JAR")
    if env_jar and os.path.isfile(env_jar):
        return env_jar

    candidates = [
        os.path.join(base, "LanguageTool-6.7", "languagetool-server.jar"),
        os.path.join(base, "LanguageTool", "languagetool-server.jar"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p

    raise RuntimeError(
        "languagetool-server.jar not found. Place it under ./LanguageTool-6.7/ "
        "or set LT_JAR to its full path."
    )
