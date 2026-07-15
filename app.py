from flask import Flask, render_template, request, jsonify, Response
import requests
import time
import os
import urllib.parse
import json

app = Flask(__name__)

GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"

def llamar_ia(prompt, temp=0.8, max_tokens=3000):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": temp, "max_tokens": max_tokens}
    for intento in range(1, 6):
        try:
            r = requests.post(GROQ_URL, json=data, headers=headers, timeout=120)
            if r.status_code == 429:
                time.sleep(25); continue
            if r.status_code != 200:
                time.sleep(10 * intento); continue
            contenido = r.json()["choices"][0]["message"]["content"]
            if not contenido or len(contenido) < 3:
                time.sleep(10 * intento); continue
            return contenido
        except:
            time.sleep(15 * intento)
    return None

def analizar_cancion(cancion, artista):
    nombre_artista = artista if artista else "artista desconocido"
    prompt = f"""Analiza la canción "{cancion}" de {nombre_artista}.
1. EL SIGNIFICADO: ¿De qué trata?
2. LA EMOCIÓN: ¿Qué emoción transmite?
3. EL AMBIENTE: ¿Qué atmósfera crea?
4. PERSONAJES: ¿Hay personajes mencionados?
5. LUGARES: ¿Se mencionan lugares?
6. SÍMBOLOS: ¿Hay símbolos importantes?
Escribe un análisis claro y detallado."""
    return llamar_ia(prompt, temp=0.7)

def limpiar_titulo(titulo):
    if not titulo:
        return "Historia Sin Título"
    primera_linea = titulo.strip().split("\n")[0].strip()
    primera_linea = primera_linea.strip('"').strip("'").strip()
    return primera_linea if primera_linea else "Historia Sin Título"

def generar_titulo(cancion, artista, analisis):
    prompt = f"""Basado en la canción "{cancion}" y este análisis:
{analisis[:600]}
Crea un TÍTULO ORIGINAL para una historia inspirada en esta canción.
- Creativo y llamativo
- NO puede ser el nombre de la canción
- Máximo 8 palabras
- Responde ÚNICAMENTE con el título, sin explicaciones"""
    titulo = llamar_ia(prompt, temp=0.95, max_tokens=50)
    if not titulo:
        titulo = llamar_ia(f"Título poético de máximo 8 palabras inspirado en '{cancion}'. Solo el título.", temp=0.95, max_tokens=50)
    return limpiar_titulo(titulo)

def generar_bloque(bloque, cancion, artista, analisis, titulo, historial):
    nombre_artista = artista if artista else "Artista desconocido"
    inicio = (bloque - 1) * 10 + 1
    fin = bloque * 10
    if not historial:
        contexto = "Esta es la PARTE INICIAL. Introduce personajes, conflicto y ambiente."
    else:
        contexto = "RESUMEN PREVIO:\n" + "\n".join(historial)
    prompt = f"""Escribe la continuación de la historia "{titulo}", inspirada en "{cancion}" de {nombre_artista}.
ANÁLISIS: {analisis[:800]}
{contexto}
INSTRUCCIONES (parte {bloque} de 8):
- Escribe EXACTAMENTE 10 PÁRRAFOS numerados (Párrafo {inicio} al Párrafo {fin})
- Cada párrafo: 4 a 6 oraciones completas
- Refleja la emoción de la canción
- NO repitas lo anterior
- Separa párrafos con línea en blanco
Escribe SOLO los 10 párrafos:"""
    parte = llamar_ia(prompt, temp=0.85, max_tokens=3000)
    if not parte or len(parte) < 200:
        parte = llamar_ia(prompt, temp=0.75, max_tokens=3000)
    if not parte:
        parte = f"[Error generando bloque {bloque}]"
    return parte

def generar_imagen_url(prompt_texto):
    prompt_limpio = prompt_texto[:400].replace("\n", " ").strip()
    prompt_codificado = urllib.parse.quote(prompt_limpio)
    return f"{POLLINATIONS_URL}{prompt_codificado}?width=768&height=512&nologo=true"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generar", methods=["POST"])
def generar():
    data = request.json
    cancion = data.get("cancion", "").strip()
    artista = data.get("artista", "").strip()
    con_imagenes = data.get("imagenes", False)
    if not cancion:
        return jsonify({"error": "Falta el nombre de la canción"}), 400

    def stream():
        def enviar(tipo, contenido):
            yield f"data: {json.dumps({'tipo': tipo, 'contenido': contenido})}\n\n"

        yield from enviar("estado", "🎤 Analizando la canción...")
        analisis = analizar_cancion(cancion, artista)
        if not analisis:
            yield from enviar("error", "No se pudo analizar la canción.")
            return
        yield from enviar("estado", "✅ Análisis completado")

        yield from enviar("estado", "🏷️ Creando título único...")
        titulo = generar_titulo(cancion, artista, analisis)
        yield from enviar("titulo", titulo)

        yield from enviar("estado", "✍️ Generando historia (80 párrafos)...")
        nombre_artista = artista if artista else "Artista desconocido"
        encabezado = f"📖 {titulo.upper()}\n{'='*60}\n\n🎵 Inspirada en: {cancion} - {nombre_artista}\n{'='*60}\n\n"
        yield from enviar("historia_inicio", encabezado)

        historial = []
        for bloque in range(1, 9):
            inicio = (bloque - 1) * 10 + 1
            fin = bloque * 10
            yield from enviar("estado", f"📝 Bloque {bloque}/8 (párrafos {inicio}-{fin})...")
            parte = generar_bloque(bloque, cancion, artista, analisis, titulo, historial)
            yield from enviar("historia_bloque", parte + "\n\n")
            historial.append(f"Bloque {bloque} ({inicio}-{fin}): {parte[:300]}...")
            time.sleep(2)

        if con_imagenes:
            yield from enviar("estado", "🖼️ Generando imágenes...")
            prompt_portada = f"Book cover art for '{titulo}', cinematic, artistic, emotional, {analisis[:120]}"
            yield from enviar("imagen", {"tipo": "portada", "url": generar_imagen_url(prompt_portada), "label": "Portada"})
            for i in range(1, 9):
                prompt_img = f"Cinematic scene part {i} of 8 from story '{titulo}', {analisis[:100]}, dramatic"
                yield from enviar("imagen", {"tipo": "bloque", "url": generar_imagen_url(prompt_img), "label": f"Parte {i}"})

        yield from enviar("fin", "🎉 ¡Historia completada!")

    return Response(stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
