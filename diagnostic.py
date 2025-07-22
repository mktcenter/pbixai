import subprocess

caminho_exe = r"C:\Users\daniel.motta_beepsau\Downloads\pbi-tools.1.2.0\pbi-tools.exe"

try:
    print("🔍 Testando execução do pbi-tools.exe diretamente...")
    resultado = subprocess.run([caminho_exe, "--version"], check=True, capture_output=True, text=True)
    print("✅ Executável encontrado e rodando:")
    print(resultado.stdout)
except FileNotFoundError:
    print("❌ Arquivo não encontrado! Verifique o caminho do .exe.")
except subprocess.CalledProcessError as e:
    print(f"❌ Erro ao executar o comando: {e}")
    print(e.stderr)
