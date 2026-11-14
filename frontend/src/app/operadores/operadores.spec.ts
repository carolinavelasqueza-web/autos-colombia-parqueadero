import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Operadores } from './operadores';

describe('Gestión de operadores', () => {
  let fixture: ComponentFixture<Operadores>;
  let http: HttpTestingController;
  const operator = {
    id: 1,
    nombre: 'Prueba Ana',
    telefono: '+57 00123',
    usuario: 'ana.prueba',
  };
  const page = { items: [operator], total: 1, offset: 0, limit: 10 };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Operadores],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Operadores);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Cargando operadores');
    http.expectOne('/operadores?offset=0&limit=10').flush(page);
  });
  afterEach(() => http.verify());

  it('muestra el usuario en el listado', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('ana.prueba');
  });

  it('crea desde el HTML, recorta textos y conserva prefijos sin duplicar envíos', () => {
    const c = fixture.componentInstance;
    c.newOperator();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector<HTMLInputElement>('#telefono')!.type).toBe('tel');
    expect(root.querySelector<HTMLInputElement>('#contrasena')!.type).toBe('password');
    for (const [key, value] of Object.entries({
      nombre: ' Prueba Ana ',
      telefono: ' +57 00123 ',
      usuario: ' Ana.Prueba ',
      contrasena: 'secreta123',
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
    const request = http.expectOne({ method: 'POST', url: '/operadores' });
    expect(request.request.body).toEqual({
      nombre: 'Prueba Ana',
      telefono: '+57 00123',
      usuario: 'ana.prueba',
      contrasena: 'secreta123',
    });
    request.flush(operator);
    http.expectOne('/operadores?offset=0&limit=10').flush(page);
    expect(c.success()).toContain('registrado');
  });

  it('rechaza campos vacíos, usuario inválido y contraseña corta sin enviar', () => {
    const c = fixture.componentInstance;
    c.newOperator();
    c.form.setValue({ nombre: ' \t', telefono: ' ', usuario: '', contrasena: '' });
    c.save();
    expect(c.fieldError('nombre')).toContain('obligatorio');
    expect(c.fieldError('telefono')).toContain('obligatorio');
    expect(c.fieldError('usuario')).toContain('obligatorio');
    expect(c.fieldError('contrasena')).toContain('obligatoria');
    http.expectNone('/operadores');

    c.form.setValue({
      nombre: 'Prueba Ana',
      telefono: '00123',
      usuario: 'ab',
      contrasena: 'corta',
    });
    c.save();
    expect(c.fieldError('usuario')).toContain('3 y 50');
    expect(c.fieldError('contrasena')).toContain('8');
    http.expectNone('/operadores');
  });

  it('marca los campos usuario y contraseña rechazados por el servicio', () => {
    const c = fixture.componentInstance;
    c.newOperator();
    c.form.setValue({
      nombre: 'Prueba Ana',
      telefono: '00123',
      usuario: 'ana.prueba',
      contrasena: 'secreta123',
    });
    c.save();
    http.expectOne('/operadores').flush(
      {
        detail: [
          { loc: ['body', 'usuario'], msg: 'Inválido', type: 'value_error' },
          { loc: ['body', 'contrasena'], msg: 'Inválido', type: 'value_error' },
        ],
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    expect(c.fieldError('usuario')).toContain('formato');
    expect(c.fieldError('contrasena')).toContain('requisitos');
    expect(c.saving()).toBe(false);
  });

  it('informa cuando el usuario ya existe', () => {
    const c = fixture.componentInstance;
    c.newOperator();
    c.form.setValue({
      nombre: 'Prueba Ana',
      telefono: '00123',
      usuario: 'ana.prueba',
      contrasena: 'secreta123',
    });
    c.save();
    http
      .expectOne('/operadores')
      .flush(
        { detail: 'Ya existe un usuario con ese nombre.' },
        { status: 409, statusText: 'Conflict' },
      );
    expect(c.actionError()).toBe('Ya existe un usuario con ese nombre.');
    expect(c.saving()).toBe(false);
  });

  it('consulta antes de editar, precarga el usuario y guarda con PATCH sin contraseña', () => {
    const c = fixture.componentInstance;
    c.edit(operator);
    http.expectOne('/operadores/1').flush(operator);
    expect(c.form.controls.usuario.value).toBe('ana.prueba');
    expect(c.form.controls.contrasena.value).toBe('');
    c.form.controls.telefono.setValue(' 00045 ');
    c.save();
    const request = http.expectOne({ method: 'PATCH', url: '/operadores/1' });
    expect(request.request.body).toEqual({
      nombre: operator.nombre,
      telefono: '00045',
      usuario: operator.usuario,
    });
    request.flush({ ...operator, telefono: '00045' });
    http.expectOne('/operadores?offset=0&limit=10').flush(page);
    expect(c.success()).toContain('actualizado');
  });

  it('permite cambiar la contraseña al editar', () => {
    const c = fixture.componentInstance;
    c.edit(operator);
    http.expectOne('/operadores/1').flush(operator);
    c.form.controls.contrasena.setValue('nuevaClave123');
    c.save();
    const request = http.expectOne({ method: 'PATCH', url: '/operadores/1' });
    expect(request.request.body).toEqual({
      nombre: operator.nombre,
      telefono: operator.telefono,
      usuario: operator.usuario,
      contrasena: 'nuevaClave123',
    });
    request.flush(operator);
    http.expectOne('/operadores?offset=0&limit=10').flush(page);
  });

  it('rechaza una contraseña vacía o con solo espacios al editar', () => {
    const c = fixture.componentInstance;
    c.edit(operator);
    http.expectOne('/operadores/1').flush(operator);
    c.form.controls.contrasena.setValue('        ');
    c.save();
    expect(c.fieldError('contrasena')).toContain('vacía');
    http.expectNone({ method: 'PATCH', url: '/operadores/1' });
  });

  it('identifica al operador, permite cancelar y elimina una sola vez', () => {
    const c = fixture.componentInstance;
    c.confirmDelete(operator);
    fixture.detectChanges();
    const confirmation = fixture.nativeElement.querySelector('[role="alertdialog"]').textContent;
    expect(confirmation).toContain(operator.nombre);
    expect(confirmation).toContain(operator.telefono);
    expect(confirmation).toContain('id 1');
    c.cancel();
    c.remove();
    http.expectNone((r) => r.method === 'DELETE');
    c.confirmDelete(operator);
    c.remove();
    c.remove();
    http
      .expectOne({ method: 'DELETE', url: '/operadores/1' })
      .flush(null, { status: 204, statusText: 'No Content' });
    http.expectOne('/operadores?offset=0&limit=10').flush({ ...page, items: [], total: 0 });
    fixture.detectChanges();
    expect(c.success()).toContain('eliminado');
    expect(fixture.nativeElement.textContent).toContain('Aún no hay operadores');
  });

  it('muestra conflicto de eliminación sin retirar la confirmación', () => {
    const c = fixture.componentInstance;
    c.confirmDelete(operator);
    c.remove();
    http.expectOne('/operadores/1').flush({}, { status: 409, statusText: 'Conflict' });
    expect(c.actionError()).toContain('registros relacionados');
    expect(c.pendingDelete()).toEqual(operator);
    expect(c.busy()).toBe(false);
  });

  it('informa 404 al editar y actualiza el listado si ya se eliminó', () => {
    const c = fixture.componentInstance;
    c.edit(operator);
    http.expectOne('/operadores/1').flush({}, { status: 404, statusText: 'Not Found' });
    expect(c.actionError()).toContain('ya no existe');
    c.confirmDelete(operator);
    c.remove();
    http.expectOne('/operadores/1').flush({}, { status: 404, statusText: 'Not Found' });
    http.expectOne('/operadores?offset=0&limit=10').flush({ ...page, items: [], total: 0 });
    expect(c.pendingDelete()).toBeNull();
  });

  it('muestra fallos de conexión y permite reintentar listado y guardado', () => {
    const c = fixture.componentInstance;
    c.load();
    http.expectOne('/operadores?offset=0&limit=10').error(new ProgressEvent('error'));
    expect(c.listError()).toContain('No se pudo conectar');
    c.load();
    http.expectOne('/operadores?offset=0&limit=10').flush(page);
    c.newOperator();
    c.form.setValue({
      nombre: 'Prueba',
      telefono: '001',
      usuario: 'prueba',
      contrasena: 'secreta123',
    });
    c.save();
    http.expectOne('/operadores').error(new ProgressEvent('error'));
    expect(c.actionError()).toContain('No se pudo conectar');
    expect(c.busy()).toBe(false);
    expect(c.showForm()).toBe(true);
  });

  it('pagina y regresa a la página anterior si la última queda vacía', () => {
    const c = fixture.componentInstance;
    c.load(10);
    http.expectOne('/operadores?offset=10&limit=10').flush({ ...page, offset: 10, total: 11 });
    expect(c.page()).toBe(2);
    c.confirmDelete(operator);
    c.remove();
    http.expectOne('/operadores/1').flush(null, { status: 204, statusText: 'No Content' });
    http
      .expectOne('/operadores?offset=10&limit=10')
      .flush({ ...page, items: [], offset: 10, total: 10 });
    http.expectOne('/operadores?offset=0&limit=10').flush({ ...page, total: 10 });
    expect(c.page()).toBe(1);
  });
});
