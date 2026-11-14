import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { OperadoresService } from '../services/operadores.service';
import { Operador, OperadorActualizar, OperadorCrear } from '../models/operador';
import { ErrorApi } from '../models/vehiculo';

const nonBlank: ValidatorFn = (control) =>
  typeof control.value === 'string' && control.value.trim() ? null : { required: true };
const USUARIO_RE = /^[a-z0-9._-]{3,50}$/;
const validarUsuario: ValidatorFn = (control) => {
  const value = typeof control.value === 'string' ? control.value.trim().toLowerCase() : '';
  if (!value) return { required: true };
  return USUARIO_RE.test(value) ? null : { usuario: true };
};
const validarContrasena: ValidatorFn = (control) => {
  const value = typeof control.value === 'string' ? control.value : '';
  if (!value) return null;
  if (!value.trim()) return { required: true };
  if (value.length < 8) return { contrasenaMin: true };
  if (new TextEncoder().encode(value).length > 72) return { contrasenaBytes: true };
  return null;
};
type Field = 'nombre' | 'telefono' | 'usuario' | 'contrasena';

@Component({
  selector: 'app-operadores',
  imports: [ReactiveFormsModule],
  templateUrl: './operadores.html',
  styleUrl: './operadores.css',
})
export class Operadores {
  private readonly api = inject(OperadoresService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly fields = [
    { key: 'nombre' as const, label: 'Nombre', type: 'text', autocomplete: 'name' },
    { key: 'telefono' as const, label: 'Teléfono', type: 'tel', autocomplete: 'tel' },
    { key: 'usuario' as const, label: 'Usuario', type: 'text', autocomplete: 'username' },
  ];
  readonly form = this.fb.group({
    nombre: this.fb.nonNullable.control('', nonBlank),
    telefono: this.fb.nonNullable.control('', nonBlank),
    usuario: this.fb.nonNullable.control('', validarUsuario),
    contrasena: this.fb.nonNullable.control('', [validarContrasena, Validators.required]),
  });
  readonly items = signal<Operador[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly showForm = signal(false);
  readonly editing = signal<number | null>(null);
  readonly pendingDelete = signal<Operador | null>(null);
  readonly listError = signal('');
  readonly actionError = signal('');
  readonly success = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));

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

  newOperator(): void {
    if (this.busy()) return;
    this.form.reset({ nombre: '', telefono: '', usuario: '', contrasena: '' });
    this.form.controls.contrasena.setValidators([validarContrasena, Validators.required]);
    this.form.controls.contrasena.updateValueAndValidity();
    this.editing.set(null);
    this.showForm.set(true);
    this.pendingDelete.set(null);
    this.actionError.set('');
    this.success.set('');
  }

  edit(operator: Operador): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.actionError.set('');
    this.success.set('');
    this.pendingDelete.set(null);
    this.api
      .get(operator.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.editing.set(data.id);
          this.form.controls.contrasena.setValidators(validarContrasena);
          this.form.reset({
            nombre: data.nombre,
            telefono: data.telefono,
            usuario: data.usuario,
            contrasena: '',
          });
          this.form.controls.contrasena.updateValueAndValidity();
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
    this.actionError.set('');
  }

  fieldError(field: Field): string {
    const control = this.form.controls[field];
    if (!control.touched || !control.errors) return '';
    if (control.errors['server']) return String(control.errors['server']);
    if (field === 'usuario') {
      if (control.errors['required']) return 'El usuario es obligatorio y no puede estar vacío.';
      return 'Usa entre 3 y 50 caracteres: minúsculas, números, punto, guion o guion bajo.';
    }
    if (field === 'contrasena') {
      if (control.errors['contrasenaMin']) return 'La contraseña debe tener al menos 8 caracteres.';
      if (control.errors['contrasenaBytes']) return 'La contraseña no puede superar 72 bytes.';
      if (control.errors['required']) {
        return this.editing() === null
          ? 'La contraseña es obligatoria y no puede estar vacía.'
          : 'La contraseña no puede estar vacía.';
      }
      return 'Revisa este campo.';
    }
    if (control.errors['required']) return 'Este campo es obligatorio y no puede estar vacío.';
    return 'Revisa este campo.';
  }

  save(): void {
    if (this.busy()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.actionError.set('Revisa los campos señalados antes de guardar el operador.');
      return;
    }
    const value = this.form.getRawValue();
    const base = {
      nombre: value.nombre.trim(),
      telefono: value.telefono.trim(),
      usuario: value.usuario.trim().toLowerCase(),
    };
    const contrasena = value.contrasena;
    this.form.patchValue(base);
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    const id = this.editing();
    const request =
      id === null
        ? this.api.create({ ...base, contrasena })
        : this.api.update(id, contrasena ? { ...base, contrasena } : base);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (operator) => {
        this.saving.set(false);
        this.showForm.set(false);
        this.success.set(
          `Operador ${operator.nombre} ${id === null ? 'registrado' : 'actualizado'} correctamente.`,
        );
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.actionError.set(this.errorMessage(error));
        const body = error.error as ErrorApi | null;
        if (error.status === 422 && Array.isArray(body?.detail)) {
          for (const issue of body.detail) {
            const field = issue.loc.at(-1);
            if (typeof field === 'string' && Object.hasOwn(this.form.controls, field)) {
              this.setFieldError(field as Field, this.serverFieldMessage(field as Field));
            }
          }
        }
      },
    });
  }

  private serverFieldMessage(field: Field): string {
    if (field === 'usuario') return 'El usuario no cumple el formato requerido.';
    if (field === 'contrasena') {
      return 'La contraseña no cumple los requisitos de seguridad.';
    }
    return 'El servicio rechazó este valor. Revisa el campo.';
  }

  private setFieldError(field: Field, message: string): void {
    this.form.controls[field].setErrors({ server: message });
    this.form.controls[field].markAsTouched();
  }

  confirmDelete(operator: Operador): void {
    if (this.busy()) return;
    this.pendingDelete.set(operator);
    this.showForm.set(false);
    this.actionError.set('');
    this.success.set('');
  }

  remove(): void {
    const operator = this.pendingDelete();
    if (!operator || this.busy()) return;
    this.saving.set(true);
    this.actionError.set('');
    this.api
      .delete(operator.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.pendingDelete.set(null);
          this.success.set(`Operador ${operator.nombre} eliminado correctamente.`);
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

  private errorMessage(error: HttpErrorResponse, deleting = false): string {
    if (error.status === 404) return 'El operador ya no existe. Actualiza el listado.';
    const body = error.error as ErrorApi | null;
    if (error.status === 409) {
      if (typeof body?.detail === 'string') return body.detail;
      return deleting
        ? 'No se puede eliminar: el operador tiene registros relacionados o un conflicto con otros datos.'
        : 'La operación entra en conflicto con los datos existentes.';
    }
    if (error.status === 422) {
      if (typeof body?.detail === 'string') return body.detail;
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    }
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado antes de reintentar.';
  }
}
