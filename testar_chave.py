import sys
import os
import httpx
import json

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def main():
    print("=" * 60)
    print("    DIAGNÓSTICO DA CHAVE GOOGLE GEMINI")
    print("=" * 60)
    print()

    key = ""
    if len(sys.argv) > 1:
        key = sys.argv[1].strip()
    else:
        try:
            key = input("Cole sua chave de API do Gemini e aperte ENTER: ").strip()
        except Exception:
            pass

    key = key.strip("'\"").strip()
    if not key:
        print("[ERRO] Nenhuma chave informada!")
        input("\nPressione ENTER para sair...")
        return

    print(f"\nChave informada: {key[:6]}...{key[-4:]} (Tamanho: {len(key)} caracteres)")
    print("-" * 60)

    with httpx.Client(timeout=15.0) as client:
        # TESTE 1: ListModels (Valida existência e permissões básicas da chave)
        print("\n[TESTE 1] Verificando se a chave é reconhecida pelo Google (ListModels)...")
        try:
            url1 = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
            headers1 = {"x-goog-api-key": key}
            r1 = client.get(url1, headers=headers1)
            print(f"Status Code: {r1.status_code}")
            if r1.status_code == 200:
                models = [m.get("name", "").replace("models/", "") for m in r1.json().get("models", [])]
                flash_models = [m for m in models if "flash" in m]
                print("✓ Chave VÁLIDA e reconhecida pelo Google!")
                print(f"Modelos 'flash' disponíveis para a sua chave: {flash_models[:8]}")
            else:
                print(f"✗ Erro do Google no Teste 1:")
                print(r1.text)
        except Exception as e:
            print(f"✗ Falha de rede: {e}")

        # TESTE 2: Interactions API (gemini-3.8-flash)
        print("\n[TESTE 2] Testando Interactions API com gemini-3.8-flash...")
        try:
            url2 = "https://generativelanguage.googleapis.com/v1beta/interactions"
            headers2 = {
                "Content-Type": "application/json",
                "x-goog-api-key": key,
                "Api-Revision": "2026-05-20"
            }
            payload2 = {"model": "gemini-3.8-flash", "input": "Diga apenas OK"}
            r2 = client.post(url2, headers=headers2, json=payload2)
            print(f"Status Code: {r2.status_code}")
            if r2.status_code == 200:
                print("✓ Sucesso absoluto na Interactions API!")
                print(f"Resposta: {r2.text[:200]}")
            else:
                print(f"✗ Retorno do Google no Teste 2:")
                print(r2.text)
        except Exception as e:
            print(f"✗ Falha: {e}")

        # TESTE 3: generateContent clássico com gemini-2.0-flash / gemini-2.5-flash
        print("\n[TESTE 3] Testando generateContent clássico...")
        for candidate_model in ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
            try:
                url3 = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={key}"
                headers3 = {"Content-Type": "application/json", "x-goog-api-key": key}
                payload3 = {"contents": [{"parts": [{"text": "Diga OK"}]}]}
                r3 = client.post(url3, headers=headers3, json=payload3)
                print(f"Modelo '{candidate_model}' -> Status: {r3.status_code}")
                if r3.status_code == 200:
                    print(f"✓ Modelo '{candidate_model}' funcionou perfeitamente via generateContent!")
                    break
                else:
                    try:
                        err_msg = r3.json().get("error", {}).get("message", r3.text[:120])
                        print(f"  Aviso: {err_msg}")
                    except Exception:
                        pass
            except Exception as e:
                print(f"  Erro ao testar {candidate_model}: {e}")

    print("\n" + "=" * 60)
    print("Fim do diagnóstico. Copie as mensagens acima caso precise de ajuda.")
    print("=" * 60)
    input("\nPressione ENTER para fechar...")

if __name__ == "__main__":
    main()
