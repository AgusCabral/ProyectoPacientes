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

    #campo dni

    #campo nombre

    #campo apellido

    #campo especialidad

    #campo fecha del turno

    #campo horario del turno

    #campo motivo de consulta

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
                #dni, #cambiar por el campo que haga Neli
                #nombre, #cambiar por el campo que haga Neli
                #apellido, #cambiar por el campo que haga Neli
                #especialidad,
                #fecha_turno,
                #hora_turno,
                #motivo_consulta,
                ft.Button(
                    content = "Solicitar Turno",
                    #on_click = ...,
                    bgcolor = ft.Colors.BLUE_700,
                    color = ft.Colors.WHITE
                ),
                ft.Text("Los campos con * son obligatorios", size = 11, color = ft.Colors.BLUE_GREY)
            ]
        )
    )

    page.add(contenedor_formulario)

ft.run(main)