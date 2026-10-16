/** Every list endpoint returns this shape (backend `StandardPagination`). */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  page: number;
  page_size: number;
  total_pages: number;
  results: T[];
}

export interface PageParams {
  page: number;
  page_size: number;
}

/** Every API error body (backend `api_exception_handler`). */
export interface ApiErrorBody {
  detail: string;
  code?: string | null;
  /** Field -> messages. Nested objects for grouped fields, e.g. custom_fields.{key}. */
  errors?: Record<string, string[] | Record<string, string[]>>;
}
