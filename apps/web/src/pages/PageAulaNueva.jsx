/**
 * Destello — Pantalla de prueba del aula nueva
 *
 * Ruta: `/aula-nueva/:id`  ·  `/aula-nueva/:id?rol=profe` para verla del otro lado.
 *
 * POR QUÉ EXISTE: el `/aula/:id` de siempre sigue intacto. Esta pantalla deja
 * ver el aula nueva con datos inventados, sin romper nada de lo que ya está en
 * producción y **sin necesitar todavía el servidor de video**.
 *
 * Este archivo es el ÚNICO que conoce a Destello. Su trabajo es armar el objeto
 * `sesion` que describe `aula/contrato.js` y pasárselo al aula. El día que la
 * sesión venga de la API real, se cambia solo aquí; el día que otra escuela
 * monte el aula, escribe su propia versión de este archivo. Nada dentro de
 * `src/aula/` se entera.
 */
import { useParams, useSearchParams } from 'react-router-dom'
import Aula from '../aula/Aula.jsx'
import { MARCA_DESTELLO } from '../aula/contrato.js'

/** Gente de mentiras para poder ver el aula antes de que exista la de verdad. */
const NOMBRES = [
    'Ana Ruiz', 'Beto Luna', 'Camila Soto', 'Diana Pérez', 'Emilio Vega',
    'Fer Nava', 'Gaby Ríos', 'Hugo Mena', 'Irene Cruz', 'Javier Toro',
    'Karla Díaz', 'Luis Ortiz', 'Mara Solís', 'Nico Bravo', 'Olga Ponce',
    'Pablo Reyes', 'Quetzal Mora', 'Rosa Iglesias', 'Sam Cárdenas', 'Tania Ávila',
]

/**
 * Se genera con una fórmula y no al azar: así la pantalla se ve igual en cada
 * recarga y se puede comparar un cambio con el anterior. Con datos aleatorios
 * nunca sabes si lo que cambió fue tu código o la suerte.
 */
const PERSONAS = NOMBRES.map((nombre, i) => ({
    id:       `p${i}`,
    nombre,
    avatarUrl: null,
    camara:   false,
    micro:    i === 3,
    silenciadoPorProfe: i === 7,
    manoArriba:    i === 2 || i === 11,
    reaccion:      i === 5 ? '👏' : i === 14 ? '🤔' : null,
    interactuando: i % 4 !== 1,
    avance:   (i * 17) % 100,
    insignias: i % 5 === 0 ? ['abeja'] : i % 7 === 0 ? ['oso', 'estrella'] : [],
}))

export default function PageAulaNueva() {
    const { id } = useParams()
    const [params] = useSearchParams()
    const rol = params.get('rol') === 'profe' ? 'profe' : 'alumno'

    const yo = rol === 'profe'
        ? { id: 'profe', nombre: 'Prof. Minerva', avatarUrl: null, camara: true,
            micro: true, silenciadoPorProfe: false, manoArriba: false,
            reaccion: null, interactuando: true, avance: 0, insignias: [] }
        : { id: 'yo', nombre: 'Paola Arreola', avatarUrl: null, camara: false,
            micro: false, silenciadoPorProfe: false, manoArriba: false,
            reaccion: null, interactuando: true, avance: 42,
            insignias: ['abeja', 'estrella'] }

    const sesion = {
        marca: MARCA_DESTELLO,
        taller: {
            nombre:     'Taller Auriculoterapia Inicial',
            instructor: 'Prof. Minerva Márquez',
            tema:       'Horizonte Zen',
            terminaEn:  147,      // minutos — el contador de la barra
        },
        rol,
        yo,
        // La profe se ve a sí misma en la lista; el alumno no se duplica.
        personas: rol === 'profe' ? PERSONAS : PERSONAS.slice(1),
        pizarron: { actividadId: null, liberado: false },
    }

    return <Aula sesion={sesion} key={`${id}-${rol}`} />
}
