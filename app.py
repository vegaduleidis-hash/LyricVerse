from flask import Flask, render_template, request, jsonify
import requests
import time
import os
import urllib.parse

app = Flask(__name__)

GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

def llamar_ia(prompt, temp=0.8, max_tokens=3000):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temp,
        "max_tokens": max_tokens
    }
    for intento in range(1, 6):
        try:
            r = requests.post(GROQ_URL, json=data, headers=headers, timeout=120)
            if r.status_code == 429:
                time.sleep(25)
                continue
            if r.status_code != 200:
                time.sleep(10 * intento)
                continue
            contenido = r.json()["choices"][0]["message"]["content"]
            if not contenido or len(contenido) < 3:
                time.sleep(10 * intento)
                continue
            return contenido
        except Exception:
            time.sleep(15 * intento)
    return None

def analizar_cancion(cancion, artista):
    nombre_artista = artista if artista else "artista desconocido"
    prompt = f"""Analiza la cancion "{cancion}" de {nombre_artista}.
1. SIGNIFICADO: De que trata?
2. EMOCION: Que emocion transmite?
3. AMBIENTE: Que atmosfera crea?
4. PERSONAJES: Hay personajes?
5. LUGARES: Se mencionan lugares?
6. SIMBOLOS: Hay simbolos importantes?"""
    return llamar_ia(prompt, temp=0.7)

def limpiar_titulo(titulo):
    if not titulo:
        return "Historia Sin Titulo"
    linea = titulo.strip().split("\n")[0].strip()
    return linea.strip('"').strip("'").strip() or "Historia Sin Titulo"

def generar_titulo(cancion, artista, analisis):
    prompt = f"Crea un titulo original de maximo 8 palabras para una historia inspirada en la cancion {cancion}. Solo el titulo, sin explicaciones."
    titulo = llamar_ia(prompt, temp=0.95, max_tokens=50)
    return limpiar_titulo(titulo)

def generar_bloque(bloque, cancion, artista, analisis, titulo, historial):
    nombre_artista = artista if artista else "Artista desconocido"
    inicio = (bloque - 1) * 10 + 1
    fin = bloque * 10
    if not historial:
        contexto = "PARTE INICIAL. Introduce personajes, conflicto y ambiente."
    else:
        ultimos = historial[-2:]
        contexto = "RESUMEN PREVIO:\n" + "\n".join(ultimos)
    prompt = f"""Escribe parte {bloque} de 8 de la historia "{titulo}", inspirada en "{cancion}" de {nombre_artista}.
{contexto}
Escribe EXACTAMENTE 10 PARRAFOS numerados del {inicio} al {fin}.
Cada parrafo minimo 4 oraciones. Separa con linea en blanco."""
    parte = llamar_ia(prompt, temp=0.85, max_tokens=3000)
    if not parte or len(parte) < 100:
        parte = llamar_ia(prompt, temp=0.75, max_tokens=3000)
    return parte or f"[Error bloque {bloque}]"

def generar_imagen_url(prompt_texto):
    limpio = prompt_texto[:300].replace("\n", " ").strip()
    codificado = urllib.parse.quote(limpio)
    return f"{POLLINATIONS_URL}{codificado}?width=768&height=512&nologo=true"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analizar", methods=["POST"])
def analizar():
    data = request.json
    cancion = data.get("cancion", "").strip()
    artista = data.get("artista", "").strip()
    if not cancion:
        return jsonify({"error": "Falta cancion"}), 400
    analisis = analizar_cancion(cancion, artista)
    if not analisis:
        return jsonify({"error": "No se pudo analizar"}), 500
    titulo = generar_titulo(cancion, artista, analisis)
    return jsonify({"analisis": analisis, "titulo": titulo})

@app.route("/bloque", methods=["POST"])
def bloque():
    data = request.json
    resultado = generar_bloque(
        data["bloque"],
        data["cancion"],
        data["artista"],
        data["analisis"],
        data["titulo"],
        data.get("historial", [])
    )
    return jsonify({"texto": resultado})

@app.route("/imagen", methods=["POST"])
def imagen():
    data = request.json
    url = generar_imagen_url(data.get("prompt", ""))
    return jsonify({"url": url})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
