import { Badge } from "@/components/ui/badge";
import type { Band, Status } from "@/lib/api";
import { BAND_LABEL } from "@/lib/format";

/** The band in words, never colour alone (S4-R8, S4-R12). */
export function BandBadge({ status, band }: { status: Status; band: Band | null }) {
  if (status === "refused" || band === null) return <Badge variant="flag">Refused</Badge>;
  return <Badge variant={band}>{BAND_LABEL[band]}</Badge>;
}
