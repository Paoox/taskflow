"""Pruebas de `LoteDescubrimiento`: unidad transaccional atómica para una
etapa del Orquestador Discovery.

Verifica el requisito explícito del checkpoint de implementación: una etapa
que genera varias entidades/relaciones se persiste como un lote — todo o
nada — nunca un Requisito creado con sus Capacidades/relaciones a medias.
"""
import pytest

from src.expediente.modelo import NaturalezaInformacion, TipoRelacion
from src.proyectos.estado import NivelConfianza, OrigenDato
from src.repositorios.capacidades import RepositorioCapacidades
from src.repositorios.lote_descubrimiento import LoteDescubrimiento
from src.repositorios.relaciones import RepositorioRelaciones
from src.repositorios.requisitos import RepositorioRequisitos


@pytest.fixture
def repos(db):
    return {
        "requisitos": RepositorioRequisitos(),
        "capacidades": RepositorioCapacidades(),
        "relaciones": RepositorioRelaciones(),
    }


class TestCommitExitoso:
    def test_todas_las_escrituras_del_lote_quedan_visibles(self, repos):
        with LoteDescubrimiento() as lote:
            req = repos["requisitos"].crear(
                "PROY-001", "suscripcion premium", NaturalezaInformacion.DECLARADO,
                OrigenDato.USER, NivelConfianza.ALTA, conn=lote.conexion,
            )
            cap = repos["capacidades"].crear(
                "PROY-001", "identificar usuario", "identidad", NaturalezaInformacion.DEDUCIDO,
                OrigenDato.INFERENCE, NivelConfianza.MEDIA, conn=lote.conexion,
            )
            repos["relaciones"].crear(
                "PROY-001", TipoRelacion.REQUIERE, "requisito", req.id, "capacidad", cap.id,
                conn=lote.conexion,
            )

        assert len(repos["requisitos"].listar("PROY-001")) == 1
        assert len(repos["capacidades"].listar("PROY-001")) == 1
        assert len(repos["relaciones"].listar("PROY-001")) == 1

    def test_conexion_se_cierra_al_salir(self, repos):
        with LoteDescubrimiento() as lote:
            conexion_usada = lote.conexion
            repos["requisitos"].crear(
                "PROY-001", "x", NaturalezaInformacion.DECLARADO, OrigenDato.USER,
                NivelConfianza.ALTA, conn=lote.conexion,
            )
        with pytest.raises(Exception):
            conexion_usada.execute("SELECT 1")  # conexión ya cerrada


class TestRollbackCompleto:
    def test_fallo_a_mitad_del_lote_no_deja_nada_escrito(self, repos):
        """Caso central del requisito: un Requisito y una Capacidad se crean
        dentro del lote, pero la relación entre ambos falla (tipo inválido) —
        NINGUNA de las tres escrituras debe sobrevivir, ni siquiera las que
        ya se habían ejecutado antes del fallo."""
        with pytest.raises(Exception):
            with LoteDescubrimiento() as lote:
                repos["requisitos"].crear(
                    "PROY-002", "requisito que no debe sobrevivir",
                    NaturalezaInformacion.DECLARADO, OrigenDato.USER,
                    NivelConfianza.ALTA, conn=lote.conexion,
                )
                repos["capacidades"].crear(
                    "PROY-002", "capacidad que no debe sobrevivir", "x",
                    NaturalezaInformacion.DEDUCIDO, OrigenDato.INFERENCE,
                    NivelConfianza.MEDIA, conn=lote.conexion,
                )
                # Fallo real de validación de dominio, no un error artificial:
                # una Capacidad "observada" está prohibida por diseño.
                repos["capacidades"].crear(
                    "PROY-002", "esto dispara la validacion", "x",
                    NaturalezaInformacion.OBSERVADO, OrigenDato.REPOSITORY,
                    NivelConfianza.BAJA, conn=lote.conexion,
                )

        assert repos["requisitos"].listar("PROY-002") == []
        assert repos["capacidades"].listar("PROY-002") == []

    def test_excepcion_generica_tambien_revierte_el_lote(self, repos):
        with pytest.raises(RuntimeError):
            with LoteDescubrimiento() as lote:
                repos["requisitos"].crear(
                    "PROY-003", "no debe sobrevivir", NaturalezaInformacion.DECLARADO,
                    OrigenDato.USER, NivelConfianza.ALTA, conn=lote.conexion,
                )
                raise RuntimeError("fallo simulado a mitad de la etapa")

        assert repos["requisitos"].listar("PROY-003") == []

    def test_excepcion_original_se_propaga_sin_silenciarse(self, repos):
        with pytest.raises(RuntimeError, match="fallo simulado"):
            with LoteDescubrimiento() as lote:
                repos["requisitos"].crear(
                    "PROY-004", "x", NaturalezaInformacion.DECLARADO, OrigenDato.USER,
                    NivelConfianza.ALTA, conn=lote.conexion,
                )
                raise RuntimeError("fallo simulado")

    def test_lote_no_afecta_escrituras_previas_ya_comiteadas(self, repos):
        """Una escritura fuera del lote (una conexión por operación, patrón
        de siempre) ya quedó comiteada; un rollback posterior de OTRO lote no
        debe tocarla."""
        previo = repos["requisitos"].crear(
            "PROY-005", "creado antes del lote, fuera de cualquier lote",
            NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA,
        )
        with pytest.raises(RuntimeError):
            with LoteDescubrimiento() as lote:
                repos["requisitos"].crear(
                    "PROY-005", "no debe sobrevivir", NaturalezaInformacion.DECLARADO,
                    OrigenDato.USER, NivelConfianza.ALTA, conn=lote.conexion,
                )
                raise RuntimeError("fallo")

        restantes = repos["requisitos"].listar("PROY-005")
        assert len(restantes) == 1
        assert restantes[0].id == previo.id


class TestSinConn:
    def test_repositorios_siguen_funcionando_sin_lote(self, repos):
        """El patrón "una conexión por operación" del resto de TaskFlow no
        se rompe: sin `conn`, cada llamada sigue abriendo/comiteando/
        cerrando su propia conexión, exactamente igual que antes."""
        r = repos["requisitos"].crear(
            "PROY-006", "x", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA,
        )
        assert repos["requisitos"].obtener(r.id) is not None
