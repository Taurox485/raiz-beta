"""
test_pdf.py — Prueba manual del generador de PDFs de rAÍz

Usa un historial simulado realista para probar el pipeline completo
sin depender de un estudiante que haya terminado el proceso.

Uso:
    python test_pdf.py

Genera en la raíz del proyecto:
    test_estudiante.pdf
    test_orientador.pdf
"""

import sys
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Secrets ────────────────────────────────────────────────────────────────────
secrets = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))
API_KEY = secrets["GEMINI_API_KEY"]

# ── Gemini client ──────────────────────────────────────────────────────────────
from google import genai
MODEL  = "gemini-3.1-flash-lite"
client = genai.Client(api_key=API_KEY)

# ── System instruction ─────────────────────────────────────────────────────────
system_instruction = (ROOT / "instrucciones.txt").read_text(encoding="utf-8").strip()

# ── Generador ─────────────────────────────────────────────────────────────────
import pdf_generator

# ── Estudiante simulado ───────────────────────────────────────────────────────
ESTUDIANTE_SIMULADO = {
    "id":           "00000000-0000-0000-0000-000000000001",
    "estudiante_id": "ALC-9-2026-0001",
    "nombre":       "Valentina",
    "apellido":     "Ortiz Mina",
    "grado":        9,
    "sede_id":      1,
    "perfil_riesgo": "medio",       # bajo | medio | alto | sin_evaluar
    "mentoria_completada": True,
}

# ── Sede simulada (normalmente viene de db.get_sede_info) ─────────────────────
# Parcheamos la función para no depender de la DB en este test
import pdf_generator as _pg
_pg.db.get_sede_info = lambda sede_id: {
    "institucion":       "Institución Educativa La Pradera",
    "municipio":         "Alcalá",
    "orientador_nombre": "Mg. Patricia Salcedo",
}

# ── Historial simulado (4 sesiones completas, incluyendo [FIN_CONSEJERIA]) ────
HISTORIAL_SIMULADO = [
    # SESIÓN 1
    {
        "rol": "model",
        "sesion_numero": 1,
        "contenido": (
            "¡Hola! Soy rAÍz, tu mentor de proyecto de vida 🌱\n"
            "Soy una inteligencia artificial diseñada para acompañarte. "
            "¿Listo/a para arrancar? ¿Cómo preferís que te llame?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 1,
        "contenido": "Hola, me llamo Valentina pero todos me dicen Vale.",
    },
    {
        "rol": "model",
        "sesion_numero": 1,
        "contenido": "Perfecto, Vale. Cuéntame, ¿cómo es un día normal tuyo entre semana?",
    },
    {
        "rol": "user",
        "sesion_numero": 1,
        "contenido": (
            "Me levanto a las 5 porque vivo lejos del colegio y toca madrugar. "
            "Llego como a las 7, estudio hasta las 2, y en la tarde ayudo a mi mamá "
            "en la tienda que tenemos en la casa. Los fines de semana a veces voy "
            "con mi tío a la finca a ayudar con la caña."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 1,
        "contenido": (
            "Eso es bastante. ¿Y en ese trajín del día, hay algún momento que disfrutes "
            "especialmente, algo que haga que el tiempo pase rápido?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 1,
        "contenido": (
            "Sí, cuando estoy en la tienda y me toca hacer las cuentas del día. "
            "Me gusta ordenar todo, saber cuánto se vendió, qué faltó. "
            "También me gusta mucho cuando en el colegio hacemos trabajos de biología, "
            "eso de estudiar cómo funcionan las plantas y los animales."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 1,
        "contenido": (
            "¿Con quién vivís en tu casa, Vale?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 1,
        "contenido": (
            "Con mi mamá y mis dos hermanos menores. Mi papá se fue cuando yo tenía 8 años "
            "y no sabemos mucho de él. Mi mamá trabaja todo el día en la tienda y en las noches "
            "está muy cansada, pero siempre me pregunta cómo me fue en el colegio."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 1,
        "contenido": (
            "Tu mamá suena a una persona muy importante para vos. ¿Hay alguien más, "
            "fuera de tu familia, que admires o que te parezca un ejemplo a seguir?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 1,
        "contenido": (
            "Mi tío Hernando. Él estudió técnico en el SENA, montó su propio negocio de "
            "mantenimiento agrícola y ahora tiene como 5 empleados. Empezó de la nada "
            "y siempre dice que la clave es no quedarse quieto."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 1,
        "contenido": (
            "Qué ejemplo tan concreto y cercano. Te dejo una misión para cuando volvamos "
            "a hablar: preguntale a tu tío Hernando cuál fue el momento más difícil que "
            "tuvo cuando arrancó su negocio y cómo lo superó. "
            "Hasta la próxima, Vale. [RIESGO_MEDIO]"
        ),
    },

    # SESIÓN 2
    {
        "rol": "model",
        "sesion_numero": 2,
        "contenido": (
            "Hola de nuevo, Vale. La última vez me contaste que los fines de semana "
            "vas con tu tío a la finca. ¿Pudiste preguntarle lo de la misión?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 2,
        "contenido": (
            "Sí, le pregunté. Me dijo que lo más difícil fue convencer a los clientes "
            "de confiarle su maquinaria siendo tan joven. Dijo que tuvo que demostrar "
            "que sabía más que los que tenían más años. Me pareció muy bacano eso."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 2,
        "contenido": (
            "Eso que te contó tu tío tiene mucho que ver con algo que he notado en vos. "
            "Cuando me hablaste de las cuentas de la tienda, ¿qué fue lo más satisfactorio "
            "de ese momento para vos?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 2,
        "contenido": (
            "Que al final todo cuadraba. Yo lo hice sola, sin calculadora, y le mostré "
            "a mi mamá y ella quedó sorprendida porque encontré un error que ella no había visto. "
            "Sentí que servía para algo."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 2,
        "contenido": (
            "Ahora hagamos un ejercicio rápido. Te voy a dar pares de actividades y "
            "me decís cuál preferís. ¿Listo para la Ronda Relámpago?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 2,
        "contenido": "Sí, dale.",
    },
    {
        "rol": "model",
        "sesion_numero": 2,
        "contenido": "¿Preferís: (A) organizar el inventario de la tienda o (B) enseñarle a un vecino cómo hacerlo?",
    },
    {
        "rol": "user",
        "sesion_numero": 2,
        "contenido": "La A, definitivamente. Me gusta más hacer las cosas que explicarlas.",
    },
    {
        "rol": "model",
        "sesion_numero": 2,
        "contenido": "¿Preferís: (A) diseñar un experimento de biología o (B) escribir un cuento sobre naturaleza?",
    },
    {
        "rol": "user",
        "sesion_numero": 2,
        "contenido": "La A también. Me gusta más lo concreto, lo que puedo ver y medir.",
    },
    {
        "rol": "model",
        "sesion_numero": 2,
        "contenido": "¿Preferís: (A) reparar una bomba de agua dañada o (B) hacer una presentación sobre por qué se dañó?",
    },
    {
        "rol": "user",
        "sesion_numero": 2,
        "contenido": "La A. Una vez ayudé a mi tío a reparar la bomba de agua de la finca. Fue complicado pero lo logramos.",
    },
    {
        "rol": "model",
        "sesion_numero": 2,
        "contenido": (
            "Ese episodio de la bomba de agua me dice mucho. ¿Cómo supieron qué hacer "
            "si nunca lo habían hecho antes?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 2,
        "contenido": (
            "Mi tío buscó un video en YouTube y yo leí el manual que venía con la bomba. "
            "Nos tocó improvisar con lo que teníamos porque la pieza exacta no la conseguimos "
            "en el pueblo. Al final funcionó."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 2,
        "contenido": (
            "Vale, eso que acabás de describir — leer, analizar, improvisar con recursos limitados "
            "y resolver el problema — eso no lo hace cualquiera. "
            "Tu misión: fijate esta semana en qué momento del día sentís que el tiempo pasa volando "
            "sin darte cuenta. [RIESGO_MEDIO]"
        ),
    },

    # SESIÓN 3
    {
        "rol": "model",
        "sesion_numero": 3,
        "contenido": (
            "¡Hola Vale! Me quedé pensando en eso que me dijiste de que encontraste el error "
            "en las cuentas de tu mamá. ¿Encontraste ese momento donde el tiempo vuela?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 3,
        "contenido": (
            "Sí, cuando estoy estudiando biología o cuando le ayudo a mi tío a revisar "
            "los registros de la finca. Ahí no me aburro."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 3,
        "contenido": "¿Y qué es lo que más te gusta de los registros de la finca?",
    },
    {
        "rol": "user",
        "sesion_numero": 3,
        "contenido": (
            "Ver cómo los números cuentan una historia. Si la producción bajó, "
            "preguntarme por qué. Si subió, entender qué pasó diferente. "
            "Mi tío dice que yo tengo ojo para eso."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 3,
        "contenido": (
            "Vale, si pudieras imaginar cómo querés que sea tu vida cuando termines el colegio, "
            "¿qué imagen te aparece, aunque sea borrosa?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 3,
        "contenido": (
            "Me veo trabajando en algo relacionado con el campo pero no solo metida en la tierra. "
            "Algo donde pueda usar los números, entender cómo mejorar los cultivos, "
            "quizás ayudar a familias como la mía a que les vaya mejor. "
            "No sé si eso existe como trabajo."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 3,
        "contenido": "¿Y qué te detiene o te da miedo cuando pensás en ese futuro?",
    },
    {
        "rol": "user",
        "sesion_numero": 3,
        "contenido": (
            "El dinero, principalmente. Estudiar fuera de Alcalá cuesta mucho "
            "y no sé si mi mamá puede. También me da miedo dejarla sola con mis hermanos. "
            "Ella necesita ayuda en la tienda."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 3,
        "contenido": (
            "Esos miedos son muy reales y los entiendo. Pero también noto que "
            "el deseo de ayudar a familias como la tuya es muy fuerte. "
            "¿Conocés alguna opción de estudio cerca de Alcalá o en el Valle "
            "que te llame la atención?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 3,
        "contenido": (
            "El SENA de Cartago tiene algo de agroindustria, creo. Y una vez escuché "
            "que la Universidad del Valle tiene sede en Tuluá. Pero no sé bien qué ofrecen."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 3,
        "contenido": (
            "Tu misión: preguntale a tu tío Hernando qué estudió exactamente en el SENA "
            "y si le ha servido para lo que hace hoy. "
            "Eso te va a dar información muy concreta. [RIESGO_MEDIO]"
        ),
    },

    # SESIÓN 4 — CIERRE
    {
        "rol": "model",
        "sesion_numero": 4,
        "contenido": (
            "Vale, llegamos a nuestra última sesión. Me alegra mucho que hayas llegado hasta acá. "
            "¿Pudiste hablar con tu tío sobre el SENA?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 4,
        "contenido": (
            "Sí. Estudió Técnico en Producción Agropecuaria. Dice que sí le sirvió mucho, "
            "que aprendió cosas prácticas que no hubiera aprendido en ningún otro lado. "
            "Y que el SENA tiene convenios para que uno no pague."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 4,
        "contenido": (
            "Qué información tan valiosa. Antes de cerrar, quiero preguntarte algo: "
            "mirando todo lo que hablamos estas cuatro sesiones, "
            "¿qué es lo que más te llevás?"
        ),
    },
    {
        "rol": "user",
        "sesion_numero": 4,
        "contenido": (
            "Que lo que hago todos los días — las cuentas, los registros de la finca, "
            "arreglar cosas cuando se dañan — no es cualquier cosa. Que tengo habilidades "
            "que no sabía que tenía. Y que querer quedarme cerca de mi familia no significa "
            "que no pueda tener un buen futuro."
        ),
    },
    {
        "rol": "model",
        "sesion_numero": 4,
        "contenido": (
            "Vale, eso que acabás de decir es exactamente lo que este proceso buscaba. "
            "Te felicito por tu apertura, tu honestidad y tu constancia. "
            "Tu perfil te va a llegar en un documento que podés compartir con quien quieras. "
            "Seguí construyendo con esa raíz tan firme que tenés. "
            "[RIESGO_MEDIO] [FIN_CONSEJERIA]"
        ),
    },
]


def main():
    print(f"Estudiante : {ESTUDIANTE_SIMULADO['nombre']} {ESTUDIANTE_SIMULADO['apellido']}")
    print(f"Mensajes   : {len(HISTORIAL_SIMULADO)}")
    print("Generando PDFs con Gemini...")

    pdf_est, pdf_ori = pdf_generator.generar_pdfs(
        ESTUDIANTE_SIMULADO,
        HISTORIAL_SIMULADO,
        client,
        MODEL,
        system_instruction,
    )

    dest_est = ROOT / "test_estudiante.pdf"
    dest_ori = ROOT / "test_orientador.pdf"

    dest_est.write_bytes(pdf_est)
    print(f"Guardado   : {dest_est}")

    dest_ori.write_bytes(pdf_ori)
    print(f"Guardado   : {dest_ori}")

    print("\n[OK] PDFs generados exitosamente.")


if __name__ == "__main__":
    main()
