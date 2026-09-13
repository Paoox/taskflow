"""Pruebas de la UI de pruebas del Discovery nuevo (TF-0031), contra el
cliente de test de Flask (`client`/`csrf_token` de `conftest.py`, TASKFLOW_DB
temporal). No usa proveedor de IA real: `TASKFLOW_AI_PROVIDER` no está fijado
en el entorno de test, así que `crear_cliente()` cae al `ClienteEco` por
defecto (sin red).
"""
import re

_PASOS = [
    ("nuevo_o_existente", "Nuevo"),
    ("nombre_proyecto", "Cafecito"),
    ("nombre_proyecto_estado", "Nombre definido"),
    ("problema_objetivo", "Quiero llevar el control de pedidos de mi cafetería."),
    ("personas_gate", "Varias personas con roles distintos"),
    ("perfil_usuario", "Meseros del café"),
    ("perfil_usuario_continuar", "No"),
    ("experiencia_persona_narrativa", "Llegan, ven la lista de pedidos, los marcan como listos."),
    ("experiencia_persona_frecuencia", "Regularmente"),
    ("experiencia_persona_primera_vez", "La primera vez reciben una breve explicación."),
    ("experiencia_persona_permisos_residual", ["Ver información"]),
    ("plataforma", "Desde el celular"),
    ("plataforma_offline", "Sí"),
    ("interaccion_cuenta", "Necesita cuenta para lo esencial"),
    ("interaccion_resultado_valor", "El pedido queda registrado y listo para prepararse."),
    ("contenido_gate", "No"),
    ("dato_recordar", "No"),
    ("monetizacion", "Sí, de alguna forma"),
    ("monetizacion_forma", "Suscripción"),
    ("monetizacion_planes_n", "1"),
    ("monetizacion_plan_detalle", "Básico: acceso a todas las funciones"),
    ("monetizacion_plan_continuar", "No"),
    ("monetizacion_prueba_gratis", "No"),
    ("monetizacion_impago", "Pierde acceso tras un periodo de gracia."),
    ("monetizacion_autogestion", "Sí"),
    ("monetizacion_factura", "No"),
    ("monetizacion_salida", "No, no le paga a nadie"),
    ("seguridad_aislamiento", "Depende"),
    ("seguridad_verificacion", "No"),
    ("seguridad_sensible", "No"),
    ("integraciones_gate", "No"),
    ("automatizacion_gate", "No"),
    ("ia_producto_gate", "No"),
    ("sintesis_confirmacion", "Sí"),
    ("sintesis_abandono", "Puede retomar después."),
    ("sintesis_reanudacion", "Sí."),
    ("sintesis_concurrencia", "No debería pasar, es un solo mesero por turno."),
    ("sintesis_peor_caso", "Se reintenta el pedido."),
    ("marca_gate", "No tengo nada"),
    ("marca_prioridad", "No"),
    ("funcionalidad_declarada", "Registrar pedidos nuevos"),
    ("funcionalidad_prioridad", "Indispensable"),
    ("funcionalidad_declarada_continuar", "No"),
    ("funcionalidad_prohibida", "No debe perder pedidos ya confirmados."),
    ("restriccion_tecnica", "Ya usamos Google Sheets, si se puede reutilizar mejor."),
    ("restriccion_tiempo_presupuesto", "Presupuesto limitado, no hay fecha límite estricta."),
    ("restriccion_negocio", "No debe compartir los datos de los clientes con terceros."),
    ("restriccion_legal", "No"),
    ("cierre_exito", "Que los meseros dejen de usar papel para tomar pedidos."),
    ("cierre_libre", "Nada más por ahora."),
]


def _responder(client, csrf, codigo, pregunta_id, valor):
    return client.post(
        f"/discovery/{codigo}/formulario",
        data={"csrf_token": csrf, "pregunta_id": pregunta_id, "respuesta": valor},
    )


def _completar_formulario(client, csrf, codigo):
    for pregunta_id, valor in _PASOS:
        resp = _responder(client, csrf, codigo, pregunta_id, valor)
        assert resp.status_code == 302, f"fallo en {pregunta_id}: {resp.status_code}"


class TestDiscoveryNuevo:
    def test_genera_codigo_y_redirige_al_formulario(self, client):
        resp = client.get("/discovery/nuevo")
        assert resp.status_code == 302
        m = re.search(r"/discovery/(DISC-[0-9a-f]{8})/formulario", resp.headers["Location"])
        assert m is not None

    def test_dos_llamadas_generan_codigos_distintos(self, client):
        r1 = client.get("/discovery/nuevo").headers["Location"]
        r2 = client.get("/discovery/nuevo").headers["Location"]
        assert r1 != r2


class TestDiscoveryFormularioGet:
    def test_codigo_nuevo_muestra_primera_pregunta(self, client):
        resp = client.get("/discovery/DISC-aaaaaaaa/formulario")
        assert resp.status_code == 200
        assert b"nuevo_o_existente" in resp.data
        assert "¿Es un proyecto nuevo o ya existe algo construido?".encode() in resp.data

    def test_incluye_csrf_token(self, client):
        resp = client.get("/discovery/DISC-aaaaaaaa/formulario")
        assert b'name="csrf_token"' in resp.data

    def test_sin_historial_no_muestra_seccion_de_historial(self, client):
        resp = client.get("/discovery/DISC-aaaaaaaa/formulario")
        assert b"Respuestas hasta ahora" not in resp.data


class TestDiscoveryFormularioPost:
    def test_responder_avanza_a_la_siguiente_pregunta(self, client, csrf_token):
        codigo = "DISC-bbbbbbbb"
        resp = _responder(client, csrf_token, codigo, "nuevo_o_existente", "Nuevo")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/discovery/{codigo}/formulario")

        siguiente = client.get(f"/discovery/{codigo}/formulario")
        assert b"nombre_proyecto" in siguiente.data

    def test_respuesta_queda_en_el_historial(self, client, csrf_token):
        codigo = "DISC-cccccccc"
        _responder(client, csrf_token, codigo, "nuevo_o_existente", "Nuevo")
        resp = client.get(f"/discovery/{codigo}/formulario")
        assert b"Respuestas hasta ahora" in resp.data
        assert "Nuevo".encode() in resp.data

    def test_pregunta_id_desconocido_responde_400(self, client, csrf_token):
        resp = client.post(
            "/discovery/DISC-dddddddd/formulario",
            data={"csrf_token": csrf_token, "pregunta_id": "no_existe", "respuesta": "x"},
        )
        assert resp.status_code == 400

    def test_opcion_invalida_responde_400_y_reexhibe_la_misma_pregunta(self, client, csrf_token):
        codigo = "DISC-eeeeeeee"
        resp = client.post(
            f"/discovery/{codigo}/formulario",
            data={"csrf_token": csrf_token, "pregunta_id": "nuevo_o_existente", "respuesta": "no es una opción"},
        )
        assert resp.status_code == 400
        assert b"nuevo_o_existente" in resp.data  # sigue en la misma pregunta

    def test_sin_csrf_token_responde_403(self, client):
        resp = client.post(
            "/discovery/DISC-ffffffff/formulario",
            data={"pregunta_id": "nuevo_o_existente", "respuesta": "Nuevo"},
        )
        assert resp.status_code == 403

    def test_multiple_checkboxes_se_guardan_y_se_muestran_deserializados(self, client, csrf_token):
        codigo = "DISC-11111111"
        _responder(client, csrf_token, codigo, "nuevo_o_existente", "Nuevo")
        _responder(client, csrf_token, codigo, "nombre_proyecto", "X")
        _responder(client, csrf_token, codigo, "nombre_proyecto_estado", "Nombre definido")
        _responder(client, csrf_token, codigo, "problema_objetivo", "algo")
        _responder(client, csrf_token, codigo, "personas_gate", "Yo solo / todos igual")
        resp_plataforma = _responder(client, csrf_token, codigo, "plataforma", "En varios de estos lugares")
        assert resp_plataforma.status_code == 302

        siguiente = client.get(f"/discovery/{codigo}/formulario")
        assert b"plataforma_detalle" in siguiente.data

        resp_detalle = client.post(
            f"/discovery/{codigo}/formulario",
            data={
                "csrf_token": csrf_token, "pregunta_id": "plataforma_detalle",
                "respuesta": ["Celular", "Desde un navegador web"],
            },
        )
        assert resp_detalle.status_code == 302

        historial = client.get(f"/discovery/{codigo}/formulario")
        assert b"Celular, Desde un navegador web" in historial.data
        assert b"[" not in historial.data.split(b"Respuestas hasta ahora")[1].split(b"</section>")[0]

    def test_checkbox_sin_ninguna_marcada_es_aceptada(self, client, csrf_token):
        """`validar_respuesta` ya acepta una lista vacía para una pregunta
        múltiple (comportamiento existente de `src.formulario`, sin cambios
        aquí) — la UI no le agrega una regla de "al menos una" que no exista."""
        codigo = "DISC-22222222"
        _responder(client, csrf_token, codigo, "nuevo_o_existente", "Nuevo")
        _responder(client, csrf_token, codigo, "nombre_proyecto", "X")
        _responder(client, csrf_token, codigo, "nombre_proyecto_estado", "Nombre definido")
        _responder(client, csrf_token, codigo, "problema_objetivo", "algo")
        _responder(client, csrf_token, codigo, "personas_gate", "Yo solo / todos igual")
        _responder(client, csrf_token, codigo, "plataforma", "En varios de estos lugares")
        resp = client.post(
            f"/discovery/{codigo}/formulario",
            data={"csrf_token": csrf_token, "pregunta_id": "plataforma_detalle"},
        )
        assert resp.status_code == 302


class TestDiscoveryFormularioCompleto:
    def test_arbol_completo_muestra_boton_ejecutar(self, client, csrf_token):
        codigo = "DISC-33333333"
        _completar_formulario(client, csrf_token, codigo)
        resp = client.get(f"/discovery/{codigo}/formulario")
        assert resp.status_code == 200
        assert b"Ejecutar Discovery" in resp.data


class TestDiscoveryEjecutar:
    def test_formulario_incompleto_redirige_al_formulario(self, client, csrf_token):
        codigo = "DISC-44444444"
        _responder(client, csrf_token, codigo, "nuevo_o_existente", "Nuevo")
        resp = client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/discovery/{codigo}/formulario")

    def test_formulario_completo_ejecuta_y_redirige_al_resultado(self, client, csrf_token):
        codigo = "DISC-55555555"
        _completar_formulario(client, csrf_token, codigo)
        resp = client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/discovery/{codigo}/resultado")

    def test_sin_csrf_token_responde_403(self, client):
        resp = client.post("/discovery/DISC-66666666/ejecutar", data={})
        assert resp.status_code == 403


class TestDiscoveryResultado:
    def test_codigo_sin_respuestas_responde_404(self, client):
        resp = client.get("/discovery/DISC-77777777/resultado")
        assert resp.status_code == 404

    def test_formulario_incompleto_muestra_aviso(self, client, csrf_token):
        codigo = "DISC-88888888"
        _responder(client, csrf_token, codigo, "nuevo_o_existente", "Nuevo")
        resp = client.get(f"/discovery/{codigo}/resultado")
        assert resp.status_code == 200
        assert "todavía no está completo".encode() in resp.data

    def test_formulario_completo_sin_ejecutar_muestra_aviso(self, client, csrf_token):
        codigo = "DISC-99999999"
        _completar_formulario(client, csrf_token, codigo)
        resp = client.get(f"/discovery/{codigo}/resultado")
        assert resp.status_code == 200
        assert "Discovery todavía no se ha ejecutado".encode() in resp.data

    def test_no_ofrece_boton_de_volver_a_ejecutar(self, client, csrf_token):
        """Ajuste explícito aprobado: sin botón de re-ejecución en esta
        primera versión (ejecutar_discovery no es idempotente)."""
        codigo = "DISC-a0a0a0a0"
        _completar_formulario(client, csrf_token, codigo)
        client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})
        resp = client.get(f"/discovery/{codigo}/resultado")
        assert b"Ejecutar Discovery" not in resp.data
        assert b"volver a ejecutar" not in resp.data.lower()

    def test_ejecutado_muestra_entidades_deterministas(self, client, csrf_token):
        codigo = "DISC-b0b0b0b0"
        _completar_formulario(client, csrf_token, codigo)
        client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})
        resp = client.get(f"/discovery/{codigo}/resultado")
        assert resp.status_code == 200
        assert b"Requisitos" in resp.data
        # Las deterministas (plataforma/monetizacion) no dependen de si el
        # ClienteEco de prueba devolvi\xc3\xb3 algo interpretable.
        assert "celular".encode() in resp.data
        assert "cobrar".encode() in resp.data
        assert b"ALTA" in resp.data

    def test_ejecutado_no_muestra_fallo(self, client, csrf_token):
        codigo = "DISC-c0c0c0c0"
        _completar_formulario(client, csrf_token, codigo)
        client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})
        resp = client.get(f"/discovery/{codigo}/resultado")
        assert b"Discovery fall\xc3\xb3" not in resp.data


class TestDiscoveryEjecutarErrores:
    """`ejecutar_discovery` ya absorbe y registra sus propios fallos
    (`acciones` en FALLIDA, TF-0030) — esta vista solo debe sobrevivir sin
    romperse (nunca un 500) y seguir redirigiendo a `/resultado`."""

    def test_formulario_incompleto_al_ejecutar_no_rompe_la_vista(self, client, csrf_token, monkeypatch):
        import app as app_module
        from src.discovery.discovery import FormularioIncompleto

        codigo = "DISC-d0d0d0d0"
        _completar_formulario(client, csrf_token, codigo)

        def _lanza(codigo, cliente):
            raise FormularioIncompleto("carrera simulada")

        monkeypatch.setattr(app_module, "ejecutar_discovery", _lanza)
        resp = client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/discovery/{codigo}/resultado")

    def test_fallo_generico_al_ejecutar_no_rompe_la_vista(self, client, csrf_token, monkeypatch):
        import app as app_module

        codigo = "DISC-e0e0e0e0"
        _completar_formulario(client, csrf_token, codigo)

        def _lanza(codigo, cliente):
            raise RuntimeError("fallo simulado de persistencia")

        monkeypatch.setattr(app_module, "ejecutar_discovery", _lanza)
        resp = client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/discovery/{codigo}/resultado")


class TestReaperturaEnLaUI:
    """TF-0032 — `_PASOS` ya contiene el caso real auditado
    (monetizacion=Sí + dato_recordar=No): ejecutar Discovery sobre un
    recorrido completo de la UI dispara la contradicción real y la reapertura
    correspondiente, sin que `procesar_reapertura()` vuelva a tocar el
    formulario completo."""

    def test_formulario_muestra_la_pregunta_reactivada_tras_ejecutar(self, client, csrf_token):
        codigo = "DISC-r0000001"
        _completar_formulario(client, csrf_token, codigo)
        client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})

        resp = client.get(f"/discovery/{codigo}/formulario")
        assert resp.status_code == 200
        assert b"dato_recordar" in resp.data
        assert "Discovery encontró algo que aclarar".encode("utf-8") in resp.data
        assert b"Ejecutar Discovery" not in resp.data  # ya no es "formulario completo"

    def test_responder_la_reapertura_la_resuelve(self, client, csrf_token):
        """Al cambiar dato_recordar a "Sí", el propio árbol (sin tocarlo)
        vuelve a pedir dato_recordar_detalle — nunca vuelve a mostrar
        "Ejecutar Discovery" hasta responder eso también. La reapertura en
        sí queda resuelta de inmediato, independiente de esa continuación."""
        codigo = "DISC-r0000002"
        _completar_formulario(client, csrf_token, codigo)
        client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})

        resp = client.post(
            f"/discovery/{codigo}/formulario",
            data={"csrf_token": csrf_token, "pregunta_id": "dato_recordar", "respuesta": "Sí"},
        )
        assert resp.status_code == 302

        from src.repositorios.contradicciones import RepositorioContradicciones
        from src.expediente.modelo import EstadoContradiccion
        contradicciones = RepositorioContradicciones().listar(codigo)
        assert contradicciones[0].estado == EstadoContradiccion.RESUELTA

        # El árbol (intacto) ahora sí requiere dato_recordar_detalle, porque
        # dato_recordar ya no es "No" — comportamiento correcto y esperado
        # de src.formulario.arbol, no un efecto de la reapertura en sí.
        siguiente = client.get(f"/discovery/{codigo}/formulario")
        assert b"dato_recordar_detalle" in siguiente.data

    def test_resultado_muestra_la_contradiccion_y_el_estado(self, client, csrf_token):
        codigo = "DISC-r0000003"
        _completar_formulario(client, csrf_token, codigo)
        client.post(f"/discovery/{codigo}/ejecutar", data={"csrf_token": csrf_token})

        resp = client.get(f"/discovery/{codigo}/resultado")
        assert resp.status_code == 200
        assert b"Contradicciones" in resp.data
        assert b"datos.existencia_de_dato" in resp.data
        assert b"requiere_aclaracion" in resp.data


class TestReaperturaPorGapEnLaUI:
    """El Gap-hallazgo (vía LLM) no ocurre con el ClienteEco por defecto de
    los demás tests — se crea directo por repositorio para ejercitar la
    rama de Gap (no Contradiccion) de `_reapertura_pendiente`."""

    def test_gap_abierto_con_pregunta_resoluble_se_muestra_en_el_formulario(self, client, csrf_token):
        from src.repositorios.gaps import RepositorioGaps

        codigo = "DISC-r0000004"
        _completar_formulario(client, csrf_token, codigo)
        RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.retencion", motivo="x")

        resp = client.get(f"/discovery/{codigo}/formulario")
        assert resp.status_code == 200
        assert b"dato_retencion" in resp.data
        assert "Discovery encontró algo que aclarar".encode("utf-8") in resp.data


class TestHistorialConPreguntaDesconocida:
    def test_fila_con_pregunta_id_ajena_al_catalogo_no_rompe_el_historial(self, client, csrf_token):
        """Defensivo: una fila de `respuestas_formulario` con un
        `pregunta_id` que ya no está en el catálogo (dato viejo/editado a
        mano) no debe romper la vista — se muestra tal cual, cruda."""
        from src.repositorios.respuestas_formulario import RepositorioRespuestasFormulario
        from src.expediente.modelo import TipoPregunta

        codigo = "DISC-f0f0f0f0"
        RepositorioRespuestasFormulario().registrar(
            codigo, "pregunta_ya_no_existe", "¿Pregunta retirada del catálogo?",
            TipoPregunta.TEXTO_LIBRE, "una respuesta vieja",
        )
        resp = client.get(f"/discovery/{codigo}/formulario")
        assert resp.status_code == 200
        assert b"una respuesta vieja" in resp.data
