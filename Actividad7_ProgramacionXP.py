import flet as ft

TURNOS_DISPONIBLES = {
    "Clínica médica": {
        "2026-11-24": ["09:30", "10:30", "11:00", "11:30", "12:00"],
        "2026-11-25": ["09:00", "11:00", "11:30", "12:00"],
        "2026-11-26": ["11:30", "12:00"],
        "2026-11-27": ["09:30"]
    },
    "Pediatría": {
        "2026-11-24": ["07:30", "08:30", "11:00", "12:00"],
        "2026-11-26": ["09:30", "10:30"],
        "2026-12-01": ["12:00", "13:00", "14:30"]
    },
    "Cardiología": {
        "2026-11-24": ["09:30", "10:30", "11:00"],
        "2026-11-27": ["09:30", "10:30", "11:00", "11:30", "12:00"],
        "2026-12-01": ["11:00", "11:30", "12:00"]
    },
    "Dermatología": {
        "2026-11-24": ["09:30", "10:30"],
        "2026-11-25": ["15:00", "16:00", "17:30"],
        "2026-11-27": ["13:00", "13:30", "15:30", "16:00"]
    },
    "Traumatología": {
        "2026-11-26": ["10:30", "11:00", "11:30", "12:00"],
        "2026-11-27": ["11:00", "11:30", "12:00"],
        "2026-12-01": ["09:30", "10:30", "11:00", "11:30", "12:00", "13:00"],
        "2026-12-02": ["11:30", "12:00", "15:00", "16:00"]
    }
}

ESPECIALIDADES = list(TURNOS_DISPONIBLES.keys())

def main(page: ft.Page):
    page.bgcolor = ft.Colors.LIGHT_BLUE_50
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.CENTER

    #funciones para el formulario

    def actualizar_fechas(e):
        fecha_turno.value = None #limpia las fecha que estaba cargada en el campo para que si el paciente cambia de especialidad, no venga este campo con un valor ya cargado 
        hora_turno.value = None #limpia la hora que estaba cargada en el campo
        hora_turno.options = ([]) #vacía las opciones del dropdown de horas hasta que el paciente elija una fecha, si cambia de especialidad cuando ya había elegido fecha y hora, esto hace que se vacíe el campo hora también.
        fechas = TURNOS_DISPONIBLES.get(elegir_especialidad.value, {}).keys()
        fecha_turno.options = [ft.DropdownOption(f) for f in fechas]
        fecha_turno.update()
        hora_turno.update()

    def actualizar_horarios(e):
        hora_turno.value = None #limpia la hora que estaba cargada en el campo para que si el paciente elige otra fecha, no quede este campo con un valor cargado
        horas = TURNOS_DISPONIBLES.get(elegir_especialidad.value, {}).get(fecha_turno.value, [])
        hora_turno.options = [ft.DropdownOption(h) for h in horas]
        hora_turno.update()

    def cerrar_popup():
        page.pop_dialog()

        #vacía también los campos que estaban cargados en el formulario para dejarlo listo para una nueva solicitud de turno
        ingresar_dni.value = ""
        ingresar_nombre.value = ""
        ingresar_apellido.value = ""
        motivo_consulta.value = ""
        elegir_especialidad.value = None
        fecha_turno.value = None
        hora_turno.value = None
        fecha_turno.options = []
        hora_turno.options = []

        page.update()

    def solicitar_turno(e):
        #mensaje_confirmacion.visible = False #si ya se confirmó un turno, y se quiere solicitar otro, limpiamos el mensaje de confirmado anterior
        
        for campo in (ingresar_dni, ingresar_nombre, ingresar_apellido, elegir_especialidad, fecha_turno, hora_turno): #si hay un error marcado y se soluciona, lo desmarca
            campo.error = None
            campo.error_text = None

        hay_error = False

        if ingresar_dni.value.strip() =="": #si está vacío
            ingresar_dni.error = "Ingresá tu DNI"
            hay_error = True
        elif not ingresar_dni.value.strip().isdigit(): #si lo que guardo no son números
            ingresar_dni.error = "El DNI solo puede contener números"
            hay_error = True

        if ingresar_nombre.value.strip() =="":
            ingresar_nombre.error = "Ingresá tu nombre"
            hay_error = True

        if ingresar_apellido.value.strip() =="":
            ingresar_apellido.error = "Ingresá tu apellido"
            hay_error = True

        if not elegir_especialidad.value: #el desplegable vale None si no se eligió nada
            elegir_especialidad.error_text = "Seleccioná una especialidad"
            hay_error = True

        if not fecha_turno.value:
            fecha_turno.error_text = "Seleccioná una fecha para el turno"
            hay_error = True

        if not hora_turno.value:
            hora_turno.error_text = "Seleccioná un horario para el turno"
            hay_error = True

        if hay_error: #si termina en True, no se puede mandar el formulario
            page.update()
            return

        modal_turno_confirmado.content.value = f"Tu turno de {elegir_especialidad.value} el {fecha_turno.value} a la {hora_turno.value} fue registrado correctamente."
        page.show_dialog(modal_turno_confirmado)
        page.update()

    #campos del formulario
    ingresar_dni = ft.TextField(label="Ingrese su DNI *", color=ft.Colors.BLUE_GREY_900)
    ingresar_nombre = ft.TextField(label="Ingrese su nombre *", color=ft.Colors.BLUE_GREY_900)
    ingresar_apellido = ft.TextField(label="Ingrese su apellido *", color=ft.Colors.BLUE_GREY_900)
    elegir_especialidad = ft.Dropdown(label="Especialidad *", options=[ft.DropdownOption(e) for e in ESPECIALIDADES],color=ft.Colors.BLUE_GREY_900, width= 250, on_select = actualizar_fechas)
    fecha_turno = ft.Dropdown(label = "Fecha turno *", color=ft.Colors.BLUE_GREY_900, width=250, on_select = actualizar_horarios)
    hora_turno = ft.Dropdown(label = "Hora turno *", color=ft.Colors.BLUE_GREY_900, width=250)
    motivo_consulta = ft.TextField(label = "Motivo de consulta (opcional)", color=ft.Colors.BLUE_GREY_900, width = 300, multiline = True, min_lines = 3, max_lines = 4)
    modal_turno_confirmado = ft.AlertDialog(title = ft.Text("¡Turno confirmado!"), content = ft.Text(""), actions=[ft.TextButton("Aceptar", on_click = cerrar_popup)])

    #espacio donde está armado el formulario en la pantalla
    contenedor_formulario = ft.Container( 
        width = 800,
        padding = 25,
        bgcolor = ft.Colors.WHITE,
        border = ft.Border.all(1, ft.Colors.BLUE_700),
        border_radius = 20,

        content = ft.Column(
            spacing = 18,
            controls = [
                ft.Text("Solicitud de turnos - Centro médico", size = 20, color = ft.Colors.BLUE_700),
                ft.Divider(color = ft.Colors.BLUE_700),
                ingresar_dni,
                ingresar_nombre,
                ingresar_apellido,
                elegir_especialidad,
                fecha_turno,
                hora_turno,
                motivo_consulta,
                ft.Button(
                    content = "Solicitar Turno",
                    on_click = solicitar_turno,                 
                    bgcolor = ft.Colors.BLUE_700,
                    color = ft.Colors.WHITE
                ),
                ft.Text("Los campos con * son obligatorios", size = 11, color = ft.Colors.BLUE_GREY)
            ]
        )
    )

    page.add(contenedor_formulario)

ft.run(main)
