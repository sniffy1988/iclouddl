export function format2faDaysLeft(daysUntil2faExpires: number | null): string {
  if (daysUntil2faExpires == null) return "—";
  if (daysUntil2faExpires === 0) return "Expired";
  if (daysUntil2faExpires === 1) return "1 day left";
  return `${daysUntil2faExpires} days left`;
}
