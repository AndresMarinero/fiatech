

function toggleNavbarSuperior() {
    const navbar = document.getElementById("navbarSuperior");
    const boton = document.getElementById("toggleNavbarBtn");

    if (!navbar) {
        return;
    }

    const estaOculto = navbar.classList.toggle("oculto");

    if (boton) {
        boton.setAttribute("aria-expanded", String(!estaOculto));

        boton.setAttribute(
            "aria-label",
            estaOculto
                ? "Mostrar barra superior"
                : "Ocultar barra superior"
        );
    }
}
