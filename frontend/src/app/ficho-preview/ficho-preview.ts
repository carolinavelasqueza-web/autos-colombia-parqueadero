import { Component, input } from '@angular/core';
import { Ficho } from '../models/estancia';

@Component({
  selector: 'app-ficho-preview',
  imports: [],
  templateUrl: './ficho-preview.html',
  styleUrl: './ficho-preview.css',
})
export class FichoPreview {
  readonly ficho = input.required<Ficho>();

  imprimir(): void {
    window.print();
  }

  fecha(value: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      timeZone: 'America/Bogota',
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  }
}
