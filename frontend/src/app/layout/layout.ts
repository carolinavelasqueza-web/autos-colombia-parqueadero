import { Component, computed, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-layout',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './layout.html',
  styleUrl: './layout.css',
})
export class Layout {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly rolEtiqueta = computed(() => {
    switch (this.auth.rol()) {
      case 'ADMINISTRADOR':
        return 'Administrador';
      case 'OPERADOR':
        return 'Operador';
      default:
        return '';
    }
  });

  cerrarSesion(): void {
    this.auth.cerrarSesion();
    void this.router.navigate(['/login']);
  }
}
