/** Universal (UTC) form of a timestamp, shown as a tooltip next to the local time. */
export function utc(value: string | null | undefined): string | undefined {
  return value ? `${new Date(value).toISOString().slice(0, 16).replace('T', ' ')} UTC` : undefined;
}
