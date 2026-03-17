"""
Arrodes Unified - Launcher
Inicia o bot e permite parar com ENTER ou Ctrl+C.

Uso:
    python run.py                  (modo do .env ou combined)
    python run.py little           (modo little)
    python run.py arrodes          (modo arrodes)
    python run.py combined         (modo combined)
"""

import os
import sys
import signal
import subprocess
import threading

MODES = ("little", "arrodes", "combined")


def main() -> None:
    # Detecta modo
    mode = None
    if len(sys.argv) > 1 and sys.argv[1] in MODES:
        mode = sys.argv[1]

    project_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, "main.py"]
    if mode:
        cmd += ["--mode", mode]

    print("=" * 50)
    print(f"  Arrodes Unified Launcher")
    print(f"  Modo: {mode or '(definido no .env)'}")
    print(f"  Diretorio: {project_dir}")
    print("=" * 50)
    print()
    print("  Bot iniciando...")
    print("  Pressione ENTER ou Ctrl+C para parar.")
    print()
    print("-" * 50)

    # Inicia o bot como subprocesso
    process = subprocess.Popen(
        cmd,
        cwd=project_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    # Handler para Ctrl+C
    def shutdown(signum=None, frame=None):
        print()
        print("-" * 50)
        print("  Parando o bot...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        print("  Bot parado.")
        print("=" * 50)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Thread que espera ENTER para parar
    def wait_for_enter():
        try:
            input()
            shutdown()
        except EOFError:
            pass

    enter_thread = threading.Thread(target=wait_for_enter, daemon=True)
    enter_thread.start()

    # Espera o processo terminar
    exit_code = process.wait()

    if exit_code != 0 and exit_code != -15:  # -15 = SIGTERM (parada normal)
        print(f"\n  Bot encerrou com erro (codigo: {exit_code})")

    sys.exit(0)


if __name__ == "__main__":
    main()
