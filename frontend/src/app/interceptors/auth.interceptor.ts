import { HttpEvent, HttpHandlerFn, HttpRequest } from '@angular/common/http';
import { Observable } from 'rxjs';

export function authInterceptor(req: HttpRequest<unknown>, next: HttpHandlerFn): Observable<HttpEvent<unknown>> {

  let newHeaders = req.headers;

  // Add mock admin token for all requests directed to /admin endpoints
  if (req.url.includes('/admin')) {
    newHeaders = newHeaders.set('X-Admin-Token', 'admin-secret-token');
  }

  const modifiedReq = req.clone({
    headers: newHeaders
  });

  return next(modifiedReq);
}
