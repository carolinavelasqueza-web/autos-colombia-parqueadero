import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { FichoPreview } from '../ficho-preview/ficho-preview';
import { ReasignacionModal } from '../reasignacion-modal/reasignacion-modal';
import {
  CeldaDisponible,
  DisponibilidadCeldas,
  ResumenTipoCelda,
  familiaTipo,
  normalizarTipo,
} from '../models/celda';
import { Cliente } from '../models/cliente';
import { EstadoVehiculo, EstanciaAbierta, Ficho, Reasignacion } from '../models/estancia';
import { Puerta } from '../models/puerta';
import { TIPOS_VEHICULO, TipoVehiculo, Vehiculo, VehiculoCrear } from '../models/vehiculo';
import { Mensualidad } from '../models/pago';
import { estaPorVencer, formatearVencimiento } from '../models/mensualidad';
import { ApiService } from '../services/api.service';
import { AuthService } from '../services/auth.service';
import { CeldasService } from '../services/celdas.service';
import { ClientesService } from '../services/clientes.service';
import { EstanciasService } from '../services/estancias.service';
import { PagosService } from '../services/pagos.service';
import { PuertasService } from '../services/puertas.service';

const nonBlank: ValidatorFn = (c) =>
  typeof c.value === 'string' && c.value.trim() ? null : { required: true };
const year: ValidatorFn = (c) =>
  Number.isInteger(c.value) && c.value >= 1 && c.value <= 9999 ? null : { year: true };
const fichoFormato: ValidatorFn = (c) =>
  /^AC-\d{8}-\d{4}$/.test(
    String(c.value ?? '')
      .trim()
      .toUpperCase(),
  )
    ? null
    : { ficho: true };
const placa = (value: string) => value.trim().toUpperCase();

@Component({
  selector: 'app-control-acceso',
  imports: [ReactiveFormsModule, FichoPreview, ReasignacionModal],
  templateUrl: './control-acceso.html',
  styleUrl: './control-acceso.css',
})
export class ControlAcceso {
  private readonly api = inject(EstanciasService);
  private readonly vehiculos = inject(ApiService);
  private readonly celdasApi = inject(CeldasService);
  private readonly clientesApi = inject(ClientesService);
  private readonly puertasApi = inject(PuertasService);
  private readonly pagosApi = inject(PagosService);
  readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  private readonly destroy = inject(DestroyRef);
  private version = 0;
  readonly tipos = TIPOS_VEHICULO;
  readonly entrada = this.fb.group({
    placa: this.fb.nonNullable.control('', nonBlank),
    puerta_entrada_id: this.fb.control<number | null>(null, Validators.required),
  });
  readonly consulta = this.fb.group({
    placa: this.fb.nonNullable.control('', nonBlank),
  });
  readonly salidaForm = this.fb.group({
    ficho_codigo: this.fb.nonNullable.control('', [nonBlank, fichoFormato]),
    puerta_salida_id: this.fb.control<number | null>(null, Validators.required),
  });
  readonly vehiculoForm = this.fb.group({
    placa: this.fb.nonNullable.control('', nonBlank),
    marca: this.fb.nonNullable.control('', nonBlank),
    modelo: this.fb.control<number | null>(null, [Validators.required, year]),
    color: this.fb.nonNullable.control('', nonBlank),
    tipo: this.fb.nonNullable.control<TipoVehiculo | ''>('', [
      Validators.required,
      (control) => (this.tipos.includes(control.value as TipoVehiculo) ? null : { type: true }),
    ]),
    cliente_id: this.fb.control<number | null>(null, Validators.required),
  });
  readonly disponibilidad = signal<DisponibilidadCeldas | null>(null);
  readonly catalogLoading = signal(false);
  readonly catalogError = signal('');
  readonly puertas = signal<Puerta[]>([]);
  readonly puertasLoading = signal(false);
  readonly puertasError = signal('');
  readonly saving = signal(false);
  readonly querying = signal(false);
  readonly busy = computed(() => this.saving() || this.querying());
  readonly estado = signal<EstadoVehiculo | null>(null);
  readonly ficho = signal<Ficho | null>(null);
  readonly fichoLoading = signal(false);
  readonly fichoError = signal('');
  readonly fichoOrigen = signal<'entrada' | 'consulta' | null>(null);
  readonly errorEntrada = signal('');
  readonly errorConsulta = signal('');
  readonly exitoEntrada = signal('');
  readonly exitoSalida = signal('');
  readonly exitoReasignacion = signal('');
  readonly reasignacionEstancia = signal<EstanciaAbierta | null>(null);
  readonly mostrarRegistro = signal(false);
  readonly registrandoVehiculo = signal(false);
  readonly errorVehiculo = signal('');
  readonly exitoVehiculo = signal('');
  readonly clientes = signal<Cliente[]>([]);
  readonly clientesLoading = signal(false);
  readonly clientesError = signal('');
  // Mensualidad del cliente del vehículo consultado (para la alerta de vencimiento).
  readonly mensualidad = signal<Mensualidad | null>(null);
  readonly vencimientoProximo = computed(() => {
    const info = this.mensualidad();
    if (!info) return null;
    const fecha = info.cliente.fecha_vencimiento;
    if (info.estado !== 'POR_VENCER' || !estaPorVencer(fecha)) return null;
    return formatearVencimiento(fecha);
  });
  readonly kpiAutos = computed(() => this.kpi('AUTOMOVIL'));
  readonly kpiMotos = computed(() => this.kpi('MOTO'));
  readonly total = computed(() => this.disponibilidad()?.total ?? 0);
  readonly disponibles = computed(() => this.disponibilidad()?.disponibles ?? 0);
  readonly ocupadas = computed(() => this.disponibilidad()?.ocupadas ?? 0);
  readonly ocupacion = computed(() => this.disponibilidad()?.ocupacion_porcentaje ?? 0);
  readonly celdasReasignables = computed(() => {
    const state = this.estado();
    const stay = state?.estancia;
    const datos = this.disponibilidad();
    if (!state || !stay || !datos) return [];
    const familia = familiaTipo(state.vehiculo.tipo);
    if (familia === null) return [];
    return datos.celdas.filter(
      (celda: CeldaDisponible) =>
        celda.disponible && celda.id !== stay.celda_id && familiaTipo(celda.tipo) === familia,
    );
  });

  constructor() {
    this.consulta.controls.placa.valueChanges
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe(() => {
        this.version++;
        this.estado.set(null);
        this.mensualidad.set(null);
        this.errorConsulta.set('');
        this.exitoSalida.set('');
        this.exitoReasignacion.set('');
        this.ficho.set(null);
        this.fichoError.set('');
        this.fichoOrigen.set(null);
        this.reasignacionEstancia.set(null);
        this.salidaForm.reset({ ficho_codigo: '', puerta_salida_id: null });
      });
    this.entrada.controls.placa.valueChanges
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe(() => {
        this.errorEntrada.set('');
        this.exitoEntrada.set('');
      });
    this.entrada.controls.puerta_entrada_id.valueChanges
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe(() => this.errorEntrada.set(''));
    this.salidaForm.controls.ficho_codigo.valueChanges
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe(() => this.errorConsulta.set(''));
    this.cargarDisponibilidad();
    this.cargarPuertas();
  }

  cargarDisponibilidad(): void {
    if (this.catalogLoading()) return;
    this.catalogLoading.set(true);
    this.catalogError.set('');
    this.celdasApi
      .disponibilidad()
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.disponibilidad.set(data);
          this.catalogLoading.set(false);
        },
        error: () => {
          this.catalogLoading.set(false);
          this.disponibilidad.set(null);
          this.catalogError.set('No se pudo cargar la disponibilidad. Reintenta actualizar.');
        },
      });
  }

  cargarPuertas(): void {
    if (this.puertasLoading()) return;
    this.puertasLoading.set(true);
    this.puertasError.set('');
    this.puertasApi
      .listar()
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.puertas.set(data);
          this.puertasLoading.set(false);
        },
        error: () => {
          this.puertas.set([]);
          this.puertasLoading.set(false);
          this.puertasError.set(
            'No se pudo cargar el listado de puertas. Reintenta antes de registrar una entrada o salida.',
          );
        },
      });
  }

  cargarFicho(estanciaId: number): void {
    this.fichoLoading.set(true);
    this.fichoError.set('');
    this.api
      .ficho(estanciaId)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.ficho.set(data);
          this.fichoLoading.set(false);
        },
        error: () => {
          this.fichoLoading.set(false);
          this.fichoError.set(
            'La operación se registró, pero no se pudo cargar el ficho. Consulta el vehículo para reintentar la impresión.',
          );
        },
      });
  }

  cargarClientes(): void {
    if (this.clientesLoading()) return;
    this.clientesLoading.set(true);
    this.clientesError.set('');
    this.clientesApi
      .list(0, 100)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.clientesLoading.set(false);
          this.clientes.set(data.items);
        },
        error: () => {
          this.clientesLoading.set(false);
          this.clientesError.set(
            'No se pudo cargar la lista de clientes. Reintenta antes de registrar el vehículo.',
          );
        },
      });
  }

  // Consulta la mensualidad del cliente para avisar si está por vencer.
  // Es informativo: si falla, no interrumpe la consulta del vehículo.
  private cargarMensualidad(clienteId: number, version: number): void {
    this.pagosApi
      .mensualidad(clienteId)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (info) => {
          if (version === this.version) this.mensualidad.set(info);
        },
        error: () => {
          if (version === this.version) this.mensualidad.set(null);
        },
      });
  }

  registrarEntrada(): void {
    if (this.busy()) return;
    this.entrada.markAllAsTouched();
    const valor = placa(this.entrada.controls.placa.value);
    this.entrada.controls.placa.setValue(valor, { emitEvent: false });
    const puertaId = this.entrada.controls.puerta_entrada_id.value;
    if (this.entrada.invalid || puertaId === null) return;

    this.saving.set(true);
    this.errorEntrada.set('');
    this.exitoEntrada.set('');
    this.ficho.set(null);
    this.fichoError.set('');
    this.fichoOrigen.set(null);
    this.version++;
    this.estado.set(null);
    this.api
      .entrada({ placa: valor, puerta_entrada_id: puertaId })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.saving.set(false);
          this.exitoEntrada.set(
            `Entrada registrada: ${valor}, celda ${result.celda.codigo}, puerta ${
              result.puerta_entrada?.codigo ?? '—'
            }, ${this.fecha(result.entrada)}.`,
          );
          this.cargarDisponibilidad();
          this.fichoOrigen.set('entrada');
          this.cargarFicho(result.id);
        },
        error: (error) => {
          this.saving.set(false);
          this.errorEntrada.set(this.mensaje(error));
        },
      });
  }

  buscar(): void {
    if (this.busy()) return;
    this.consulta.controls.placa.markAsTouched();
    if (this.consulta.controls.placa.invalid) return;
    const value = placa(this.consulta.controls.placa.value);
    this.consulta.controls.placa.setValue(value, { emitEvent: false });
    const version = ++this.version;
    this.estado.set(null);
    this.mensualidad.set(null);
    this.errorConsulta.set('');
    this.exitoSalida.set('');
    this.exitoReasignacion.set('');
    this.ficho.set(null);
    this.fichoError.set('');
    this.fichoOrigen.set(null);
    this.reasignacionEstancia.set(null);
    this.salidaForm.reset({ ficho_codigo: '', puerta_salida_id: null });
    this.querying.set(true);
    this.api
      .consultar(value)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.querying.set(false);
          if (version !== this.version) return;
          this.estado.set(result);
          const cliente = result.vehiculo.cliente;
          if (cliente) this.cargarMensualidad(cliente.id, version);
        },
        error: (error) => {
          this.querying.set(false);
          if (version !== this.version) return;
          if (error.status === 404) {
            this.errorConsulta.set('Vehículo no registrado.');
            this.abrirRegistroVehiculo(value);
            return;
          }
          this.errorConsulta.set(this.mensaje(error));
        },
      });
  }

  registrarSalida(): void {
    if (this.busy()) return;
    this.consulta.markAllAsTouched();
    this.salidaForm.markAllAsTouched();
    const state = this.estado();
    const value = placa(this.consulta.controls.placa.value);
    const stay = state?.estancia;
    if (this.consulta.invalid || !stay || !state.esta_dentro || state.vehiculo.placa !== value)
      return;

    const ficho = this.salidaForm.controls.ficho_codigo.value.trim().toUpperCase();
    this.salidaForm.controls.ficho_codigo.setValue(ficho, { emitEvent: false });
    const puertaId = this.salidaForm.controls.puerta_salida_id.value;
    if (this.salidaForm.invalid || puertaId === null) return;
    if (ficho !== stay.ficho_codigo) {
      this.errorConsulta.set(
        'El ficho no corresponde a la estancia abierta de este vehículo. Verifica el código impreso.',
      );
      return;
    }

    const version = this.version;
    this.saving.set(true);
    this.errorConsulta.set('');
    this.exitoSalida.set('');
    this.exitoReasignacion.set('');
    this.api
      .salida({ ficho_codigo: ficho, puerta_salida_id: puertaId })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.saving.set(false);
          this.estado.set(null);
          this.ficho.set(null);
          this.fichoOrigen.set(null);
          this.cargarDisponibilidad();
          if (version !== this.version) return;
          this.salidaForm.reset({ ficho_codigo: '', puerta_salida_id: null });
          // La recarga limpia los mensajes; el éxito se escribe después para que quede visible.
          this.buscar();
          this.exitoSalida.set(
            `Salida registrada: ${value}, celda ${stay.celda.codigo}, puerta ${this.puertaCodigo(
              puertaId,
            )}, ${this.fecha(result.salida!)}.`,
          );
        },
        error: (error) => {
          this.saving.set(false);
          this.estado.set(null);
          this.ficho.set(null);
          this.fichoOrigen.set(null);
          if (version === this.version)
            this.errorConsulta.set(
              this.mensaje(error) + ' Consulta nuevamente antes de confirmar otra salida.',
            );
        },
      });
  }

  mostrarFicho(estanciaId: number): void {
    this.fichoOrigen.set('consulta');
    this.cargarFicho(estanciaId);
  }

  abrirReasignacion(stay: EstanciaAbierta): void {
    this.errorConsulta.set('');
    this.exitoReasignacion.set('');
    this.reasignacionEstancia.set(stay);
  }

  cerrarReasignacion(): void {
    this.reasignacionEstancia.set(null);
  }

  alReasignar(result: Reasignacion): void {
    this.reasignacionEstancia.set(null);
    const state = this.estado();
    if (state) this.estado.set({ ...state, estancia: result.estancia });
    const previo = this.ficho();
    if (previo && previo.id === result.estancia.id) {
      this.ficho.set({ ...previo, celda: result.estancia.celda });
    }
    this.exitoReasignacion.set(
      `Celda reasignada: ${result.celda_anterior.codigo} → ${result.celda_nueva.codigo}.`,
    );
    this.cargarDisponibilidad();
  }

  abrirRegistroVehiculo(placaInicial = ''): void {
    const actual =
      placaInicial || this.consulta.controls.placa.value || this.entrada.controls.placa.value;
    if (actual.trim() && (placaInicial || !this.vehiculoForm.controls.placa.value)) {
      this.vehiculoForm.controls.placa.setValue(placa(actual));
    }
    if (!this.clientes().length) this.cargarClientes();
    this.errorVehiculo.set('');
    this.exitoVehiculo.set('');
    this.mostrarRegistro.set(true);
  }

  cancelarRegistroVehiculo(): void {
    this.mostrarRegistro.set(false);
    this.errorVehiculo.set('');
    this.vehiculoForm.reset();
  }

  registrarVehiculo(): void {
    if (this.registrandoVehiculo()) return;
    this.vehiculoForm.markAllAsTouched();
    if (this.vehiculoForm.invalid) return;

    const raw = this.vehiculoForm.getRawValue();
    const data: VehiculoCrear = {
      placa: placa(raw.placa),
      marca: raw.marca.trim(),
      modelo: raw.modelo!,
      color: raw.color.trim(),
      tipo: raw.tipo as TipoVehiculo,
      cliente_id: raw.cliente_id!,
    };
    this.registrandoVehiculo.set(true);
    this.errorVehiculo.set('');
    this.exitoVehiculo.set('');
    this.vehiculos
      .create(data)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (vehiculo: Vehiculo) => {
          this.registrandoVehiculo.set(false);
          this.mostrarRegistro.set(false);
          this.vehiculoForm.reset();
          // La entrada ya no exige buscar el tipo: el backend asigna la celda.
          this.entrada.controls.placa.setValue(vehiculo.placa);
          this.exitoVehiculo.set(
            `Vehículo ${vehiculo.placa} registrado. Ya puedes registrar su entrada.`,
          );
          this.cargarDisponibilidad();
        },
        error: (error) => {
          this.registrandoVehiculo.set(false);
          this.errorVehiculo.set(this.mensajeVehiculo(error));
        },
      });
  }

  fecha(value: string): string {
    return (
      new Intl.DateTimeFormat('es-CO', {
        timeZone: 'America/Bogota',
        dateStyle: 'medium',
        timeStyle: 'medium',
      }).format(new Date(value)) + ' (Bogotá)'
    );
  }

  puertaCodigo(id: number | null): string {
    if (id === null) return '—';
    return this.puertas().find((puerta) => puerta.id === id)?.codigo ?? `#${id}`;
  }

  private kpi(tipo: string) {
    const resumen = this.resumenTipo(tipo);
    return { libres: resumen?.disponibles ?? 0, total: resumen?.total ?? 0 };
  }

  private resumenTipo(tipo: string): ResumenTipoCelda | undefined {
    const clave = normalizarTipo(tipo);
    return this.disponibilidad()?.por_tipo.find((item) => normalizarTipo(item.tipo) === clave);
  }

  private mensaje(error: HttpErrorResponse): string {
    if ([400, 404, 409].includes(error.status) && typeof error.error?.detail === 'string')
      return error.error.detail;
    if (error.status === 422)
      return 'Datos inválidos. Revisa la placa, el ficho y la puerta seleccionada.';
    return 'No se pudo conectar con el servicio. Consulta el vehículo antes de reintentar: la operación podría haberse completado.';
  }

  private mensajeVehiculo(error: HttpErrorResponse): string {
    if (error.status === 404) {
      return typeof error.error?.detail === 'string'
        ? error.error.detail
        : 'El cliente seleccionado ya no existe. Actualiza la lista.';
    }
    if (error.status === 409) {
      return typeof error.error?.detail === 'string'
        ? error.error.detail
        : 'Ya existe un vehículo con esa placa.';
    }
    if (error.status === 422) {
      return 'Datos inválidos. Revisa la placa, el modelo, el tipo y el cliente.';
    }
    if (error.status === 0) {
      return 'No se pudo conectar con el servicio. Verifica que el backend esté activo.';
    }
    if (error.status === 503 && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    return 'No se pudo registrar el vehículo. Inténtalo de nuevo.';
  }
}
