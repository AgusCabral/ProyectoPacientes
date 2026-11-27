/**
 * Backend del Portal del Paciente.
 * Vive DENTRO del Google Sheets (Extensiones > Apps Script). Cada función de ACCIONES es un
 * "procedimiento almacenado": valida las reglas de la hoja "Reglas", cambia estados y registra
 * el historial. LockService hace que cada operación sea atómica (dos pacientes no pueden
 * reservar el mismo cupo).
 *
 * Configuración: Configuración del proyecto > Propiedades del script > TOKEN = <clave larga>
 */
const MINUTOS_BLOQUEO = 5;
const ACTIVOS = ['Ocupado', 'Confirmado'];
// Transiciones válidas según la hoja "Reglas" (estado_actual -> posibles nuevos estados)
const VALIDAS = {
  '': ['Libre'],
  'Libre': ['Ocupado', 'Confirmado'],
  'Ocupado': ['Confirmado', 'Libre'],
  'Confirmado': ['Completado', 'Cancelado', 'Reprogramado', 'Libre'],
};

// ───────────── Utilidades ─────────────
// La zona horaria se lee UNA vez por ejecución (antes se pedía a Sheets por cada celda de fecha/hora,
// lo que hacía cada ejecución varias veces más lenta).
let TZ_ = null;
const tz_ = () => TZ_ || (TZ_ = SpreadsheetApp.getActive().getSpreadsheetTimeZone());
const pad_ = (n) => ('0' + n).slice(-2);
const ahoraTxt_ = () => Utilities.formatDate(new Date(), tz_(), 'yyyy-MM-dd HH:mm');
const hoyISO_ = () => Utilities.formatDate(new Date(), tz_(), 'yyyy-MM-dd');

function falla_(codigo, mensaje) { const e = new Error(mensaje); e.codigo = codigo; return e; }

/** Fecha de la celda (Date o texto dd/MM/yyyy) -> 'yyyy-MM-dd' */
function fechaISO_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, tz_(), 'yyyy-MM-dd');
  const m = String(v).match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  return m ? m[3] + '-' + pad_(m[2]) + '-' + pad_(m[1]) : String(v);
}
/** Horario de la celda (Date o texto "08:00:00 a. m.") -> 'HH:mm' */
function hora_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, tz_(), 'HH:mm');
  const m = String(v).match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap])?/i);
  if (!m) return String(v);
  let h = +m[1]; const ap = (m[3] || '').toLowerCase();
  if (ap === 'p' && h < 12) h += 12;
  if (ap === 'a' && h === 12) h = 0;
  return pad_(h) + ':' + m[2];
}

function tabla_(nombre) {
  const sh = SpreadsheetApp.getActive().getSheetByName(nombre);
  if (!sh) throw falla_('CONFIG', 'No existe la hoja ' + nombre);
  const vals = sh.getDataRange().getValues();
  const cab = vals.shift().map(String);
  return { sh, cab, filas: vals, col: (n) => cab.indexOf(n) };
}
/** Fecha-hora de un evento (Date o texto "dd/MM/yyyy HH:mm:ss") -> milisegundos; 0 si no se puede leer. */
function instante_(v) {
  if (v instanceof Date) return v.getTime();
  const m = String(v).match(/(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/);
  if (!m) return 0;
  // Se interpreta en la zona horaria de la HOJA (new Date(...) usaba la del proyecto de Apps Script,
  // y si no coinciden, un evento viejo escrito como texto podía "ganarle" a uno nuevo).
  const txt = m[3] + '-' + m[2] + '-' + m[1] + ' ' + (m[4] || 0) + ':' + (m[5] || 0) + ':' + (m[6] || 0);
  return Utilities.parseDate(txt, tz_(), 'yyyy-M-d H:m:s').getTime();
}
/** Último evento de cada turno en Historial_Turnos: {id_turno: {anterior, actual}}.
 *  Es la fuente de verdad de estado_anterior / estado_actual de la hoja Turnos.
 *  Se lee una sola vez por ejecución y registrar_ lo mantiene al día en memoria. */
let ULT_ = null;
function ultimosEstados_() {
  if (ULT_) return ULT_;
  const h = tabla_('Historial_Turnos'), m = {};
  const ci = h.col('id_turno'), ca = h.col('estado_anterior'), cs = h.col('estado_actual'), cf = h.col('fecha_hora_evento');
  h.filas.forEach((f) => {
    const ts = instante_(f[cf]);
    const prev = m[f[ci]];
    if (!prev || ts >= prev.ts) m[f[ci]] = { ts, anterior: f[ca], actual: f[cs] };   // ante empate, gana la fila posterior
  });
  return (ULT_ = m);
}
function filas_(t) {                       // filas como objetos (con fecha/horario normalizados)
  const ult = ultimosEstados_();
  return t.filas.map((f, i) => {
    const o = { _fila: i + 2 };
    t.cab.forEach((c, j) => { o[c] = f[j]; });
    o.fecha = fechaISO_(o.fecha); o.horario = hora_(o.horario);
    const u = ult[o.id_turno];             // si hay historial, sus estados mandan sobre los de la hoja Turnos
    if (u) { o.estado_anterior = u.anterior; o.estado_actual = u.actual; }
    return o;
  }).filter((o) => o.id_turno !== '');
}
const futuro_ = (o) => (o.fecha + ' ' + o.horario) > ahoraTxt_();

function registrar_(idTurno, anterior, actual, origen) {
  const sh = SpreadsheetApp.getActive().getSheetByName('Historial_Turnos');
  const id = 'H' + ('000000' + sh.getLastRow()).slice(-6);   // la fila 1 es el encabezado
  const ahora = new Date();
  sh.appendRow([id, idTurno, anterior, actual, ahora, origen]);
  const m = ultimosEstados_(), prev = m[idTurno];   // mismo criterio que la lectura: gana el más reciente
  if (!prev || ahora.getTime() >= prev.ts) m[idTurno] = { ts: ahora.getTime(), anterior, actual };
}

/** Cambia el estado de un cupo, valida la transición y deja registro en Historial_Turnos. */
function cambiar_(t, o, nuevo, extra, origen) {
  const ant = o.estado_actual || '';
  if (!(VALIDAS[ant] || []).includes(nuevo))
    throw falla_('TRANSICION', 'Transición no permitida: ' + ant + ' -> ' + nuevo);
  for (const k in extra) t.sh.getRange(o._fila, t.col(k) + 1).setValue(extra[k]);
  registrar_(o.id_turno, ant, nuevo, origen);
  const u = ultimosEstados_()[o.id_turno];  // Turnos copia SIEMPRE el último evento del historial (sin releer la hoja)
  o.estado_anterior = u.anterior; o.estado_actual = u.actual;   // el objeto en memoria queda coherente
  t.sh.getRange(o._fila, t.col('estado_anterior') + 1).setValue(u.anterior);
  t.sh.getRange(o._fila, t.col('estado_actual') + 1).setValue(u.actual);
}

/** Alinea toda la hoja Turnos con el último evento de Historial_Turnos (por si alguien editó a mano). */
function sincronizarEstados_() {
  const t = tabla_('Turnos'), ult = ultimosEstados_();
  const ca = t.col('estado_anterior'), cs = t.col('estado_actual'), ci = t.col('id_turno');
  t.filas.forEach((f, i) => {
    const u = ult[f[ci]];
    if (!u) return;
    if (f[ca] !== u.anterior) t.sh.getRange(i + 2, ca + 1).setValue(u.anterior);
    if (f[cs] !== u.actual) t.sh.getRange(i + 2, cs + 1).setValue(u.actual);
  });
}

function pacientePorDni_(dni) {
  const t = tabla_('Pacientes');
  const f = t.filas.find((r) => String(r[t.col('dni')]).replace(/\D/g, '') === String(dni).replace(/\D/g, ''));
  if (!f) return null;
  const g = (n) => f[t.col(n)];
  return { id_paciente: String(g('id_paciente')), dni: String(g('dni')).replace(/\D/g, ''),
           nombre: String(g('nombre')), apellido: String(g('apellido')) };
}
function exigirPaciente_(dni) {
  const p = pacientePorDni_(dni);
  if (!p) throw falla_('NO_PACIENTE', 'No existe un paciente con ese DNI.');
  return p;
}
function sinSuperposicion_(fs, idPaciente, cupo, ignorar) {
  if (fs.some((x) => x.id_paciente === idPaciente && ACTIVOS.includes(x.estado_actual) &&
      x.fecha === cupo.fecha && x.horario === cupo.horario && x.id_turno !== ignorar))
    throw falla_('DUPLICADO', 'Ya tiene un turno activo en ese día y horario.');
}

/** Ocupados con más de 5 minutos sin confirmar vuelven a Libre (se borra id_paciente y ocupado_desde). */
function liberarVencidos_() {
  const t = tabla_('Turnos'), limite = Date.now() - MINUTOS_BLOQUEO * 60000;
  filas_(t).forEach((o) => {
    if (o.estado_actual !== 'Ocupado') return;
    const desde = o.ocupado_desde instanceof Date ? o.ocupado_desde.getTime() : 0;
    if (desde < limite) cambiar_(t, o, 'Libre', { id_paciente: '', ocupado_desde: '' }, 'Sistema (vencimiento)');
  });
}

// ───────────── Procedimientos ─────────────
const ACCIONES = {
  /** {especialidad: [profesionales]} */
  catalogo() {
    const cat = {};
    filas_(tabla_('Turnos')).forEach((o) => {
      cat[o.especialidad] = cat[o.especialidad] || [];
      if (!cat[o.especialidad].includes(o.profesional)) cat[o.especialidad].push(o.profesional);
    });
    return cat;
  },
  paciente(p) { return pacientePorDni_(p.dni); },

  /** Fechas futuras con al menos un cupo Libre. */
  fechas(p) {
    const s = new Set();
    filas_(tabla_('Turnos')).forEach((o) => {
      if (o.estado_actual === 'Libre' && o.especialidad === p.especialidad &&
          o.profesional === p.profesional && futuro_(o)) s.add(o.fecha);
    });
    return Array.from(s).sort();
  },
  horarios(p) {
    return filas_(tabla_('Turnos'))
      .filter((o) => o.estado_actual === 'Libre' && o.especialidad === p.especialidad &&
                     o.profesional === p.profesional && o.fecha === p.fecha && futuro_(o))
      .map((o) => ({ id_turno: o.id_turno, hora: o.horario }))
      .sort((a, b) => a.hora.localeCompare(b.hora));
  },

  /** Libre -> Ocupado (bloquea el cupo 5 min). */
  reservar(p) {
    const pac = exigirPaciente_(p.dni), t = tabla_('Turnos'), fs = filas_(t);
    const c = fs.find((o) => o.id_turno === p.id_turno);
    if (!c || c.estado_actual !== 'Libre' || !futuro_(c))
      throw falla_('NO_DISPONIBLE', 'Ese horario ya no está disponible.');
    sinSuperposicion_(fs, pac.id_paciente, c, null);
    cambiar_(t, c, 'Ocupado', { id_paciente: pac.id_paciente, ocupado_desde: new Date(),
                                cancelado_por: '', reprogramado_por: '' }, 'Paciente (chatbot)');
    return { id_turno: c.id_turno, minutos: MINUTOS_BLOQUEO };
  },
  /** Ocupado -> Confirmado (solo el mismo paciente y dentro de los 5 min). */
  confirmar(p) {
    const pac = exigirPaciente_(p.dni), t = tabla_('Turnos');
    const c = filas_(t).find((o) => o.id_turno === p.id_turno);
    if (!c || c.estado_actual !== 'Ocupado' || c.id_paciente !== pac.id_paciente)
      throw falla_('EXPIRADO', 'La reserva venció y el horario fue liberado.');
    cambiar_(t, c, 'Confirmado', { ocupado_desde: '' }, 'Paciente (chatbot)');
    return { id_turno: c.id_turno };
  },
  /** Ocupado -> Libre (el paciente no confirmó). */
  liberar(p) {
    const pac = exigirPaciente_(p.dni), t = tabla_('Turnos');
    const c = filas_(t).find((o) => o.id_turno === p.id_turno);
    if (!c || c.estado_actual !== 'Ocupado' || c.id_paciente !== pac.id_paciente) return { liberado: false };
    cambiar_(t, c, 'Libre', { id_paciente: '', ocupado_desde: '' }, 'Paciente (chatbot)');
    return { liberado: true };
  },
  /** Turnos vigentes del paciente (incluye los cancelados/reprogramados por el profesional). */
  turnos(p) {
    const pac = exigirPaciente_(p.dni), hoy = hoyISO_();
    return filas_(tabla_('Turnos'))
      .filter((o) => o.id_paciente === pac.id_paciente && o.fecha >= hoy &&
                     ['Confirmado', 'Cancelado', 'Reprogramado'].includes(o.estado_actual))
      .sort((a, b) => (a.fecha + a.horario).localeCompare(b.fecha + b.horario))
      .map((o) => ({ id_turno: o.id_turno, fecha: o.fecha, hora: o.horario, especialidad: o.especialidad,
                     profesional: o.profesional, estado: o.estado_actual,
                     modificable: o.estado_actual === 'Confirmado' && futuro_(o) }));
  },
  /** Confirmado -> Libre, cancelado_por = Paciente, se borra id_paciente. */
  cancelar(p) {
    const pac = exigirPaciente_(p.dni), t = tabla_('Turnos');
    const c = filas_(t).find((o) => o.id_turno === p.id_turno);
    if (!c || c.estado_actual !== 'Confirmado' || c.id_paciente !== pac.id_paciente || !futuro_(c))
      throw falla_('NO_CANCELABLE', 'Ese turno no se puede cancelar.');
    cambiar_(t, c, 'Libre', { id_paciente: '', cancelado_por: 'Paciente', reprogramado_por: '' }, 'Paciente (chatbot)');
    return { id_turno: c.id_turno };
  },
  /** Turno viejo -> Libre (reprogramado_por = Paciente); turno nuevo (posterior, misma especialidad) -> Confirmado. */
  reprogramar(p) {
    const pac = exigirPaciente_(p.dni), t = tabla_('Turnos'), fs = filas_(t);
    const v = fs.find((o) => o.id_turno === p.id_turno);
    const n = fs.find((o) => o.id_turno === p.id_turno_nuevo);
    if (!v || v.estado_actual !== 'Confirmado' || v.id_paciente !== pac.id_paciente || !futuro_(v))
      throw falla_('NO_REPROGRAMABLE', 'Ese turno no se puede reprogramar.');
    if (!n || n.estado_actual !== 'Libre' || !futuro_(n))
      throw falla_('NO_DISPONIBLE', 'El nuevo horario ya no está disponible.');
    if (n.especialidad !== v.especialidad || (n.fecha + n.horario) <= (v.fecha + v.horario))
      throw falla_('REGLA', 'El nuevo turno debe ser de la misma especialidad y posterior al actual.');
    sinSuperposicion_(fs, pac.id_paciente, n, v.id_turno);
    cambiar_(t, n, 'Confirmado', { id_paciente: pac.id_paciente, cancelado_por: '', reprogramado_por: '' }, 'Paciente (chatbot)');
    cambiar_(t, v, 'Libre', { id_paciente: '', reprogramado_por: 'Paciente' }, 'Paciente (chatbot)');
    return { id_turno: n.id_turno };
  },
};

// ───────────── Punto de entrada (Web App) y vencimientos ─────────────
function salida_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const p = JSON.parse(e.postData.contents);
    if (p.token !== PropertiesService.getScriptProperties().getProperty('TOKEN'))
      return salida_({ ok: false, codigo: 'NO_AUTORIZADO', error: 'No autorizado' });
    const accion = Object.prototype.hasOwnProperty.call(ACCIONES, p.accion) ? ACCIONES[p.accion] : null;
    if (!accion) return salida_({ ok: false, codigo: 'ACCION', error: 'Acción desconocida' });
    lock.waitLock(20000);
    liberarVencidos_();
    return salida_({ ok: true, datos: accion(p) });
  } catch (err) {
    return salida_({ ok: false, codigo: err.codigo || 'ERROR', error: String(err.message || err) });
  } finally {
    try { lock.releaseLock(); } catch (_) {}
  }
}
/** Trigger de tiempo: libera los cupos Ocupados vencidos y alinea Turnos con el historial.
 *  Si en ese momento hay una consulta del chatbot en curso, simplemente saltea esta vuelta:
 *  la propia consulta ya libera los vencidos (doPost llama a liberarVencidos_). Antes esperaba
 *  el bloqueo hasta 20 s y, si no lo conseguía, la ejecución terminaba en error. */
function liberarVencidos() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(2000)) { console.log('Ocupado por otra ejecución; se saltea esta vuelta.'); return; }
  try { liberarVencidos_(); sincronizarEstados_(); } finally { lock.releaseLock(); }
}
/** Ejecutar a mano cuando se quiera alinear Turnos con el historial de inmediato. */
function sincronizarEstados() {
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try { sincronizarEstados_(); } finally { lock.releaseLock(); }
}
/** Ejecutar UNA vez a mano desde el editor: borra el activador viejo (cada 1 min) y crea uno cada 5 min.
 *  Cada 1 minuto son 1440 ejecuciones por día, y las cuentas Gmail gratuitas tienen un tope de
 *  ~90 minutos diarios de ejecución para activadores: al pasarlo, las ejecuciones fallan.
 *  Con 5 minutos alcanza, porque cada consulta del chatbot ya libera los cupos vencidos. */
function instalarTrigger() {
  ScriptApp.getProjectTriggers()
    .filter((tr) => tr.getHandlerFunction() === 'liberarVencidos')
    .forEach((tr) => ScriptApp.deleteTrigger(tr));
  ScriptApp.newTrigger('liberarVencidos').timeBased().everyMinutes(5).create();
}