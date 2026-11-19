import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin } from 'rxjs';
import { Cliente } from '../models/cliente';
import { METODOS_PAGO, MetodoPago, Pago } from '../models/pago';
import { TipoVehiculo } from '../models/vehiculo';
import { ErrorApi } from '../models/vehiculo';
import { ApiService } from '../services/api.service';
import { ClientesService } from '../services/clientes.service';
import { PagosService } from '../services/pagos.service';
import { TarifasService } from '../services/tarifas.service';

type Paso = 1 | 2 | 3;

/** Vehículo del cliente con su tarifa individual y si está marcado para pagar. */
export interface VehiculoPago {
  id: number;
  placa: string;
  tipo: TipoVehiculo;
  tarifa: number;
  seleccionado: boolean;
}

const MESES = Array.from({ length: 12 }, (_valor, indice) => indice + 1);

@Component({
  selector: 'app-registrar-pago',
  templateUrl: './registrar-pago.html',
  styleUrl: './registrar-pago.css',
})
export class RegistrarPago {
  private readonly clientesApi = inject(ClientesService);
  private readonly vehiculosApi = inject(ApiService);
  private readonly tarifasApi = inject(TarifasService);
  private readonly pagosApi = inject(PagosService);
  private readonly destroyRef = inject(DestroyRef);

  readonly mesesDisponibles = MESES;
  readonly metodos = METODOS_PAGO;

  readonly paso = signal<Paso>(1);
  readonly documento = signal('');
  readonly buscando = signal(false);
  readonly cliente = signal<Cliente | null>(null);
  // Lista individual de vehículos del cliente con su tarifa y selección.
  readonly vehiculos = signal<VehiculoPago[]>([]);

  readonly meses = signal(1);
  readonly metodo = signal<MetodoPago>('EFECTIVO');
  readonly referencia = signal('');
  readonly montoRecibido = signal<number | null>(null);

  readonly confirmando = signal(false);
  readonly resultado = signal<Pago | null>(null);
  // Guarda cuánto entregó el cliente en efectivo para el recibo impreso.
  readonly montoRecibidoPago = signal<number | null>(null);
  readonly error = signal('');

  readonly referenciaRequerida = computed(() => this.metodo() !== 'EFECTIVO');
  readonly esEfectivo = computed(() => this.metodo() === 'EFECTIVO');
  readonly bloqueado = computed(() => this.confirmando() || this.resultado() !== null);

  /** Vehículos marcados para pagar. */
  readonly seleccionados = computed(() => this.vehiculos().filter((v) => v.seleccionado));
  /** Tipos (únicos) de los vehículos seleccionados, para el resumen del cliente. */
  readonly tiposCliente = computed(() => [
    ...new Set(this.seleccionados().map((v) => v.tipo)),
  ]);
  /** Suma de tarifas mensuales de los vehículos seleccionados (sin multiplicar por meses). */
  readonly tarifaMensualSeleccionada = computed(() =>
    this.seleccionados().reduce((suma, v) => suma + v.tarifa, 0),
  );
  readonly haySeleccion = computed(() => this.seleccionados().length > 0);
  // Total = suma de tarifas de los vehículos seleccionados × meses. Coincide
  // con el cálculo del backend al enviar esos mismos vehiculo_ids.
  readonly total = computed(() => this.tarifaMensualSeleccionada() * this.meses());
  readonly totalTexto = computed(() => this.formatearMonto(this.total()));

  /** Cambio a devolver; null si no aplica (otro método) o si aún no hay monto recibido. */
  readonly cambio = computed(() => {
    if (!this.esEfectivo()) return null;
    const recibido = this.montoRecibido();
    if (recibido === null) return null;
    return recibido - this.total();
  });
  readonly cambioTexto = computed(() => {
    const cambio = this.cambio();
    return cambio === null ? '' : this.formatearMonto(cambio);
  });
  /** El efectivo entregado alcanza para cubrir el total. */
  readonly efectivoSuficiente = computed(() => {
    const recibido = this.montoRecibido();
    return recibido !== null && recibido >= this.total();
  });
  /** No se puede confirmar en efectivo sin un monto recibido que cubra el total. */
  readonly puedeConfirmar = computed(() => !this.esEfectivo() || this.efectivoSuficiente());

  /** Cambio devuelto registrado en el pago (para el recibo), solo si fue en efectivo. */
  readonly cambioPago = computed(() => {
    const recibido = this.montoRecibidoPago();
    const pago = this.resultado();
    if (recibido === null || pago === null) return null;
    return recibido - Number(pago.monto);
  });

  onDocumentoInput(event: Event): void {
    this.documento.set((event.target as HTMLInputElement).value);
  }

  buscar(): void {
    if (this.buscando()) return;
    const documento = this.documento().trim();
    if (!documento) {
      this.error.set('Ingresa el documento del cliente.');
      return;
    }

    this.buscando.set(true);
    this.error.set('');
    forkJoin({
      clientes: this.clientesApi.list(0, 100),
      vehiculos: this.vehiculosApi.list(0, 100),
      tarifas: this.tarifasApi.listar(),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ clientes, vehiculos, tarifas }) => {
          this.buscando.set(false);
          const cliente = clientes.items.find((item) => item.documento === documento);
          if (!cliente) {
            this.error.set('No se encontró un cliente con ese documento.');
            return;
          }

          const propios = vehiculos.items.filter(
            (vehiculo) => vehiculo.cliente_id === cliente.id,
          );
          if (propios.length === 0) {
            this.error.set('El cliente no tiene vehículos registrados.');
            return;
          }

          const valores = new Map(tarifas.map((tarifa) => [tarifa.tipo, Number(tarifa.valor)]));
          // Un vehículo por fila (sin agrupar por tipo), cada uno con su tarifa.
          const lista: VehiculoPago[] = propios
            .map((vehiculo) => ({
              id: vehiculo.id,
              placa: vehiculo.placa,
              tipo: vehiculo.tipo,
              tarifa: valores.get(vehiculo.tipo) ?? 0,
              seleccionado: true,
            }))
            .sort((a, b) => a.placa.localeCompare(b.placa));

          this.cliente.set(cliente);
          this.documento.set(cliente.documento);
          this.vehiculos.set(lista);
          this.paso.set(2);
        },
        error: (error: HttpErrorResponse) => {
          this.buscando.set(false);
          this.error.set(
            error.status === 0
              ? 'No se pudo conectar con el servicio. Intenta de nuevo.'
              : 'No se pudo consultar la información del cliente.',
          );
        },
      });
  }

  onMesesChange(event: Event): void {
    this.cambiarMeses(Number((event.target as HTMLSelectElement).value));
  }

  cambiarMeses(valor: number): void {
    const entero = Math.trunc(valor);
    this.meses.set(Number.isFinite(entero) ? Math.min(12, Math.max(1, entero)) : 1);
  }

  alternarVehiculo(id: number, seleccionado: boolean): void {
    this.vehiculos.update((lista) =>
      lista.map((v) => (v.id === id ? { ...v, seleccionado } : v)),
    );
  }

  onVehiculoToggle(id: number, event: Event): void {
    this.alternarVehiculo(id, (event.target as HTMLInputElement).checked);
  }

  onMetodoChange(event: Event): void {
    this.cambiarMetodo((event.target as HTMLSelectElement).value as MetodoPago);
  }

  cambiarMetodo(metodo: MetodoPago): void {
    this.metodo.set(metodo);
    if (metodo === 'EFECTIVO') {
      this.referencia.set('');
    } else {
      // El monto recibido solo aplica al efectivo.
      this.montoRecibido.set(null);
    }
  }

  onMontoRecibidoInput(event: Event): void {
    const valor = (event.target as HTMLInputElement).value.trim();
    if (valor === '') {
      this.montoRecibido.set(null);
      return;
    }
    const numero = Number(valor);
    this.montoRecibido.set(Number.isFinite(numero) ? numero : null);
  }

  onReferenciaInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const limpia = input.value.toUpperCase().slice(0, 100);
    if (input.value !== limpia) input.value = limpia;
    this.referencia.set(limpia);
  }

  continuar(): void {
    this.error.set('');
    if (!this.haySeleccion()) {
      this.error.set('Selecciona al menos un vehículo para pagar.');
      return;
    }
    if (this.referenciaRequerida()) {
      const referencia = this.referencia().trim().toUpperCase();
      if (!referencia) {
        this.error.set('La referencia es obligatoria para transferencia o tarjeta.');
        return;
      }
      if (referencia.length > 100) {
        this.error.set('La referencia no puede superar 100 caracteres.');
        return;
      }
      this.referencia.set(referencia);
    } else {
      this.referencia.set('');
    }
    this.paso.set(3);
  }

  volver(): void {
    if (this.bloqueado()) return;
    this.error.set('');
    this.paso.set(2);
  }

  confirmar(): void {
    const cliente = this.cliente();
    if (!cliente || this.bloqueado()) return;

    const seleccionados = this.seleccionados();
    if (seleccionados.length === 0) {
      this.error.set('Selecciona al menos un vehículo para pagar.');
      return;
    }

    const referencia = this.referenciaRequerida()
      ? this.referencia().trim().toUpperCase()
      : null;
    if (this.referenciaRequerida() && !referencia) {
      this.error.set('La referencia es obligatoria para transferencia o tarjeta.');
      return;
    }

    if (!this.puedeConfirmar()) {
      this.error.set('El monto recibido debe ser mayor o igual al total a cobrar.');
      return;
    }

    const recibido = this.esEfectivo() ? this.montoRecibido() : null;

    this.confirmando.set(true);
    this.error.set('');
    this.pagosApi
      .registrar({
        documento: cliente.documento,
        meses: this.meses(),
        metodo: this.metodo(),
        referencia,
        vehiculo_ids: seleccionados.map((v) => v.id),
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (pago) => {
          this.montoRecibidoPago.set(recibido);
          this.resultado.set(pago);
          this.confirmando.set(false);
        },
        error: (error: HttpErrorResponse) => {
          this.confirmando.set(false);
          this.error.set(this.mensajeError(error));
        },
      });
  }

  nuevoPago(): void {
    this.paso.set(1);
    this.documento.set('');
    this.buscando.set(false);
    this.cliente.set(null);
    this.vehiculos.set([]);
    this.meses.set(1);
    this.metodo.set('EFECTIVO');
    this.referencia.set('');
    this.montoRecibido.set(null);
    this.montoRecibidoPago.set(null);
    this.confirmando.set(false);
    this.resultado.set(null);
    this.error.set('');
  }

  imprimirRecibo(): void {
    window.print();
  }

  fechaPago(valor: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      timeZone: 'America/Bogota',
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(valor));
  }

  formatearMonto(valor: number): string {
    return `$ ${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(valor)}`;
  }

  formatearMontoTexto(valor: string): string {
    const numero = Number(valor);
    return Number.isNaN(numero) ? valor : this.formatearMonto(numero);
  }

  private mensajeError(error: HttpErrorResponse): string {
    const detalle = this.detalle(error);
    if (detalle) return detalle;
    if (error.status === 404) return 'No se encontró el cliente.';
    if (error.status === 409) return 'El pago entra en conflicto con otro registro.';
    if (error.status === 422) return 'Revisa los datos del pago e intenta de nuevo.';
    return 'No se pudo registrar el pago. Intenta de nuevo.';
  }

  private detalle(error: HttpErrorResponse): string {
    const cuerpo = error.error as ErrorApi | null;
    return typeof cuerpo?.detail === 'string' ? cuerpo.detail : '';
  }
}
