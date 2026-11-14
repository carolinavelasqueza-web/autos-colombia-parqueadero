import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { Cliente, ClienteActualizar, ClienteCrear } from '../models/cliente';
import { ErrorApi } from '../models/vehiculo';
import { AuthService } from '../services/auth.service';
import { ClientesService } from '../services/clientes.service';

const nonBlank: ValidatorFn = (control) =>
  typeof control.value === 'string' && control.value.trim() ? null : { required: true };
// Misma validación pragmática que backend/app/models.py.
const CORREO_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const validarCorreo: ValidatorFn = (control) => {
  const value = typeof control.value === 'string' ? control.value.trim() : '';
  if (!value) return { required: true };
  return CORREO_RE.test(value) ? null : { correo: true };
};
type Field = 'documento' | 'nombre' | 'telefono' | 'correo' | 'activo';

@Component({
  selector: 'app-clientes',
  imports: [ReactiveFormsModule],
  templateUrl: './clientes.html',
  styleUrl: './clientes.css',
})
export class Clientes {
  readonly auth = inject(AuthService);
  private readonly api = inject(ClientesService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly fields = [
    { key: 'documento' as const, label: 'Documento', type: 'text', autocomplete: 'off' },
    { key: 'nombre' as const, label: 'Nombre', type: 'text', autocomplete: 'name' },
    { key: 'telefono' as const, label: 'Teléfono', type: 'tel', autocomplete: 'tel' },
    { key: 'correo' as const, label: 'Correo', type: 'email', autocomplete: 'email' },
  ];
  readonly form = this.fb.group({
    documento: this.fb.nonNullable.control('', nonBlank),
    nombre: this.fb.nonNullable.control('', nonBlank),
    telefono: this.fb.nonNullable.control('', nonBlank),
    correo: this.fb.nonNullable.control('', [validarCorreo, Validators.required]),
    activo: this.fb.nonNullable.control(true),
  });
  readonly items = signal<Cliente[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly showForm = signal(false);
  readonly editing = signal<number | null>(null);
  readonly pendingDelete = signal<Cliente | null>(null);
  readonly pendingHardDelete = signal<Cliente | null>(null);
  readonly listError = signal('');
  readonly actionError = signal('');
  readonly success = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.ceil(this.total() / this.limit) || 1);

  constructor() {
    this.load();
  }

  load(offset = this.offset()): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.listError.set('');
    this.api
      .list(offset, this.limit)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          if (offset > 0 && offset >= data.total) {
            this.load(Math.max(0, Math.floor((data.total - 1) / this.limit) * this.limit));
            return;
          }
          this.items.set(data.items);
          this.total.set(data.total);
          this.offset.set(offset);
        },
        error: (error) => {
          this.loading.set(false);
          this.listError.set(this.errorMessage(error));
        },
      });
  }

  newCliente(): void {
    if (this.busy()) return;
    this.form.reset({
      documento: '',
      nombre: '',
      telefono: '',
      correo: '',
      activo: true,
    });
    this.editing.set(null);
    this.showForm.set(true);
    this.pendingDelete.set(null);
    this.pendingHardDelete.set(null);
    this.actionError.set('');
    this.success.set('');
  }

  edit(cliente: Cliente): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.actionError.set('');
    this.success.set('');
    this.pendingDelete.set(null);
    this.pendingHardDelete.set(null);
    this.api
      .get(cliente.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.editing.set(data.id);
          this.form.reset({
            documento: data.documento,
            nombre: data.nombre,
            telefono: data.telefono,
            correo: data.correo,
            activo: data.activo,
          });
          this.showForm.set(true);
        },
        error: (error) => {
          this.loading.set(false);
          this.actionError.set(this.errorMessage(error));
        },
      });
  }

  cancel(): void {
    if (this.busy()) return;
    this.showForm.set(false);
    this.pendingDelete.set(null);
    this.pendingHardDelete.set(null);
    this.actionError.set('');
  }

  fieldError(field: Field): string {
    const control = this.form.controls[field];
    if (!control.touched || !control.errors) return '';
    if (control.errors['server']) return String(control.errors['server']);
    if (field === 'correo') {
      if (control.errors['required']) return 'El correo es obligatorio y no puede estar vacío.';
      return 'Introduce un correo con formato válido, por ejemplo nombre@dominio.com.';
    }
    if (control.errors['required']) return 'Este campo es obligatorio y no puede estar vacío.';
    return 'Revisa este campo.';
  }

  save(): void {
    if (this.busy()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.actionError.set('Revisa los campos señalados antes de guardar el cliente.');
      return;
    }
    const value = this.form.getRawValue();
    const payload: ClienteCrear = {
      documento: value.documento.trim(),
      nombre: value.nombre.trim(),
      telefono: value.telefono.trim(),
      correo: value.correo.trim(),
      activo: value.activo,
    };
    this.form.patchValue(payload);
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    const id = this.editing();
    const request =
      id === null ? this.api.create(payload) : this.api.update(id, payload as ClienteActualizar);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (cliente) => {
        this.saving.set(false);
        this.showForm.set(false);
        this.success.set(
          `Cliente ${cliente.nombre} ${id === null ? 'registrado' : 'actualizado'} correctamente.`,
        );
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.actionError.set(this.errorMessage(error));
        const body = error.error as ErrorApi | null;
        if (error.status === 409) {
          this.setFieldError('documento', 'Ya existe un cliente con ese documento.');
        }
        if (error.status === 422 && Array.isArray(body?.detail)) {
          for (const issue of body.detail) {
            const field = issue.loc.at(-1);
            if (typeof field === 'string' && Object.hasOwn(this.form.controls, field)) {
              this.setFieldError(
                field as Field,
                'El servicio rechazó este valor. Revisa el campo.',
              );
            }
          }
        }
      },
    });
  }

  private setFieldError(field: Field, message: string): void {
    this.form.controls[field].setErrors({ server: message });
    this.form.controls[field].markAsTouched();
  }

  confirmDelete(cliente: Cliente): void {
    if (this.busy() || !cliente.activo) return;
    this.pendingDelete.set(cliente);
    this.pendingHardDelete.set(null);
    this.showForm.set(false);
    this.actionError.set('');
    this.success.set('');
  }

  // Desactivación lógica (PATCH) -> Accesible por OPERADOR y ADMINISTRADOR
  remove(): void {
    const cliente = this.pendingDelete();
    if (!cliente || this.busy()) return;
    this.saving.set(true);
    this.actionError.set('');
    this.api
      .update(cliente.id, { activo: false })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.pendingDelete.set(null);
          this.success.set(`Cliente ${cliente.nombre} desactivado correctamente.`);
          this.load();
        },
        error: (error) => {
          this.saving.set(false);
          this.actionError.set(this.errorMessage(error, true));
          if (error.status === 404) {
            this.pendingDelete.set(null);
            this.load();
          }
        },
      });
  }

  confirmHardDelete(cliente: Cliente): void {
    if (this.busy() || !this.auth.esAdministrador()) return;
    this.pendingHardDelete.set(cliente);
    this.pendingDelete.set(null);
    this.showForm.set(false);
    this.actionError.set('');
    this.success.set('');
  }

  // Eliminación física (DELETE) -> Exclusivo para ADMINISTRADOR
  hardDelete(): void {
    const cliente = this.pendingHardDelete();
    if (!cliente || this.busy() || !this.auth.esAdministrador()) return;
    this.saving.set(true);
    this.actionError.set('');
    this.api
      .delete(cliente.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.pendingHardDelete.set(null);
          this.success.set(`Cliente ${cliente.nombre} eliminado definitivamente.`);
          this.load();
        },
        error: (error) => {
          this.saving.set(false);
          this.actionError.set(this.errorMessage(error, true));
          if (error.status === 404) {
            this.pendingHardDelete.set(null);
            this.load();
          }
        },
      });
  }

  reactivate(cliente: Cliente): void {
    if (this.busy() || cliente.activo) return;
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    this.api
      .update(cliente.id, { activo: true })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (saved) => {
          this.saving.set(false);
          this.success.set(`Cliente ${saved.nombre} reactivado correctamente.`);
          this.load();
        },
        error: (error) => {
          this.saving.set(false);
          this.actionError.set(this.errorMessage(error));
        },
      });
  }

  private errorMessage(error: HttpErrorResponse, deleting = false): string {
    if (error.status === 403) return 'No tienes permisos suficientes para realizar esta acción.';
    if (error.status === 404) return 'El cliente ya no existe. Actualiza el listado.';
    const body = error.error as ErrorApi | null;
    if (error.status === 409) {
      if (typeof body?.detail === 'string') return body.detail;
      return deleting
        ? 'No se puede realizar la acción: el cliente tiene registros relacionados o un conflicto con otros datos.'
        : 'La operación entra en conflicto con los datos existentes.';
    }
    if (error.status === 422) {
      if (typeof body?.detail === 'string') return body.detail;
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    }
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado antes de reintentar.';
  }
}