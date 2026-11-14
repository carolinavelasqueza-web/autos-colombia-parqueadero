import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Clientes } from './clientes';

describe('Gestión de clientes', () => {
  let fixture: ComponentFixture<Clientes>;
  let http: HttpTestingController;
  const cliente = {
    id: 1,
    documento: '123456',
    nombre: 'Cliente Prueba',
    telefono: '+57 00123',
    correo: 'cliente@example.com',
    activo: true,
  };
  const page = { items: [cliente], total: 1, offset: 0, limit: 10 };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Clientes],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Clientes);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Cargando clientes');
    http.expectOne('/clientes?offset=0&limit=10').flush(page);
  });
  afterEach(() => http.verify());

  it('muestra documento, correo y estado en el listado', () => {
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('123456');
    expect(text).toContain('cliente@example.com');
    expect(text).toContain('Activo');
  });

  it('crea desde el HTML, recorta textos y conserva el correo', () => {
    const c = fixture.componentInstance;
    c.newCliente();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector<HTMLInputElement>('#correo')!.type).toBe('email');
    expect(root.querySelector<HTMLInputElement>('#telefono')!.type).toBe('tel');
    for (const [key, value] of Object.entries({
      documento: ' 123456 ',
      nombre: ' Cliente Prueba ',
      telefono: ' +57 00123 ',
      correo: ' cliente@example.com ',
    })) {
      const input = root.querySelector<HTMLInputElement>(`#${key}`)!;
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    c.save();
    fixture.detectChanges();
    expect(root.querySelector('fieldset')!.disabled).toBe(true);
    const request = http.expectOne({ method: 'POST', url: '/clientes' });
    expect(request.request.body).toEqual({
      documento: '123456',
      nombre: 'Cliente Prueba',
      telefono: '+57 00123',
      correo: 'cliente@example.com',
      activo: true,
    });
    request.flush(cliente);
    http.expectOne('/clientes?offset=0&limit=10').flush(page);
    expect(c.success()).toContain('registrado');
  });

  it('rechaza campos vacíos y correo inválido sin enviar', () => {
    const c = fixture.componentInstance;
    c.newCliente();
    c.form.setValue({
      documento: ' ',
      nombre: ' ',
      telefono: ' ',
      correo: '',
      activo: true,
    });
    c.save();
    expect(c.fieldError('documento')).toContain('obligatorio');
    expect(c.fieldError('nombre')).toContain('obligatorio');
    expect(c.fieldError('telefono')).toContain('obligatorio');
    expect(c.fieldError('correo')).toContain('obligatorio');
    http.expectNone('/clientes');

    c.form.setValue({
      documento: '123456',
      nombre: 'Cliente',
      telefono: '001',
      correo: 'sin-arroba',
      activo: true,
    });
    c.save();
    expect(c.fieldError('correo')).toContain('formato válido');
    http.expectNone('/clientes');
  });

  it('informa cuando el documento ya existe y marca el campo', () => {
    const c = fixture.componentInstance;
    c.newCliente();
    c.form.setValue({
      documento: '123456',
      nombre: 'Cliente Prueba',
      telefono: '001',
      correo: 'cliente@example.com',
      activo: true,
    });
    c.save();
    http
      .expectOne('/clientes')
      .flush(
        { detail: 'Ya existe un cliente con ese documento.' },
        { status: 409, statusText: 'Conflict' },
      );
    expect(c.actionError()).toBe('Ya existe un cliente con ese documento.');
    expect(c.fieldError('documento')).toContain('Ya existe');
    expect(c.saving()).toBe(false);
  });

  it('consulta antes de editar, precarga el estado y guarda con PATCH', () => {
    const c = fixture.componentInstance;
    c.edit(cliente);
    http.expectOne('/clientes/1').flush(cliente);
    expect(c.form.controls.documento.value).toBe('123456');
    expect(c.form.controls.activo.value).toBe(true);
    c.form.controls.telefono.setValue(' 00045 ');
    c.save();
    const request = http.expectOne({ method: 'PATCH', url: '/clientes/1' });
    expect(request.request.body).toEqual({
      documento: cliente.documento,
      nombre: cliente.nombre,
      telefono: '00045',
      correo: cliente.correo,
      activo: true,
    });
    request.flush({ ...cliente, telefono: '00045' });
    http.expectOne('/clientes?offset=0&limit=10').flush(page);
    expect(c.success()).toContain('actualizado');
  });

  it('desactiva con DELETE y reactiva con PATCH sin borrar el registro', () => {
    const c = fixture.componentInstance;
    c.confirmDelete(cliente);
    fixture.detectChanges();
    const confirmation = fixture.nativeElement.querySelector('[role="alertdialog"]').textContent;
    expect(confirmation).toContain(cliente.nombre);
    expect(confirmation).toContain(cliente.documento);
    expect(confirmation).toContain('no podrán registrar nuevas entradas');
    c.remove();
    c.remove();
    http
      .expectOne({ method: 'DELETE', url: '/clientes/1' })
      .flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne('/clientes?offset=0&limit=10').flush({
      ...page,
      items: [{ ...cliente, activo: false }],
    });
    expect(c.success()).toContain('desactivado');

    const inactivo = { ...cliente, activo: false };
    c.reactivate(inactivo);
    const request = http.expectOne({ method: 'PATCH', url: '/clientes/1' });
    expect(request.request.body).toEqual({ activo: true });
    request.flush(cliente);
    http.expectOne('/clientes?offset=0&limit=10').flush(page);
    expect(c.success()).toContain('reactivado');
  });

  it('no permite desactivar dos veces ni reactivar un cliente activo', () => {
    const c = fixture.componentInstance;
    c.confirmDelete(cliente);
    c.confirmDelete({ ...cliente, activo: false });
    expect(c.pendingDelete()).toEqual(cliente);
    c.reactivate(cliente);
    http.expectNone({ method: 'PATCH', url: '/clientes/1' });
  });

  it('informa 404 al editar y actualiza el listado si ya se eliminó', () => {
    const c = fixture.componentInstance;
    c.edit(cliente);
    http.expectOne('/clientes/1').flush({}, { status: 404, statusText: 'Not Found' });
    expect(c.actionError()).toContain('ya no existe');
    c.confirmDelete(cliente);
    c.remove();
    http.expectOne('/clientes/1').flush({}, { status: 404, statusText: 'Not Found' });
    http.expectOne('/clientes?offset=0&limit=10').flush({ ...page, items: [], total: 0 });
    expect(c.pendingDelete()).toBeNull();
  });

  it('muestra fallos de conexión y permite reintentar', () => {
    const c = fixture.componentInstance;
    c.load();
    http.expectOne('/clientes?offset=0&limit=10').error(new ProgressEvent('error'));
    expect(c.listError()).toContain('No se pudo conectar');
    c.load();
    http.expectOne('/clientes?offset=0&limit=10').flush(page);
    c.newCliente();
    c.form.setValue({
      documento: '1',
      nombre: 'Cliente',
      telefono: '001',
      correo: 'cliente@example.com',
      activo: true,
    });
    c.save();
    http.expectOne('/clientes').error(new ProgressEvent('error'));
    expect(c.actionError()).toContain('No se pudo conectar');
    expect(c.busy()).toBe(false);
    expect(c.showForm()).toBe(true);
  });
});
