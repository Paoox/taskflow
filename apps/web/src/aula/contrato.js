/**
 * Destello — El aula: el contrato con el mundo de afuera
 *
 * ⚠️ REGLA QUE NO SE ROMPE ⚠️
 *
 * El aula NO es una pantalla de Destello: es un producto aparte que un día se
 * va a rentar a escuelas, empresas y otras plataformas, con la marca de quien
 * la contrate.
 *
 * Por eso **nada dentro de `src/aula/` puede consultar la API de Destello, ni
 * leer `usuarios`, `talleres` o `chispas`.** El aula recibe TODO lo que
 * necesita saber en un solo objeto —el que describe este archivo— y quien la
 * monta se encarga de llenarlo.
 *
 * Hoy quien lo llena es Destello. Mañana puede ser el sistema de otra escuela,
 * y el aula no se entera ni le importa.
 *
 * Si algún día alguien necesita un dato que no está aquí, la respuesta correcta
 * es **agregarlo al contrato**, nunca ir a buscarlo por su cuenta. En el momento
 * en que un componente del aula haga `fetch('/api/...')`, el producto dejó de
 * ser vendible y volver atrás cuesta rehacerlo.
 */

/**
 * @typedef {Object} Marca
 * Todo lo que hace que el aula se vea de quien la contrató. Marca blanca.
 * @property {string}  nombre        Cómo se llama la escuela ("Destello")
 * @property {string?} logoUrl       Su logo. Si falta, se usa el símbolo ✦
 * @property {string}  colorPrimario Su color de acento
 */

/**
 * @typedef {Object} Persona
 * @property {string}  id
 * @property {string}  nombre    Nombre o alias — lo que la persona eligió que
 *                               se vea. NUNCA se muestra una inicial sola.
 * @property {string?} avatarUrl Su imagen. Si falta, se dibuja un avatar con
 *                               su nombre.
 * @property {boolean} camara    ¿Está transmitiendo video ahora?
 * @property {boolean} micro     ¿Tiene el micrófono abierto?
 * @property {boolean} silenciadoPorProfe  El silencio de la profe gana: si
 *                               esto es `true`, la persona no puede hablar
 *                               aunque le dé a su botón.
 * @property {boolean} manoArriba
 * @property {string?} reaccion  Emoji que acaba de mandar, o null
 * @property {boolean} interactuando  El semáforo: ¿tocó el pizarrón en los
 *                               últimos minutos?
 * @property {number}  avance    0 a 100 — qué tan avanzada va en la actividad
 * @property {string[]} insignias Sellos que le ha puesto la profe hoy
 */

/**
 * @typedef {Object} Sesion
 * El objeto que el aula recibe. Es su única ventana al mundo.
 *
 * @property {Marca}   marca
 * @property {Object}  taller
 * @property {string}  taller.nombre
 * @property {string}  taller.instructor
 * @property {string?} taller.tema      Nombre del fondo/ambiente ("Horizonte Zen")
 * @property {number}  taller.terminaEn Minutos que faltan para que acabe
 * @property {'alumno'|'profe'} rol     Desde qué lado se ve el aula
 * @property {Persona} yo
 * @property {Persona[]} personas       Todos los demás
 * @property {Object}  pizarron
 * @property {string?} pizarron.actividadId  Qué se está mostrando
 * @property {boolean} pizarron.liberado     ¿Pueden tocarlo los alumnos?
 */

/** Marca por defecto, para cuando el aula se monta sin configurar nada. */
export const MARCA_DESTELLO = {
    nombre:        'Destello',
    logoUrl:       null,
    colorPrimario: 'var(--color-jade-500)',
}

/**
 * Sellos que la profe puede poner. Van aquí y no dentro de un componente
 * porque los quiere ver tanto ella (para elegir) como el alumno (en su
 * pizarrón), y una sola lista evita que se desincronicen.
 *
 * Son de tinta, estilo kínder: motivan sin calificar con un número.
 */
export const SELLOS = [
    { id: 'abeja',   emoji: '🐝', label: 'Trabajadora' },
    { id: 'oso',     emoji: '🧸', label: 'Pensativo' },
    { id: 'estrella',emoji: '⭐', label: 'Excelente' },
    { id: 'cohete',  emoji: '🚀', label: 'Va volando' },
    { id: 'corazon', emoji: '💚', label: 'Con cariño' },
    { id: 'foco',    emoji: '💡', label: 'Buena idea' },
]

/** Reacciones que un alumno puede mandar en clase. */
export const REACCIONES = ['💚', '👏', '😮', '😄', '🤔', '👍']

/**
 * Cuántos minutos sin tocar el pizarrón antes de que el semáforo se ponga rojo.
 *
 * Va aquí, con nombre, para que el día que Paola diga "se me hace muy rápido"
 * se cambie UN número y no haya que buscarlo entre el código. Un quiz y un
 * modelo 3D tienen ritmos distintos, así que a futuro cada actividad podrá
 * traer el suyo.
 */
export const MINUTOS_SIN_TOCAR = 3
