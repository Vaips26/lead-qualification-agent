import express, { Request, Response } from 'express';
import { Mastra } from '@mastra/core';
import { z } from 'zod';
import fs from 'fs';
import path from 'path';
import { config } from './config.js';

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const LEADS_FILE = path.resolve('leads.json');

// Inicializar archivo de leads si no existe
if (!fs.existsSync(LEADS_FILE)) {
  fs.writeFileSync(LEADS_FILE, JSON.stringify([], null, 2));
}

// 1. Inicializar la instancia del Core de Mastra (Con parche de inicialización)
const mastra = Mastra.init({
  name: 'lead-qualification-app',
  systemHostURL: `http://localhost:${config.PORT}`,
  routeRegistrationPath: '/api/mastra',
  db: {
    provider: 'sqlite',
    uri: 'file:./mastra.db',
  },
  workflows: {
    blueprintDirPath: 'src/blueprints',
    systemEvents: {},
    systemApis: [],
  },
  integrations: [],
  agents: {
    agentDirPath: 'src/agents',
    vectorProvider: [],
  },
});

// 2. Registrar la Herramienta de Enriquecimiento Real mediante Scraper Inline de Mastra (Tipado estricto)
mastra.registerApi('enrichCompanyData', {
  type: 'enrichCompanyData',
  description: 'Busca información detallada de una empresa a partir de su dominio web corporativo.',
  label: 'Busca información detallada de una empresa a partir de su dominio web corporativo.',
  schema: z.object({
    domain: z.string().describe('El dominio del correo electrónico de la empresa (ej. stripe.com)'),
  }),
  executor: async ({ data }) => {
    const { domain } = data;
    console.log(`[Tool: enrichCompanyData] Realizando petición HTTP externa a: https://${domain}`);
    
    const isPersonalEmail = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com'].includes(domain.toLowerCase());

    if (isPersonalEmail) {
      return {
        companyName: 'N/A',
        size: '1',
        industry: 'Consumidor Individual (B2C)',
        description: 'Correo personal, no asociado a una organización corporativa.'
      };
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000); // 4 segundos de límite

      const response = await fetch(`https://${domain}`, {
        signal: controller.signal,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
      });

      clearTimeout(timeoutId);
      const html = await response.text();

      // Extraer metatags HTML usando búsquedas de texto eficientes
      const titleMatch = html.match(/<title>([^<]*)<\/title>/i);
      const title = titleMatch ? titleMatch[1].trim() : '';

      const descMatch = html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']*)["']/i) 
        || html.match(/<meta[^>]*content=["']([^"']*)["'][^>]*name=["']description["']/i);
      const description = descMatch ? descMatch[1].trim() : '';

      console.log(`[Tool: enrichCompanyData] Metadatos reales extraídos con éxito para ${domain}`);

      return {
        companyName: domain.split('.')[0].toUpperCase(),
        size: 'Mediana/Grande (Inferencia por presencia web)',
        industry: 'Servicios Profesionales o Corporativos',
        description: description || title || 'Presencia web corporativa activa sin descripción explícita.'
      };
    } catch (error) {
      console.log(`[Tool: enrichCompanyData] No se pudo acceder por HTTP a ${domain}. Usando fallback inteligente.`);
      return {
        companyName: domain.split('.')[0].toUpperCase(),
        size: 'Incierto',
        industry: 'Incierto (Web protegida o inactiva)',
        description: 'Empresa identificada por su dominio de correo electrónico.'
      };
    }
  },
});

// 3. Registrar la Herramienta de Registro en CRM Inline (Tipado estricto)
mastra.registerApi('registerLeadInCRM', {
  type: 'registerLeadInCRM',
  description: 'Guarda la información calificada del lead en la base de datos o sistema CRM.',
  label: 'Guarda la información calificada del lead en la base de datos o sistema CRM.',
  schema: z.object({
    email: z.string().email(),
    companyName: z.string(),
    score: z.enum(['HOT', 'WARM', 'COLD']).describe('La calificación del lead según su prioridad de negocio'),
    summary: z.string().describe('Justificación objetiva de la calificación basada en los datos recopilados'),
    suggestedAction: z.string().describe('Próxima acción comercial recomendada para el equipo de ventas'),
    emailDraft: z.string().describe('Propuesta de correo de seguimiento personalizado y formal adaptado al lead'),
    crmTask: z.string().describe('Tarea interna estructurada para el equipo (estilo Trello/Jira) detallando los requerimientos'),
    scrapedTitle: z.string().optional().describe('El título HTML real obtenido de la web de la empresa'),
    scrapedDesc: z.string().optional().describe('La meta-descripción HTML real obtenida de la web de la empresa'),
  }),
  executor: async ({ data }) => {
    const { email, companyName, score, summary, suggestedAction, emailDraft, crmTask, scrapedTitle, scrapedDesc } = data;
    console.log(`[Tool: registerLeadInCRM] Registrando lead calificado: ${email}`);
    
    // Simulación de despacho de notificaciones externas
    const notificationLogs = [];
    if (score === 'HOT') {
      notificationLogs.push('Alerta de alta prioridad despachada a Slack (#leads-priority)');
      notificationLogs.push(`Email de seguimiento encolado en servidor de despacho para: ${email}`);
    } else {
      notificationLogs.push('Registro estándar de lead en logs del sistema');
    }

    const leadRecord = {
      id: `lead_${Math.random().toString(36).substring(2, 9)}`,
      email,
      companyName,
      score,
      summary,
      suggestedAction,
      emailDraft,
      crmTask,
      scrapedTitle: scrapedTitle || 'No disponible o dominio público.',
      scrapedDesc: scrapedDesc || 'No disponible o dominio público.',
      notifications: notificationLogs,
      timestamp: new Date().toLocaleString()
    };

    // Leer y añadir al archivo local de base de datos
    const fileData = JSON.parse(fs.readFileSync(LEADS_FILE, 'utf8'));
    fileData.unshift(leadRecord);
    fs.writeFileSync(LEADS_FILE, JSON.stringify(fileData, null, 2));

    return { status: 'success', leadId: leadRecord.id };
  },
});

// 4. Interfaz Visual Premium (Dark Slate & Indigo Corporate Theme)
app.get('/', (req: Request, res: Response) => {
  const leads = JSON.parse(fs.readFileSync(LEADS_FILE, 'utf8'));
  
  // Agrupar leads para las columnas del Tablero Kanban (Tipado estricto string[])
  const hotLeadsCards: string[] = [];
  const warmLeadsCards: string[] = [];
  const coldLeadsCards: string[] = [];

  const rows = leads.map((lead: any) => {
    let badgeClass = 'badge-cold';
    let cardAccent = 'kanban-card-cold';
    if (lead.score === 'HOT') {
      badgeClass = 'badge-hot';
      cardAccent = 'kanban-card-hot';
    }
    if (lead.score === 'WARM') {
      badgeClass = 'badge-warm';
      cardAccent = 'kanban-card-warm';
    }
    
    const notificationsArray = lead.notifications || [];
    const notificationItems = notificationsArray.map((n: string) => `<li>${n}</li>`).join('');

    // Generar tarjeta para el Kanban Board (Usa ID seguro en lugar de pasar strings largos)
    const kanbanCardHtml = `
      <div class="kanban-card ${cardAccent} mb-3 p-3" id="kcard-${lead.id}">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <span class="kanban-card-company">${lead.companyName || 'N/A'}</span>
          <span class="badge-priority ${badgeClass}" style="font-size: 0.65rem; padding: 2px 6px;">${lead.score}</span>
        </div>
        <p class="kanban-card-text text-secondary mb-3">${lead.email}</p>
        <div class="d-flex gap-2">
          <button class="btn btn-action btn-indigo flex-grow-1 btn-sm" onclick="openDossierModal('${lead.id}')">Expediente</button>
          <button class="btn btn-action btn-outline-danger btn-sm" onclick="deleteLead('${lead.id}')">Borrar</button>
        </div>
      </div>
    `;

    if (lead.score === 'HOT') hotLeadsCards.push(kanbanCardHtml);
    else if (lead.score === 'WARM') warmLeadsCards.push(kanbanCardHtml);
    else coldLeadsCards.push(kanbanCardHtml);

    return `
      <tr>
        <td>
          <div class="company-title">${lead.companyName || 'N/A'}</div>
          <div class="lead-email">${lead.email || 'N/A'}</div>
        </td>
        <td><span class="badge-priority ${badgeClass}">${lead.score || 'COLD'}</span></td>
        <td class="text-secondary" style="font-size: 0.85rem;">${lead.summary || 'Sin análisis disponible.'}</td>
        <td>
          <div class="d-flex gap-2">
            <button class="btn btn-action btn-outline-primary btn-sm" onclick="openDossierModal('${lead.id}')">Ver Expediente</button>
            <button class="btn btn-action btn-outline-danger btn-sm" onclick="deleteLead('${lead.id}')">Borrar</button>
          </div>
        </td>
        <td style="font-size: 0.8rem; color: #64748b;">
          <ul class="notification-list m-0 p-0">
            ${notificationItems || '<li>Sin logs de despacho</li>'}
          </ul>
        </td>
      </tr>
    `;
  }).join('');

  const html = `
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <title>CRM Agent Dashboard</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
      <style>
        :root {
          --bg-main: #0f172a;
          --bg-card: #1e293b;
          --border-color: #334155;
          --text-main: #f8fafc;
          --text-secondary: #94a3b8;
          --indigo-accent: #6366f1;
        }
        body { 
          background-color: var(--bg-main); 
          color: var(--text-main);
          font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Helvetica, Arial, sans-serif;
        }
        .header-panel {
          border-bottom: 1px solid var(--border-color);
          background-color: #0b0f19;
        }
        .card { 
          background-color: var(--bg-card); 
          border: 1px solid var(--border-color);
          border-radius: 12px;
          color: var(--text-main);
        }
        .form-control, .form-control:focus {
          background-color: #0f172a;
          border-color: var(--border-color);
          color: var(--text-main);
        }
        .form-control::placeholder {
          color: #475569;
        }
        .btn-indigo {
          background-color: var(--indigo-accent);
          color: #ffffff;
          border: none;
          font-weight: 500;
        }
        .btn-indigo:hover {
          background-color: #4f46e5;
          color: #ffffff;
        }
        .table {
          color: var(--text-main);
          border-color: var(--border-color);
        }
        .table-light-custom {
          background-color: #1e293b;
          color: var(--text-secondary);
          border-bottom: 1px solid var(--border-color);
        }
        .company-title {
          font-weight: 600;
          color: var(--text-main);
        }
        .lead-email {
          font-size: 0.8rem;
          color: var(--text-secondary);
        }
        .badge-priority {
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 0.75rem;
          font-weight: 600;
          display: inline-block;
          text-align: center;
        }
        .badge-hot {
          background-color: rgba(239, 68, 68, 0.15);
          color: #f87171;
          border: 1px solid rgba(239, 68, 68, 0.3);
        }
        .badge-warm {
          background-color: rgba(245, 158, 11, 0.15);
          color: #fbbf24;
          border: 1px solid rgba(245, 158, 11, 0.3);
        }
        .badge-cold {
          background-color: rgba(148, 163, 184, 0.15);
          color: #94a3b8;
          border: 1px solid rgba(148, 163, 184, 0.3);
        }
        .btn-action {
          font-size: 0.75rem;
          padding: 6px 12px;
          border-radius: 6px;
        }
        .notification-list {
          list-style-type: none;
        }
        .notification-list li {
          margin-bottom: 4px;
          color: #38bdf8;
        }
        /* Estilos del Tablero Kanban */
        .kanban-column {
          background-color: #0b1329;
          border: 1px solid var(--border-color);
          border-radius: 12px;
          min-height: 400px;
        }
        .kanban-card {
          background-color: var(--bg-card);
          border-radius: 8px;
          border: 1px solid var(--border-color);
        }
        .kanban-card-hot {
          border-left: 4px solid #ef4444;
        }
        .kanban-card-warm {
          border-left: 4px solid #f59e0b;
        }
        .kanban-card-cold {
          border-left: 4px solid #94a3b8;
        }
        .kanban-card-company {
          font-weight: 600;
          font-size: 0.9rem;
          color: var(--text-main);
        }
        .kanban-card-text {
          font-size: 0.75rem;
        }
        .modal-content {
          background-color: var(--bg-card);
          border: 1px solid var(--border-color);
          color: var(--text-main);
        }
        .modal-header, .modal-footer {
          border-color: var(--border-color);
        }
        .pre-box {
          white-space: pre-wrap;
          font-family: monospace;
          background-color: #0f172a;
          padding: 12px;
          border-radius: 8px;
          border: 1px solid var(--border-color);
          color: #38bdf8;
          font-size: 0.85rem;
        }
      </style>
    </head>
    <body class="pb-5">
      <header class="header-panel py-4 mb-5">
        <div class="container d-flex justify-content-between align-items-center">
          <h1 class="h3 m-0">CRM Agent Dashboard</h1>
          <span class="badge bg-dark border border-secondary text-secondary">Mastra v0.1.26 + Llama 3 70B</span>
        </div>
      </header>

      <div class="container mb-5">
        <div class="row g-4">
          <!-- Panel Izquierdo: Formulario de Entrada -->
          <div class="col-lg-4">
            <div class="card p-4 h-100 justify-content-between">
              <div>
                <h3 class="h5 mb-3">Simulador de Entrada de Prospectos</h3>
                <form id="leadForm" action="/submit" method="POST" onsubmit="showProcessingState()">
                  <div class="mb-3">
                    <label class="form-label text-secondary small">Nombre Completo</label>
                    <input type="text" name="name" class="form-control" required placeholder="Ej. Jane Doe">
                  </div>
                  <div class="mb-3">
                    <label class="form-label text-secondary small">Email Corporativo (Rastreo HTTP en vivo)</label>
                    <input type="email" name="email" class="form-control" required placeholder="Ej. partners@netflix.com">
                  </div>
                  <div class="mb-3">
                    <label class="form-label text-secondary small">Mensaje o Requerimiento Comercial</label>
                    <textarea name="message" class="form-control" rows="5" required placeholder="Detalla aquí los requerimientos técnicos o de negocio que solicita el lead..."></textarea>
                  </div>
                  <button type="submit" id="submitBtn" class="btn btn-indigo w-100 py-2">Procesar mediante Agente IA</button>
                </form>
              </div>
              <div id="processingLog" class="mt-4 p-3 border border-secondary rounded bg-dark d-none">
                <div class="d-flex align-items-center gap-2 mb-2">
                  <div class="spinner-border spinner-border-sm text-indigo" role="status"></div>
                  <span class="small fw-semibold text-secondary">Log de Operación del Agente:</span>
                </div>
                <div class="small text-secondary" id="logLines" style="font-family: monospace; font-size: 0.75rem; line-height: 1.4;">
                  [Iniciando] Esperando transacción...
                </div>
              </div>
            </div>
          </div>
          
          <!-- Panel Derecho: Tabla de resultados calificados -->
          <div class="col-lg-8">
            <div class="card p-4 h-100">
              <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="h5 m-0">Historial de Calificación</h3>
                <a href="/" class="btn btn-sm btn-outline-secondary">Actualizar Datos</a>
              </div>
              <div class="table-responsive">
                <table class="table align-middle">
                  <thead>
                    <tr class="table-light-custom">
                      <th>Contacto / Empresa</th>
                      <th>Prioridad</th>
                      <th>Justificación del Agente</th>
                      <th>Expediente</th>
                      <th>Despachos / Notificaciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${rows || '<tr><td colspan="5" class="text-center text-muted py-4">No se han procesado prospectos en la base de datos local.</td></tr>'}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- SECCIÓN EXTRA "SHOW-OFF": Tablero Kanban de Ventas -->
      <div class="container mt-5">
        <h3 class="h4 mb-4">Tablero Kanban de Ventas (Clasificación Automática)</h3>
        <div class="row g-4">
          <!-- Columna HOT -->
          <div class="col-md-4">
            <div class="kanban-column p-3">
              <div class="d-flex justify-content-between align-items-center border-bottom border-danger pb-2 mb-3">
                <span class="fw-bold text-danger">Alta Prioridad (HOT)</span>
                <span class="badge bg-danger rounded-pill">${hotLeadsCards.length}</span>
              </div>
              <div class="kanban-list">
                ${hotLeadsCards.join('') || '<div class="text-center text-secondary py-4 small">Sin leads asignados.</div>'}
              </div>
            </div>
          </div>
          
          <!-- Columna WARM -->
          <div class="col-md-4">
            <div class="kanban-column p-3">
              <div class="d-flex justify-content-between align-items-center border-bottom border-warning pb-2 mb-3">
                <span class="fw-bold text-warning">Prioridad Media (WARM)</span>
                <span class="badge bg-warning text-dark rounded-pill">${warmLeadsCards.length}</span>
              </div>
              <div class="kanban-list">
                ${warmLeadsCards.join('') || '<div class="text-center text-secondary py-4 small">Sin leads asignados.</div>'}
              </div>
            </div>
          </div>
          
          <!-- Columna COLD -->
          <div class="col-md-4">
            <div class="kanban-column p-3">
              <div class="d-flex justify-content-between align-items-center border-bottom border-secondary pb-2 mb-3">
                <span class="fw-bold text-secondary">Descartados / Spam (COLD)</span>
                <span class="badge bg-secondary rounded-pill">${coldLeadsCards.length}</span>
              </div>
              <div class="kanban-list">
                ${coldLeadsCards.join('') || '<div class="text-center text-secondary py-4 small">Sin leads asignados.</div>'}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Ventana Modal de Expediente de Inteligencia de Cliente -->
      <div class="modal fade" id="dossierModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-xl">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">Expediente de Inteligencia del Cliente</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="row g-4">
                <div class="col-md-5">
                  <h6 class="text-secondary small fw-bold">1. Datos del Análisis del Agente</h6>
                  <div class="pre-box mb-4" id="dossierAnalysis"></div>

                  <h6 class="text-secondary small fw-bold">2. Enriquecimiento Web Real (HTTP Scraping)</h6>
                  <div class="p-3 rounded bg-dark border border-secondary mb-4" style="font-size: 0.8rem;">
                    <div class="mb-2"><span class="text-secondary">Título del Sitio Web:</span> <span id="webTitle" class="text-info fw-semibold"></span></div>
                    <div><span class="text-secondary">Meta-Descripción:</span> <span id="webDesc" class="text-info"></span></div>
                  </div>
                </div>
                <div class="col-md-7">
                  <h6 class="text-secondary small fw-bold">3. Propuesta de Email de Seguimiento Autónomo</h6>
                  <div class="pre-box mb-4" style="color: #a7f3d0;" id="dossierEmail"></div>

                  <h6 class="text-secondary small fw-bold">4. Tarea Interna de Ingeniería / CRM</h6>
                  <div class="pre-box" style="color: #fbcfe8;" id="dossierTask"></div>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar Expediente</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Formulario oculto para eliminar leads -->
      <form id="deleteForm" action="/delete" method="POST" style="display: none;">
        <input type="hidden" name="id" id="deleteLeadId">
      </form>

      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
      <script>
        // Array de datos inyectado de forma segura en el cliente para evitar errores de comillas en HTML
        const LEADS_DATA = ${JSON.stringify(leads)};

        function openDossierModal(leadId) {
          // Buscar el lead por ID de forma limpia en el cliente
          const lead = LEADS_DATA.find(l => l.id === leadId);
          if (!lead) return;

          // Rellenar datos en la modal
          document.getElementById('webTitle').innerText = lead.scrapedTitle || 'No disponible (Email personal)';
          document.getElementById('webDesc').innerText = lead.scrapedDesc || 'No disponible (Email personal)';
          document.getElementById('dossierEmail').innerText = lead.emailDraft || 'No disponible.';
          document.getElementById('dossierTask').innerText = lead.crmTask || 'No disponible.';

          // Formatear JSON de análisis de negocio
          const cleanAnalysis = "Contacto: " + lead.email + "\\n" +
                                "Empresa Identificada: " + lead.companyName + "\\n" +
                                "Calificación: " + lead.score + "\\n\\n" +
                                "Justificación de Negocio:\\n" + lead.summary;
          
          document.getElementById('dossierAnalysis').innerText = cleanAnalysis;

          const modal = new bootstrap.Modal(document.getElementById('dossierModal'));
          modal.show();
        }

        function deleteLead(leadId) {
          if (confirm('¿Estás seguro de que deseas eliminar este expediente del CRM?')) {
            document.getElementById('deleteLeadId').value = leadId;
            document.getElementById('deleteForm').submit();
          }
        }

        function showProcessingState() {
          document.getElementById('submitBtn').disabled = true;
          document.getElementById('submitBtn').innerText = 'Agente Procesando...';
          const logBox = document.getElementById('processingLog');
          logBox.classList.remove('d-none');
          
          const lines = [
            "[Paso 1/4] Extrayendo dominio de correo...",
            "[Paso 2/4] Iniciando Scraping de Metadatos Web...",
            "[Paso 3/4] Enviando contexto a Llama 3 70B...",
            "[Paso 4/4] Redactando email de seguimiento y tarea CRM..."
          ];

          let i = 0;
          const interval = setInterval(() => {
            if(i < lines.length) {
              document.getElementById('logLines').innerHTML += "<br>" + lines[i];
              i++;
            } else {
              clearInterval(interval);
            }
          }, 1200);
        }
      </script>
    </body>
    </html>
  `;
  res.send(html);
});

// Endpoint para procesar el formulario visual
app.post('/submit', async (req: Request, res: Response) => {
  const { name, email, message } = req.body;
  try {
    const agentRunner = (await mastra.getAgent({ connectionId: 'system', agentId: 'leadAgent' })) as any;
    if (agentRunner) {
      const prompt = `Procesa este prospecto entrante: Nombre: ${name}, Email: ${email}, Message: "${message || 'Sin mensaje.'}"`;
      await agentRunner({ prompt });
    }
    res.redirect('/');
  } catch (error) {
    res.status(500).send(`Error procesando lead: ${error}`);
  }
});

// Endpoint para eliminar leads
app.post('/delete', (req: Request, res: Response) => {
  const { id } = req.body;
  try {
    const fileData = JSON.parse(fs.readFileSync(LEADS_FILE, 'utf8'));
    const filteredData = fileData.filter((lead: any) => lead.id !== id);
    fs.writeFileSync(LEADS_FILE, JSON.stringify(filteredData, null, 2));
    res.redirect('/');
  } catch (error) {
    res.status(500).send(`Error al eliminar lead: ${error}`);
  }
});

// Endpoint Webhook tradicional
app.post('/webhook/lead', async (req: Request, res: Response) => {
  const { name, email, message } = req.body;
  if (!email || !name) {
    return res.status(400).json({ error: 'Parámetros inválidos.' });
  }
  try {
    const agentRunner = (await mastra.getAgent({ connectionId: 'system', agentId: 'leadAgent' })) as any;
    if (!agentRunner) throw new Error('No se pudo inicializar el agente.');
    const prompt = `Procesa este prospecto entrante: Nombre: ${name}, Email: ${email}, Message: "${message || 'Sin mensaje.'}"`;
    const agentResponse = await agentRunner({ prompt });
    return res.status(200).json({ success: true, agentOutput: agentResponse.text });
  } catch (error: any) {
    return res.status(500).json({ success: false, error: error.message });
  }
});

app.listen(config.PORT, () => {
  console.log("🚀 Servidor Mastra ejecutándose en el puerto " + config.PORT);
});
