"""
Portal del Paciente - Prototipo de escritorio con Flet (Windows)
Instalar:  pip install flet
Ejecutar:  python portal_paciente_flet.py
"""
import asyncio
import random
import re
import unicodedata
from datetime import date, timedelta

import flet as ft

# ───────────────────────── Paleta (blanco / azul) ─────────────────────────
AZUL, AZUL_OSC, AZUL_CLARO, AZUL_SUAVE = "#1E6FD9", "#154C9C", "#E3EEFC", "#F4F8FE"
BLANCO, GRIS, TEXTO = "#FFFFFF", "#5B6B7F", "#1B2A3D"

# ───────────────────────── Datos simulados ─────────────────────────
ESPECIALIDADES = {
    "Clínica Médica": ["Dra. Laura Pérez", "Dr. Martín Gómez"],
    "Cardiología": ["Dr. Ricardo Salas", "Dra. Inés Molina"],
    "Pediatría": ["Dra. Carla Ruiz", "Dr. Pablo Benítez"],
    "Dermatología": ["Dra. Sofía Navarro"],
    "Traumatología": ["Dr. Andrés Ibarra", "Dr. Julián Torres"],
}
# Raíces de palabras para detectar la especialidad en lenguaje natural
RAICES = {"clinic": "Clínica Médica", "generalista": "Clínica Médica", "cardi": "Cardiología",
          "pediat": "Pediatría", "dermat": "Dermatología", "traumat": "Traumatología"}
HORARIOS = ["09:00", "09:30", "10:00", "10:30", "11:00", "15:00", "15:30", "16:00"]
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = "ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic"


# ───────────────────────── Utilidades de texto y fechas ─────────────────────────
def norm(txt):
    """Minúsculas y sin tildes, para comparar texto del usuario."""
    txt = unicodedata.normalize("NFD", txt.lower().strip())
    return "".join(c for c in txt if unicodedata.category(c) != "Mn")


def fmt_dni(dni):
    return f"{int(dni):,}".replace(",", ".")


def parse_dni(txt):
    """Devuelve el DNI (solo dígitos) si tiene 7 u 8 números; si no, None."""
    d = re.sub(r"[.\s-]", "", txt)
    return d if d.isdigit() and 7 <= len(d) <= 8 else None


def fechas_disponibles(n=10):
    """Próximos n días hábiles a partir de mañana."""
    out, d = [], date.today()
    while len(out) < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out


def etiqueta_fecha(d):
    return f"{DIAS[d.weekday()]} {d.strftime('%d/%m')}"


def parse_hora(t):
    """Busca una hora ('10:30', '10 hs', 'a las 10'). Devuelve (hora 'HH:MM' | None, texto sin la hora)."""
    for pat in (r"\b(\d{1,2})[:.](\d{2})\b", r"\b(\d{1,2})\s*(?:hs|h|horas)\b", r"\ba las (\d{1,2})\b"):
        m = re.search(pat, t)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2)) if m.lastindex == 2 else 0
            h = h + 12 if h < 7 else h          # "a las 4" -> 16:00
            return f"{h:02d}:{mi:02d}", t[:m.start()] + " " + t[m.end():]
    return None, t


def parse_fecha(t, estado=""):
    """Interpreta fechas coloquiales: 'martes 6', '6 de octubre', '06/10', 'mañana', 'el lunes'."""
    cands = fechas_disponibles()
    if "manana" in t:
        manana = date.today() + timedelta(days=1)
        return manana if manana in cands else None
    dia = mes = None
    if m := re.search(r"\b(\d{1,2})/(\d{1,2})\b", t):
        dia, mes = int(m.group(1)), int(m.group(2))
    elif m := re.search(rf"\b(\d{{1,2}})\s*(?:de\s+)?({MESES})", t):
        dia, mes = int(m.group(1)), MESES.split("|").index(m.group(2)) + 1
    elif m := re.search(r"\b(\d{1,2})\b", t):
        dia = int(m.group(1))
    wd = re.search(r"\b(lun|mar|mie|jue|vie)", t)
    wd = ["lun", "mar", "mie", "jue", "vie"].index(wd.group(1)) if wd else None
    if wd is None and (dia is None or (mes is None and estado != "fecha")):
        return None                              # un número suelto solo cuenta al elegir fecha
    for d in cands:
        if (wd is None or d.weekday() == wd) and (dia is None or d.day == dia) and (mes is None or d.month == mes):
            return d
    return None


class Sesion:
    """Estado compartido mientras la aplicación está abierta."""
    def __init__(self):
        self.dni = None      # DNI recordado en la sesión
        self.turnos = []     # turnos reservados (en memoria)

    def horarios_libres(self, prof, fecha):
        ocupados = {t["hora"] for t in self.turnos if t["prof"] == prof and t["fecha"] == fecha}
        ocupados |= set(random.Random(f"{prof}{fecha}").sample(HORARIOS, 3))  # agenda simulada
        return [h for h in HORARIOS if h not in ocupados]


# ───────────────────────── Lógica del chatbot ─────────────────────────
class Bot:
    """Máquina de estados + intenciones por palabras clave + extracción de datos (slots)
    desde una sola frase. responder(texto) -> (mensajes, opciones_rapidas)"""

    def __init__(self, sesion):
        self.s, self.estado, self.tmp, self.fechas_vis = sesion, "inicio", {}, []

    @staticmethod
    def lista(titulo, ops):
        return titulo + "\n" + "\n".join(f"{i}. {o}" for i, o in enumerate(ops, 1))

    def menu(self, pref=""):
        self.estado, self.tmp = "menu", {}
        return [pref + "¿Qué desea hacer?"], ["Sacar un turno", "Ver mis turnos",
                                              "Consultar otro DNI", "Cambiar de DNI"]

    def pedir_dni(self, destino):
        self.estado, self.tmp = "pedir_dni", {"destino": destino}
        return ["Escriba el DNI (solo números, 7 u 8 dígitos)."], []

    def iniciar(self):
        if self.s.dni:
            self.estado = "usar_dni"
            return ([f"¡Hola de nuevo! 👋 Tengo registrado el DNI {fmt_dni(self.s.dni)}.",
                     "¿Desea continuar con ese usuario o ingresar uno nuevo?"],
                    ["Continuar con este DNI", "Ingresar otro DNI"])
        self.estado, self.tmp = "pedir_dni", {"destino": "sesion"}
        return ["¡Hola! 👋 Soy el asistente virtual de turnos.",
                "Para comenzar, escriba su DNI (solo números)."], []

    def responder(self, texto):
        t = norm(texto)
        if t in ("menu", "inicio", "cancelar", "salir"):          # intenciones globales
            return self.menu("Operación cancelada. ") if self.s.dni else self.iniciar()
        if t in ("ayuda", "help", "?"):
            return (["Puedo ayudarle a sacar un turno, consultar turnos o cambiar de DNI. "
                     "Puede escribir frases como 'turno con cardiólogo el martes 6 a las 10'.",
                     "Escriba 'menu' en cualquier momento para volver al inicio."], [])
        return getattr(self, "_" + self.estado)(texto, t)

    # ---- DNI
    def _usar_dni(self, texto, t):
        if re.search(r"otro|nuevo|ingresar", t):
            return self.pedir_dni("sesion")
        if re.search(r"continu|\bsi\b|mismo|este", t):
            return self.menu(f"Perfecto, continuamos con el DNI {fmt_dni(self.s.dni)}. ")
        return ["No entendí. ¿Continuamos con el DNI actual o ingresamos otro?"], \
               ["Continuar con este DNI", "Ingresar otro DNI"]

    def _pedir_dni(self, texto, t):
        dni = parse_dni(texto)
        if not dni:
            return ["⚠️ El DNI no es válido. Debe tener 7 u 8 números, por ejemplo 30123456."], []
        if self.tmp.get("destino") == "consulta":                  # consulta puntual
            return self.mostrar_turnos(dni)
        self.s.dni = dni
        return self.menu(f"✅ DNI {fmt_dni(dni)} registrado. ")

    # ---- menú e intenciones
    def _menu(self, texto, t):
        consulta = re.search(r"mis turnos|consult|\bver\b|revisar", t)
        if m := re.search(r"\d[\d.]{5,10}\d", texto):              # "ver turnos del dni 3012..."
            if consulta and parse_dni(m.group()):
                return self.mostrar_turnos(parse_dni(m.group()))
        if consulta and re.search(r"otro|nuevo|distinto", t):
            return self.pedir_dni("consulta")
        if re.search(r"cambiar|otro dni|nuevo dni", t):
            return self.pedir_dni("sesion")
        if consulta:                                               # usa el DNI ya confirmado, sin repreguntar
            return self.mostrar_turnos(self.s.dni)
        if re.search(r"turno|sacar|pedir|reserv|agendar|solicitar|cita", t):
            self.tmp = {}
            self.llenar(texto, "menu")                             # toma especialidad/fecha/hora si ya vienen
            return self.avanzar()
        return ["No logré entenderle 🤔. Puede escribir 'sacar turno' o 'ver mis turnos'."], \
               ["Sacar un turno", "Ver mis turnos", "Consultar otro DNI", "Cambiar de DNI"]

    def mostrar_turnos(self, dni):
        mios = [x for x in self.s.turnos if x["dni"] == dni]
        if not mios:
            return self.menu(f"El DNI {fmt_dni(dni)} no tiene turnos registrados. ")
        lineas = [f"📅 {etiqueta_fecha(x['fecha'])} · {x['hora']} hs · {x['esp']} · {x['prof']}" for x in mios]
        return self.menu(f"Turnos del DNI {fmt_dni(dni)}:\n" + "\n".join(lineas) + "\n\n")

    # ---- reserva con relleno de datos (slots)
    def llenar(self, texto, estado=""):
        """Extrae de la frase todo lo que pueda: especialidad, profesional, fecha y hora."""
        d, t = self.tmp, norm(texto)
        hora, t_sin_hora = parse_hora(t)
        if hora:
            d["hora"] = hora
        for raiz, esp in RAICES.items():
            if raiz in t and d.get("esp") != esp:
                d["esp"] = esp
                d.pop("prof", None)
        for esp, profs in ESPECIALIDADES.items():
            for p in profs:
                if norm(p.split()[-1]) in t:                       # por apellido
                    d["esp"], d["prof"] = esp, p
        if fecha := parse_fecha(t_sin_hora, estado):
            d["fecha"] = fecha

    def avanzar(self, pref=""):
        """Pide el primer dato que falta, o resume el turno si ya está todo."""
        d = self.tmp
        if "esp" not in d:
            self.estado, ops = "esp", list(ESPECIALIDADES)
            return [pref + self.lista("Elija una especialidad (número o nombre):", ops)], ops
        if "prof" not in d:
            profs = ESPECIALIDADES[d["esp"]]
            if len(profs) == 1:
                d["prof"] = profs[0]
                pref += f"Para {d['esp']} atiende {profs[0]}. "
            else:
                self.estado = "prof"
                return [pref + self.lista(f"{d['esp']}. ¿Con qué profesional?", profs)], profs
        if "fecha" not in d:
            self.estado, self.fechas_vis = "fecha", fechas_disponibles()[:5]
            ops = [etiqueta_fecha(x) for x in self.fechas_vis]
            return [pref + self.lista("¿Qué día prefiere? (también puede escribir, por ej., 'martes 6')", ops)], ops
        libres = self.s.horarios_libres(d["prof"], d["fecha"])
        if d.get("hora") and d["hora"] not in libres:
            pref += f"⚠️ A las {d['hora']} no hay lugar. "
            d.pop("hora")
        if "hora" not in d:
            if not libres:
                d.pop("fecha")
                return self.avanzar(pref + "Ese día no hay horarios libres. ")
            self.estado = "hora"
            return [pref + self.lista(f"Horarios disponibles el {etiqueta_fecha(d['fecha'])}:", libres)], libres
        self.estado = "confirmar"
        return [f"{pref}Resumen del turno:\n• Paciente DNI: {fmt_dni(self.s.dni)}\n• {d['esp']} · {d['prof']}\n"
                f"• {etiqueta_fecha(d['fecha'])} a las {d['hora']} hs\n\n¿Confirmamos?"], ["Confirmar", "Cancelar"]

    def _slot(self, texto, t):
        """Maneja los estados esp / prof / fecha / hora."""
        clave = {"esp": "esp", "prof": "prof", "fecha": "fecha", "hora": "hora"}[self.estado]
        opciones = {"esp": list(ESPECIALIDADES), "prof": ESPECIALIDADES.get(self.tmp.get("esp"), []),
                    "fecha": self.fechas_vis,
                    "hora": self.s.horarios_libres(self.tmp.get("prof"), self.tmp.get("fecha"))
                    if self.estado == "hora" else []}[self.estado]
        if t.isdigit() and 1 <= int(t) <= len(opciones):          # eligió por número
            self.tmp[clave] = opciones[int(t) - 1]
        else:
            antes = self.tmp.get(clave)
            self.llenar(texto, self.estado)
            if self.tmp.get(clave) == antes:
                return self.avanzar("No logré entender ese dato 🤔. ")
        return self.avanzar()

    _esp = _prof = _fecha = _hora = _slot

    def _confirmar(self, texto, t):
        if re.search(r"\bsi\b|confirm|\bok\b|dale", t):
            d = self.tmp
            self.s.turnos.append({"dni": self.s.dni, "esp": d["esp"], "prof": d["prof"],
                                  "fecha": d["fecha"], "hora": d["hora"]})
            return self.menu("🎉 ¡Turno confirmado con éxito! Lo esperamos. ")
        if t == "no":
            return self.menu("Turno cancelado. ")
        return ["Responda 'Confirmar' o 'Cancelar'."], ["Confirmar", "Cancelar"]


# ───────────────────────── Interfaz (Flet) ─────────────────────────
def sombra():
    return ft.BoxShadow(blur_radius=18, color="#331E6FD9", offset=ft.Offset(0, 6))


def burbuja(texto, usuario=False):
    """Burbuja de chat; el ancho se ajusta al texto con un máximo."""
    ancho = min(470, max(90, max(len(l) for l in texto.split("\n")) * 8.6 + 38))
    cuerpo = ft.Container(
        content=ft.Text(texto, color=BLANCO if usuario else TEXTO, size=14.5, selectable=True),
        width=ancho, padding=ft.Padding.symmetric(horizontal=16, vertical=11),
        bgcolor=AZUL if usuario else AZUL_CLARO,
        border_radius=ft.BorderRadius(18, 18, 4 if usuario else 18, 18 if usuario else 4))
    return ft.Row([cuerpo], alignment=ft.MainAxisAlignment.END if usuario else ft.MainAxisAlignment.START)


def degradado(c1, c2):
    return ft.LinearGradient(begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT, colors=[c1, c2])


def es_hover(e):
    return str(e.data).lower() == "true"


def boton_pill(texto, icono, on_click):
    def hover(e):                                   # se agranda y se ilumina al pasar el mouse
        e.control.scale = 1.05 if es_hover(e) else 1.0
        e.control.gradient = degradado("#3D8BFF", AZUL) if es_hover(e) else degradado(AZUL, AZUL_OSC)
        e.control.update()

    def presion(e):                                 # se "hunde" al hacer click
        e.control.scale = 0.96
        e.control.update()

    return ft.Container(
        content=ft.Row([ft.Icon(icono, color=BLANCO, size=24),
                        ft.Text(texto, color=BLANCO, size=18, weight=ft.FontWeight.BOLD)],
                       alignment=ft.MainAxisAlignment.CENTER, spacing=12),
        width=340, height=62, border_radius=31, ink=True, on_click=on_click, shadow=sombra(),
        scale=1.0, animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        on_hover=hover, on_tap_down=presion, gradient=degradado(AZUL, AZUL_OSC))


def chip(texto, on_click):
    """Botón de respuesta rápida con efecto hover (se rellena de azul) y de presión."""
    def hover(e):
        on = es_hover(e)
        e.control.bgcolor = AZUL if on else BLANCO
        e.control.content.color = BLANCO if on else AZUL
        e.control.scale = 1.04 if on else 1.0
        e.control.update()

    def presion(e):
        e.control.bgcolor = AZUL_OSC
        e.control.content.color = BLANCO
        e.control.scale = 0.96
        e.control.update()

    return ft.Container(
        ft.Text(texto, color=AZUL, size=13, weight=ft.FontWeight.W_500), data=texto,
        padding=ft.Padding.symmetric(horizontal=16, vertical=8), ink=True,
        border=ft.Border.all(1.5, AZUL), border_radius=20, bgcolor=BLANCO, scale=1.0,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
        on_hover=hover, on_tap_down=presion, on_click=on_click)


def main(page: ft.Page):
    page.title = "Portal del Paciente"
    page.padding, page.bgcolor = 0, BLANCO
    page.window.width, page.window.height = 1000, 720
    page.window.min_width, page.window.min_height = 760, 600
    page.theme = ft.Theme(font_family="Segoe UI")
    sesion = Sesion()                      # persiste mientras la app esté abierta

    # ---------- Pantalla de inicio ----------
    def mostrar_inicio(e=None):
        page.controls.clear()
        logo = ft.Container(
            content=ft.Icon(ft.Icons.MEDICAL_SERVICES_ROUNDED, color=BLANCO, size=54),
            width=110, height=110, border_radius=55, alignment=ft.Alignment.CENTER, shadow=sombra(),
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                       colors=["#4C9BFF", AZUL_OSC]))
        etiquetas = ft.Row(
            [ft.Container(ft.Row([ft.Icon(ic, color=AZUL, size=18), ft.Text(tx, color=AZUL_OSC, size=13)],
                                 spacing=6, tight=True),
                          padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                          bgcolor=AZUL_CLARO, border_radius=20)
             for ic, tx in [(ft.Icons.EVENT_AVAILABLE, "Turnos online"), (ft.Icons.HISTORY, "Sus consultas"),
                            (ft.Icons.SUPPORT_AGENT, "Asistente virtual")]],
            alignment=ft.MainAxisAlignment.CENTER, spacing=10)
        page.add(ft.Container(
            expand=True, alignment=ft.Alignment.CENTER,
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_CENTER, end=ft.Alignment.BOTTOM_CENTER,
                                       colors=[BLANCO, AZUL_CLARO]),
            content=ft.Column(
                [logo,
                 ft.Text("Centro Médico Vida", color=AZUL, size=15, weight=ft.FontWeight.W_600),
                 ft.Text("Portal del Paciente", color=AZUL_OSC, size=40, weight=ft.FontWeight.BOLD),
                 ft.Text("¡Bienvenido/a! Gestione sus turnos médicos de forma rápida y simple.",
                         color=GRIS, size=16, text_align=ft.TextAlign.CENTER),
                 ft.Container(height=14), boton_pill("Chatbot de turnos", ft.Icons.CHAT_BUBBLE_ROUNDED, mostrar_chat),
                 ft.Container(height=10), etiquetas],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER,
                spacing=8)))
        page.update()

    # ---------- Pantalla del chat (se crea desde cero en cada ingreso) ----------
    def mostrar_chat(e=None):
        page.controls.clear()
        bot = Bot(sesion)
        conversacion = ft.ListView(expand=True, spacing=10, auto_scroll=True,
                                   padding=ft.Padding.symmetric(horizontal=22, vertical=16))
        rapidas = ft.Row(wrap=True, spacing=8, run_spacing=8)
        entrada = ft.TextField(hint_text="Escriba su mensaje…", expand=True, filled=True, bgcolor=BLANCO,
                               border_radius=26, border_color="#9DBFEA", focused_border_color=AZUL,
                               color=TEXTO, text_size=15, cursor_color=AZUL,
                               hint_style=ft.TextStyle(color="#8A9BB0"),
                               content_padding=ft.Padding.symmetric(horizontal=20, vertical=14),
                               autofocus=True)

        def bot_dice(mensajes, opciones):
            for m in mensajes:
                conversacion.controls.append(burbuja(m))
            rapidas.controls = [chip(o, click_chip) for o in opciones]
            page.update()

        async def enviar(texto=None):
            texto = (texto or entrada.value or "").strip()
            if not texto:
                return
            entrada.value = ""
            conversacion.controls.append(burbuja(texto, usuario=True))
            rapidas.controls = []
            escribiendo = burbuja("escribiendo…")                   # indicador breve
            conversacion.controls.append(escribiendo)
            page.update()
            await asyncio.sleep(0.45)
            conversacion.controls.remove(escribiendo)
            bot_dice(*bot.responder(texto))
            await entrada.focus()                                   # el campo sigue activo para escribir

        async def enviar_texto(e):                                  # Enter o botón Enviar
            await enviar()

        entrada.on_submit = enviar_texto                            # Enter: se asigna la función async directamente

        async def click_chip(e):                                    # botones de respuesta rápida
            await enviar(e.control.data)

        encabezado = ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            gradient=ft.LinearGradient(begin=ft.Alignment.CENTER_LEFT, end=ft.Alignment.CENTER_RIGHT,
                                       colors=[AZUL, AZUL_OSC]),
            content=ft.Row([
                ft.IconButton(ft.Icons.HOME_ROUNDED, icon_color=BLANCO, icon_size=26,
                              hover_color="#33FFFFFF", highlight_color="#55FFFFFF",
                              tooltip="Volver al menú principal", on_click=mostrar_inicio),
                ft.Container(ft.Icon(ft.Icons.SMART_TOY_ROUNDED, color=AZUL, size=24), width=40, height=40,
                             bgcolor=BLANCO, border_radius=20, alignment=ft.Alignment.CENTER),
                ft.Column([ft.Text("Asistente de turnos", color=BLANCO, size=17, weight=ft.FontWeight.BOLD),
                           ft.Text("● En línea", color="#B9D6FF", size=12)], spacing=0)], spacing=12))
        pie = ft.Container(
            bgcolor=AZUL_SUAVE, padding=ft.Padding(16, 10, 16, 14),
            content=ft.Column([rapidas, ft.Row([entrada, ft.IconButton(
                ft.Icons.SEND_ROUNDED, icon_color=BLANCO, bgcolor=AZUL, icon_size=22,
                hover_color=AZUL_OSC, highlight_color="#0F3A78",
                tooltip="Enviar", on_click=enviar_texto)], spacing=10)], spacing=10))
        page.add(ft.Column([encabezado, ft.Container(conversacion, expand=True, bgcolor=BLANCO), pie],
                           expand=True, spacing=0))
        bot_dice(*bot.iniciar())                                    # saludo inicial en cada ingreso

    mostrar_inicio()


if __name__ == "__main__":
    ft.run(main)