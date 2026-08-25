/**
 * Destello — El aula: avatar de una persona
 *
 * POR QUÉ EXISTE ESTE ARCHIVO APARTE: la regla de que **nunca se muestra una
 * inicial sola** aparece en tres lugares (la tira del alumno, la rejilla de la
 * profe, y el modal de un alumno). Si cada uno lo dibujara por su cuenta,
 * tarde o temprano uno acabaría con la letra en un círculo gris — que es
 * justamente lo que hace que una plataforma se sienta a formulario y no a salón.
 *
 * Cuando no hay foto, se dibuja un avatar de color derivado del nombre: la
 * misma persona siempre sale del mismo color, así que la profe la reconoce de
 * un vistazo aunque no le lea el nombre.
 */

/** Doce tonos que se distinguen entre sí y se ven bien sobre fondo oscuro. */
const TONOS = [
    '#0D7377', '#D97706', '#7C3AED', '#DB2777', '#059669', '#2563EB',
    '#DC2626', '#0891B2', '#CA8A04', '#9333EA', '#E11D48', '#15803D',
]

/** Suma estable de los caracteres → siempre el mismo color para el mismo nombre. */
function tonoDe(nombre = '') {
    let n = 0
    for (let i = 0; i < nombre.length; i++) n = (n + nombre.charCodeAt(i) * (i + 1)) % TONOS.length
    return TONOS[n]
}

/** Las iniciales SOLO se usan dentro del avatar de color, nunca solas. */
function iniciales(nombre = '') {
    const partes = nombre.trim().split(/\s+/).filter(Boolean)
    if (!partes.length) return '·'
    if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase()
    return (partes[0][0] + partes[1][0]).toUpperCase()
}

export default function Avatar({ persona, size = 40, mostrarNombre = false }) {
    const { nombre = '', avatarUrl = null, camara = false } = persona ?? {}
    const tono = tonoDe(nombre)

    const cuadro = {
        width:        size,
        height:       size,
        borderRadius: size > 56 ? 'var(--radius-lg)' : '50%',
        flex:         'none',
        overflow:     'hidden',
        display:      'flex',
        alignItems:   'center',
        justifyContent: 'center',
        background:   avatarUrl ? 'var(--bg-surface)' : tono,
        color:        '#fff',
        fontFamily:   'var(--font-sans)',
        fontWeight:   700,
        fontSize:     Math.max(10, size * 0.36),
        letterSpacing: '0.02em',
        userSelect:   'none',
    }

    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
            <div style={cuadro} title={nombre}>
                {avatarUrl
                    ? <img src={avatarUrl} alt={nombre}
                           style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    : iniciales(nombre)}
                {/* Cuando la cámara está prendida, aquí va el video en lugar del
                    avatar. Se deja el hueco marcado para no tener que rehacer
                    este componente al conectar LiveKit. */}
                {camara && null}
            </div>
            {mostrarNombre && (
                <span style={{
                    fontSize:     'var(--text-xs)',
                    color:        'var(--text-secondary)',
                    whiteSpace:   'nowrap',
                    overflow:     'hidden',
                    textOverflow: 'ellipsis',
                }}>
                    {nombre}
                </span>
            )}
        </div>
    )
}
