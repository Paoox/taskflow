/**
 * Destello API — Admin Routes
 *
 * POST   /admin/login              → pública — emite adminToken
 * POST   /admin/chispas            → genera una chispa (admin)
 * POST   /admin/chispas/batch      → genera N chispas (admin)
 * GET    /admin/chispas            → lista todas (admin)
 * GET    /admin/chispas/stats      → estadísticas (admin)
 * DELETE /admin/chispas/:code      → revoca (admin)
 *
 * GET    /admin/talleres/stats     → conteos lista de espera por taller (admin)
 * GET    /admin/talleres           → lista todos (admin)
 * POST   /admin/talleres           → crea taller nuevo (admin)
 * PUT    /admin/talleres/:id       → actualiza taller (admin)
 *
 * GET    /admin/lista-espera       → lista de espera completa (admin)
 * PATCH  /admin/lista-espera/:id   → actualiza estado (admin)
 *
 * POST   /admin/send-wa            → envía WA desde el bot (admin)
 *
 * GET    /admin/usuarios                  → lista con estado de bloqueo (admin)
 * GET    /admin/usuarios/:email/historial → bitácora de bloqueos (admin)
 * PATCH  /admin/usuarios/:email/bloqueo   → bloquea/desbloquea acceso o compras
 */
import { Router }            from 'express'
import { adminLogin, getTalleresStats } from '../controllers/adminController.js'
import { authenticateAdmin } from '../middleware/authenticateAdmin.js'
import * as chispaCtrl       from '../controllers/chispasController.js'
import { crearTaller, actualizarTaller, getTallerById } from '../services/tallerService.js'
import { AppError }          from '../middleware/errorHandler.js'
import { query }             from '../db/db.js'
import { sendConfirmacionTaller, sendConfirmacionLugar, sendResplandor, sendBienvenida } from '../services/mailService.js'
import { sendWhatsapp }      from '../services/botService.js'
import { cuentaConWhatsapp, normalizarWhatsapp } from '../services/usuarioService.js'
import { listReportes, resolverReporte } from '../services/reporteService.js'
import { activarAlumno }    from '../services/inscripcionService.js'
import metricasRouter     from './metricas.js'
import * as asistenciaService  from '../services/asistenciaService.js'
import * as certificadoService from '../services/certificadoService.js'
import * as bloqueoService      from '../services/bloqueoService.js'
import { sincronizarEstadoCupo } from '../services/cupoService.js'
import crypto                from 'node:crypto'

const router = Router()

// ── Pública ───────────────────────────────────────────────
router.post('/login', adminLogin)

// ── Protegidas con adminToken ─────────────────────────────
router.use(authenticateAdmin)

// Métricas del dashboard (va después de authenticateAdmin: son datos del negocio)
router.use('/metricas', metricasRouter)

// Chispas
router.post('/chispas',         chispaCtrl.generateChispa)
router.post('/chispas/batch',   chispaCtrl.generateBatch)
router.get('/chispas',          chispaCtrl.listChispas)
router.get('/chispas/stats',    chispaCtrl.getStats)
router.delete('/chispas/:code', chispaCtrl.revokeChispa)

// Talleres — stats ANTES de /:id para evitar conflicto de rutas
router.get('/talleres/stats', getTalleresStats)

router.get('/talleres', async (_req, res, next) => {
    try {
        // Incluye "inscritos" = chispas emitidas (no revocadas) por taller.
        // Sirve para el control de cupo (máx 20) y evitar reventa.
        const { rows } = await query(
            `SELECT t.*, COALESCE(ch.inscritos, 0)::int AS inscritos
             FROM talleres t
             LEFT JOIN (
                 SELECT taller_id, COUNT(*) AS inscritos
                 FROM chispas
                 WHERE revoked = FALSE
                 GROUP BY taller_id
             ) ch ON ch.taller_id = t.id
             ORDER BY t.created_at DESC`
        )
        res.json({ status: 'ok', talleres: rows })
    } catch (err) { next(err) }
})

router.post('/talleres', async (req, res, next) => {
    try {
        const { nombre } = req.body
        if (!nombre) throw new AppError('nombre es requerido', 400, 'BAD_REQUEST')
        const taller = await crearTaller(req.body)
        res.status(201).json({ status: 'ok', taller })
    } catch (err) { next(err) }
})

router.put('/talleres/:id', async (req, res, next) => {
    try {
        const taller = await actualizarTaller(req.params.id, req.body)
        if (!taller) throw new AppError('Taller no encontrado', 404, 'NOT_FOUND')

        // Subir o bajar el cupo cambia si el taller está lleno, y la etiqueta
        // tiene que enterarse EN ESE MOMENTO.
        //
        // EL BUG (25 ago 2026): sin esto, subir el cupo de 20 a 23 para meter a
        // alguien de último momento dejaba el taller marcado como 'lleno'. El
        // Habitat seguía mostrando AGOTADO y el bot seguía diciendo que no hay
        // lugar — aunque la API sí lo hubiera aceptado, porque el candado real
        // lee la vista viva y no esa etiqueta. Resultado: tres lugares abiertos
        // que nadie podía ver.
        //
        // Va antes de responder para que el panel reciba ya el estado correcto
        // y no tenga que recargar para enterarse.
        const sync = await sincronizarEstadoCupo(req.params.id)
        if (sync) taller.estado = sync.estado

        res.json({ status: 'ok', taller })
    } catch (err) { next(err) }
})

// Lista de espera (admin)
router.get('/lista-espera', async (_req, res, next) => {
    try {
        const { rows } = await query(
            `SELECT le.*,
                    t.nombre       AS taller_nombre,
                    t.precio       AS taller_precio,
                    t.horario      AS taller_horario,
                    t.fecha_inicio AS taller_fecha,
                    t.descripcion  AS taller_descripcion,
                    EXISTS (
                        SELECT 1 FROM resplandores r
                        WHERE LOWER(r.email) = LOWER(le.email)
                          AND r.used = FALSE AND r.revoked = FALSE
                    ) AS tiene_resplandor,
                    -- Cuándo se le apartó el lugar. La tabla no lo guarda, pero
                    -- la chispa ES la reserva: su fecha de creación es el momento
                    -- exacto en que se apartó. De aquí sale el reloj de 48 h.
                    ch.created_at AS apartado_at,
                    -- Una cortesía ocupa lugar igual que un pago, así que vive
                    -- en esta misma lista. El panel la distingue con la etiqueta
                    -- 🎁 demo y le muestra el reloj de VIGENCIA en vez del de pago
                    -- (no hay nada que cobrar, pero sí cuándo se le acaba).
                    COALESCE(ch.is_demo, FALSE) AS is_demo,
                    ch.expires_at AS chispa_expira_at
             FROM lista_espera le
                      LEFT JOIN talleres t ON t.id = le.taller_id
                      LEFT JOIN LATERAL (
                          SELECT c.created_at, c.is_demo, c.expires_at
                          FROM chispas c
                          WHERE LOWER(c.usuario_email) = LOWER(le.email)
                            AND c.taller_id = le.taller_id
                            AND c.revoked = FALSE
                          ORDER BY c.created_at DESC
                          LIMIT 1
                      ) ch ON TRUE
             ORDER BY le.created_at DESC`
        )
        res.json({ status: 'ok', lista: rows })
    } catch (err) { next(err) }
})

/**
 * PATCH /admin/lista-espera/:id
 * Cambia el estado desde el selector del panel.
 *
 * ⚠️ Marcar 'pagado' DEBE activar también al usuario. Si solo se cambiara el
 * estado de la lista, la persona quedaría pagada pero con `usuarios.estado =
 * 'espera'`, y el login por número la rechazaría (phoneAuthController exige
 * 'activo'). Este era un desfase real: el selector y el botón "confirmar pago"
 * hacían cosas distintas.
 *
 * ── Cómo se resolvió (22 ago 2026) ──────────────────────────────────────────
 * Ya no se parcha aquí: cuando el estado nuevo es 'pagado' se delega en
 * `activarAlumno()`, EL MISMO servicio que usa el botón "Confirmar pago". Un
 * solo lugar decide qué significa que un alumno esté adentro, y todo pasa en
 * una transacción.
 *
 * Diferencia deliberada con el botón: aquí NO se manda correo ni WhatsApp.
 * Mover un selector no debería dispararle mensajes a nadie. Los datos quedan
 * idénticos; avisar es una acción aparte y explícita. Por eso la respuesta
 * incluye `notificado: false`, para que el panel lo diga en pantalla.
 */
router.patch('/lista-espera/:id', async (req, res, next) => {
    try {
        const { estado } = req.body
        if (!estado) throw new AppError('estado es requerido', 400, 'BAD_REQUEST')

        if (estado === 'pagado') {
            const r = await activarAlumno(req.params.id, {
                actor: 'admin:selector',
                pago:  { nota: 'Marcado como pagado desde el selector del panel' },
            })
            return res.json({
                status:          'ok',
                registro:        r.registro,
                usuarioActivado: true,
                chispa:          r.chispaCode,
                notificado:      false,
                ...(r.avisoWa && { avisoWa: r.avisoWa }),
            })
        }

        const { rows } = await query(
            `UPDATE lista_espera SET estado = $2 WHERE id = $1 RETURNING *`,
            [req.params.id, estado]
        )
        if (!rows.length) throw new AppError('Registro no encontrado', 404, 'NOT_FOUND')

        res.json({ status: 'ok', registro: rows[0], usuarioActivado: false })
    } catch (err) { next(err) }
})

/**
 * POST /admin/lista-espera/:id/confirmar-lugar
 * Confirma el lugar → cambia estado a 'confirmado' y envía correo con
 * detalles del taller + métodos de pago (sin chispa aún).
 */
router.post('/lista-espera/:id/confirmar-lugar', async (req, res, next) => {
    try {
        // Obtener el registro con info del taller
        const { rows } = await query(
            `SELECT le.*, t.nombre AS taller_nombre, t.descripcion AS taller_descripcion,
                    t.fecha_inicio AS taller_fecha, t.horario AS taller_horario,
                    t.precio AS taller_precio
             FROM lista_espera le
                      LEFT JOIN talleres t ON t.id = le.taller_id
             WHERE le.id = $1`,
            [req.params.id]
        )
        if (!rows.length) throw new AppError('Registro no encontrado', 404, 'NOT_FOUND')
        const reg = rows[0]

        // Actualizar estado a confirmado
        await query(
            `UPDATE lista_espera SET estado = 'cupo_confirmado' WHERE id = $1`,
            [req.params.id]
        )

        // Enviar correo de confirmación de lugar (sin chispa)
        const taller = {
            nombre:           reg.taller_nombre      ?? reg.taller_id,
            descripcion:      reg.taller_descripcion ?? null,
            fecha_disponible: reg.taller_fecha       ?? null,
            horario:          reg.taller_horario     ?? null,
            precio:           reg.taller_precio      ?? 0,
        }

        let enviado = false
        try {
            await sendConfirmacionLugar({ to: reg.email, nombre: reg.nombre ?? '', taller })
            enviado = true
        } catch (mailErr) {
            console.error('[mail] Error al enviar confirmación de lugar:', mailErr.message)
        }

        res.json({ status: 'ok', mensaje: 'Lugar confirmado', enviado })
    } catch (err) { next(err) }
})

/**
 * POST /admin/lista-espera/:id/confirmar
 * Genera resplandor o chispa y envía el código por correo.
 * Body: { tipo: 'resplandor' | 'chispa', expiresInDays?: number }
 */
router.post('/lista-espera/:id/confirmar', async (req, res, next) => {
    try {
        const { tipo = 'resplandor', expiresInDays = 30 } = req.body

        // Obtener el registro con info del taller
        const { rows } = await query(
            `SELECT le.*, t.nombre AS taller_nombre, t.descripcion AS taller_descripcion,
                    t.fecha_inicio AS taller_fecha, t.horario AS taller_horario,
                    t.precio AS taller_precio
             FROM lista_espera le
                      LEFT JOIN talleres t ON t.id = le.taller_id
             WHERE le.id = $1`,
            [req.params.id]
        )
        if (!rows.length) throw new AppError('Registro no encontrado', 404, 'NOT_FOUND')
        const reg = rows[0]

        const taller = {
            id:               reg.taller_id,
            nombre:           reg.taller_nombre      ?? reg.taller_id,
            descripcion:      reg.taller_descripcion ?? null,
            fecha_disponible: reg.taller_fecha       ?? null,
            horario:          reg.taller_horario     ?? null,
            precio:           reg.taller_precio      ?? 0,
        }

        const seg = () => crypto.randomBytes(3).toString('hex').toUpperCase().slice(0, 4)

        if (tipo === 'chispa') {
            // Generar chispa
            const code      = `DEST-${seg()}-${seg()}`
            const expiresAt = expiresInDays
                ? new Date(Date.now() + expiresInDays * 86400000)
                : null

            await query(
                `INSERT INTO chispas
                    (code, taller_id, expires_at, usuario_nombre, usuario_email, usuario_wa)
                 VALUES ($1, $2, $3, $4, $5, $6)`,
                [code, reg.taller_id, expiresAt, reg.nombre, reg.email, reg.whatsapp]
            )

            // Enviar correo con chispa
            try {
                await sendConfirmacionTaller({ to: reg.email, nombre: reg.nombre ?? '', taller, chispaCode: code })
            } catch (mailErr) {
                console.error('[mail] Error al enviar chispa:', mailErr.message)
            }

            return res.status(201).json({ status: 'ok', chispa: { code } })
        }

        // Generar resplandor
        const { rows: existentes } = await query(
            `SELECT * FROM resplandores WHERE email = $1 AND revoked = FALSE AND used = FALSE`,
            [reg.email]
        )
        if (existentes.length > 0) {
            throw new AppError('El usuario ya tiene un resplandor activo.', 409, 'CONFLICT')
        }

        const code = `RES-${seg()}-${seg()}`
        await query(
            `INSERT INTO resplandores (code, email, created_at) VALUES ($1, $2, NOW())`,
            [code, reg.email]
        )

        // Enviar correo con resplandor
        try {
            await sendResplandor({ to: reg.email, nombre: reg.nombre ?? '', code })
        } catch (mailErr) {
            console.error('[mail] Error al enviar resplandor:', mailErr.message)
        }

        res.status(201).json({ status: 'ok', resplandor: { code } })
    } catch (err) { next(err) }
})

/**
 * POST /admin/lista-espera/:id/confirmar-pago
 *
 * Confirma el pago de un alumno. Delega TODO el trabajo de datos en
 * `activarAlumno()` — el mismo servicio que usa el selector del panel — y aquí
 * solo se encarga de avisarle a la persona.
 *
 * Antes esta ruta hacía las seis operaciones a mano y sin transacción; si
 * fallaba a la mitad quedaba el desfase "pagado sin activar" que el bot detecta.
 *
 * Body (todo opcional): { monto, metodo, banco, titular, folio, nota }
 *   · monto ausente  → se toma el precio del taller
 *   · metodo ausente → 'transferencia'
 * Sirve para dejar registrado en la tabla `pagos` cuánto entró y por qué se
 * aceptó, no solo que se aceptó.
 *
 * El alumno nunca captura códigos: al entrar con Google o su número, el taller
 * ya está en su dashboard.
 */
router.post('/lista-espera/:id/confirmar-pago', async (req, res, next) => {
    try {
        const { monto, metodo, banco, titular, folio, nota } = req.body ?? {}

        const r = await activarAlumno(req.params.id, {
            actor: 'admin',
            pago:  { monto, metodo, banco, titular, folio, nota },
        })

        const { usuario, registro, chispaCode, avisoWa, waDestino } = r

        // Los avisos van FUERA de la transacción a propósito: que el correo o el
        // bot estén caídos no debe deshacer una activación que ya quedó bien.
        let mailEnviado = false
        let waEnviado   = false

        try {
            await sendBienvenida({ to: usuario.email, nombre: usuario.nombre ?? registro.nombre ?? '' })
            mailEnviado = true
        } catch (e) { console.error('[bienvenida mail]', e.message) }

        if (waDestino) {
            try {
                const primerNombre = (usuario.nombre ?? registro.nombre ?? '').split(' ')[0]
                // NO se habla de "crear cuenta": la cuenta ya existe desde que el
                // bot tomó sus datos. Aquí solo se le dice que ya puede entrar.
                const msg =
                    `✦ *Destello*\n\n` +
                    `¡Hola ${primerNombre}! Tu pago quedó *confirmado* y tu lugar está apartado. 🎉\n\n` +
                    `Ya puedes entrar aquí:\n` +
                    `https://destello.courses/login\n\n` +
                    `Entra con Google o con tu número. ¡Nos vemos dentro! 🌟`
                await sendWhatsapp(waDestino, msg)
                waEnviado = true
            } catch (e) { console.error('[bienvenida wa]', e.message) }
        }

        res.json({
            status:      'ok',
            usuario:     { id: usuario.id, email: usuario.email, whatsapp: usuario.whatsapp },
            chispa:      chispaCode,
            pagoId:      r.pagoId,
            mailEnviado,
            waEnviado,
            notificado:  mailEnviado || waEnviado,
            ...(avisoWa && { avisoWa }),
        })
    } catch (err) { next(err) }
})

router.get('/resplandores/all', async (_req, res, next) => {
    try {
        const { rows } = await query(
            `SELECT r.*, u.nombre AS usuario_nombre, u.whatsapp AS usuario_whatsapp
             FROM resplandores r
             LEFT JOIN usuarios u ON u.email = r.email
             ORDER BY r.created_at DESC`
        )
        res.json({ status: 'ok', resplandores: rows })
    } catch (err) { next(err) }
})

// ── Resplandores (admin) ──────────────────────────────────


/**
 * GET /admin/resplandores?email=xxx
 * Lista los resplandores de un usuario por correo.
 */
router.get('/resplandores', async (req, res, next) => {
    try {
        const { email } = req.query
        if (!email) throw new AppError('email es requerido', 400, 'BAD_REQUEST')

        const { rows: users } = await query(
            `SELECT id, email, nombre, whatsapp, estado FROM usuarios WHERE email = $1`,
            [email.toLowerCase().trim()]
        )
        const usuario = users[0] ?? null

        const { rows: resplandores } = await query(
            `SELECT * FROM resplandores WHERE email = $1 ORDER BY created_at DESC`,
            [email.toLowerCase().trim()]
        )

        res.json({ status: 'ok', usuario, resplandores })
    } catch (err) { next(err) }
})

/**
 * POST /admin/resplandores
 * Crea un nuevo resplandor para el usuario (email debe existir).
 * Solo permite crear si no tiene uno activo/expirado sin revocar.
 * Body: { email }
 */
router.post('/resplandores', async (req, res, next) => {
    try {
        const { email } = req.body
        if (!email) throw new AppError('email es requerido', 400, 'BAD_REQUEST')
        const emailNorm = email.toLowerCase().trim()

        // Verificar si ya tiene un resplandor activo o expirado (no revocado, no usado)
        const { rows: existentes } = await query(
            `SELECT * FROM resplandores
             WHERE email = $1 AND revoked = FALSE AND used = FALSE`,
            [emailNorm]
        )
        if (existentes.length > 0) {
            throw new AppError(
                'El usuario ya tiene un resplandor activo. Revócalo primero para crear uno nuevo.',
                409, 'CONFLICT'
            )
        }

        // Generar código: RES-XXXX-XXXX
        const seg  = () => crypto.randomBytes(3).toString('hex').toUpperCase().slice(0, 4)
        const code = `RES-${seg()}-${seg()}`

        // Buscar datos del usuario para el correo
        const { rows: users } = await query(
            `SELECT nombre FROM usuarios WHERE email = $1`,
            [emailNorm]
        )
        const nombre = users[0]?.nombre ?? ''

        // Guardar resplandor
        const { rows } = await query(
            `INSERT INTO resplandores (code, email, created_at)
             VALUES ($1, $2, NOW())
             RETURNING *`,
            [code, emailNorm]
        )
        const resplandor = rows[0]

        // Enviar correo automáticamente
        try {
            await sendResplandor({ to: emailNorm, nombre, code })
            resplandor.enviado = true
        } catch { resplandor.enviado = false }

        res.status(201).json({ status: 'ok', code, resplandor })
    } catch (err) { next(err) }
})

/**
 * POST /admin/resplandores/:code/reenviar
 * Reenvía un resplandor existente al correo del usuario.
 */
router.post('/resplandores/:code/reenviar', async (req, res, next) => {
    try {
        const { rows } = await query(
            `SELECT r.*,
                    COALESCE(u.nombre, le.nombre) AS nombre
             FROM resplandores r
             LEFT JOIN usuarios    u  ON u.email  = r.email
             LEFT JOIN lista_espera le ON le.email = r.email
             WHERE r.code = $1
             LIMIT 1`,
            [req.params.code]
        )
        if (!rows.length) throw new AppError('Resplandor no encontrado', 404, 'NOT_FOUND')
        const r = rows[0]

        await sendResplandor({ to: r.email, nombre: r.nombre ?? '', code: r.code })
        res.json({ status: 'ok', message: `Resplandor reenviado a ${r.email}` })
    } catch (err) { next(err) }
})

/**
 * DELETE /admin/resplandores/:code
 * Revoca un resplandor. Queda en historial pero no puede usarse.
 * Al revocar, el admin puede crear uno nuevo.
 */
router.delete('/resplandores/:code', async (req, res, next) => {
    try {
        const { rows } = await query(
            `UPDATE resplandores SET revoked = TRUE WHERE code = $1 RETURNING *`,
            [req.params.code]
        )
        if (!rows.length) throw new AppError('Resplandor no encontrado', 404, 'NOT_FOUND')
        res.json({ status: 'ok', message: `Resplandor ${req.params.code} revocado` })
    } catch (err) { next(err) }
})

// ── Correos (admin) ────────────────────────────────────────

/**
 * POST /admin/mail/confirmacion-taller
 * Envía el correo de confirmación de taller con la chispa.
 * Body: { to, nombre, tallerId, chispaCode }
 */
router.post('/mail/confirmacion-taller', async (req, res, next) => {
    try {
        const { to, nombre, tallerId, chispaCode } = req.body
        if (!to || !tallerId || !chispaCode) {
            throw new AppError('to, tallerId y chispaCode son requeridos', 400, 'BAD_REQUEST')
        }
        const taller = await getTallerById(tallerId)
        if (!taller) throw new AppError('Taller no encontrado', 404, 'NOT_FOUND')

        await sendConfirmacionTaller({ to, nombre: nombre || '', taller, chispaCode })
        res.json({ status: 'ok', message: `Correo enviado a ${to}` })
    } catch (err) { next(err) }
})

/**
 * POST /admin/mail/resplandor
 * Envía un resplandor (código de acceso para crear cuenta) por correo.
 * Body: { to, nombre, code }
 */
router.post('/mail/resplandor', async (req, res, next) => {
    try {
        const { to, nombre, code } = req.body
        if (!to || !code) throw new AppError('to y code son requeridos', 400, 'BAD_REQUEST')

        await sendResplandor({ to, nombre: nombre || '', code })
        res.json({ status: 'ok', message: `Resplandor enviado a ${to}` })
    } catch (err) { next(err) }
})

// ── WhatsApp desde el bot ──────────────────────────────────

/**
 * POST /admin/send-wa
 * Envía un mensaje de WhatsApp desde el número del bot (Baileys).
 * Body: { numero, mensaje }
 *   numero:  10 dígitos locales MX (ej: 5577888800)
 *   mensaje: texto a enviar (soporta formato WA con *bold*, etc.)
 *
 * Requiere que el bot esté corriendo y BOT_HTTP_URL esté configurado.
 * Por defecto apunta a http://127.0.0.1:4001 (bot en la misma máquina).
 */
router.post('/send-wa', async (req, res, next) => {
    try {
        const { numero, mensaje } = req.body

        if (!numero || !mensaje) {
            throw new AppError('numero y mensaje son requeridos', 400, 'BAD_REQUEST')
        }

        // Normalizar a 10 dígitos
        const numeroLimpio = String(numero).replace(/\D/g, '').slice(-10)
        if (numeroLimpio.length !== 10) {
            throw new AppError('El número debe tener 10 dígitos (ej: 5577888800)', 400, 'BAD_REQUEST')
        }

        // Formato JID de WhatsApp para México: 521XXXXXXXXXX@s.whatsapp.net
        // Los números móviles MX en WhatsApp llevan el "1" después del código de país
        const jid    = `521${numeroLimpio}@s.whatsapp.net`
        const botUrl = process.env.BOT_HTTP_URL || 'http://127.0.0.1:4001'

        const botRes = await fetch(`${botUrl}/send`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ jid, mensaje }),
        })

        if (!botRes.ok) {
            const errData = await botRes.json().catch(() => ({ error: 'Error desconocido del bot' }))
            throw new AppError(
                errData.error || 'No se pudo enviar el mensaje por WhatsApp',
                502,
                'BOT_ERROR',
            )
        }

        res.json({ status: 'ok', message: `Mensaje enviado a ${numeroLimpio}` })
    } catch (err) { next(err) }
})

/**
 * POST /admin/lista-espera/:id/recordatorio
 *
 * Deja constancia de que ya se le mandó un recordatorio de pago. Se llama
 * DESPUÉS de que el mensaje salió bien — si el envío falla, no se estampa.
 *
 * Es lo que arranca las 24 h de gracia. Sin este dato el panel no puede
 * distinguir a quien nunca supo que tenía que pagar de quien ya no contestó,
 * y ofrecería liberar el lugar de los dos por igual.
 */
router.post('/lista-espera/:id/recordatorio', async (req, res, next) => {
    try {
        const { rows } = await query(
            `UPDATE lista_espera
                SET recordatorio_at = NOW(),
                    recordatorios   = COALESCE(recordatorios, 0) + 1
              WHERE id = $1
            RETURNING id, email, taller_id, recordatorio_at, recordatorios`,
            [req.params.id]
        )
        if (!rows.length) throw new AppError('Registro no encontrado', 404, 'NOT_FOUND')

        res.json({ status: 'ok', registro: rows[0] })
    } catch (err) { next(err) }
})

/**
 * POST /admin/lista-espera/:id/liberar
 *
 * Libera el lugar de quien no pagó dentro del plazo.
 *
 * ⚠️ Hace DOS cosas, y la segunda es la que importa: además de marcar el
 * registro como 'rechazado', REVOCA la chispa. Si solo se cambiara el estado, la
 * persona conservaría su llave y podría seguir entrando al taller que nunca pagó
 * — el lugar quedaría "liberado" solo en la tabla, no en la realidad.
 *
 * Es manual a propósito: alguien puede pagar el domingo y avisar el lunes, y no
 * queremos que un cron le quite el lugar de madrugada.
 */
router.post('/lista-espera/:id/liberar', async (req, res, next) => {
    try {
        const { rows } = await query(
            `UPDATE lista_espera SET estado = 'rechazado' WHERE id = $1 RETURNING *`,
            [req.params.id]
        )
        if (!rows.length) throw new AppError('Registro no encontrado', 404, 'NOT_FOUND')
        const reg = rows[0]

        const { rows: revocadas } = await query(
            `UPDATE chispas
             SET revoked = TRUE
             WHERE LOWER(usuario_email) = LOWER($1)
               AND taller_id = $2
               AND revoked = FALSE
             RETURNING code`,
            [reg.email, reg.taller_id]
        )

        console.log(`[liberar] ${reg.email} · ${reg.taller_id} · ${revocadas.length} chispa(s) revocada(s)`)

        res.json({
            status:    'ok',
            registro:  reg,
            revocadas: revocadas.map(c => c.code),
        })
    } catch (err) { next(err) }
})

/**
 * GET /admin/reportes?abiertos=1
 * Bandeja de reportes: pagos que hay que cotejar y problemas de acceso.
 *
 * Sin esto los reportes solo llegaban por WhatsApp, así que un mensaje perdido
 * entre conversaciones era un pago perdido. Aquí quedan revisables.
 */
router.get('/reportes', async (req, res, next) => {
    try {
        const reportes = await listReportes({ soloAbiertos: req.query.abiertos === '1' })
        res.json({ status: 'ok', reportes })
    } catch (err) { next(err) }
})

/**
 * PATCH /admin/reportes/:id/resolver
 * Marca un reporte como atendido. `nota` guarda qué se hizo (opcional).
 */
router.patch('/reportes/:id/resolver', async (req, res, next) => {
    try {
        const reporte = await resolverReporte(req.params.id, req.body?.nota || null)
        if (!reporte) throw new AppError('Reporte no encontrado', 404, 'NOT_FOUND')
        res.json({ status: 'ok', reporte })
    } catch (err) { next(err) }
})


// ══════════════════════════════════════════════════════════════════════════
//  Asistencia y certificados
// ══════════════════════════════════════════════════════════════════════════
//
// Regla de Paola: certifica quien asistió, no quien pagó. La emisión es
// automática por asistencia, pero SIEMPRE corregible a mano — a alguien se le
// va el internet y eso no puede costarle el certificado.

/**
 * GET /admin/talleres/:id/asistencia
 * Quién entró al aula, cuánto tiempo estuvo, y si ya tiene certificado.
 */
router.get('/talleres/:id/asistencia', async (req, res, next) => {
    try {
        const lista = await asistenciaService.asistenciaDeTaller(req.params.id)
        const min   = certificadoService.MINUTOS_PARA_CERTIFICAR
        res.json({
            status: 'ok',
            asistencia: lista,
            // El umbral viaja con la lista para que el panel pueda marcar quién
            // califica sin repetir el número por su cuenta.
            minMinutos: min,
            resumen: {
                inscritos:    lista.length,
                entraron:     lista.filter(p => p.entro).length,
                califican:    lista.filter(p => Number(p.minutos) >= min).length,
                certificados: lista.filter(p => p.tiene_certificado).length,
            },
        })
    } catch (err) { next(err) }
})

/**
 * POST /admin/talleres/:id/certificados
 * Body: { emails?: string[], motivo?, minMinutos? }
 *
 * Un solo botón para dos formas de emitir:
 *
 *   · **sin `emails`** → a todos los que califican por asistencia. Es el
 *     "emitir todos" de después de cada taller.
 *   · **con `emails`** → exactamente a ésos, ni uno más. Es el "emitir sólo
 *     éstos" de palomear renglones en el panel; a quien no llegó a los minutos
 *     se le registra la asistencia a mano con su motivo, porque escogerlo a
 *     mano ya fue la decisión pero tiene que quedar por escrito.
 *
 * En los dos casos se devuelve a quién NO se le emitió y por qué: una emisión
 * que deja gente fuera en silencio se lee como "ya está todo" cuando no lo está.
 */
router.post('/talleres/:id/certificados', async (req, res, next) => {
    try {
        const { emails, motivo, minMinutos } = req.body ?? {}
        const actor = req.admin?.email ?? 'admin'
        const min   = minMinutos != null ? Number(minMinutos) : undefined

        // `emails: []` (un arreglo vacío) NO es lo mismo que no mandar nada:
        // significa "no seleccionaste a nadie". Emitirle a todo el taller en
        // ese caso sería justo lo contrario de lo que se pidió.
        if (Array.isArray(emails)) {
            if (emails.length === 0) {
                throw new AppError('No seleccionaste a nadie', 400, 'BAD_REQUEST')
            }
            const resultado = await certificadoService.emitirSeleccion(
                req.params.id, emails, { actor, motivo, minMinutos: min })
            return res.json({ status: 'ok', ...resultado })
        }

        const resultado = await certificadoService.emitirTaller(req.params.id, {
            minMinutos: min, actor,
        })
        res.json({ status: 'ok', ...resultado })
    } catch (err) { next(err) }
})

/**
 * POST /admin/certificados
 * Body: { email, tallerId, motivo? }
 * Emisión individual: el caso de "sí estuvo, pero el registro no lo alcanzó".
 */
router.post('/certificados', async (req, res, next) => {
    try {
        const { email, tallerId, motivo } = req.body ?? {}
        if (!email || !tallerId) {
            throw new AppError('email y tallerId son requeridos', 400, 'BAD_REQUEST')
        }
        // Se registra también la asistencia: si no, la lista diría "no entró"
        // junto a un certificado emitido, y eso no se entiende en tres meses.
        await asistenciaService.agregarManual(email, tallerId, {
            actor: req.admin?.email ?? 'admin',
            nota:  motivo || 'certificado emitido a mano',
        })
        const { certificado, nuevo } = await certificadoService.emitir(email, tallerId, {
            actor: req.admin?.email ?? 'admin',
        })
        res.json({ status: 'ok', certificado, nuevo })
    } catch (err) { next(err) }
})

/**
 * DELETE /admin/certificados/:folio
 * Body: { motivo }
 * No borra: anula. El folio ya pudo haber circulado, y uno sin respaldo es
 * peor que uno anulado con su explicación.
 */
router.delete('/certificados/:folio', async (req, res, next) => {
    try {
        const cert = await certificadoService.anular(req.params.folio, {
            motivo: req.body?.motivo,
            actor:  req.admin?.email ?? 'admin',
        })
        if (!cert) throw new AppError('Certificado no encontrado o ya anulado', 404, 'NOT_FOUND')
        res.json({ status: 'ok', certificado: cert })
    } catch (err) { next(err) }
})


// ══════════════════════════════════════════════════════════════════════════
//  Usuarios — bloquear sin borrar
// ══════════════════════════════════════════════════════════════════════════
//
// Dos interruptores por cuenta, los dos reversibles:
//   · acceso  → no entra a la plataforma, ni por la web ni por el bot
//   · compras → entra y usa lo que ya tiene, pero no aparta lugar en nada nuevo
//
// Aquí no hay ningún DELETE, a propósito. Borrar una cuenta se lleva por
// delante su historial, sus certificados y las métricas del negocio; y sobre
// todo, no se puede deshacer el día que resulte que el bloqueo estuvo mal.

/** GET /admin/usuarios?filtro=todos|bloqueados|activos&busca=texto */
router.get('/usuarios', async (req, res, next) => {
    try {
        const [usuarios, resumen] = await Promise.all([
            bloqueoService.listar({ filtro: req.query.filtro, busca: req.query.busca }),
            bloqueoService.stats(),
        ])
        res.json({ status: 'ok', usuarios, stats: resumen })
    } catch (err) { next(err) }
})

/** GET /admin/usuarios/:email/historial → cada bloqueo y desbloqueo, con motivo. */
router.get('/usuarios/:email/historial', async (req, res, next) => {
    try {
        res.json({
            status:    'ok',
            historial: await bloqueoService.historialDe(req.params.email),
        })
    } catch (err) { next(err) }
})

/**
 * PATCH /admin/usuarios/:email/bloqueo
 * Body: { tipo: 'acceso'|'compras', bloquear: true|false, motivo }
 *
 * El motivo es obligatorio al bloquear. Es lo único que va a existir dentro de
 * tres meses, cuando alguien reclame y haya que explicar por qué.
 */
router.patch('/usuarios/:email/bloqueo', async (req, res, next) => {
    try {
        const { tipo, bloquear, motivo } = req.body ?? {}
        const r = await bloqueoService.cambiar({
            email:    req.params.email,
            tipo,
            bloquear: bloquear === true,
            motivo,
            hechoPor: req.admin?.email ?? 'admin',
        })
        if (!r.ok) {
            const msg = {
                TIPO_INVALIDO:    'tipo debe ser "acceso" o "compras"',
                MOTIVO_REQUERIDO: 'Escribe el motivo del bloqueo',
                USER_NOT_FOUND:   'No encontramos esa cuenta',
            }[r.reason] ?? 'No se pudo aplicar el cambio'
            throw new AppError(msg, r.reason === 'USER_NOT_FOUND' ? 404 : 400, r.reason)
        }
        res.json({ status: 'ok', usuario: r.usuario })
    } catch (err) { next(err) }
})

export default router