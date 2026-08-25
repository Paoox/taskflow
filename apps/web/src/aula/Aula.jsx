/**
 * Destello — El aula
 *
 * La cáscara: las dos ventanas, la barra de arriba y los controles. Todavía sin
 * video real ni actividades — esos se enchufan aquí dentro sin mover esta
 * estructura.
 *
 * ⚠️ Este componente y todo lo que vive en `src/aula/` NO consulta la API de
 * Destello. Recibe una `sesion` (ver `contrato.js`) y con eso le basta. Es lo
 * que permite rentar el aula a otra escuela sin reescribirla.
 *
 * ── Por qué está armada así ──────────────────────────────────────────────
 *
 * Dos ventanas **lado a lado**, no una encima de otra: a la izquierda quien
 * habla, a la derecha en qué se trabaja. Es la decisión que separa esto de una
 * videollamada — el pizarrón no es un extra, es la mitad de la pantalla.
 *
 * La tira de personas va **debajo del video y con scroll propio**, para que la
 * lista pueda crecer sin encoger la ventana de quien está dando la clase.
 */
import { useState, useEffect, useRef } from 'react'
import {
    Microphone, MicrophoneSlash, VideoCamera, VideoCameraSlash, Hand,
    ChatCircleDots, Gear, Question, Lock, LockOpen, Stack, X,
} from '@phosphor-icons/react'
import Avatar from './Avatar.jsx'
import { MARCA_DESTELLO, SELLOS, REACCIONES } from './contrato.js'

/* ══════════════════════════════════════════════════════════════════════════
   Barra de arriba
   ══════════════════════════════════════════════════════════════════════════ */

/** "1:47" — el contador de cuánto falta. En rojo cuando quedan 10 min o menos. */
function formatoRestante(min) {
    if (min == null) return null
    if (min <= 0) return 'Terminando'
    const h = Math.floor(min / 60)
    const m = min % 60
    return h > 0 ? `${h}:${String(m).padStart(2, '0')}` : `${m} min`
}

function BarraSuperior({ sesion }) {
    const { marca, taller, yo } = sesion
    const restante = formatoRestante(taller.terminaEn)
    // Los últimos 10 minutos se marcan en ámbar. La profe necesita saber que
    // va a tener que cerrar, y el alumno agradece no perder la noción del tiempo.
    const porTerminar = taller.terminaEn != null && taller.terminaEn <= 10

    return (
        <header style={{
            display: 'flex', alignItems: 'center', gap: 'var(--space-4)',
            padding: '10px var(--space-4)', flexWrap: 'wrap',
            background: 'var(--bg-surface)',
            borderBottom: '1px solid var(--border-subtle)',
        }}>
            {/* Marca — de quien renta el aula, no necesariamente Destello */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 'none' }}>
                {marca.logoUrl
                    ? <img src={marca.logoUrl} alt={marca.nombre} style={{ height: 24 }} />
                    : <span style={{ fontSize: 18, color: marca.colorPrimario }}>✦</span>}
                <strong style={{ fontSize: 'var(--text-sm)' }}>{marca.nombre}</strong>
            </div>

            {/* Qué clase es y quién la da */}
            <div style={{ minWidth: 0, flex: '1 1 200px', lineHeight: 1.25 }}>
                <div style={{
                    fontSize: 'var(--text-sm)', fontWeight: 600,
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                    {taller.nombre}
                </div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                    {taller.instructor}
                </div>
            </div>

            {restante && (
                <span style={{
                    fontFamily: 'var(--font-mono)', fontSize: 'var(--text-sm)',
                    fontWeight: 700, flex: 'none',
                    color: porTerminar ? 'var(--color-amber-500)' : 'var(--color-jade-400)',
                }} title="Tiempo que falta para que termine la clase">
                    {restante}
                </span>
            )}

            {taller.tema && (
                <span style={{
                    fontSize: 'var(--text-xs)', color: 'var(--text-muted)',
                    textTransform: 'uppercase', letterSpacing: '0.08em', flex: 'none',
                }}>
                    {taller.tema}
                </span>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto', flex: 'none' }}>
                <BotonIcono titulo="Ajustes"><Gear size={17} /></BotonIcono>
                <Avatar persona={yo} size={28} />
            </div>
        </header>
    )
}

/* ══════════════════════════════════════════════════════════════════════════
   Piezas chicas
   ══════════════════════════════════════════════════════════════════════════ */

function BotonIcono({ children, titulo, activo = false, peligro = false, onClick, disabled = false }) {
    const [hover, setHover] = useState(false)
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            title={titulo}
            aria-label={titulo}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
            style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 34, height: 34, padding: 0,
                background: peligro ? 'rgba(220,38,38,0.15)'
                          : activo  ? 'rgba(13,115,119,0.18)'
                          : hover   ? 'var(--bg-card)' : 'transparent',
                border: `1px solid ${peligro ? 'var(--color-error)'
                                   : activo ? 'var(--color-jade-500)'
                                   : 'var(--border-subtle)'}`,
                borderRadius: 'var(--radius-full)',
                color: peligro ? 'var(--color-error)'
                     : activo  ? 'var(--color-jade-400)'
                     : 'var(--text-secondary)',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.45 : 1,
                transition: 'all .15s',
            }}
        >
            {children}
        </button>
    )
}

/** El puntito del semáforo. Verde = tocó el pizarrón hace poco. */
function Semaforo({ activo, size = 8 }) {
    return (
        <span
            title={activo ? 'Está trabajando' : 'No ha tocado el pizarrón'}
            style={{
                width: size, height: size, borderRadius: '50%', flex: 'none',
                display: 'inline-block',
                background: activo ? 'var(--color-success)' : 'var(--color-error)',
            }}
        />
    )
}

/* ══════════════════════════════════════════════════════════════════════════
   Ventana izquierda — el video
   ══════════════════════════════════════════════════════════════════════════ */

function VentanaVideo({ sesion, onAbrirChat, chatAbierto }) {
    const { rol, taller, personas, yo } = sesion
    const esProfe = rol === 'profe'

    return (
        <section className="aula-ventana" style={{
            // `flex: 1` + `minHeight: 0`: sin los dos, la ventana se queda del
            // tamaño de su contenido y deja un hueco muerto abajo. El `minHeight`
            // es el que permite que se encoja cuando se abre el chat.
            flex: '1 1 auto', minHeight: 0,
            display: 'flex', flexDirection: 'column', minWidth: 0,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
        }}>
            {/* Quien está dando la clase */}
            <div style={{
                flex: '1 1 auto', minHeight: 150,
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 10,
                background: 'var(--bg-dark)',
                position: 'relative',
            }}>
                {/* Aquí entra el <video> de LiveKit. El hueco ya está listo. */}
                <div style={{ fontSize: 44, opacity: .5 }}>🎥</div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
                    {taller.instructor}
                </div>
                <span style={{
                    position: 'absolute', top: 10, left: 12,
                    fontSize: 'var(--text-xs)', color: 'var(--text-muted)',
                    background: 'rgba(0,0,0,0.35)', padding: '2px 8px',
                    borderRadius: 'var(--radius-full)',
                }}>
                    Sin video todavía
                </span>
            </div>

            {/* La tira de personas. Scroll propio: la lista crece sin robarle
                altura a la ventana de arriba. La profe las ve en dos filas
                porque necesita a todas de un vistazo. */}
            <div style={{
                display: esProfe ? 'grid' : 'flex',
                gridTemplateColumns: esProfe ? 'repeat(auto-fill, minmax(52px, 1fr))' : undefined,
                gap: 8,
                padding: 'var(--space-3)',
                flex: 'none',
                // La ficha mide 40 del avatar + 3 de hueco + el nombre. Estos
                // topes se calcularon para que NO se corte el nombre de abajo:
                // si se tocan, hay que volver a mirarlo en pantalla.
                maxHeight: esProfe ? 158 : 90,
                overflowX: esProfe ? 'hidden' : 'auto',
                overflowY: esProfe ? 'auto' : 'hidden',
                borderTop: '1px solid var(--border-subtle)',
            }}>
                {[yo, ...personas].map(p => (
                    <FichaPersona key={p.id} persona={p} esProfe={esProfe} soyYo={p.id === yo.id} />
                ))}
            </div>

            {/* Controles */}
            <BarraControles
                sesion={sesion}
                onAbrirChat={onAbrirChat}
                chatAbierto={chatAbierto}
            />
        </section>
    )
}

/** Una persona en la tira: avatar, nombre, y sus señales encima. */
function FichaPersona({ persona, esProfe, soyYo }) {
    const { nombre, manoArriba, reaccion, micro, silenciadoPorProfe } = persona
    return (
        <div style={{
            position: 'relative', display: 'flex', flexDirection: 'column',
            alignItems: 'center', gap: 3, flex: 'none', width: 52,
        }}>
            <Avatar persona={persona} size={40} />

            {/* La mano y la reacción van ENCIMA del avatar: son cosas que la
                profe tiene que cachar sin leer, de reojo. */}
            {manoArriba && (
                <span style={{ position: 'absolute', top: -4, right: 2, fontSize: 15 }} title="Levantó la mano">✋</span>
            )}
            {reaccion && !manoArriba && (
                <span style={{ position: 'absolute', top: -4, right: 2, fontSize: 15 }}>{reaccion}</span>
            )}
            {silenciadoPorProfe && (
                <span style={{
                    position: 'absolute', bottom: 16, right: 0,
                    color: 'var(--color-error)', background: 'var(--bg-dark)',
                    borderRadius: '50%', display: 'flex', padding: 1,
                }} title="Silenciada por la profe">
                    <MicrophoneSlash size={11} weight="fill" />
                </span>
            )}
            {micro && !silenciadoPorProfe && (
                <span style={{
                    position: 'absolute', bottom: 16, right: 0,
                    color: 'var(--color-success)', background: 'var(--bg-dark)',
                    borderRadius: '50%', display: 'flex', padding: 1,
                }} title="Hablando">
                    <Microphone size={11} weight="fill" />
                </span>
            )}

            <span style={{
                fontSize: 10, color: soyYo ? 'var(--color-jade-400)' : 'var(--text-muted)',
                maxWidth: 52, whiteSpace: 'nowrap', overflow: 'hidden',
                textOverflow: 'ellipsis', textAlign: 'center',
            }}>
                {soyYo ? 'Tú' : nombre.split(' ')[0]}
            </span>
        </div>
    )
}

/** Los botones de abajo. Cambian según de qué lado estés. */
function BarraControles({ sesion, onAbrirChat, chatAbierto }) {
    const { rol, yo } = sesion
    const esProfe = rol === 'profe'
    const [micro,  setMicro]  = useState(false)
    const [camara, setCamara] = useState(false)
    const [mano,   setMano]   = useState(false)

    // El silencio de la profe gana. Se comprueba también aquí, en la interfaz,
    // para que el botón se vea claramente bloqueado — pero la comprobación de
    // verdad la hace el servidor: esto es cortesía, no seguridad.
    const bloqueada = yo.silenciadoPorProfe === true

    return (
        <div style={{
            display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
            padding: 'var(--space-3)', borderTop: '1px solid var(--border-subtle)',
        }}>
            <BotonIcono
                titulo={bloqueada ? 'La profe te tiene silenciada' : micro ? 'Cerrar micrófono' : 'Abrir micrófono'}
                activo={micro && !bloqueada}
                peligro={bloqueada}
                disabled={bloqueada}
                onClick={() => setMicro(m => !m)}
            >
                {micro && !bloqueada ? <Microphone size={17} /> : <MicrophoneSlash size={17} />}
            </BotonIcono>

            <BotonIcono
                titulo={camara ? 'Apagar cámara' : 'Prender cámara'}
                activo={camara}
                onClick={() => setCamara(c => !c)}
            >
                {camara ? <VideoCamera size={17} /> : <VideoCameraSlash size={17} />}
            </BotonIcono>

            {!esProfe && (
                <BotonIcono titulo="Levantar la mano" activo={mano} onClick={() => setMano(m => !m)}>
                    <Hand size={17} />
                </BotonIcono>
            )}

            {!esProfe && (
                <div style={{ display: 'flex', gap: 2, marginLeft: 4 }}>
                    {REACCIONES.map(e => (
                        <button key={e} title={`Reaccionar ${e}`} style={{
                            background: 'transparent', border: 'none', cursor: 'pointer',
                            fontSize: 16, padding: '2px 3px', lineHeight: 1,
                        }}>{e}</button>
                    ))}
                </div>
            )}

            {esProfe && (
                <button style={{
                    display: 'flex', alignItems: 'center', gap: 6, marginLeft: 4,
                    padding: '6px 12px', background: 'rgba(220,38,38,0.12)',
                    border: '1px solid var(--color-error)', borderRadius: 'var(--radius-full)',
                    color: 'var(--color-error)', fontFamily: 'var(--font-sans)',
                    fontSize: 'var(--text-xs)', fontWeight: 700, cursor: 'pointer',
                }}>
                    <MicrophoneSlash size={13} /> Silenciar a todos
                </button>
            )}

            <div style={{ marginLeft: 'auto' }}>
                <BotonIcono titulo="Chat de la clase" activo={chatAbierto} onClick={onAbrirChat}>
                    <ChatCircleDots size={17} />
                </BotonIcono>
            </div>
        </div>
    )
}

/* ══════════════════════════════════════════════════════════════════════════
   Ventana derecha — el pizarrón
   ══════════════════════════════════════════════════════════════════════════ */

function VentanaPizarron({ sesion }) {
    const { rol, personas, yo, pizarron } = sesion
    const esProfe = rol === 'profe'
    const [liberado, setLiberado] = useState(pizarron.liberado)
    const [soloLosQueNecesitan, setSoloLosQueNecesitan] = useState(false)
    const [abierta, setAbierta] = useState(null)   // pizarrón de quién estoy viendo

    // El filtro que hace que esto sirva igual con 20 que con 40: no se trata de
    // vigilar a todas, se trata de encontrar rápido a quien no le está saliendo.
    const visibles = soloLosQueNecesitan
        ? personas.filter(p => !p.interactuando || p.manoArriba)
        : personas

    return (
        <section className="aula-ventana" style={{
            display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0,
            background: 'var(--bg-card)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            position: 'relative',
        }}>
            {/* Lo que se está trabajando */}
            <div style={{
                flex: '1 1 auto', minHeight: 170, position: 'relative',
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 8,
                background: 'var(--bg-dark)',
            }}>
                <div style={{ fontSize: 44, opacity: .5 }}>🧩</div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
                    {abierta ? `Pizarrón de ${abierta.nombre}` : 'Aquí va la actividad'}
                </div>
                {!liberado && !esProfe && (
                    <div style={{
                        fontSize: 'var(--text-xs)', color: 'var(--color-amber-500)',
                        display: 'flex', alignItems: 'center', gap: 5,
                    }}>
                        <Lock size={13} weight="fill" /> La profe está explicando
                    </div>
                )}

                {/* Las insignias viven arriba a la derecha y NO se van cuando
                    cambia el material: son de la persona, no del ejercicio. */}
                {!esProfe && yo.insignias?.length > 0 && (
                    <div style={{ position: 'absolute', top: 10, right: 12, display: 'flex', gap: 3 }}>
                        {yo.insignias.map((s, i) => {
                            const sello = SELLOS.find(x => x.id === s)
                            return <span key={i} title={sello?.label} style={{ fontSize: 17 }}>{sello?.emoji ?? '⭐'}</span>
                        })}
                    </div>
                )}

                {/* Cerrar el pizarrón de una alumna devuelve a la profe al suyo */}
                {abierta && (
                    <button onClick={() => setAbierta(null)} title="Volver a mi pizarrón" style={{
                        position: 'absolute', top: 8, left: 8, display: 'flex',
                        padding: 5, background: 'var(--bg-surface)',
                        border: '1px solid var(--border-default)', borderRadius: 'var(--radius-full)',
                        color: 'var(--text-secondary)', cursor: 'pointer',
                    }}>
                        <X size={14} />
                    </button>
                )}

                {/* Controles de la profe, pegados al borde derecho como en el prototipo */}
                {esProfe && (
                    <div style={{
                        position: 'absolute', top: 10, right: 10,
                        display: 'flex', flexDirection: 'column', gap: 6,
                    }}>
                        <BotonIcono
                            titulo={liberado ? 'Bloquear: que solo vean mi modelo' : 'Liberar: que cada quien tome el suyo'}
                            activo={liberado}
                            onClick={() => setLiberado(l => !l)}
                        >
                            {liberado ? <LockOpen size={16} /> : <Lock size={16} />}
                        </BotonIcono>
                        <BotonIcono titulo="Elegir qué se muestra"><Stack size={16} /></BotonIcono>
                    </div>
                )}

                {/* El bot de dudas, abajo a la derecha */}
                {!esProfe && (
                    <button title="¿Tienes una duda?" style={{
                        position: 'absolute', bottom: 10, right: 12, display: 'flex',
                        padding: 7, background: 'var(--bg-surface)',
                        border: '1px solid var(--border-default)', borderRadius: 'var(--radius-full)',
                        color: 'var(--color-jade-400)', cursor: 'pointer',
                    }}>
                        <Question size={16} weight="fill" />
                    </button>
                )}
            </div>

            {/* La rejilla — solo la ve la profe */}
            {esProfe && (
                <div style={{ borderTop: '1px solid var(--border-subtle)', padding: 'var(--space-3)' }}>
                    <div style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        marginBottom: 8, flexWrap: 'wrap',
                    }}>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                            {visibles.length} de {personas.length}
                        </span>
                        <button
                            onClick={() => setSoloLosQueNecesitan(v => !v)}
                            style={{
                                marginLeft: 'auto', padding: '4px 11px',
                                background: soloLosQueNecesitan ? 'rgba(220,38,38,0.14)' : 'transparent',
                                border: `1px solid ${soloLosQueNecesitan ? 'var(--color-error)' : 'var(--border-subtle)'}`,
                                borderRadius: 'var(--radius-full)',
                                color: soloLosQueNecesitan ? 'var(--color-error)' : 'var(--text-muted)',
                                fontFamily: 'var(--font-sans)', fontSize: 'var(--text-xs)',
                                fontWeight: soloLosQueNecesitan ? 700 : 400, cursor: 'pointer',
                            }}
                        >
                            Solo los que me necesitan
                        </button>
                    </div>

                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(88px, 1fr))',
                        gap: 6, maxHeight: 168, overflowY: 'auto',
                    }}>
                        {visibles.map(p => (
                            <MiniPizarron key={p.id} persona={p} onClick={() => setAbierta(p)} />
                        ))}
                        {visibles.length === 0 && (
                            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-success)', gridColumn: '1/-1' }}>
                                ✓ Todas están trabajando.
                            </p>
                        )}
                    </div>
                </div>
            )}
        </section>
    )
}

/**
 * La miniatura del pizarrón de una alumna.
 *
 * DECISIÓN (Paola, 25 ago 2026): muestra **estado, no detalle**. Cuando la
 * profe barre la rejilla no necesita ver el modelo de cada quien — necesita ver
 * quién va bien, quién no ha tocado nada y quién se atoró. El modelo completo
 * se abre al picarle.
 *
 * Es lo que hace que 30 o 40 personas se sigan viendo. Con miniaturas-imagen el
 * techo eran unas 14.
 */
function MiniPizarron({ persona, onClick }) {
    const { nombre, interactuando, avance = 0, manoArriba, insignias = [] } = persona
    const necesitaAyuda = !interactuando || manoArriba

    return (
        <button
            onClick={onClick}
            title={`Abrir el pizarrón de ${nombre}`}
            style={{
                display: 'flex', flexDirection: 'column', gap: 4,
                padding: '7px 8px', textAlign: 'left',
                background: 'var(--bg-surface)',
                border: `1px solid ${necesitaAyuda ? 'var(--color-error)' : 'var(--border-subtle)'}`,
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer', fontFamily: 'var(--font-sans)',
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, width: '100%' }}>
                <Semaforo activo={interactuando} />
                <span style={{
                    fontSize: 10, color: 'var(--text-secondary)', flex: 1,
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                    {nombre.split(' ')[0]}
                </span>
                {manoArriba && <span style={{ fontSize: 11 }}>✋</span>}
            </div>

            {/* Qué tan avanzada va — una barra basta, un número sería ruido */}
            <div style={{
                height: 4, width: '100%', borderRadius: 2,
                background: 'var(--border-subtle)', overflow: 'hidden',
            }}>
                <div style={{
                    height: '100%', width: `${Math.min(100, Math.max(0, avance))}%`,
                    background: interactuando ? 'var(--color-jade-400)' : 'var(--color-error)',
                }} />
            </div>

            {insignias.length > 0 && (
                <div style={{ display: 'flex', gap: 1, fontSize: 10 }}>
                    {insignias.slice(0, 4).map((s, i) => {
                        const sello = SELLOS.find(x => x.id === s)
                        return <span key={i}>{sello?.emoji ?? '⭐'}</span>
                    })}
                </div>
            )}
        </button>
    )
}

/* ══════════════════════════════════════════════════════════════════════════
   El chat
   ══════════════════════════════════════════════════════════════════════════ */

/**
 * Chat de la clase. **No guarda historial visible** — es para compartir un dato
 * suelto, no para una conversación paralela que compita con la clase.
 *
 * Ocupa el ancho de la ventana de video y empuja lo demás, como pidió Paola.
 */
function Chat({ onCerrar }) {
    const [mensajes, setMensajes] = useState([])
    const [texto, setTexto] = useState('')
    const finRef = useRef(null)

    useEffect(() => { finRef.current?.scrollIntoView({ block: 'nearest' }) }, [mensajes])

    const enviar = (e) => {
        e.preventDefault()
        const t = texto.trim()
        if (!t) return
        setMensajes(m => [...m, { id: m.length, de: 'Tú', texto: t }])
        setTexto('')
    }

    return (
        <div style={{
            display: 'flex', flexDirection: 'column', height: 150, flex: 'none',
            background: 'var(--bg-card)', border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-lg)', overflow: 'hidden',
        }}>
            <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '7px var(--space-3)', borderBottom: '1px solid var(--border-subtle)',
            }}>
                <ChatCircleDots size={14} color="var(--color-jade-400)" />
                <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>Chat de la clase</span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>· no se guarda</span>
                <button onClick={onCerrar} style={{
                    marginLeft: 'auto', display: 'flex', background: 'transparent',
                    border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 2,
                }}><X size={13} /></button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-3)', fontSize: 'var(--text-xs)' }}>
                {mensajes.length === 0 && (
                    <p style={{ color: 'var(--text-muted)', margin: 0 }}>
                        Por si necesitas compartir algo con el grupo.
                    </p>
                )}
                {mensajes.map(m => (
                    <p key={m.id} style={{ margin: '0 0 4px', color: 'var(--text-secondary)' }}>
                        <strong style={{ color: 'var(--color-jade-400)' }}>{m.de}: </strong>{m.texto}
                    </p>
                ))}
                <div ref={finRef} />
            </div>

            <form onSubmit={enviar} style={{ display: 'flex', gap: 6, padding: 'var(--space-2) var(--space-3)', borderTop: '1px solid var(--border-subtle)' }}>
                <input
                    value={texto}
                    onChange={e => setTexto(e.target.value)}
                    placeholder="Escribe algo…"
                    style={{
                        flex: 1, padding: '6px 10px', background: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-full)',
                        color: 'var(--text-primary)', fontFamily: 'var(--font-sans)',
                        fontSize: 'var(--text-xs)', outline: 'none',
                    }}
                />
            </form>
        </div>
    )
}

/* ══════════════════════════════════════════════════════════════════════════
   El aula completa
   ══════════════════════════════════════════════════════════════════════════ */

export default function Aula({ sesion }) {
    const [chatAbierto, setChatAbierto] = useState(false)
    const s = { ...sesion, marca: sesion.marca ?? MARCA_DESTELLO }

    return (
        <div style={{
            display: 'flex', flexDirection: 'column',
            height: '100dvh', background: 'var(--bg-dark)',
        }}>
            <BarraSuperior sesion={s} />

            <main style={{
                flex: 1, minHeight: 0, display: 'grid', gap: 'var(--space-3)',
                padding: 'var(--space-3)',
                gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
            }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', minHeight: 0 }}>
                    <VentanaVideo
                        sesion={s}
                        chatAbierto={chatAbierto}
                        onAbrirChat={() => setChatAbierto(v => !v)}
                    />
                    {/* El chat empuja hacia arriba en lugar de taparlo todo */}
                    {chatAbierto && <Chat onCerrar={() => setChatAbierto(false)} />}
                </div>

                <VentanaPizarron sesion={s} />
            </main>

            {/* En celular las dos ventanas se apilan y la pantalla hace scroll:
                una al lado de la otra en pantalla chica dejaría las dos
                inservibles.
                ⚠️ PENDIENTE: en celular las ventanas quedan del tamaño de su
                contenido y sobra hueco abajo. Se intentó forzarles altura
                mínima y salió peor (el contenido se descuadraba dentro). El
                celular necesita su propio diseño, no un ajuste: probablemente
                pestañas para alternar entre video y pizarrón, en vez de
                apilarlos. No es urgente — una clase de 4 h con modelos 3D no se
                toma en el teléfono. */}
            <style>{`
                @media (max-width: 860px) {
                    main {
                        grid-template-columns: 1fr !important;
                        overflow-y: auto;
                        align-content: start;
                    }
                }
            `}</style>
        </div>
    )
}
