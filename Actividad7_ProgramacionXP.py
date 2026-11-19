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
    
    ingresar_dni = ft.TextField(label="Ingrese su DNI *", color=ft.Colors.BLUE_GREY_900)
    ingresar_nombre = ft.TextField(label="Ingrese su nombre *", color=ft.Colors.BLUE_GREY_900)
    ingresar_apellido = ft.TextField(label="Ingrese su apellido *", color=ft.Colors.BLUE_GREY_900)
    elegir_especialidad = ft.Dropdown(label="Especialidad *", options=[ft.DropdownOption(e) for e in ESPECIALIDADES],)

    #campo fecha del turno

    #campo horario del turno

    #campo motivo de consulta

    def solicitar_turno(e):
        for campo in (ingresar_dni, ingresar_nombre, ingresar_apellido, elegir_especialidad): #si hay un error marcado y se soluciona, lo desmarca
            campo.error = None

        dni = ingresar_dni.value.strip() #guardo lo que se ingresó en el input
        nombre = ingresar_nombre.value.strip() 
        apellido = ingresar_apellido.value.strip()
        especialidad = elegir_especialidad.value

        hay_error = False

        if dni =="": #si está vacío
            ingresar_dni.error = "Ingresá tu DNI"
            hay_error = True
        elif not dni.isdigit(): #si lo que guardo no son números
            ingresar_dni.error = "El DNI solo puede contener números"
            hay_error = True

        if nombre =="":
            ingresar_nombre.error = "Ingresá tu nombre"
            hay_error = True

        if apellido =="":
            ingresar_apellido.error = "Ingresá tu apellido"
            hay_error = True

        if not especialidad: #el desplegable vale None si no se eligió nada
            elegir_especialidad.error = "Seleccioná una especialidad"
            hay_error = True

        page.update()
        if hay_error: #si termina en True, no se puede mandar el formulario
            return
            
    #funciones necesarias para el funcionamiento del formulario

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
                #fecha_turno,
                #hora_turno,
                #motivo_consulta,
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
