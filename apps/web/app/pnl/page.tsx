import { PagePlaceholder } from "../../components/page-placeholder";

export default function PnlPage() {
  return (
    <PagePlaceholder
      title="PnL"
      ticketId="P1-FE4"
      dependency="V2 auth and GET /api/me/pnl/daily"
      summary="This page route is ready, but the full PnL view is intentionally deferred until the authenticated user-scoped PnL API contract is stable."
    />
  );
}
