"""
Portal del Paciente - Prototipo de escritorio (Windows)
Requiere:  pip install customtkinter
Ejecutar:  python portal_paciente.py
"""
import random
import re
import unicodedata
from datetime import date, timedelta

import customtkinter as ctk
import tkinter as tk

# ───────────────────────── Paleta (blanco / azul) ─────────────────────────
AZUL, AZUL_OSC, AZUL_CLARO = "#1E6FD9", "#154C9C", "#E8F1FC"
BLANCO, GRIS, TEXTO = "#FFFFFF", "#5B6B7F", "#1B2A3D"

# ───────────────────────── Datos simulados ─────────────────────────
ESPECIALIDADES = {
    "Clínica Médica": ["Dra. Laura Pérez", "Dr. Martín Gómez"],
    "Cardiología": ["Dr. Ricardo Salas", "Dra. Inés Molina"],
    "Pediatría": ["Dra. Carla Ruiz", "Dr. Pablo Benítez"],
    "Dermatología": ["Dra. Sofía Navarro"],
    "Traumatología": ["Dr. Andrés Ibarra", "Dr. Julián Torres"],
}
HORARIOS = ["09:00", "09:30", "10:00", "10:30", "11:00", "15:00", "15:30", "16:00"]
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


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


def fechas_disponibles(n=5):
    """Próximos n días hábiles a partir de mañana."""
    out, d = [], date.today()
    while len(out) < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return out


def etiqueta_fecha(d):
    return f"{DIAS[d.weekday()]} {d.strftime('%d/%m')}"


class Sesion:
    """Estado compartido durante toda la ejecución de la app."""
    def __init__(self):
        self.dni = None      # DNI recordado en la sesión
        self.turnos = []     # turnos reservados (en memoria)

    def horarios_libres(self, prof, fecha):
        ocupados = {t["hora"] for t in self.turnos if t["prof"] == prof and t["fecha"] == fecha}
        # Simula agenda ya ocupada de forma estable por profesional/fecha
        ocupados |= set(random.Random(f"{prof}{fecha}").sample(HORARIOS, 3))
        return [h for h in HORARIOS if h not in ocupados]


# ───────────────────────── Lógica del chatbot ─────────────────────────
class Bot:
    """Máquina de estados + reconocimiento de intenciones por palabras clave.
    responder(texto) -> (lista_de_mensajes, lista_de_opciones_rapidas)"""

    def __init__(self, sesion):
        self.s, self.estado, self.tmp = sesion, "inicio", {}

    # ---- utilidades
    @staticmethod
    def elegir(texto, opciones):
        """Devuelve el índice elegido por número o por nombre (o None)."""
        t = norm(texto)
        if t.isdigit() and 1 <= int(t) <= len(opciones):
            return int(t) - 1
        for i, o in enumerate(opciones):
            if len(t) >= 3 and (t in norm(o) or norm(o) in t):
                return i
        return None

    @staticmethod
    def lista(titulo, opciones):
        return titulo + "\n" + "\n".join(f"{i}. {o}" for i, o in enumerate(opciones, 1))

    def menu(self, pref=""):
        self.estado, self.tmp = "menu", {}
        return [pref + "¿Qué desea hacer?"], ["Sacar un turno", "Ver mis turnos", "Cambiar de DNI"]

    def pedir_dni(self, destino):
        self.estado, self.tmp = "pedir_dni", {"destino": destino}
        return ["Escriba el DNI (solo números, 7 u 8 dígitos)."], []

    # ---- punto de entrada
    def iniciar(self):
        if self.s.dni:
            self.estado = "usar_dni"
            return ([f"¡Hola de nuevo! 👋 Tengo registrado el DNI {fmt_dni(self.s.dni)}.",
                     "¿Desea continuar con ese usuario o ingresar uno nuevo?"],
                    ["Continuar con este DNI", "Ingresar otro DNI"])
        self.estado = "pedir_dni"
        self.tmp = {"destino": "sesion"}
        return ["¡Hola! 👋 Soy el asistente virtual de turnos.",
                "Para comenzar, escriba su DNI (solo números)."], []

    def responder(self, texto):
        t = norm(texto)
        # Intenciones globales (válidas en cualquier momento)
        if t in ("menu", "inicio", "cancelar", "salir"):
            return self.menu("Operación cancelada. ") if self.s.dni else self.iniciar()
        if t in ("ayuda", "help", "?"):
            return (["Puedo ayudarle a: sacar un turno, consultar sus turnos o cambiar de DNI.",
                     "Escriba 'menu' en cualquier momento para volver al inicio."], [])
        return getattr(self, "_" + self.estado)(texto, t)

    # ---- estados
    def _usar_dni(self, texto, t):
        if "continu" in t or t in ("si", "mismo") or "este" in t:
            return self.menu(f"Perfecto, continuamos con el DNI {fmt_dni(self.s.dni)}. ")
        if "otro" in t or "nuevo" in t or "ingresar" in t:
            return self.pedir_dni("sesion")
        return ["No entendí. ¿Continuamos con el DNI actual o ingresamos otro?"], \
               ["Continuar con este DNI", "Ingresar otro DNI"]

    def _pedir_dni(self, texto, t):
        dni = parse_dni(texto)
        if not dni:
            return ["⚠️ El DNI no es válido. Debe tener 7 u 8 números, por ejemplo 30123456."], []
        if self.tmp.get("destino") == "consulta":      # consulta puntual, no cambia la sesión
            return self.mostrar_turnos(dni)
        self.s.dni = dni
        return self.menu(f"✅ DNI {fmt_dni(dni)} registrado. ")

    def _menu(self, texto, t):
        if re.search(r"cambiar|otro dni|nuevo dni", t):
            return self.pedir_dni("sesion")
        if re.search(r"mis turnos|consult|\bver\b|revisar|tengo", t):
            self.estado = "consulta_quien"
            return [f"¿Consultamos los turnos del DNI {fmt_dni(self.s.dni)} o de otro?"], \
                   ["Mi DNI actual", "Otro DNI"]
        if re.search(r"turno|sacar|pedir|reserv|agendar|solicitar|cita", t):
            return self.paso_especialidad()
        return ["No logré entenderle 🤔. Puede escribir 'sacar turno' o 'ver mis turnos'."], \
               ["Sacar un turno", "Ver mis turnos", "Cambiar de DNI"]

    # -- consulta
    def _consulta_quien(self, texto, t):
        if "otro" in t:
            return self.pedir_dni("consulta")
        if "actual" in t or "mi" in t or t == "si":
            return self.mostrar_turnos(self.s.dni)
        return ["Elija una opción, por favor."], ["Mi DNI actual", "Otro DNI"]

    def mostrar_turnos(self, dni):
        mios = [x for x in self.s.turnos if x["dni"] == dni]
        if not mios:
            return self.menu(f"El DNI {fmt_dni(dni)} no tiene turnos registrados. ")
        lineas = [f"📅 {etiqueta_fecha(x['fecha'])} {x['hora']} hs · {x['esp']} · {x['prof']}" for x in mios]
        return self.menu(f"Turnos del DNI {fmt_dni(dni)}:\n" + "\n".join(lineas) + "\n\n")

    # -- reserva paso a paso
    def paso_especialidad(self):
        self.estado, self.tmp = "esp", {}
        ops = list(ESPECIALIDADES)
        return [self.lista("Elija una especialidad (número o nombre):", ops)], ops

    def _esp(self, texto, t):
        ops = list(ESPECIALIDADES)
        i = self.elegir(texto, ops)
        if i is None:
            return ["No reconocí la especialidad. Pruebe con el número."], ops
        self.tmp["esp"] = ops[i]
        self.estado = "prof"
        profs = ESPECIALIDADES[ops[i]]
        return [self.lista(f"{ops[i]}. ¿Con qué profesional?", profs)], profs

    def _prof(self, texto, t):
        profs = ESPECIALIDADES[self.tmp["esp"]]
        i = self.elegir(texto, profs)
        if i is None:
            return ["No reconocí al profesional. Pruebe con el número."], profs
        self.tmp["prof"] = profs[i]
        self.estado = "fecha"
        fechas = fechas_disponibles()
        self.tmp["fechas"] = fechas
        ops = [etiqueta_fecha(d) for d in fechas]
        return [self.lista("¿Qué día prefiere?", ops)], ops

    def _fecha(self, texto, t):
        ops = [etiqueta_fecha(d) for d in self.tmp["fechas"]]
        i = self.elegir(texto, ops)
        if i is None:
            return ["No reconocí la fecha. Pruebe con el número."], ops
        fecha = self.tmp["fechas"][i]
        libres = self.s.horarios_libres(self.tmp["prof"], fecha)
        if not libres:
            return ["Ese día no hay horarios libres. Elija otra fecha."], ops
        self.tmp["fecha"], self.estado = fecha, "hora"
        return [self.lista("Horarios disponibles:", libres)], libres

    def _hora(self, texto, t):
        libres = self.s.horarios_libres(self.tmp["prof"], self.tmp["fecha"])
        i = self.elegir(texto.replace(" hs", ""), libres)
        if i is None:
            return ["Horario no disponible. Elija uno de la lista."], libres
        self.tmp["hora"], self.estado = libres[i], "confirmar"
        d = self.tmp
        return [f"Resumen del turno:\n• Paciente DNI: {fmt_dni(self.s.dni)}\n• {d['esp']} - {d['prof']}\n"
                f"• {etiqueta_fecha(d['fecha'])} a las {d['hora']} hs\n\n¿Confirmamos?"], ["Confirmar", "Cancelar"]

    def _confirmar(self, texto, t):
        if t in ("si", "confirmar", "ok", "dale") or "confirm" in t:
            d = self.tmp
            self.s.turnos.append({"dni": self.s.dni, "esp": d["esp"], "prof": d["prof"],
                                  "fecha": d["fecha"], "hora": d["hora"]})
            return self.menu("🎉 ¡Turno confirmado con éxito! Lo esperamos. ")
        if t == "no":
            return self.menu("Turno cancelado. ")
        return ["Responda 'Confirmar' o 'Cancelar'."], ["Confirmar", "Cancelar"]


# ───────────────────────── Interfaz gráfica ─────────────────────────
class Logo(tk.Canvas):
    """Logo simple: círculo azul con cruz blanca."""
    def __init__(self, master, size=110, bg=BLANCO):
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0)
        m, c, a, b = 4, size / 2, size * 0.12, size * 0.30
        self.create_oval(m, m, size - m, size - m, fill=AZUL, outline=AZUL_OSC, width=3)
        self.create_rectangle(c - a, c - b, c + a, c + b, fill=BLANCO, outline=BLANCO)
        self.create_rectangle(c - b, c - a, c + b, c + a, fill=BLANCO, outline=BLANCO)


class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, abrir_chat):
        super().__init__(master, fg_color=BLANCO)
        franja = ctk.CTkFrame(self, fg_color=AZUL, height=90, corner_radius=0)
        franja.pack(fill="x")
        ctk.CTkLabel(franja, text="Centro Médico", text_color=BLANCO,
                     font=("Segoe UI", 22, "bold")).pack(pady=28)
        centro = ctk.CTkFrame(self, fg_color=BLANCO)
        centro.pack(expand=True)
        Logo(centro).pack(pady=(10, 10))
        ctk.CTkLabel(centro, text="Portal del Paciente", text_color=AZUL_OSC,
                     font=("Segoe UI", 32, "bold")).pack()
        ctk.CTkLabel(centro, text="¡Bienvenido/a! Gestione sus turnos médicos de forma rápida y simple.",
                     text_color=GRIS, font=("Segoe UI", 15)).pack(pady=(8, 28))
        ctk.CTkButton(centro, text="💬  Chatbot de turnos", command=abrir_chat, width=300, height=56,
                      corner_radius=28, fg_color=AZUL, hover_color=AZUL_OSC,
                      font=("Segoe UI", 18, "bold")).pack()


class ChatFrame(ctk.CTkFrame):
    def __init__(self, master, sesion, volver):
        super().__init__(master, fg_color=BLANCO)
        self.sesion = sesion
        # Encabezado con icono para volver al menú principal
        head = ctk.CTkFrame(self, fg_color=AZUL, height=64, corner_radius=0)
        head.pack(fill="x")
        ctk.CTkButton(head, text="🏠", width=46, height=40, corner_radius=20, command=volver,
                      fg_color=AZUL_OSC, hover_color="#0F3A78", font=("Segoe UI Emoji", 20)
                      ).pack(side="left", padx=14, pady=12)
        ctk.CTkLabel(head, text="Asistente de turnos", text_color=BLANCO,
                     font=("Segoe UI", 18, "bold")).pack(side="left")
        # Conversación
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=BLANCO)
        self.scroll.pack(fill="both", expand=True, padx=10, pady=(8, 0))
        # Respuestas rápidas
        self.rapidas = ctk.CTkFrame(self, fg_color=BLANCO)
        self.rapidas.pack(fill="x", padx=14, pady=4)
        # Entrada de texto
        barra = ctk.CTkFrame(self, fg_color=AZUL_CLARO, corner_radius=0)
        barra.pack(fill="x")
        self.entry = ctk.CTkEntry(barra, placeholder_text="Escriba su mensaje…", height=42,
                                  fg_color=BLANCO, border_color=AZUL, text_color=TEXTO,
                                  font=("Segoe UI", 14))
        self.entry.pack(side="left", fill="x", expand=True, padx=(14, 8), pady=12)
        self.entry.bind("<Return>", lambda e: self.enviar())
        ctk.CTkButton(barra, text="Enviar ➤", width=100, height=42, fg_color=AZUL,
                      hover_color=AZUL_OSC, command=self.enviar,
                      font=("Segoe UI", 14, "bold")).pack(side="right", padx=(0, 14))

    def iniciar(self):
        """Reinicia la conversación cada vez que se entra al chat (el DNI de sesión se conserva)."""
        for w in self.scroll.winfo_children():
            w.destroy()
        self.bot = Bot(self.sesion)
        self.bot_dice(*self.bot.iniciar())
        self.entry.focus()

    def burbuja(self, texto, usuario=False):
        fila = ctk.CTkFrame(self.scroll, fg_color="transparent")
        fila.pack(fill="x", pady=3)
        b = ctk.CTkFrame(fila, corner_radius=16, fg_color=AZUL if usuario else AZUL_CLARO)
        b.pack(side="right" if usuario else "left", padx=(80, 6) if usuario else (6, 80))
        ctk.CTkLabel(b, text=texto, wraplength=430, justify="left", font=("Segoe UI", 14),
                     text_color=BLANCO if usuario else TEXTO).pack(padx=14, pady=9)
        self.after(60, lambda: self.scroll._parent_canvas.yview_moveto(1.0))

    def bot_dice(self, mensajes, opciones):
        for m in mensajes:
            self.burbuja(m)
        for w in self.rapidas.winfo_children():
            w.destroy()
        for i, o in enumerate(opciones):            # botones en cuadrícula de 4 columnas
            ctk.CTkButton(self.rapidas, text=o, height=32, corner_radius=16, fg_color=BLANCO,
                          border_width=2, border_color=AZUL, text_color=AZUL,
                          hover_color=AZUL_CLARO, font=("Segoe UI", 12),
                          command=lambda x=o: self.enviar(x)).grid(row=i // 4, column=i % 4,
                                                                    padx=3, pady=3, sticky="w")

    def enviar(self, texto=None):
        texto = (texto or self.entry.get()).strip()
        if not texto:
            return
        self.entry.delete(0, "end")
        self.burbuja(texto, usuario=True)
        # Pequeña pausa para simular que el bot "escribe"
        self.after(350, lambda: self.bot_dice(*self.bot.responder(texto)))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("Portal del Paciente")
        self.geometry("900x680")
        self.minsize(720, 560)
        self.configure(fg_color=BLANCO)
        self.home = HomeFrame(self, self.ir_chat)
        self.chat = ChatFrame(self, Sesion(), self.ir_home)
        self.ir_home()

    def ir_home(self):
        self.chat.pack_forget()
        self.home.pack(fill="both", expand=True)

    def ir_chat(self):
        self.home.pack_forget()
        self.chat.pack(fill="both", expand=True)
        self.chat.iniciar()


if __name__ == "__main__":
    App().mainloop()