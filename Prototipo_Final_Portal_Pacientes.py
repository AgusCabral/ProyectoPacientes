"""
Portal del Paciente - Prototipo de escritorio con Flet (Windows)
Instalar:  pip install flet
Ejecutar:  python Prototipo_Final_Portal_Pacientes.py

Los datos viven en Google Sheets. El programa habla con la Web App de Apps Script (codigo.gs).
Configuración: crear "config.json" junto a este archivo (ver config.example.json):
    {"url": "https://script.google.com/macros/s/XXXX/exec", "token": "<el mismo TOKEN del script>"}
También se pueden usar las variables de entorno PORTAL_URL y PORTAL_TOKEN.
"""
import asyncio
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime

import flet as ft

# ───────────────────────── Paleta (blanco / azul) ─────────────────────────
AZUL, AZUL_OSC, AZUL_CLARO, AZUL_SUAVE = "#1E6FD9", "#154C9C", "#E3EEFC", "#F4F8FE"
BLANCO, GRIS, TEXTO = "#FFFFFF", "#5B6B7F", "#1B2A3D"

# Raíces de palabras para detectar la especialidad en lenguaje natural
RAICES = {"clinic": "Clínica Médica", "generalista": "Clínica Médica", "cardi": "Cardiología",
          "pediat": "Pediatría", "dermat": "Dermatología", "traumat": "Traumatología"}
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = "ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic"
MAX_OPCIONES = 8          # cuántas fechas/turnos se muestran como botones


# ───────────────────────── Conexión con Google Sheets (Apps Script) ─────────────────────────
class ErrorAPI(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


def cargar_config():
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    cfg = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            cfg = json.load(f)
    return (os.environ.get("PORTAL_URL") or cfg.get("url", "")).strip(), \
           (os.environ.get("PORTAL_TOKEN") or cfg.get("token", "")).strip()


class API:
    """Cliente de la Web App. Cada método es una acción de ACCIONES en codigo.gs.
    Apps Script responde un 302 hacia googleusercontent.com: urllib lo sigue con GET,
    que es justo lo que hace falta para leer la respuesta."""

    def __init__(self):
        self.url, self.token = cargar_config()

    def _llamar(self, accion, **datos):
        if not self.url or not self.token:
            raise ErrorAPI("CONFIG", "Falta configurar la conexión (config.json con 'url' y 'token').")
        cuerpo = json.dumps({"token": self.token, "accion": accion, **datos}).encode("utf-8")
        req = urllib.request.Request(self.url, data=cuerpo, method="POST",
                                     headers={"Content-Type": "text/plain;charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                texto = r.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErrorAPI("RED", f"No pude conectarme con el sistema de turnos ({e}).")
        try:
            resp = json.loads(texto)
        except ValueError:      # suele ser una página HTML de Google: implementación sin acceso público
            raise ErrorAPI("RED", "El sistema de turnos respondió algo inesperado. Revise que la Web App "
                                  "esté implementada con acceso 'Cualquier usuario'.")
        if not resp.get("ok"):
            raise ErrorAPI(resp.get("codigo", "ERROR"), resp.get("error", "Error desconocido"))
        return resp.get("datos")

    def catalogo(self):                     return self._llamar("catalogo")
    def paciente(self, dni):                return self._llamar("paciente", dni=dni)
    def fechas(self, esp, prof):            return self._llamar("fechas", especialidad=esp, profesional=prof)
    def horarios(self, esp, prof, fecha):   return self._llamar("horarios", especialidad=esp, profesional=prof,
                                                                 fecha=fecha.isoformat())
    def reservar(self, dni, id_turno):      return self._llamar("reservar", dni=dni, id_turno=id_turno)
    def confirmar(self, dni, id_turno):     return self._llamar("confirmar", dni=dni, id_turno=id_turno)
    def liberar(self, dni, id_turno):       return self._llamar("liberar", dni=dni, id_turno=id_turno)
    def turnos(self, dni):                  return self._llamar("turnos", dni=dni)
    def cancelar(self, dni, id_turno):      return self._llamar("cancelar", dni=dni, id_turno=id_turno)
    def reprogramar(self, dni, id_viejo, id_nuevo):
        return self._llamar("reprogramar", dni=dni, id_turno=id_viejo, id_turno_nuevo=id_nuevo)


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


def a_fecha(iso):
    return datetime.strptime(iso, "%Y-%m-%d").date()


def etiqueta_fecha(d):
    if isinstance(d, str):
        d = a_fecha(d)
    return f"{DIAS[d.weekday()]} {d.strftime('%d/%m')}"


def etiqueta_turno(x):
    return f"{etiqueta_fecha(x['fecha'])} · {x['hora']} hs · {x['especialidad']} · {x['profesional']}"


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


def criterio_fecha(t, estado=""):
    """Qué fecha menciona el texto: 'manana' o (dia, mes, dia_semana); None si no menciona ninguna."""
    if "manana" in t:
        return "manana"
    dia = mes = None
    if m := re.search(r"\b(\d{1,2})/(\d{1,2})\b", t):
        dia, mes = int(m.group(1)), int(m.group(2))
    elif m := re.search(rf"\b(\d{{1,2}})\s*(?:de\s+)?({MESES})", t):
        dia, mes = int(m.group(1)), MESES.split("|").index(m.group(2)) + 1
    elif m := re.search(r"\b(\d{1,2})\b", t):
        dia = int(m.group(1))
    wd = re.search(r"\b(lun|mar|mie|jue|vie|sab)", t)
    wd = ["lun", "mar", "mie", "jue", "vie", "sab"].index(wd.group(1)) if wd else None
    if wd is None and (dia is None or (mes is None and estado != "fecha")):
        return None                              # un número suelto solo cuenta al elegir fecha
    return dia, mes, wd


def parse_fecha(t, cands, estado=""):
    """Interpreta fechas coloquiales ('martes 6', '6 de octubre', '06/10', 'mañana', 'el lunes')
    y devuelve la primera fecha de 'cands' (fechas con cupos libres) que coincida."""
    c = criterio_fecha(t, estado)
    if c is None:
        return None
    if c == "manana":
        manana = date.fromordinal(date.today().toordinal() + 1)
        return manana if manana in cands else None
    dia, mes, wd = c
    for d in cands:
        if (wd is None or d.weekday() == wd) and (dia is None or d.day == dia) and (mes is None or d.month == mes):
            return d
    return None


class Sesion:
    """Estado compartido mientras la aplicación está abierta."""
    def __init__(self):
        self.api = API()
        self.dni = None          # DNI recordado en la sesión (ya validado contra la hoja Pacientes)
        self.nombre = ""
        self._catalogo = None    # {especialidad: [profesionales]} leído de la hoja Turnos

    def catalogo(self):
        if self._catalogo is None:
            self._catalogo = self.api.catalogo()
        return self._catalogo


# ───────────────────────── Lógica del chatbot ─────────────────────────
OPCIONES_MENU = ["Sacar un turno", "Ver mis turnos", "Reprogramar un turno", "Cancelar un turno",
                 "Consultar otro DNI", "Cambiar de DNI"]


class Bot:
    """Máquina de estados + intenciones por palabras clave + extracción de datos (slots)
    desde una sola frase. responder(texto) -> (mensajes, opciones_rapidas)

    Flujo de reserva (igual que las reglas del backend):
      elegir horario -> reservar (Libre -> Ocupado, bloqueado 5 min) -> confirmar (-> Confirmado)
      o, si el paciente se arrepiente, liberar (Ocupado -> Libre).
    Reprogramar:  elegir turno Confirmado -> nuevo horario posterior, misma especialidad -> reprogramar.
    Cancelar:     elegir turno Confirmado -> confirmar -> cancelar (Confirmado -> Libre)."""

    def __init__(self, sesion):
        self.s, self.estado, self.tmp = sesion, "inicio", {}
        self.ops = []            # opciones numeradas que se están mostrando (fechas, horarios o turnos)

    @property
    def api(self):
        return self.s.api

    @staticmethod
    def lista(titulo, ops):
        return titulo + "\n" + "\n".join(f"{i}. {o}" for i, o in enumerate(ops, 1))

    def menu(self, pref=""):
        self.estado, self.tmp = "menu", {}
        return [pref + "¿Qué desea hacer?"], OPCIONES_MENU

    def pedir_dni(self, destino):
        self.estado, self.tmp = "pedir_dni", {"destino": destino}
        return ["Escriba el DNI (solo números, 7 u 8 dígitos)."], []

    def iniciar(self):
        if self.s.dni:
            self.estado = "usar_dni"
            return ([f"¡Hola de nuevo! 👋 Tengo registrado el DNI {fmt_dni(self.s.dni)} ({self.s.nombre}).",
                     "¿Desea continuar con ese usuario o ingresar uno nuevo?"],
                    ["Continuar con este DNI", "Ingresar otro DNI"])
        self.estado, self.tmp = "pedir_dni", {"destino": "sesion"}
        return ["¡Hola! 👋 Soy el asistente virtual de turnos.",
                "Para comenzar, escriba su DNI (solo números)."], []

    def soltar_reserva(self):
        """Si quedó un cupo bloqueado (Ocupado) sin confirmar, lo devuelve a Libre."""
        if self.estado == "confirmar" and self.tmp.get("id_turno"):
            try:
                self.api.liberar(self.s.dni, self.tmp["id_turno"])
            except ErrorAPI:
                pass            # si falla, el backend lo libera solo a los 5 minutos

    def responder(self, texto):
        """Se ejecuta en un hilo aparte (hace llamadas de red)."""
        t = norm(texto)
        try:
            if t in ("menu", "inicio", "cancelar", "salir", "volver"):      # intenciones globales
                self.soltar_reserva()
                return self.menu("Operación cancelada. ") if self.s.dni else self.iniciar()
            if t in ("ayuda", "help", "?"):
                return (["Puedo ayudarle a sacar, ver, reprogramar o cancelar turnos. "
                         "Puede escribir frases como 'turno con cardiólogo el martes 6 a las 10'.",
                         "Escriba 'menu' en cualquier momento para volver al inicio."], [])
            return getattr(self, "_" + self.estado)(texto, t)
        except ErrorAPI as e:
            pref = f"⚠️ {e.mensaje} "
            if e.codigo in ("RED", "CONFIG", "NO_AUTORIZADO", "ACCION", "ERROR"):
                pref += "Intente nuevamente en unos instantes. "
            if self.s.dni:
                return self.menu(pref)
            self.estado, self.tmp = "pedir_dni", {"destino": "sesion"}
            return [pref + "Escriba su DNI para continuar."], []

    def _inicio(self, texto, t):
        return self.iniciar()

    # ---- DNI
    def _usar_dni(self, texto, t):
        if re.search(r"otro|nuevo|ingresar", t):
            return self.pedir_dni("sesion")
        if re.search(r"continu|\bsi\b|mismo|este", t):
            return self.menu(f"Perfecto, continuamos con {self.s.nombre}. ")
        return ["No entendí. ¿Continuamos con el DNI actual o ingresamos otro?"], \
               ["Continuar con este DNI", "Ingresar otro DNI"]

    def _pedir_dni(self, texto, t):
        dni = parse_dni(texto)
        if not dni:
            return ["⚠️ El DNI no es válido. Debe tener 7 u 8 números, por ejemplo 30123456."], []
        if self.tmp.get("destino") == "consulta":                  # consulta puntual
            return self.mostrar_turnos(dni)
        pac = self.api.paciente(dni)
        if not pac:
            return [f"No encontramos un paciente con el DNI {fmt_dni(dni)}. "
                    "Verifique el número o acérquese a recepción para darse de alta."], []
        self.s.dni, self.s.nombre = dni, f"{pac['nombre']} {pac['apellido']}".strip()
        return self.menu(f"✅ Hola, {self.s.nombre}. ")

    # ---- menú e intenciones
    def _menu(self, texto, t):
        consulta = re.search(r"mis turnos|consult|\bver\b|revisar", t)
        if m := re.search(r"\d[\d.]{5,10}\d", texto):              # "ver turnos del dni 3012..."
            if consulta and parse_dni(m.group()):
                return self.mostrar_turnos(parse_dni(m.group()))
        if consulta and re.search(r"otro|nuevo|distinto", t):
            return self.pedir_dni("consulta")
        if re.search(r"reprogram|cambiar (?:el |mi |un )?turno|mover|posponer|otra fecha|otro dia", t):
            return self.elegir_turno("reprogramar")
        if re.search(r"cancel|anular|dar de baja", t):
            return self.elegir_turno("cancelar")
        if re.search(r"cambiar|otro dni|nuevo dni", t):
            return self.pedir_dni("sesion")
        if consulta:                                               # usa el DNI ya confirmado, sin repreguntar
            return self.mostrar_turnos(self.s.dni)
        if re.search(r"turno|sacar|pedir|reserv|agendar|solicitar|cita", t):
            self.tmp = {}
            self.llenar(texto, "menu")                             # toma especialidad/fecha/hora si ya vienen
            return self.avanzar()
        return ["No logré entenderle 🤔. Puede escribir 'sacar turno', 'ver mis turnos', "
                "'reprogramar' o 'cancelar turno'."], OPCIONES_MENU

    def mostrar_turnos(self, dni):
        try:
            mios = self.api.turnos(dni)
        except ErrorAPI as e:
            if e.codigo == "NO_PACIENTE":
                return self.menu(f"No encontramos un paciente con el DNI {fmt_dni(dni)}. ")
            raise
        if not mios:
            return self.menu(f"El DNI {fmt_dni(dni)} no tiene turnos próximos. ")
        iconos = {"Confirmado": "✅", "Cancelado": "❌", "Reprogramado": "🔁"}
        lineas = []
        for x in mios:
            nota = "" if x["estado"] == "Confirmado" else f" ({x['estado'].lower()} por el profesional)"
            lineas.append(f"{iconos.get(x['estado'], '📅')} {etiqueta_turno(x)}{nota}")
        return self.menu(f"Turnos del DNI {fmt_dni(dni)}:\n" + "\n".join(lineas) + "\n\n")

    # ---- elegir un turno propio (para reprogramar o cancelar)
    def elegir_turno(self, accion):
        mods = [x for x in self.api.turnos(self.s.dni) if x["modificable"]]
        if not mods:
            return self.menu("No tiene turnos confirmados próximos que se puedan modificar. ")
        self.tmp, self.ops = {"accion": accion}, mods[:MAX_OPCIONES]
        if len(mods) == 1:
            return self.turno_elegido(mods[0])
        self.estado = "elegir_turno"
        verbo = "reprogramar" if accion == "reprogramar" else "cancelar"
        labels = [etiqueta_turno(x) for x in self.ops]
        return [self.lista(f"¿Qué turno desea {verbo}?", labels)], labels

    def _elegir_turno(self, texto, t):
        x = self.opcion_elegida(t, [etiqueta_turno(o) for o in self.ops])
        if x is None:
            return ["Elija el turno por su número o tocando una de las opciones."], \
                   [etiqueta_turno(o) for o in self.ops]
        return self.turno_elegido(self.ops[x])

    def turno_elegido(self, turno):
        self.tmp["viejo"] = turno
        if self.tmp["accion"] == "cancelar":
            self.estado = "confirmar_cancelacion"
            return [f"Va a cancelar este turno:\n• {etiqueta_turno(turno)}\n\n¿Confirma la cancelación?"], \
                   ["Sí, cancelar turno", "No, mantenerlo"]
        # Reprogramar: misma especialidad, horario posterior al actual
        self.tmp.update({"esp": turno["especialidad"], "reprogramar": True})
        return self.avanzar(f"Busquemos un nuevo horario de {turno['especialidad']} posterior al "
                            f"{etiqueta_fecha(turno['fecha'])} {turno['hora']} hs. ")

    def _confirmar_cancelacion(self, texto, t):
        if re.search(r"^no\b|mantener", t):
            return self.menu("Perfecto, su turno sigue en pie. ")
        if re.search(r"\bsi\b|confirm|\bok\b|dale", t):
            self.api.cancelar(self.s.dni, self.tmp["viejo"]["id_turno"])
            return self.menu("✅ Turno cancelado. El horario quedó libre para otro paciente. ")
        return ["Responda 'Sí' o 'No'."], ["Sí, cancelar turno", "No, mantenerlo"]

    @staticmethod
    def opcion_elegida(t, labels):
        """Índice elegido por número o por el texto exacto del botón; None si no coincide."""
        if t.isdigit() and 1 <= int(t) <= len(labels):
            return int(t) - 1
        normas = [norm(l) for l in labels]
        return normas.index(t) if t in normas else None

    # ---- reserva con relleno de datos (slots)
    def llenar(self, texto, estado=""):
        """Extrae de la frase todo lo que pueda: especialidad, profesional, fecha y hora."""
        d, t = self.tmp, norm(texto)
        cat = self.s.catalogo()
        hora, t_sin_hora = parse_hora(t)
        if hora:
            d["hora"] = hora
        if not d.get("reprogramar"):                               # al reprogramar la especialidad es fija
            for raiz, esp in RAICES.items():
                if raiz in t and esp in cat and d.get("esp") != esp:
                    d["esp"] = esp
                    d.pop("prof", None)
                    d.pop("fechas", None)
        for esp, profs in cat.items():
            if d.get("reprogramar") and esp != d["esp"]:
                continue
            for p in profs:
                if norm(p.split()[-1]) in t and d.get("prof") != p:  # por apellido
                    d["esp"], d["prof"] = esp, p
                    d.pop("fechas", None)
        if criterio_fecha(t_sin_hora, estado) is None:
            return
        if "prof" in d:
            if fecha := parse_fecha(t_sin_hora, self.fechas_libres(), estado):
                d["fecha"] = fecha
        else:   # escribió la fecha antes de elegir profesional: se interpreta cuando lo haya
            d["texto_fecha"] = t_sin_hora

    def fechas_libres(self):
        """Fechas con cupos Libres para la especialidad/profesional elegidos (cacheadas por paso)."""
        d = self.tmp
        if "fechas" not in d:
            fs = [a_fecha(f) for f in self.api.fechas(d["esp"], d["prof"])]
            if d.get("reprogramar"):
                fs = [f for f in fs if f >= a_fecha(d["viejo"]["fecha"])]
            d["fechas"] = fs
        return d["fechas"]

    def horarios_libres(self):
        d = self.tmp
        hs = self.api.horarios(d["esp"], d["prof"], d["fecha"])
        if d.get("reprogramar"):
            v = d["viejo"]
            hs = [h for h in hs if (d["fecha"].isoformat(), h["hora"]) > (v["fecha"], v["hora"])]
        return hs

    def avanzar(self, pref=""):
        """Pide el primer dato que falta; cuando está todo, bloquea el cupo y pide confirmación."""
        d = self.tmp
        cat = self.s.catalogo()
        if "esp" not in d:
            self.estado, ops = "esp", list(cat)
            return [pref + self.lista("Elija una especialidad (número o nombre):", ops)], ops
        if "prof" not in d:
            profs = cat.get(d["esp"], [])
            if len(profs) == 1:
                d["prof"] = profs[0]
                pref += f"Para {d['esp']} atiende {profs[0]}. "
            else:
                self.estado = "prof"
                return [pref + self.lista(f"{d['esp']}. ¿Con qué profesional?", profs)], profs
        if "fecha" not in d and d.get("texto_fecha"):              # fecha escrita antes de tener profesional
            if f := parse_fecha(d.pop("texto_fecha"), self.fechas_libres(), "menu"):
                d["fecha"] = f
            else:
                pref += "⚠️ Esa fecha no tiene horarios libres. "
        d.pop("texto_fecha", None)
        if "fecha" not in d:
            fechas = self.fechas_libres()
            if not fechas:
                if d.get("reprogramar") and len(cat.get(d["esp"], [])) > 1:
                    d.pop("prof"), d.pop("fechas", None)
                    self.estado = "prof"
                    profs = cat[d["esp"]]
                    return [pref + self.lista("Ese profesional no tiene horarios libres. ¿Probamos con otro?",
                                              profs)], profs
                return self.menu(pref + f"No hay horarios libres con {d['prof']} por el momento. ")
            self.estado, self.ops = "fecha", fechas[:MAX_OPCIONES]
            ops = [etiqueta_fecha(x) for x in self.ops]
            return [pref + self.lista("¿Qué día prefiere? (también puede escribir, por ej., 'martes 6')", ops)], ops
        libres = self.horarios_libres()
        horas = [h["hora"] for h in libres]
        if d.get("hora") and d["hora"] not in horas:
            pref += f"⚠️ A las {d['hora']} no hay lugar. "
            d.pop("hora")
        if "hora" not in d:
            if not libres:
                d.pop("fecha")
                d.pop("fechas", None)                              # se vuelve a consultar al backend
                return self.avanzar(pref + "Ese día ya no quedan horarios libres. ")
            self.estado, self.ops = "hora", horas
            return [pref + self.lista(f"Horarios disponibles el {etiqueta_fecha(d['fecha'])}:", horas)], horas
        id_turno = libres[horas.index(d["hora"])]["id_turno"]
        resumen = (f"• Paciente: {self.s.nombre} (DNI {fmt_dni(self.s.dni)})\n• {d['esp']} · {d['prof']}\n"
                   f"• {etiqueta_fecha(d['fecha'])} a las {d['hora']} hs")
        if d.get("reprogramar"):
            d["id_turno_nuevo"] = id_turno
            self.estado = "confirmar_reprogramacion"
            return [f"{pref}Reprogramación:\n• Turno actual: {etiqueta_turno(d['viejo'])}\n"
                    f"• Nuevo turno: {etiqueta_fecha(d['fecha'])} {d['hora']} hs · {d['prof']}\n\n¿Confirmamos el cambio?"], \
                   ["Confirmar cambio", "Volver"]
        try:
            r = self.api.reservar(self.s.dni, id_turno)            # Libre -> Ocupado (bloqueo temporal)
        except ErrorAPI as e:
            if e.codigo in ("NO_DISPONIBLE", "DUPLICADO"):
                d.pop("hora")
                d.pop("fechas", None)
                return self.avanzar(f"⚠️ {e.mensaje} ")
            raise
        d["id_turno"] = id_turno
        self.estado = "confirmar"
        return [f"{pref}Resumen del turno:\n{resumen}\n\n"
                f"Le reservo este horario por {r['minutos']} minutos. ¿Confirmamos?"], ["Confirmar", "Cancelar"]

    def _slot(self, texto, t):
        """Maneja los estados esp / prof / fecha / hora."""
        clave = self.estado
        opciones = {"esp": lambda: list(self.s.catalogo()),
                    "prof": lambda: self.s.catalogo().get(self.tmp.get("esp"), []),
                    "fecha": lambda: self.ops, "hora": lambda: self.ops}[clave]()
        labels = [etiqueta_fecha(o) for o in opciones] if clave == "fecha" else opciones
        i = self.opcion_elegida(t, labels)
        if i is not None:                                          # eligió por número o tocando el botón
            if clave == "prof" and self.tmp.get("prof") != opciones[i]:
                self.tmp.pop("fechas", None)
            self.tmp[clave] = opciones[i]
        else:
            antes = self.tmp.get(clave)
            self.llenar(texto, clave)
            if self.tmp.get(clave) == antes:
                return self.avanzar("No logré entender ese dato 🤔. ")
        return self.avanzar()

    _esp = _prof = _fecha = _hora = _slot

    def _confirmar(self, texto, t):
        if re.search(r"\bsi\b|confirm|\bok\b|dale", t):
            try:
                self.api.confirmar(self.s.dni, self.tmp["id_turno"])  # Ocupado -> Confirmado
            except ErrorAPI as e:
                if e.codigo == "EXPIRADO":
                    return self.menu("⌛ Pasaron más de 5 minutos y el horario se liberó. Puede volver a pedirlo. ")
                raise
            return self.menu("🎉 ¡Turno confirmado con éxito! Lo esperamos. ")
        if re.search(r"^no\b", t):
            self.soltar_reserva()
            return self.menu("Listo, no se reservó el turno. ")
        return ["Responda 'Confirmar' o 'Cancelar'."], ["Confirmar", "Cancelar"]

    def _confirmar_reprogramacion(self, texto, t):
        if re.search(r"\bsi\b|confirm|\bok\b|dale", t):
            d = self.tmp
            try:
                self.api.reprogramar(self.s.dni, d["viejo"]["id_turno"], d["id_turno_nuevo"])
            except ErrorAPI as e:
                if e.codigo in ("NO_DISPONIBLE", "DUPLICADO"):
                    d.pop("hora"), d.pop("fechas", None)
                    return self.avanzar(f"⚠️ {e.mensaje} ")
                raise
            return self.menu(f"🔁 ¡Listo! Su turno quedó para el {etiqueta_fecha(d['fecha'])} a las {d['hora']} hs "
                             f"con {d['prof']}. ")
        if re.search(r"^no\b", t):
            return self.menu("Su turno original se mantiene. ")
        return ["Responda 'Confirmar cambio' o 'Volver'."], ["Confirmar cambio", "Volver"]
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

        ocupado = {"v": False}                                      # evita mandar dos mensajes a la vez

        async def enviar(texto=None):
            texto = (texto or entrada.value or "").strip()
            if not texto or ocupado["v"]:
                return
            ocupado["v"] = True
            entrada.value = ""
            conversacion.controls.append(burbuja(texto, usuario=True))
            rapidas.controls = []
            escribiendo = burbuja("escribiendo…")                   # se ve mientras consulta Google Sheets
            conversacion.controls.append(escribiendo)
            page.update()
            try:
                # La consulta a la Web App tarda 1-3 s: se hace en otro hilo para no congelar la ventana
                respuesta, _ = await asyncio.gather(asyncio.to_thread(bot.responder, texto), asyncio.sleep(0.45))
            except Exception as ex:                                 # error inesperado: se informa en el chat
                respuesta = ([f"⚠️ Ocurrió un error inesperado: {ex}"], OPCIONES_MENU if sesion.dni else [])
            finally:
                ocupado["v"] = False
                conversacion.controls.remove(escribiendo)
            bot_dice(*respuesta)
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