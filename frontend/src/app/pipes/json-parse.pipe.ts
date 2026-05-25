import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'jsonParse',
  standalone: true
})
export class JsonParsePipe implements PipeTransform {
  transform(value: any): any {
    if (!value) return [];
    if (typeof value !== 'string') return value;
    try {
      return JSON.parse(value);
    } catch (e) {
      console.error('JsonParsePipe error:', e);
      return [];
    }
  }
}
