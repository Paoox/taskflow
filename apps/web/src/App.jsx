/**
 * Destello — App Router
 * Define todas las rutas de la aplicación con lazy loading.
 * Cada página es un componente separado → código modular y reutilizable.
 *
 * Flujo: Intro → Login → Home → Habitat → Aula
 */
import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'

// Layouts
import MainLayout    from '@components/layout/MainLayout.jsx'
import AuthLayout    from '@components/layout/AuthLayout.jsx'

// Lazy-load de páginas → cada una es un chunk independiente
const PageIntro    = lazy(() => import('@pages/PageIntro.jsx'))
const PageLanding  = lazy(() => import('@pages/PageLanding.jsx'))
const PageAcceso   = lazy(() => import('@pages/PageAcceso.jsx'))
const PageLogin    = lazy(() => import('@pages/PageLogin.jsx'))
const PageHome     = lazy(() => import('@pages/PageHome.jsx'))
const PageHabitat  = lazy(() => import('@pages/PageHabitat.jsx'))
const PageAula     = lazy(() => import('@pages/PageAula.jsx'))
const PagePerfil   = lazy(() => import('@pages/PagePerfil.jsx'))
const Page404      = lazy(() => import('@pages/Page404.jsx'))
const PageAdmin    = lazy(() => import('@pages/PageAdmin.jsx'))
const PageCertificado = lazy(() => import('@pages/PageCertificado.jsx'))
const PageAulaNueva   = lazy(() => import('@pages/PageAulaNueva.jsx'))


// Loading fallback mientras carga la página
function PageLoader() {
    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            background: 'var(--bg-dark)',
        }}>
            <div style={{
                width: 40, height: 40,
                border: '3px solid var(--border-subtle)',
                borderTopColor: 'var(--color-jade-500)',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
            }} />
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    )
}

export default function App() {
    return (
        <Suspense fallback={<PageLoader />}>
            <Routes>

                {/* ── Rutas públicas (sin layout) ───────────────── */}
                <Route path="/intro"  element={<PageIntro />} />

                {/* ── Verificación pública de certificados ──────────
                    Es a donde lleva el QR impreso en el diploma. Va SIN layout
                    a propósito: quien la abre es quien recibió el certificado
                    (una escuela, un empleador), no tiene cuenta en Destello y
                    no debe ver la barra lateral de la plataforma ni que se le
                    pida entrar antes de responderle. */}
                <Route path="/certificado/:folio" element={<PageCertificado />} />

                {/* ── Rutas de auth ─────────────────────────────── */}
                <Route element={<AuthLayout />}>
                    <Route path="/acceso" element={<PageAcceso />} />
                    <Route path="/bienvenida" element={<PageLanding />} />
                    <Route path="/login" element={<PageLogin />} />
                </Route>

                {/* ── Rutas privadas (con sidebar/navbar) ───────── */}
                <Route element={<MainLayout />}>
                    <Route path="/home"          element={<PageHome />} />
                    <Route path="/habitat"       element={<PageHabitat />} />
                    <Route path="/aula/:id"      element={<PageAula />} />
                    <Route path="/perfil"        element={<PagePerfil />} />
                    {/* Admin integrado en el shell — link visible solo para cuentas admin */}
                    <Route path="/admin"         element={<PageAdmin />} />
                </Route>

                {/* ── El aula nueva, en construcción ─────────────
                    Va SIN layout y con ruta propia: ocupa la pantalla completa
                    y así el `/aula/:id` de siempre sigue intacto mientras esta
                    se construye. `?rol=profe` la muestra del lado de la
                    maestra. Se borra esta ruta cuando reemplace a la vieja. */}
                <Route path="/aula-nueva/:id" element={<PageAulaNueva />} />

                {/* ── Redirects ─────────────────────────────────── */}
                <Route path="/"   element={<Navigate to="/intro" replace />} />
                <Route path="*"   element={<Page404 />} />

            </Routes>
        </Suspense>
    )
}