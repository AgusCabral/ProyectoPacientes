import flet as ft

contenedor_formulario = ft.Container(
    border_radius= 20,
    width= 1000,
    height=650,
    bgcolor= ft.Colors.BLUE_400
)

def main(page: ft.Page):
    page.bgcolor = ft.Colors.WHITE
    page.vertical_alignment = "center"
    page.horizontal_alignment = "center"
    page.add(contenedor_formulario)

ft.run(main)