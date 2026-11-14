import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { ReasignacionModal } from '../reasignacion-modal/reasignacion-modal';
import { ControlAcceso } from './control-acceso';

describe('Control de acceso', () => {
  let http: HttpTestingController;
  let fixture: ComponentFixture<ControlAcceso>;
  let c: ControlAcceso;
  const cliente = {
    id: 7,
    documento: '123456',
    nombre: 'Cliente Prueba',
    telefono: '001',
    correo: 'cliente@example.com',
    activo: true,
  };
  const disponibilidad = {
    total: 80,
    disponibles: 64,
    ocupadas: 16,
    ocupacion_porcentaje: 20,
    por_tipo: [
      { tipo: 'AUTOMOVIL', total: 70, disponibles: 55, ocupadas: 15 },
      { tipo: 'MOTO', total: 10, disponibles: 8, ocupadas: 2 },
    ],
    celdas: [
      { id: 2, codigo: 'C-01', tipo: 'AUTOMOVIL', disponible: true },
      { id: 3, codigo: 'C-02', tipo: 'AUTOMOVIL', disponible: false },
      { id: 5, codigo: 'M-01', tipo: 'MOTO', disponible: false },
      { id: 6, codigo: 'M-02', tipo: 'MOTO', disponible: false },
      { id: 7, codigo: 'M-03', tipo: 'MOTO', disponible: true },
    ],
  };
  const puertaNorte = { id: 1, codigo: 'NORTE', ubicacion: 'Entrada Norte', activo: true };
  const puertaSur = { id: 2, codigo: 'SUR', ubicacion: 'Entrada Sur', activo: true };
  const stay = {
    id: 3,
    vehiculo_id: 1,
    celda_id: 5,
    entrada: '2026-10-19T15:00:00Z',
    salida: null,
    operador_entrada_id: 4,
    operador_salida_id: null,
    ficho_codigo: 'AC-20261019-0001',
    ficho_usado_en: null,
    puerta_entrada_id: 1,
    puerta_salida_id: null,
  };
  const celda = { id: 5, codigo: 'M-01', tipo: 'MOTO', activo: true };
  const state = {
    vehiculo: {
      id: 1,
      placa: 'TEST-A',
      marca: 'Prueba',
      color: 'Azul',
      modelo: 2026,
      tipo: 'MOTO',
      cliente_id: cliente.id,
      cliente,
    },
    esta_dentro: true,
    estancia: { ...stay, celda, puerta_entrada: puertaNorte },
  };
  const ficho = {
    id: 3,
    ficho_codigo: 'AC-20261019-0001',
    entrada: '2026-10-19T15:00:00Z',
    salida: null,
    ficho_usado_en: null,
    vehiculo: state.vehiculo,
    celda,
    puerta_entrada: puertaNorte,
    puerta_salida: null,
    operador_entrada_id: 4,
    operador_salida_id: null,
    cliente,
  };
  const vehiculo = {
    id: 9,
    placa: 'TEST-N',
    marca: 'Marca',
    color: 'Rojo',
    modelo: 2026,
    tipo: 'MOTO',
    cliente_id: cliente.id,
    cliente,
  };

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      imports: [ControlAcceso],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ControlAcceso);
    c = fixture.componentInstance;
    http.expectOne('/celdas/disponibilidad').flush(disponibilidad);
    http.expectOne('/puertas').flush([puertaNorte, puertaSur]);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function flushClientes(): void {
    http
      .expectOne('/clientes?offset=0&limit=100')
      .flush({ items: [cliente], total: 1, offset: 0, limit: 100 });
  }

  function flushEntrada(): void {
    c.entrada.controls.placa.setValue('TEST-A');
    c.entrada.controls.puerta_entrada_id.setValue(1);
    c.registrarEntrada();
    http.expectOne('/estancias/entrada').flush({ ...stay, celda, puerta_entrada: puertaNorte });
    http.expectOne('/celdas/disponibilidad').flush(disponibilidad);
    http.expectOne('/estancias/3/ficho').flush(ficho);
    fixture.detectChanges();
  }

  it('inicia con la disponibilidad y muestra los contadores', () => {
    expect(c.kpiAutos()).toEqual({ libres: 55, total: 70 });
    expect(c.kpiMotos()).toEqual({ libres: 8, total: 10 });
    expect(c.ocupacion()).toBe(20);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('55 / 70');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('8 / 10');
  });

  it('carga las puertas activas y las ofrece en entrada y salida', () => {
    expect(c.puertas().map((puerta) => puerta.codigo)).toEqual(['NORTE', 'SUR']);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Entrada Norte');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Entrada Sur');
  });

  it('registra la entrada con placa y puerta, y muestra el ficho asignado', () => {
    c.entrada.controls.placa.setValue(' test-a ');
    c.entrada.controls.puerta_entrada_id.setValue(1);
    c.registrarEntrada();
    c.registrarEntrada();
    const req = http.expectOne('/estancias/entrada');
    expect(req.request.body).toEqual({ placa: 'TEST-A', puerta_entrada_id: 1 });
    req.flush({ ...stay, celda, puerta_entrada: puertaNorte });
    expect(c.exitoEntrada()).toContain('M-01');
    expect(c.exitoEntrada()).toContain('NORTE');
    expect(c.exitoEntrada()).toContain('Bogotá');
    expect(c.saving()).toBe(false);
    http.expectOne('/celdas/disponibilidad').flush(disponibilidad);
    http.expectOne('/estancias/3/ficho').flush(ficho);
    expect(c.ficho()?.ficho_codigo).toBe('AC-20261019-0001');
    expect(c.fichoOrigen()).toBe('entrada');
  });

  it('imprime el ficho y muestra su código y la puerta de entrada', () => {
    flushEntrada();
    const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const button = (fixture.nativeElement as HTMLElement).querySelector(
      '.ficho-print .print',
    ) as HTMLButtonElement;
    expect(button.textContent).toContain('Imprimir Ficho');
    button.click();
    expect(print).toHaveBeenCalled();
    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('AC-20261019-0001');
    expect(text).toContain('NORTE');
  });

  it('rechaza una placa vacía o una entrada sin puerta sin llamar a la API', () => {
    c.entrada.controls.placa.setValue(' ');
    c.registrarEntrada();
    http.expectNone('/estancias/entrada');
    expect(c.errorEntrada()).toBe('');

    c.entrada.controls.placa.setValue('TEST-A');
    c.registrarEntrada();
    http.expectNone('/estancias/entrada');
    expect(c.entrada.controls.puerta_entrada_id.invalid).toBe(true);
  });

  it('muestra los conflictos de cliente y ocupación tal como llegan', () => {
    c.entrada.controls.placa.setValue('TEST-A');
    c.entrada.controls.puerta_entrada_id.setValue(1);
    for (const [status, detail] of [
      [409, 'Vehículo no registrado o mensualidad vencida'],
      [409, 'Sin celdas disponibles'],
      [409, 'El vehículo ya está dentro.'],
      [404, 'Vehículo no encontrado.'],
    ] as const) {
      c.registrarEntrada();
      http.expectOne('/estancias/entrada').flush({ detail }, { status, statusText: 'Error' });
      expect(c.errorEntrada()).toBe(detail);
      expect(c.saving()).toBe(false);
    }
  });

  it('descarta respuestas antiguas y no permite salida al cambiar de placa', () => {
    c.consulta.setValue({ placa: 'TEST-A' });
    c.buscar();
    c.consulta.controls.placa.setValue('TEST-B');
    http.expectOne('/estancias/vehiculo/TEST-A').flush(state);
    expect(c.estado()).toBeNull();
    c.registrarSalida();
    http.expectNone('/estancias/salida');
    c.consulta.controls.placa.setValue('TEST-A');
    c.buscar();
    http.expectOne('/estancias/vehiculo/TEST-A').flush(state);
    c.consulta.controls.placa.setValue('TEST-B');
    expect(c.estado()).toBeNull();
  });

  it('consulta antes de salir, valida el ficho y refresca tras cerrar', () => {
    c.consulta.setValue({ placa: 'test-a' });
    c.buscar();
    http.expectOne('/estancias/vehiculo/TEST-A').flush(state);
    c.salidaForm.setValue({ ficho_codigo: ' ac-20261019-0001 ', puerta_salida_id: 2 });
    c.registrarSalida();
    c.registrarSalida();
    const req = http.expectOne('/estancias/salida');
    expect(req.request.body).toEqual({
      ficho_codigo: 'AC-20261019-0001',
      puerta_salida_id: 2,
    });
    req.flush({
      ...stay,
      salida: '2026-10-19T16:00:00Z',
      operador_salida_id: 4,
      ficho_usado_en: '2026-10-19T16:00:00Z',
      puerta_salida_id: 2,
    });
    http.expectOne('/celdas/disponibilidad').flush(disponibilidad);
    http
      .expectOne('/estancias/vehiculo/TEST-A')
      .flush({ ...state, esta_dentro: false, estancia: null });
    expect(c.estado()?.esta_dentro).toBe(false);
    expect(c.exitoSalida()).toContain('Salida registrada');
    expect(c.exitoSalida()).toContain('SUR');
  });

  it('rechaza un ficho con formato inválido o de otra estancia', () => {
    c.consulta.setValue({ placa: 'TEST-A' });
    c.buscar();
    http.expectOne('/estancias/vehiculo/TEST-A').flush(state);
    c.salidaForm.setValue({ ficho_codigo: 'ABC', puerta_salida_id: 2 });
    c.registrarSalida();
    http.expectNone('/estancias/salida');
    expect(c.salidaForm.controls.ficho_codigo.invalid).toBe(true);

    c.salidaForm.setValue({ ficho_codigo: 'AC-20261019-9999', puerta_salida_id: 2 });
    c.registrarSalida();
    http.expectNone('/estancias/salida');
    expect(c.errorConsulta()).toContain('no corresponde');
  });

  it('abre el modal de reasignación con las celdas libres compatibles y actualiza la estancia', () => {
    c.consulta.setValue({ placa: 'TEST-A' });
    c.buscar();
    http.expectOne('/estancias/vehiculo/TEST-A').flush(state);
    fixture.detectChanges();

    c.abrirReasignacion(state.estancia);
    fixture.detectChanges();
    expect(c.celdasReasignables().map((item) => item.id)).toEqual([7]);
    const modal = fixture.debugElement.query(By.directive(ReasignacionModal))
      .componentInstance as ReasignacionModal;
    modal.form.setValue({ celda_nueva_id: 7, motivo: '  Cambio operativo  ' });
    modal.guardar();
    const req = http.expectOne('/estancias/3/reasignar');
    expect(req.request.body).toEqual({ celda_nueva_id: 7, motivo: 'Cambio operativo' });
    const nueva = { id: 7, codigo: 'M-03', tipo: 'MOTO', activo: true };
    req.flush({
      id: 11,
      estancia_id: 3,
      celda_anterior: celda,
      celda_nueva: nueva,
      operador_id: 4,
      fecha: '2026-10-19T17:00:00Z',
      motivo: 'Cambio operativo',
      estancia: { ...state.estancia, celda_id: 7, celda: nueva },
    });
    expect(c.reasignacionEstancia()).toBeNull();
    expect(c.estado()?.estancia?.celda_id).toBe(7);
    expect(c.exitoReasignacion()).toContain('M-01');
    expect(c.exitoReasignacion()).toContain('M-03');
    http.expectOne('/celdas/disponibilidad').flush(disponibilidad);
  });

  it('abre el registro de vehículo, carga clientes y conserva la placa consultada', () => {
    c.consulta.setValue({ placa: 'test-n' });
    c.buscar();
    http
      .expectOne('/estancias/vehiculo/TEST-N')
      .flush({}, { status: 404, statusText: 'Not Found' });
    expect(c.errorConsulta()).toBe('Vehículo no registrado.');
    expect(c.mostrarRegistro()).toBe(true);
    expect(c.vehiculoForm.controls.placa.value).toBe('TEST-N');
    flushClientes();
    expect(c.clientes()).toEqual([cliente]);
  });

  it('registra un vehículo nuevo con cliente y prepara la placa para la entrada', () => {
    c.abrirRegistroVehiculo('test-n');
    flushClientes();
    c.vehiculoForm.setValue({
      placa: ' test-n ',
      marca: 'Marca',
      modelo: 2026,
      color: 'Rojo',
      tipo: 'MOTO',
      cliente_id: cliente.id,
    });
    c.registrarVehiculo();
    const req = http.expectOne('/vehiculos');
    expect(req.request.body).toEqual({
      placa: 'TEST-N',
      marca: 'Marca',
      modelo: 2026,
      color: 'Rojo',
      tipo: 'MOTO',
      cliente_id: cliente.id,
    });
    req.flush(vehiculo);
    expect(c.mostrarRegistro()).toBe(false);
    expect(c.entrada.controls.placa.value).toBe('TEST-N');
    expect(c.exitoVehiculo()).toContain('TEST-N');
    http.expectOne('/celdas/disponibilidad').flush(disponibilidad);
  });

  it('no permite registrar un vehículo sin cliente', () => {
    c.abrirRegistroVehiculo('TEST-N');
    flushClientes();
    c.vehiculoForm.setValue({
      placa: 'TEST-N',
      marca: 'Marca',
      modelo: 2026,
      color: 'Rojo',
      tipo: 'MOTO',
      cliente_id: null,
    });
    c.registrarVehiculo();
    expect(c.vehiculoForm.controls.cliente_id.invalid).toBe(true);
    http.expectNone('/vehiculos');
  });

  it('informa cuando la placa del vehículo ya existe', () => {
    c.abrirRegistroVehiculo('TEST-N');
    flushClientes();
    c.vehiculoForm.setValue({
      placa: 'TEST-N',
      marca: 'Marca',
      modelo: 2026,
      color: 'Rojo',
      tipo: 'MOTO',
      cliente_id: cliente.id,
    });
    c.registrarVehiculo();
    http
      .expectOne('/vehiculos')
      .flush(
        { detail: 'Ya existe un vehículo con esa placa.' },
        { status: 409, statusText: 'Conflict' },
      );
    expect(c.errorVehiculo()).toBe('Ya existe un vehículo con esa placa.');
    expect(c.registrandoVehiculo()).toBe(false);
  });

  it('distingue no registrado y conexión fallida e invalida salida rechazada', () => {
    c.consulta.setValue({ placa: 'TEST-A' });
    c.buscar();
    http
      .expectOne('/estancias/vehiculo/TEST-A')
      .flush({}, { status: 404, statusText: 'Not Found' });
    expect(c.errorConsulta()).toBe('Vehículo no registrado.');
    flushClientes();
    c.buscar();
    http.expectOne('/estancias/vehiculo/TEST-A').error(new ProgressEvent('error'));
    expect(c.errorConsulta()).toContain('No se pudo conectar');
    c.buscar();
    http.expectOne('/estancias/vehiculo/TEST-A').flush(state);
    c.salidaForm.setValue({ ficho_codigo: 'AC-20261019-0001', puerta_salida_id: 2 });
    c.registrarSalida();
    http
      .expectOne('/estancias/salida')
      .flush({ detail: 'La estancia ya está cerrada.' }, { status: 409, statusText: 'Conflict' });
    expect(c.estado()).toBeNull();
    expect(c.errorConsulta()).toContain('Consulta nuevamente');
  });

  it('interpreta el offset recibido y presenta el mismo instante en Bogotá', () => {
    expect(c.fecha('2026-10-19T15:00:00Z')).toBe(c.fecha('2026-10-19T10:00:00-05:00'));
    expect(c.fecha('2026-10-19T15:00:00Z')).toContain('10:00:00');
  });
});
